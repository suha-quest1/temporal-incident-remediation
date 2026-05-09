"""
LAYER 2 — Tests for ExecuteStepWorkflow (child workflow).
Each remediation command runs in its own child workflow for independent retry.
"""

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from temporalio.exceptions import ActivityError

from temporal.sub_workflow import ExecuteStepWorkflow

TASK_QUEUE = "test-step-queue"


@activity.defn(name="ExecuteStep")
async def mock_ExecuteStep_success(command: str) -> dict:
    return {"command": command, "status": "success", "output": f"executed: {command}"}


@activity.defn(name="ExecuteStep")
async def mock_ExecuteStep_fail(command: str) -> dict:
    raise RuntimeError(f"mock-k8s rejected: {command}")


async def test_ExecuteStep_workflow_success():
    """Child workflow returns result dict from ExecuteStep activity."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[ExecuteStepWorkflow],
            activities=[mock_ExecuteStep_success],
        ):
            result = await env.client.execute_workflow(
                ExecuteStepWorkflow.run,
                "kubectl get pods",
                id="step-success-001",
                task_queue=TASK_QUEUE,
            )

    assert result["status"] == "success"
    assert result["command"] == "kubectl get pods"
    assert "executed:" in result["output"]


async def test_ExecuteStep_workflow_propagates_failure():
    """Child workflow failure should surface as an ActivityError to the parent."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[ExecuteStepWorkflow],
            activities=[mock_ExecuteStep_fail],
        ):
            with pytest.raises(Exception):
                await env.client.execute_workflow(
                    ExecuteStepWorkflow.run,
                    "kubectl delete --force",
                    id="step-fail-001",
                    task_queue=TASK_QUEUE,
                )


async def test_ExecuteStep_workflow_passes_command_to_activity():
    """Command string must be passed through to the ExecuteStep activity unchanged."""
    received_commands = []

    @activity.defn(name="ExecuteStep")
    async def capture_command(command: str) -> dict:
        received_commands.append(command)
        return {"command": command, "status": "success", "output": "ok"}

    cmd = "kubectl rollout restart deployment/backend-api -n production"
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[ExecuteStepWorkflow],
            activities=[capture_command],
        ):
            await env.client.execute_workflow(
                ExecuteStepWorkflow.run,
                cmd,
                id="step-capture-001",
                task_queue=TASK_QUEUE,
            )

    assert received_commands == [cmd]
