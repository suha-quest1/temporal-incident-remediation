import asyncio
import os

from temporalio.client import Client

from temporal.workflows import IncidentWorkflow

async def main():

    temporal_host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    client = await Client.connect(temporal_host)

    result= await client.execute_workflow(
        IncidentWorkflow.run,
         "OOMKilled pod backend-api",
        id="incident-001",
        task_queue="incident-task-queue",
    )

    print(result)


if __name__ == "__main__":
    asyncio.run(main())