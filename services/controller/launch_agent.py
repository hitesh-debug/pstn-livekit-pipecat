# services/controller/launch_agent.py
import os, logging, boto3

log = logging.getLogger("launcher")

# Required env (set these on the EC2 controller):
#   ECS_CLUSTER       = lk-agents
#   AGENT_TASK_DEF    = lk-agent:1
#   SUBNETS_CSV       = subnet-aaa,subnet-bbb
#   SECGRPS_CSV       = sg-xxxx
# Optional:
#   AWS_REGION        = us-east-1

REGION   = os.getenv("AWS_REGION", "us-east-1")
CLUSTER  = os.getenv("ECS_CLUSTER", "lk-agents")
TASK_DEF = os.getenv("AGENT_TASK_DEF", "lk-agent:1")

SUBNETS  = [s.strip() for s in os.getenv("SUBNETS_CSV", "").split(",") if s.strip()]
SECGRPS  = [g.strip() for g in os.getenv("SECGRPS_CSV", "").split(",") if g.strip()]

ecs = boto3.client("ecs", region_name=REGION)

def launch_agent(room_name: str, livekit_url: str, livekit_token: str) -> str:
    """
    Starts one agent task on FARGATE_SPOT. Returns taskArn.
    Passes ROOM_NAME, LIVEKIT_URL, LIVEKIT_TOKEN through container overrides.
    """
    overrides = {
        "containerOverrides": [{
            "name": "agent",  # must match container name in the agent task definition
            "environment": [
                {"name": "ROOM_NAME", "value": room_name},
                {"name": "LIVEKIT_URL", "value": livekit_url},
                {"name": "LIVEKIT_TOKEN", "value": livekit_token},
            ],
        }]
    }

    resp = ecs.run_task(
        cluster=CLUSTER,
        taskDefinition=TASK_DEF,
        capacityProviderStrategy=[{"capacityProvider": "FARGATE_SPOT", "weight": 1}],
        count=1,
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": SUBNETS,
                "securityGroups": SECGRPS,
                "assignPublicIp": "ENABLED",
            }
        },
        overrides=overrides,
    )

    failures = resp.get("failures") or []
    if failures:
        raise RuntimeError(f"ECS RunTask failed: {failures}")

    task_arn = resp["tasks"][0]["taskArn"]
    log.info("RunTask ok: %s", task_arn)
    return task_arn

def stop_agent(task_arn: str):
    try:
        ecs.stop_task(cluster=CLUSTER, task=task_arn, reason="room_ended")
        log.info("StopTask sent for %s", task_arn)
    except Exception as e:
        log.warning("StopTask error for %s: %s", task_arn, e)
