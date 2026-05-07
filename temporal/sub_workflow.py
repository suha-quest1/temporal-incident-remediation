from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from temporal.activities import execute_step


@workflow.defn
class ExecuteStepWorkflow:

    @workflow.run
    async def run(self, command: str) -> dict:
        result = await workflow.execute_activity(
            execute_step,
            command,
            start_to_close_timeout=timedelta(seconds=30),
        )

        return result