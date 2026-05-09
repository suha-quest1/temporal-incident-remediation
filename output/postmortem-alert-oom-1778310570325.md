# Incident Report — alert-oom-1778310570325

Date: 2026-05-09 07:09:32 UTC

Severity: P1
Issue Type: OOM

## Actions
- Run `kubectl top pods -n default` to identify resource-intensive pods
- Run `kubectl describe pod -l app=backend-api` to gather pod details
- Run `kubectl set resources deployment backend-api --limits=memory=512Mi` to adjust resource limits
- Run `kubectl rollout restart deployment/backend-api` to restart the deployment

## Result
- Successfully identified resource-intensive pods
- Gathered pod details for backend-api
- Adjusted resource limits for backend-api deployment
- Successfully restarted backend-api deployment

## Follow-Up
- Monitor pod resource utilization
- Review deployment logs for errors
- Verify application functionality

INCIDENT DATA:

Incident ID:
alert-oom-1778310570325

Timestamp:
2026-05-09 07:09:32 UTC

Incident Type:
OOM

Severity:
P1

Remediation Plan:
kubectl top pods -n default; kubectl describe pod -l app=backend-api; kubectl set resources deployment backend-api --limits=memory=512Mi; kubectl rollout restart deployment/backend-api

Execution Results:
kubectl top pods -n default->success; kubectl describe pod -l app=backend-api->success; kubectl set resources deployment backend-api --limits=memory=512Mi->success; kubectl rollout restart deployment/backend-api->success

Healthy After Fix:
True

Override Action:
rollback