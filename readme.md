# DevOps: Autonomous Incident Triage & Remediation Orchestrator


This project is an autonomous incident triage and remediation orchestration system built using Temporal’s Python SDK.

When an operational alert is triggered, the workflow automatically classifies the incident using an LLM, retrieves the relevant remediation runbook, generates infrastructure recovery commands, and executes them against a simulated Kubernetes environment.

The system supports long-running orchestration patterns including:
- Automated remediation execution
- Separated child workflows
- Retry handling
- Human override signals
- Rollback workflows
- Automated postmortem generation

A 30-minute intervention window allows on-call engineers to approve or rollback remediation actions before the workflow auto-closes.

<img width="600" height="800" alt="workflow_dg_2" src="https://github.com/user-attachments/assets/059fe906-572d-4fa5-9db8-1f92d1098dce" />

## Demo

Watch the full demo video here: [Autonomous Incident Remediation System](https://drive.google.com/file/d/1sSlQd0I5S5IfMwqQsgscBjkZliwwiiIs/view?usp=drive_link)

---
### Environment Variables  


This project uses the Groq API for LLM-powered incident classification, remediation planning, and postmortem generation.

Change the example `.env` file in the project root and add your own API key:

You can generate an API key from:
https://console.groq.com/keys

## Running the code:

Go to directory root:
```
docker compose up --build
```
## Access the UI at:
```
http://localhost:3000
```
## To view Temporal workflow monitoring UI:
```
http://localhost:8081
```

## To monitor using Swagger UI:
```
http://localhost:8000/docs
```












