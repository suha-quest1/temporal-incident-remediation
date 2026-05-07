from datetime import timedelta
from temporalio import workflow
from temporal.data.data_class import IncidentDetails, OverrideSignal
from temporalio.common import RetryPolicy

#importing activities:
with workflow.unsafe.imports_passed_through():
    from  temporal.activities import classifyIncident, fetchRunbook, generate_plan, rollback_changes, verify_resolution, generate_postmortem
    from temporal.sub_workflow import ExecuteStepWorkflow


@workflow.defn
class IncidentWorkflow:

    def __init__(self):
        self.override_action = None
        self.override_engineer = None

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

        workflow.logger.info("Workflow entering wait state for human override (30 minutes max)...")
        override_received = await workflow.wait_condition(
        lambda: self.override_action is not None,
        timeout=timedelta(minutes=30),
        )

        if override_received and self.override_action == "rollback":
            workflow.logger.info("Rollback signal received! Executing rollback.")
            rollback_result = await workflow.execute_activity(
                rollback_changes,
                plan,
                start_to_close_timeout=timedelta(seconds=30),
            )

            workflow.logger.info("Executing verification after rollback.")
            verification = await workflow.execute_activity(
                verify_resolution,
                incident.service,
                start_to_close_timeout=timedelta(seconds=30),
            )

        else:
            workflow.logger.info(f"Proceeding without rollback. Override received: {override_received}, Action: {self.override_action}")
            rollback_result = None

            workflow.logger.info("Executing verification without rollback.")
            verification = await workflow.execute_activity(
                verify_resolution,
                incident.service,
                start_to_close_timeout=timedelta(seconds=30),
            )

        workflow.logger.info("Generating postmortem report...")
        postmortem_path = await workflow.execute_activity(
            generate_postmortem,
            args=[
                incident.alertId,
                classify,
                plan,
                step_results,
                verification,
                self.override_action,
            ],
            start_to_close_timeout=timedelta(seconds=30),
        )

        return {"classification": classify,
                "runbooks": runbook,
                "plan": plan,
                 "execution_results": step_results,
                 "rollback_result": rollback_result,
                "verification": verification,
                "override_action": self.override_action,
                "postmortem_path": postmortem_path,}
    
    
    @workflow.signal
    async def human_override(self, override: OverrideSignal):
        workflow.logger.info(f"Signal received: action={override.action}, engineer={override.engineer}")
        self.override_action = override.action
        self.override_engineer = override.engineer
    

