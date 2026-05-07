from datetime import timedelta
from temporalio import workflow
from data.data_class import IncidentDetails, OverrideSignal
from temporalio.common import RetryPolicy

#importing activities:
with workflow.unsafe.imports_passed_through():
    from  temporal.activities import classifyIncident, fetchRunbook, generate_plan, rollback_changes, verify_resolution
    from temporal.sub_workflow import ExecuteStepWorkflow


@workflow.defn
class IncidentWorkflow:

    def __init__(self):
        self.override_action = None
        self.engineer_override = None

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


        step_results = []

        for idx, command in enumerate(plan):

            result = await workflow.execute_child_workflow(
                ExecuteStepWorkflow.run,
                command,
                id=f"{incident.alertId}-step-{idx}",
                task_queue="incident-task-queue",
            )

            step_results.append(result)

        override_received = await workflow.wait_condition(
        lambda: self.override_action is not None,
        timeout=timedelta(minutes=30),
        )

        if override_received and self.override_action == "rollback":

            rollback_result = await workflow.execute_activity(
                rollback_changes,
                plan,
                start_to_close_timeout=timedelta(seconds=30),
            )

            verification = await workflow.execute_activity(
                verify_resolution,
                incident.service,
                start_to_close_timeout=timedelta(seconds=30),
            )

        else:

            rollback_result = None

            verification = await workflow.execute_activity(
                verify_resolution,
                incident.service,
                start_to_close_timeout=timedelta(seconds=30),
            )

        return {"classification": classify,
                "runbooks": runbook,
                "plan": plan,
                 "execution_results": step_results,
                 "rollback_result": rollback_result,
                "verification": verification,
                "override_action": self.override_action,}
    
    
    @workflow.signal
    def human_override(self, signal: OverrideSignal):
        self.override_action = signal.action
        self.engineer_override = signal.engineer
    

