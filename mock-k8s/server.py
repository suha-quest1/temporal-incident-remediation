from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class CommandRequest(BaseModel):
    command: str


@app.post("/execute")
async def execute(req: CommandRequest):

    command = req.command

    if "restart" in command:

        return {
            "status": "failed",
            "output": "Mock Kubernetes restart failure"
        }

    return {
        "status": "success",
        "output": f"kubectl executed: {command}"
    }