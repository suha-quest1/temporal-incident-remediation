**Incident Postmortem: alert-oom-1778223902383**
==============================================

### Summary
On [date], a Production 1 (P1) Out of Memory (OOM) incident occurred due to a memory leak in the backend-api deployment. The incident resulted in a restart of the deployment, causing a brief outage.

### Root Cause
The root cause of the incident was a memory leak in the backend-api deployment, which was not properly limited. The deployment's resource limits were not set, allowing the pods to consume excessive memory and eventually leading to an OOM error.

### Actions Taken
1. **Initial Response**: The on-call engineer was notified and responded to the incident.
2. **Investigation**: The engineer used `kubectl top pods` and `kubectl describe pod` to identify the affected pod and deployment.
3. **Resource Limitation**: The deployment's resource limits were set to 512Mi using `kubectl set resources deployment`.
4. **Restart**: The deployment was restarted using `kubectl rollout restart`.
5. **Rollback**: Due to the severity of the incident, a rollback was performed to restore the previous version of the deployment.

### Verification
The incident was resolved, and the deployment is now running with the corrected resource limits. Monitoring tools have been updated to detect similar issues in the future.

### Lessons Learned
1. **Resource Limitation**: Ensure that resource limits are set for all deployments to prevent memory leaks.
2. **Monitoring**: Improve monitoring tools to detect OOM errors and other resource-related issues.
3. **Rollback Procedure**: Review and refine the rollback procedure to minimize downtime and ensure a smooth recovery.
4. **Communication**: Improve communication during incidents to ensure that all stakeholders are informed and up-to-date.