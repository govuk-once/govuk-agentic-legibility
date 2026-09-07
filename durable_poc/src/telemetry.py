from __future__ import annotations

from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult, BatchSpanProcessor
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor, Span, TracerProvider
from opentelemetry.context import Context
import boto3
from botocore.exceptions import ClientError
from pathlib import Path
import json
from datetime import datetime as dt
import os
import sys
import logging
from typing import Any, Sequence


def get_logger() -> logging.Logger:
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

logger = get_logger()


class SessionSpanProcessor(SpanProcessor):
    def __init__(self) -> None:
        self.session_id = None

    def set_session_id(self, session_id: str) -> None:
        self.session_id = session_id

    def on_start(self, span: Span, parent_context: Context | None = None) -> None:
        if self.session_id:
            span.set_attribute("session_id", self.session_id)

    def on_end(self, span: ReadableSpan) -> None:
        pass


class FileSpanExporter(SpanExporter):
    def __init__(self, path: Path):
        self._file = open(path, 'a')

    def export(self, spans: Sequence[ReadableSpan]):
        num_spans = len(spans)
        logger.info(f'There are {num_spans} spans to be exported to file')
        span_counter = 0
        for span in spans:
            span_counter += 1
            logger.info(f'Exporting span: {span.name}, {span_counter} of {num_spans}')
            if span.context:
                self._file.write(
                    json.dumps(
                        {
                            "name": span.name,
                            "trace_id": format(span.context.trace_id, "032x"),
                            "span_id": format(span.context.span_id, "016x"),
                            "start_time": span.start_time,
                            "end_time": span.end_time,
                            "attributes": dict(span.attributes.items() if span.attributes else {}),
                            "status": span.status.status_code.name
                        }
                    )
                 + "\n"
                )
            else:
                logger.info(f"Span {span.name} ({span_counter} of {num_spans}) has no context")
                return SpanExportResult.FAILURE
        self._file.flush()
        return SpanExportResult.SUCCESS

    def shutdown(self):
        self._file.close()


class S3SpanExporter(SpanExporter):
    def __init__(self, bucket: str, region: str, prefix: str):
        self.s3 = boto3.client("s3", region_name=region)
        self.bucket = bucket
        self.prefix = prefix
        self.traces = []

    def export(self, spans: Sequence[ReadableSpan]):
        num_spans = len(spans)
        result = False
        logger.info(f'There are {num_spans} spans to be exported to S3')
        span_counter = 0
        for span in spans:
            if span.context:
                self.traces.append(
                    json.dumps(
                        {
                            "name": span.name,
                            "trace_id": format(span.context.trace_id, "032x"),
                            "span_id": format(span.context.span_id, "016x"),
                            "start_time": span.start_time,
                            "end_time": span.end_time,
                            "attributes": dict(span.attributes.items() if span.attributes else {}),
                            "status": span.status.status_code.name
                        }
                    ) + "\n"
                )
            else:
                logger.info(f"Span {span.name} ({span_counter} of {num_spans}) has no context")
                return SpanExportResult.FAILURE

        if self.traces:
            result = self.flush_traces()

        return SpanExportResult.SUCCESS if result else SpanExportResult.FAILURE

    def flush_traces(self):
        if not self.traces:
            return True

        try:
            current_date_time = dt.now()
            year, month, day, hour = (current_date_time.year, current_date_time.month, current_date_time.day, current_date_time.hour)
            timestamp = current_date_time.isoformat().replace(":", "-")
            key = f"{self.prefix}/year={year}/month={month}/day={day}/hour={hour}/trace-{timestamp}.jsonl"
            body = "\n".join(self.traces)
            self.s3.put_object(Bucket=self.bucket, Key=key, Body=body)
            logger.info(f"Wrote {len(self.traces)} traces to s3://{self.bucket}/{key}")
            self.traces.clear()
            return True
        except ClientError as c:
            logger.error(f"An error occurred writing traces to S3: {c}")
            return False
        except Exception as e:
            logger.error(f"There was an unexpected error while writing traces: {e}")
            return False

    def shutdown(self) -> None:
        result = self.flush_traces()
        logger.info(f"S3 Exporter shutdown with result {result}")


