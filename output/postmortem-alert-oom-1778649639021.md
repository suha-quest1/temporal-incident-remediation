# Incident Report — alert-oom-1778649639021

Date: 2026-05-13 05:20:45 UTC

Severity: P1
Issue Type: OOM

## Actions
- Approved override action
- Ran `kubectl get pods -A`
- Ran `kubectl describe pod -l app=backend-api`
- Ran `kubectl rollout restart deployment/backend-api`

## Result
- OOM incident resolved
- Deployment restarted successfully

## Follow-Up
- Review pod logs for backend-api
- Verify deployment stability

INCIDENT DATA:

Incident ID:
alert-oom-1778649639021

Timestamp:
2026-05-13 05:20:45 UTC

Incident Type:
OOM

Severity:
P1

Remediation Plan:
kubectl get pods -A; kubectl describe pod -l app=backend-api; kubectl rollout restart deployment/backend-api

Execution Results:
kubectl get pods -A->success; kubectl describe pod -l app=backend-api->success; kubectl rollout restart deployment/backend-api->success

Healthy After Fix:
True

Override Action:
approve