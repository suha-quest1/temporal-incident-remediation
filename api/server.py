import os
import asyncio
import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from temporalio.client import Client

from temporal.data.data_class import IncidentDetails, OverrideSignal
from temporal.workflows import IncidentWorkflow
from api.models import OverrideRequest


# ── FastAPI app ──────────────────────────────────────────────────────────────
app = FastAPI(title="Incident Orchestration API")

temporal_client: Client | None = None
TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "localhost:7233")


# ── Startup: connect to Temporal with retry ──────────────────────────────────
@app.on_event("startup")
async def startup():
    global temporal_client
    for attempt in range(1, 21):
        try:
            temporal_client = await Client.connect(TEMPORAL_HOST)
            print(f"[api-server] Connected to Temporal at {TEMPORAL_HOST} (attempt {attempt})")
            return
        except Exception as e:
            print(f"[api-server] Temporal not ready (attempt {attempt}): {e} — retrying in 3s")
            await asyncio.sleep(3)
    print("[api-server] ERROR: Could not connect to Temporal after 20 attempts.")


# ── Request model for starting an incident ───────────────────────────────────
class StartIncidentRequest(BaseModel):
    alertId: str = "alert-001"
    severity: str = "critical"
    service: str = "backend-api"
    errorMessage: str = "OOMKilled pod backend-api"
    runbookTags: list[str] = ["OOM", "memory", "kubernetes"]


# ── Endpoints ────────────────────────────────────────────────────────────────
@app.post("/incidents/start")
async def start_incident(request: StartIncidentRequest = StartIncidentRequest()):
    if temporal_client is None:
        raise HTTPException(status_code=503, detail="Temporal not connected")

    incident = IncidentDetails(
        alertId=request.alertId,
        severity=request.severity,
        service=request.service,
        errorMessage=request.errorMessage,
        runbookTags=request.runbookTags,
    )

    # Unique ID: prevents WorkflowAlreadyStartedError on repeated calls
    workflow_id = f"incident-{request.alertId}-{uuid.uuid4().hex[:6]}"

    handle = await temporal_client.start_workflow(
        IncidentWorkflow.run,
        incident,
        id=workflow_id,
        task_queue="incident-task-queue",
    )

    print(f"[api-server] Workflow started: {workflow_id}")
    return {
        "message": "Workflow started",
        "workflow_id": handle.id,
        "run_id": handle.result_run_id,
    }


@app.post("/incidents/{workflow_id}/override")
async def override_incident(workflow_id: str, request: OverrideRequest):
    if temporal_client is None:
        raise HTTPException(status_code=503, detail="Temporal not connected")

    handle = temporal_client.get_workflow_handle(workflow_id)

    await handle.signal(
        IncidentWorkflow.human_override,
        OverrideSignal(
            action=request.action,
            engineer=request.engineer,
        ),
    )

    print(f"[api-server] Override signal sent to {workflow_id}: action={request.action}")
    return {
        "message": "Override signal sent",
        "workflow_id": workflow_id,
        "action": request.action,
    }


@app.get("/health")
async def health():
    return {"status": "ok", "temporal_connected": temporal_client is not None}