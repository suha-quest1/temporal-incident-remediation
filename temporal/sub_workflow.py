from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from temporal.activities import ExecuteStep


@workflow.defn
class ExecuteStepWorkflow:

    @workflow.run
    async def run(self, command: str) -> dict:
        result = await workflow.execute_activity(
            ExecuteStep,
            command,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_attempts=3,
            ),
        )

        return result
