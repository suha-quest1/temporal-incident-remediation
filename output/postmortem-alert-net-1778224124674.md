# Incident Report — alert-net-1778224124674

Severity: P2
Service Issue: networking

## Actions
- Ran `kubectl get svc -n default` to verify service status
- Ran `kubectl describe svc backend-api` to investigate service details
- Ran `kubectl get networkpolicies -n default` to check network policies
- Ran `kubectl rollout restart deployment/backend-api` to restart the deployment

## Result
- Service restored after deployment restart
- No further issues reported

## Follow-Up
- Review network policies to prevent similar issues
- Consider implementing monitoring for service status and network policies
- Document steps taken to resolve the incident for future reference