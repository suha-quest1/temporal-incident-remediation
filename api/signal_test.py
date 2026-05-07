#the engineer override signal

import asyncio
import os

from temporalio.client import Client

from temporal.workflows import IncidentWorkflow
from data.data_class import OverrideSignal


async def main():

    temporal_host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    client = await Client.connect(temporal_host)

    handle = client.get_workflow_handle("incident-003")

    await handle.signal(
        IncidentWorkflow.human_override,
        OverrideSignal(action="rollback", engineer="alice")
    )
    print("Rollback signal sent")
    


if __name__ == "__main__":
    asyncio.run(main())