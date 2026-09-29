"""
Entry point for executing BPMN workflows using SpiffWorkflow.

This module is responsible for:

* Loading BPMN process definitions.
* Creating workflow instances.
* Driving workflow execution.
* Identifying executable tasks.
* Dispatching task execution.
* Monitoring workflow completion.

Execution follows a simple loop:

1. Let the workflow engine perform automatic work.
2. Identify executable tasks.
3. Execute each task.
4. Repeat until the workflow completes.

The runner is intentionally process-agnostic to execute any BPMN process using the generic task handlers.
"""

from __future__ import annotations

import logging
from typing import Final

from SpiffWorkflow.bpmn.parser.BpmnParser import BpmnParser
from SpiffWorkflow.bpmn.workflow import BpmnWorkflow

from bpmn.helper import (
    dump_tasks,
    get_executable_tasks,
)
from bpmn.task_handlers import (
    execute_task,
)

logger = logging.getLogger(__name__)

BPMN_FILE: Final[str] = "change_of_address.bpmn"
PROCESS_ID: Final[str] = "change_address"

MAX_ITERATIONS: Final[int] = 1000


def main() -> None:
    """
    Execute a BPMN workflow.

    The workflow definition is loaded from the configured BPMN
    file and process identifier. The engine performs automatic
    workflow progression while executable tasks are delegated to
    task handlers.

    Raises:
        RuntimeError:
            Raised when the workflow exceeds the maximum iteration
            limit or encounters an unrecoverable execution error.
    """
    try:
        logger.info(
            "Loading BPMN process '%s' from '%s'",
            PROCESS_ID,
            BPMN_FILE,
        )

        parser = BpmnParser()

        parser.add_bpmn_files([BPMN_FILE])

        spec = parser.get_spec(PROCESS_ID)

        workflow = BpmnWorkflow(spec)

        logger.info("Starting workflow execution")

        iteration = 0

        while not workflow.is_completed():
            iteration += 1

            logger.debug(
                "Workflow iteration %d",
                iteration,
            )

            if iteration > MAX_ITERATIONS:
                logger.error(
                    "Maximum iteration limit (%d) reached",
                    MAX_ITERATIONS,
                )

                raise RuntimeError("Maximum iteration limit reached")

            workflow.do_engine_steps()

            tasks = get_executable_tasks(workflow)

            if not tasks:
                logger.warning("No executable tasks found")

                dump_tasks(workflow)

                break

            logger.debug(
                "Found %d executable task(s)",
                len(tasks),
            )

            for task in tasks:
                execute_task(
                    task,
                )

        if workflow.is_completed():
            logger.info("Workflow completed successfully")

        else:
            logger.warning("Workflow terminated before completion")

    except Exception:
        logger.exception("Workflow execution failed")
        raise


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format=("%(asctime)s %(levelname)s %(name)s %(message)s"),
    )

    main()
