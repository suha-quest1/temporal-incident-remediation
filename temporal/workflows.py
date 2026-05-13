import asyncio
from datetime import timedelta
from temporalio import workflow
from temporal.data.data_class import IncidentDetails, OverrideSignal
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from temporal.activities import (
        ClassifyIncident,
        FetchRunbook,
        GeneratePlan,
        RollbackChanges,
        VerifyResolution,
        GeneratePostmortem,
    )
    from temporal.sub_workflow import ExecuteStepWorkflow


@workflow.defn
class IncidentWorkflow:

    def __init__(self):
        self.override_action = None
        self.override_engineer = None

    @workflow.run
    async def run(self, incident: IncidentDetails) -> dict:
        common_retry = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_attempts=3,
        )

        classify = await workflow.execute_activity(
            ClassifyIncident,
            incident.errorMessage,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=common_retry,
        )

        # Pass incident_type as first tag so runbook lookup is reliable
        runbook_lookup_tags = [classify["incident_type"]] + incident.runbookTags
        runbook = await workflow.execute_activity(
            FetchRunbook,
            runbook_lookup_tags,
            start_to_close_timeout=timedelta(seconds=15),
            retry_policy=common_retry,
        )

        plan = await workflow.execute_activity(
            GeneratePlan,
            args=[classify["incident_type"], runbook, classify["severity"]],
            start_to_close_timeout=timedelta(seconds=45),
            retry_policy=common_retry,
        )

        step_results = []

        for idx, command in enumerate(plan):

            result = await workflow.execute_child_workflow(
                ExecuteStepWorkflow.run,
                command,
                id=f"{incident.alertId}-step-{idx}-{workflow.uuid4().hex}",
                task_queue=workflow.info().task_queue,
            )

            step_results.append(result)

        workflow.logger.info("[workflow] waiting for human override...")
        try:
            await workflow.wait_condition(
                lambda: self.override_action is not None,
                timeout=timedelta(minutes=30),
            )
            override_received = True
            # Log signal reception immediately when override is set
            workflow.logger.info(f"[signal] human override received: action={self.override_action}")
        except asyncio.TimeoutError:
            override_received = False

        if override_received and self.override_action == "rollback":
            workflow.logger.info("Rollback signal received! Executing rollback.")
            rollback_result = await workflow.execute_activity(
                RollbackChanges,
                plan,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=common_retry,
            )

            workflow.logger.info("Executing verification after rollback.")
            verification = await workflow.execute_activity(
                VerifyResolution,
                incident.service,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=common_retry,
            )

        else:
            workflow.logger.info(
                f"Proceeding. Override received: {override_received}, action: {self.override_action}"
            )
            rollback_result = None

            workflow.logger.info("Executing verification without rollback.")
            verification = await workflow.execute_activity(
                VerifyResolution,
                incident.service,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=common_retry,
            )

        workflow.logger.info("Generating postmortem report...")
        postmortem_path = await workflow.execute_activity(
            GeneratePostmortem,
            args=[
                incident.alertId,
                classify,
                plan,
                step_results,
                verification,
                self.override_action,
            ],
            start_to_close_timeout=timedelta(seconds=90),
            retry_policy=common_retry,
        )

        return {
            "classification": classify,
            "runbooks": runbook,
            "plan": plan,
            "execution_results": step_results,
            "rollback_result": rollback_result,
            "verification": verification,
            "override_action": self.override_action,
            "postmortem_path": postmortem_path,
        }

    @workflow.signal
    async def humanOverride(self, override: OverrideSignal):
        workflow.logger.info(
            f"Signal received: action={override.action}, engineer={override.engineer}"
        )
        self.override_action = override.action
        self.override_engineer = override.engineer