def _attach_exporters(
    provider: Any,
    *,
    file_path: Path | None = None,
    s3_bucket: str | None = None,
    s3_region: str = "eu-west-2",
    s3_prefix: str = "traces",
) -> None:
    if file_path:
        provider.add_span_processor(BatchSpanProcessor(FileSpanExporter(file_path)))
        logger.info(f"Attached FileSpanExporter -> {file_path}")
    if s3_bucket:
        provider.add_span_processor(
            BatchSpanProcessor(
                S3SpanExporter(s3_bucket, s3_region, s3_prefix),
                schedule_delay_millis=30_000,
            )
        )
        logger.info(f"Attached S3SpanExporter -> s3://{s3_bucket}/{s3_prefix}")


def create_agent_provider(
    *,
    session_processor: SessionSpanProcessor | None = None,
    file_path: Path | None = None,
    s3_bucket: str | None = None,
    s3_region: str = "eu-west-2",
    s3_prefix: str = "traces",
) -> TracerProvider:
    """Build a standard TracerProvider for the chat/agent process."""
    file_path = file_path or _path_from_env()
    s3_region = os.environ.get("AWS_REGION", s3_region)
    s3_bucket = _resolve_s3_bucket(s3_bucket, s3_region)
    s3_prefix = os.environ.get("OTEL_EXPORT_S3_PREFIX", s3_prefix)

    provider = TracerProvider()
    if session_processor:
        provider.add_span_processor(session_processor)
    _attach_exporters(
        provider, file_path=file_path, s3_bucket=s3_bucket,
        s3_region=s3_region, s3_prefix=s3_prefix,
    )
    return provider


def create_worker_provider(
    *,
    file_path: Path | None = None,
    s3_bucket: str | None = None,
    s3_region: str = "eu-west-2",
    s3_prefix: str = "traces",
) -> Any:
    """Build a replay-safe TracerProvider for the Temporal worker process.

    Uses Temporal's create_tracer_provider() which returns a
    ReplaySafeTracerProvider that suppresses spans during replay.
    """
    from temporalio.contrib.opentelemetry import create_tracer_provider

    file_path = file_path or _path_from_env()
    s3_region = os.environ.get("AWS_REGION", s3_region)
    s3_bucket = _resolve_s3_bucket(s3_bucket, s3_region)
    s3_prefix = os.environ.get("OTEL_EXPORT_S3_PREFIX", s3_prefix)

    provider = create_tracer_provider()
    _attach_exporters(
        provider, file_path=file_path, s3_bucket=s3_bucket,
        s3_region=s3_region, s3_prefix=s3_prefix,
    )
    return provider


SSM_PARAM_TRACE_BUCKET = "/durable_poc/temp_trace_bucket"


def _bucket_from_ssm(region: str | None = None) -> str | None:
    """Read the S3 trace bucket name from Parameter Store."""
    try:
        ssm = boto3.client("ssm", region_name=region or os.environ.get("AWS_REGION"))
        resp = ssm.get_parameter(Name=SSM_PARAM_TRACE_BUCKET)
        value = resp["Parameter"]["Value"]
        logger.info(f"Resolved trace bucket from SSM {SSM_PARAM_TRACE_BUCKET} -> {value}")
        return value
    except Exception as e:
        logger.warning(f"Could not read SSM parameter {SSM_PARAM_TRACE_BUCKET}: {e}")
        return None


def _resolve_s3_bucket(explicit: str | None, region: str) -> str | None:
    """Resolve S3 bucket: explicit arg > env var > Parameter Store."""
    return explicit or os.environ.get("OTEL_EXPORT_S3_BUCKET") or _bucket_from_ssm(region)


def _path_from_env() -> Path | None:
    raw = os.environ.get("OTEL_EXPORT_FILE")
    return Path(raw) if raw else None


