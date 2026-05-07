import os

from fastapi import FastAPI
from temporalio.client import Client

from temporal.data.data_class import IncidentDetails, OverrideSignal
from temporal.workflows import IncidentWorkflow

from api.models import OverrideRequest


app = FastAPI()

temporal_client = None

TEMPORAL_HOST = os.getenv(
    "TEMPORAL_HOST",
    "localhost:7233"
)


@app.on_event("startup")
async def startup():

    global temporal_client

    temporal_client = await Client.connect(
        TEMPORAL_HOST
    )


@app.post("/incidents/start")
async def start_incident():

    incident = IncidentDetails(
        alertId="alert-001",
        severity="critical",
        service="backend-api",
        errorMessage="OOMKilled pod backend-api",
        runbookTags=["kubernetes", "memory", "oom"],
    )

    handle = await temporal_client.start_workflow(
        IncidentWorkflow.run,
        incident,
        id="incident-001",
        task_queue="incident-task-queue",
    )

    return {
        "message": "Workflow started",
        "workflow_id": handle.id,
    }


@app.post("/incidents/{workflow_id}/override")
async def override_incident(
    workflow_id: str,
    request: OverrideRequest,
):

    handle = temporal_client.get_workflow_handle(
        workflow_id
    )

    await handle.signal(
        IncidentWorkflow.human_override,
        OverrideSignal(
            action=request.action,
            engineer=request.engineer,
        ),
    )

    return {
        "message": "Override signal sent",
        "workflow_id": workflow_id,
    }