import os
import asyncio
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from temporalio.client import Client
from temporalio.service import RPCError

from temporal.data.data_class import IncidentDetails, OverrideSignal
from temporal.workflows import IncidentWorkflow
from api.models import OverrideRequest


# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(title="Incident Orchestration API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

temporal_client: Client | None = None
TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "localhost:7233")
_OUTPUT_DIR = Path("/app/output")

# In-memory registry of workflows started through this API server.
# Keyed by workflow_id → {alertId, severity, service, ...}
_started_workflows: dict[str, dict] = {}

_STATUS_LABELS = {
    1: "RUNNING",
    2: "COMPLETED",
    3: "FAILED",
    4: "CANCELLED",
    5: "TERMINATED",
    6: "CONTINUED_AS_NEW",
    7: "TIMED_OUT",
}


# ── Startup ───────────────────────────────────────────────────────────────────
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


# ── Models ────────────────────────────────────────────────────────────────────
class StartIncidentRequest(BaseModel):
    alertId: str = "alert-001"
    severity: str = "critical"
    service: str = "backend-api"
    errorMessage: str = "OOMKilled pod backend-api"
    runbookTags: list[str] = ["OOM", "memory", "kubernetes"]


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "temporal_connected": temporal_client is not None}


# ── Start workflow ────────────────────────────────────────────────────────────
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

    workflow_id = f"incident-{request.alertId}-{uuid.uuid4().hex[:6]}"

    handle = await temporal_client.start_workflow(
        IncidentWorkflow.run,
        incident,
        id=workflow_id,
        task_queue="incident-task-queue",
    )

    # Persist metadata so /incidents list works even without advanced visibility
    _started_workflows[workflow_id] = {
        "workflow_id": workflow_id,
        "alert_id": request.alertId,
        "severity": request.severity,
        "service": request.service,
        "error_message": request.errorMessage,
    }

    print(f"[api-server] Workflow started: {workflow_id}")
    return {
        "message": "Workflow started",
        "workflow_id": handle.id,
    }


# ── Override signal ───────────────────────────────────────────────────────────
@app.post("/incidents/{workflow_id}/override")
async def override_incident(workflow_id: str, request: OverrideRequest):
    if temporal_client is None:
        raise HTTPException(status_code=503, detail="Temporal not connected")

    try:
        handle = temporal_client.get_workflow_handle(workflow_id)
        await handle.signal(
            IncidentWorkflow.human_override,
            OverrideSignal(action=request.action, engineer=request.engineer),
        )
    except RPCError as e:
        raise HTTPException(status_code=400, detail=f"Signal failed: {e}")

    print(f"[api-server] Override signal sent to {workflow_id}: action={request.action}")
    return {
        "message": "Override signal sent",
        "workflow_id": workflow_id,
        "action": request.action,
    }


# ── Workflow status ───────────────────────────────────────────────────────────
@app.get("/incidents/{workflow_id}/status")
async def get_workflow_status(workflow_id: str):
    if temporal_client is None:
        raise HTTPException(status_code=503, detail="Temporal not connected")
    try:
        handle = temporal_client.get_workflow_handle(workflow_id)
        desc = await handle.describe()
        status_val = desc.status.value if desc.status else 0
        status_str = _STATUS_LABELS.get(status_val, "RUNNING")

        result = None
        if status_val == 2:  # COMPLETED
            try:
                result = await handle.result(follow_runs=False)
            except Exception as e:
                print(f"[api-server] Could not fetch result for {workflow_id}: {e}")

        meta = _started_workflows.get(workflow_id, {})
        return {
            "workflow_id": workflow_id,
            "status": status_str,
            "start_time": desc.start_time.isoformat() if desc.start_time else None,
            "close_time": desc.close_time.isoformat() if desc.close_time else None,
            "result": result,
            "meta": meta,
        }
    except RPCError as e:
        # Temporal gRPC error — workflow truly not found or namespace issue
        raise HTTPException(status_code=404, detail=f"Workflow not found: {e.message}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Postmortem ────────────────────────────────────────────────────────────────
@app.get("/incidents/{workflow_id}/postmortem")
async def get_postmortem(workflow_id: str):
    candidates = list(_OUTPUT_DIR.glob("postmortem-*.md")) if _OUTPUT_DIR.exists() else []

    # Try to match by alertId embedded in the workflow_id:
    # workflow_id format: incident-{alertId}-{hex6}
    # alertId format: alert-oom-001  →  postmortem-alert-oom-001.md
    parts = workflow_id.split("-")
    if len(parts) >= 3:
        # drop "incident" prefix and last hex suffix
        alert_id = "-".join(parts[1:-1])
        exact = _OUTPUT_DIR / f"postmortem-{alert_id}.md"
        if exact.exists():
            return {"workflow_id": workflow_id, "content": exact.read_text(encoding="utf-8")}

    # Fall back: serve the most recently written postmortem
    if candidates:
        latest = max(candidates, key=lambda p: p.stat().st_mtime)
        return {
            "workflow_id": workflow_id,
            "content": latest.read_text(encoding="utf-8"),
            "note": f"Serving latest: {latest.name}",
        }

    raise HTTPException(status_code=404, detail="Postmortem not yet generated")


# ── List incidents ────────────────────────────────────────────────────────────
@app.get("/incidents")
async def list_incidents(limit: int = 20):
    if temporal_client is None:
        raise HTTPException(status_code=503, detail="Temporal not connected")

    # Build list from local registry first — this works without advanced visibility.
    results = []

    for wf_id in list(reversed(list(_started_workflows.keys())))[:limit]:
        # Try to get live status from Temporal
        status_str = "UNKNOWN"
        start_time = None
        close_time = None
        try:
            handle = temporal_client.get_workflow_handle(wf_id)
            desc = await handle.describe()
            status_val = desc.status.value if desc.status else 0
            status_str = _STATUS_LABELS.get(status_val, "RUNNING")
            start_time = desc.start_time.isoformat() if desc.start_time else None
            close_time = desc.close_time.isoformat() if desc.close_time else None
        except Exception:
            status_str = "UNKNOWN"

        results.append({
            "workflow_id": wf_id,
            "status": status_str,
            "start_time": start_time,
            "close_time": close_time,
            **_started_workflows[wf_id],
        })

    return {"workflows": results}