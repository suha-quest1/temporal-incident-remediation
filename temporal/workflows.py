from datetime import timedelta
from temporalio import workflow


#importing activities:
with workflow.unsafe.imports_passed_through():
    from  temporal.activities import classifyIncident

@workflow.defn
class IncidentWorkflow:

    @workflow.run
    async def run(self, err_msg: str):

        result= await workflow.execute_activity(
            classifyIncident,
            err_msg,
            start_to_close_timeout=timedelta(seconds=30),
        )

        return result
