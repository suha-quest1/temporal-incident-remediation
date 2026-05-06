import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

import os

from temporal.logger import logger #py logger

from temporal.workflows import IncidentWorkflow
from temporal.activities import classifyIncident, fetchRunbook, generate_plan


async def main():

    temporal_host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    client = await Client.connect(temporal_host)

    worker = Worker(
        client,
        task_queue="incident-task-queue",
        workflows=[IncidentWorkflow],
        activities=[classifyIncident, fetchRunbook, generate_plan]
    )

    logger.info("Worker started")

    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())


