from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Mock Kubernetes API")

class CommandRequest(BaseModel):
    command: str

# Commands that contain these strings will simulate transient failure
# (but NOT "restart" — rollout restarts are valid remediation!)
FAIL_PATTERNS = ["delete --force", "drain --force"]

@app.post("/execute")
async def execute(req: CommandRequest):
    command = req.command.strip()

    for pattern in FAIL_PATTERNS:
        if pattern in command:
            return {
                "status": "failed",
                "output": f"Mock Kubernetes: simulated failure for '{command}'",
            }

    return {
        "status": "success",
        "output": f"mock-kubectl executed: {command}",
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}