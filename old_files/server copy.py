import asyncio
import os

from temporalio.client import Client

from temporal.workflows import IncidentWorkflow
from data.data_class import IncidentDetails, OverrideSignal

test_incident= IncidentDetails(
    alertId="alert-001",
    severity="critical",
    service="backend-api",
    errorMessage="OOMKilled pod backend-api",
    runbookTags=["kubernetes", "memory", "oom"],
)

async def send_rollback_signal():

    temporal_host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    client = await Client.connect(temporal_host)
    handle = client.get_workflow_handle("incident-001") #!!!!

    await handle.signal(
        IncidentWorkflow.humanOverride,
        OverrideSignal(
            action="rollback",
            engineer="alice"
        )
    )

    print("Rollback signal sent")

async def main():

    temporal_host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    client = await Client.connect(temporal_host)

    result= await client.execute_workflow(
        IncidentWorkflow.run,
        test_incident,
        id="incident-003",
        task_queue="incident-task-queue",
    )

    print(result)

if __name__ == "__main__":
    asyncio.run(main())