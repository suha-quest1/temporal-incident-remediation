DevOps: Autonomous Incident Triage & Remediation Orchestrator
Use Case: 2

This project is an autonomous Dev-Ops system that logs incidents and automatically triggers response workflows for it. 




Workflows:
- IncidentWorkflow (Main workflow)
- ExecuteStepWorkflow

Activities:
- ClassifyIncident
- FetchRunbook
- GeneratePlan
- RollbackChanges
- VerifyResolution
- GeneratePostmortem

Signals:
- humanOverride: sent to IncidentWorkflow 












Running the code:

Go to directory root:
docker compose up --build

Access the UI at:


To monitor using Uvicorn UI:


