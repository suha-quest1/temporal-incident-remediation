import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

import os

from temporal.logger import logger #py logger

from temporal.workflows import IncidentWorkflow
from temporal.sub_workflow import ExecuteStepWorkflow
from temporal.activities import classifyIncident, fetchRunbook, generate_plan, rollback_changes, verify_resolution, execute_step


async def main():

    temporal_host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    client = await Client.connect(temporal_host)

    worker = Worker(
        client,
        task_queue="incident-task-queue",
        workflows=[IncidentWorkflow, ExecuteStepWorkflow],
        activities=[classifyIncident, fetchRunbook, generate_plan, rollback_changes, verify_resolution, execute_step]
    )

    logger.info("Worker started")

    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())


