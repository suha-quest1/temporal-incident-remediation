from datetime import timedelta
from temporalio import workflow
from data.data_class import IncidentDetails
from temporalio.common import RetryPolicy

#importing activities:
with workflow.unsafe.imports_passed_through():
    from  temporal.activities import classifyIncident, fetchRunbook, generate_plan

@workflow.defn
class IncidentWorkflow:

    @workflow.run
    async def run(self, incident: IncidentDetails) -> dict:

        classify= await workflow.execute_activity(
            classifyIncident,
            incident.errorMessage,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_attempts=3,
            )
        )

        runbook= await workflow.execute_activity(
            fetchRunbook,
            incident.runbookTags,
            start_to_close_timeout=timedelta(seconds=30)

        )

        plan= await workflow.execute_activity(
            generate_plan,
            args=[classify["incident_type"], runbook, classify["severity"]],
            start_to_close_timeout=timedelta(seconds=30)

        )

        return {"classification": classify,
                "runbooks": runbook,
                "plan": plan}
    

