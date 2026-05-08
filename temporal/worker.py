import asyncio
import os

from temporalio.client import Client
from temporalio.worker import Worker

from temporal.logger import logger
from temporal.workflows import IncidentWorkflow
from temporal.sub_workflow import ExecuteStepWorkflow
from temporal.activities import (
    classifyIncident,
    fetchRunbook,
    generate_plan,
    execute_step,
    rollback_changes,
    verify_resolution,
    generate_postmortem,
)

TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "localhost:7233")


async def main():
    logger.info("[worker] Connecting to Temporal at %s ...", TEMPORAL_HOST)

    # Retry loop: Temporal server may not be ready immediately after compose start
    client = None
    for attempt in range(1, 21):
        try:
            client = await Client.connect(TEMPORAL_HOST)
            logger.info("[worker] Connected to Temporal (attempt %d)", attempt)
            break
        except Exception as e:
            logger.warning("[worker] Temporal not ready (attempt %d): %s — retrying in 3s", attempt, e)
            await asyncio.sleep(3)

    if client is None:
        logger.error("[worker] Could not connect to Temporal after 20 attempts. Exiting.")
        return

    worker = Worker(
        client,
        task_queue="incident-task-queue",
        workflows=[IncidentWorkflow, ExecuteStepWorkflow],
        activities=[
            classifyIncident,
            fetchRunbook,
            generate_plan,
            execute_step,
            rollback_changes,
            verify_resolution,
            generate_postmortem,
        ],
    )

    logger.info("[worker] Worker registered and polling incident-task-queue")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
