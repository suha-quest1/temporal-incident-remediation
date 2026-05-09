import os
import asyncio
import uuid
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from temporalio.client import Client
from temporalio.service import RPCError

from temporal.data.data_class import IncidentDetails, OverrideSignal
from temporal.workflows import IncidentWorkflow
from api.models import OverrideRequest
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

temporal_client: Client | None = None
TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "localhost:7233")
_OUTPUT_DIR = Path("/app/output")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global temporal_client
    for attempt in range(1, 21):
        try:
            temporal_client = await Client.connect(TEMPORAL_HOST)
            logger.info(f"Connected to Temporal at {TEMPORAL_HOST} (attempt {attempt})")
            break
        except Exception as e:
            logger.warning(f"Temporal not ready (attempt {attempt}): {e}")
            await asyncio.sleep(3)
    else:
        raise RuntimeError("Could not connect to Temporal after 20 attempts")
    yield
    logger.info("Shutting down API server...")


app = FastAPI(
    title="Incident Orchestration API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():

    return {"message": "Incident Orchestration API"}


@app.get("/health")
async def health():
    return {"status": "ok", "temporal_connected": temporal_client is not None}


@app.post("/incidents/start")
async def start_incident(request: IncidentDetails):

    if temporal_client is None:
        raise HTTPException(status_code=503, detail="Temporal not connected")

    workflow_id = (
        f"incident_"
        f"{request.service}_"
        f"{request.severity}_"
        f"{request.alertId}_"
        f"{uuid.uuid4().hex[:6]}"
    )

    await temporal_client.start_workflow(
        IncidentWorkflow.run,
        request,
        id=workflow_id,
        task_queue="incident-task-queue",
    )

    logger.info(f"Workflow started: {workflow_id}")

    return {
        "message": "Workflow started",
        "workflow_id": workflow_id,
    }


@app.post("/incidents/{workflow_id}/override")
async def override_incident(workflow_id: str, request: OverrideRequest):
    if temporal_client is None:
        raise HTTPException(status_code=503, detail="Temporal not connected")

    try:
        handle = temporal_client.get_workflow_handle(workflow_id)
        await handle.signal(
            IncidentWorkflow.humanOverride,
            OverrideSignal(action=request.action, engineer=request.engineer),
        )
    except RPCError as e:
        raise HTTPException(status_code=404, detail=f"Signal failed: {e}")

    logger.info(f"Override signal sent " f"to {workflow_id}: " f"{request.action}")

    return {
        "message": "Override signal sent",
        "workflow_id": workflow_id,
        "action": request.action,
    }


@app.get("/incidents/{workflow_id}/status")
async def get_workflow_status(workflow_id: str):

    if temporal_client is None:
        raise HTTPException(status_code=503, detail="Temporal not connected")

    try:

        handle = temporal_client.get_workflow_handle(workflow_id)

        desc = await handle.describe()

        status_str = desc.status.name if desc.status else "UNKNOWN"

        result = None

        if status_str == "COMPLETED":
            try:
                result = await handle.result(follow_runs=False)
            except Exception as e:
                logger.warning(f"Could not fetch result " f"for {workflow_id}: {e}")

        return {
            "workflow_id": workflow_id,
            "status": status_str,
            "start_time": (desc.start_time.isoformat() if desc.start_time else None),
            "close_time": (desc.close_time.isoformat() if desc.close_time else None),
            "result": result,
        }

    except RPCError as e:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {str(e)}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/incidents/{workflow_id}/postmortem")
async def get_postmortem(workflow_id: str):

    if temporal_client is None:
        raise HTTPException(
            status_code=503,
            detail="Temporal not connected",
        )

    if not _OUTPUT_DIR.exists():
        raise HTTPException(
            status_code=404,
            detail="Output directory missing",
        )

    parts = workflow_id.split("_")

    if len(parts) < 5:
        raise HTTPException(
            status_code=400,
            detail="Invalid workflow ID format",
        )

    alert_id = parts[3]

    filepath = _OUTPUT_DIR / f"postmortem-{alert_id}.md"

    if filepath.exists():
        return {
            "workflow_id": workflow_id,
            "status": "available",
            "content": filepath.read_text(encoding="utf-8"),
        }

    try:

        handle = temporal_client.get_workflow_handle(workflow_id)

        desc = await handle.describe()

        status_str = desc.status.name if desc.status else "UNKNOWN"

        if status_str == "RUNNING":
            return {
                "workflow_id": workflow_id,
                "status": "waiting_for_postmortem",
                "message": (
                    "Workflow still running. " "Postmortem has not been generated yet."
                ),
            }

        return {
            "workflow_id": workflow_id,
            "status": "postmortem_unavailable",
            "message": ("Workflow finished but " "postmortem could not be generated."),
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Could not determine workflow state: {str(e)}",
        )


@app.get("/incidents")
async def list_incidents(limit: int = 20):

    if temporal_client is None:
        raise HTTPException(
            status_code=503,
            detail="Temporal not connected",
        )

    workflows = []

    try:

        async for wf in temporal_client.list_workflows():
            if wf.workflow_type != "IncidentWorkflow":
                continue

            parts = wf.id.split("_")

            service = parts[1] if len(parts) >= 5 else "unknown"
            severity = parts[2] if len(parts) >= 5 else "unknown"
            alert_id = parts[3] if len(parts) >= 5 else "unknown"

            workflows.append(
                {
                    "workflow_id": wf.id,
                    "run_id": wf.run_id,
                    "service": service,
                    "severity": severity,
                    "alert_id": alert_id,
                    "status": (wf.status.name if wf.status else "UNKNOWN"),
                    "workflow_type": wf.workflow_type,
                    "start_time": (
                        wf.start_time.isoformat() if wf.start_time else None
                    ),
                    "close_time": (
                        wf.close_time.isoformat() if wf.close_time else None
                    ),
                }
            )

            if len(workflows) >= limit:
                break

        return {"workflows": workflows}

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to list workflows: {str(e)}",
        )
