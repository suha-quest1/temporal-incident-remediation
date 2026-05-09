# Incident Report — alert-disk-1778239496821

Severity: P2
Service Issue: disk

## Actions
- Executed plan to restart backend-api deployment: kubectl get pods -n default; kubectl describe pod -l app=backend-api; kubectl rollout restart deployment/backend-api
- Rolled out the deployment successfully

## Result
- Disk issue resolved
- Backend-api service restored to normal operation

## Follow-Up
- Monitor disk health to prevent future incidents
- Review deployment strategy to improve resilience