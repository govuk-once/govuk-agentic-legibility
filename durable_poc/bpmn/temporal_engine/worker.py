"""Worker bootstrap"""

import asyncio
import logging
import os

from temporalio.client import Client
from temporalio.worker import Worker

from bpmn.temporal_engine.activities import (
    http_call,
    send_notification,
    load_process,
)
from bpmn.temporal_engine.bpmn_interpreter import (
    BPMNInterpreter,
)

logging.basicConfig(
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

TASK_QUEUE = os.environ.get(
    "TEMPORAL_TASK_QUEUE",
    "bpmn-queue",
)


async def main() -> None:

    temporal_address = os.environ.get(
        "TEMPORAL_ADDRESS",
        "localhost:7233",
    )

    client = await Client.connect(
        temporal_address,
    )

    logger.info(
        "Connected to Temporal at %s",
        temporal_address,
    )

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[
            BPMNInterpreter,
        ],
        activities=[
            http_call,
            send_notification,
            load_process,
        ],
    )

    logger.info(
        "Starting BPMN worker "
        "(task_queue=%s, temporal=%s)",
        TASK_QUEUE,
        temporal_address,
    )

    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())