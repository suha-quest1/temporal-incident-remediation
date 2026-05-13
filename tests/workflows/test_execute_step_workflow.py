import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from temporal.sub_workflow import ExecuteStepWorkflow
from temporalio import activity

TASK_QUEUE = "step-queue"

@activity.defn(name="ExecuteStep")
async def mock_step_success(cmd): return {"status": "success", "output": "ok"}

@activity.defn(name="ExecuteStep")
async def mock_step_fail(cmd): raise RuntimeError("rejected")

async def test_execute_step_workflow_success():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(env.client, task_queue=TASK_QUEUE, workflows=[ExecuteStepWorkflow], activities=[mock_step_success]):
            result = await env.client.execute_workflow(ExecuteStepWorkflow.run, "ls", id="step-1", task_queue=TASK_QUEUE)
            assert result["status"] == "success"

async def test_execute_step_workflow_failure():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(env.client, task_queue=TASK_QUEUE, workflows=[ExecuteStepWorkflow], activities=[mock_step_fail]):
            with pytest.raises(Exception):
                await env.client.execute_workflow(ExecuteStepWorkflow.run, "rm -rf /", id="step-2", task_queue=TASK_QUEUE)
