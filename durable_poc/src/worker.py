"""Worker bootstrap."""

import asyncio
import logging
import os

from opentelemetry import trace
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.contrib.opentelemetry import TracingInterceptor

from src.activities import http_call, notify
from src.interpreter import SFSMInterpreter
from src.telemetry import create_worker_provider

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    temporal_address = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")

    provider = create_worker_provider()
    trace.set_tracer_provider(provider)
    tracing_interceptor = TracingInterceptor()

    client = await Client.connect(
        temporal_address,
        interceptors=[tracing_interceptor],
    )
    worker = Worker(
        client,
        task_queue="sfsm-queue",
        workflows=[SFSMInterpreter],
        activities=[http_call, notify],
        interceptors=[tracing_interceptor],
    )
    logging.info("Starting worker on %s...", temporal_address)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
