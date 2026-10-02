"""Worker bootstrap."""

import asyncio
import logging
import os

from temporalio.client import Client
from temporalio.worker import Worker

from bpmn.temporal_engine.activities import (
    http_call,
)

from bpmn.temporal_engine.bpmn_interpreter import (
    BPMNInterpreter,
)

logging.basicConfig(
    level=logging.INFO,
)

TASK_QUEUE = "bpmn-queue"


async def main() -> None:

    temporal_address = os.environ.get(
        "TEMPORAL_ADDRESS",
        "localhost:7233",
    )

    client = await Client.connect(
        temporal_address,
    )

    logging.info(f"Connected to Temporal at {temporal_address}")

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[
            BPMNInterpreter,
        ],
        activities=[
            http_call,
        ],
    )

    logging.info(
        f"Starting BPMN worker (task_queue={TASK_QUEUE}, temporal={temporal_address})"
    )

    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
