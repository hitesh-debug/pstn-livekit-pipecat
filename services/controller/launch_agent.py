# services/controller/launch_agent.py
import os
import time
import logging
import boto3
from botocore.exceptions import ClientError

log = logging.getLogger("launcher")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


REGION    = os.getenv("AWS_REGION", "us-east-1")
CLUSTER   = os.getenv("ECS_CLUSTER", "lk-agents")
TASK_DEF  = os.getenv("AGENT_TASK_DEF", "lk-agent:1")
CONTAINER = os.getenv("AGENT_CONTAINER", "agent")

SUBNETS   = [s.strip() for s in os.getenv("SUBNETS_CSV", "").split(",") if s.strip()]
SECGRPS   = [g.strip() for g in os.getenv("SECGRPS_CSV", "").split(",") if g.strip()]

CAPACITY_PROVIDER = os.getenv("CAPACITY_PROVIDER", "FARGATE_SPOT")
PUBLIC_IP         = os.getenv("PUBLIC_IP", "ENABLED") 
WAIT_FOR_RUNNING  = int(os.getenv("WAIT_FOR_RUNNING_S", "0"))

PLAIN_DEEPGRAM = os.getenv("DEEPGRAM_API_KEY")
PLAIN_ELEVEN   = os.getenv("ELEVEN_API_KEY")
ELEVEN_VOICE_ID = os.getenv("ELEVEN_VOICE_ID")

ecs = boto3.client("ecs", region_name=REGION)

def _validate_networking():
    if not SUBNETS:
        raise RuntimeError("SUBNETS_CSV is empty; provide at least one subnet id")
    if not SECGRPS:
        raise RuntimeError("SECGRPS_CSV is empty; provide at least one security group id")

def _build_overrides(room_name: str, livekit_url: str, livekit_token: str):
    env = [
        {"name": "ROOM_NAME",     "value": room_name},
        {"name": "LIVEKIT_URL",   "value": livekit_url},
        {"name": "LIVEKIT_TOKEN", "value": livekit_token},
    ]
    if PLAIN_DEEPGRAM:
        env.append({"name": "DEEPGRAM_API_KEY", "value": PLAIN_DEEPGRAM})
    if PLAIN_ELEVEN:
        env.append({"name": "ELEVEN_API_KEY", "value": PLAIN_ELEVEN})
    if ELEVEN_VOICE_ID:
        env.append({"name": "ELEVEN_VOICE_ID", "value": ELEVEN_VOICE_ID})

    return {
        "containerOverrides": [{
            "name": CONTAINER,
            "environment": env
        }]
    }

def launch_agent(room_name: str, livekit_url: str, livekit_token: str) -> str:
    """
    Starts one agent task on ECS. Returns taskArn.
    Passes ROOM_NAME, LIVEKIT_URL, LIVEKIT_TOKEN (+ optional STT/TTS envs) through container overrides.
    """
    _validate_networking()
    overrides = _build_overrides(room_name, livekit_url, livekit_token)

    try:
        resp = ecs.run_task(
            cluster=CLUSTER,
            taskDefinition=TASK_DEF,
            capacityProviderStrategy=[{"capacityProvider": CAPACITY_PROVIDER, "weight": 1}],
            count=1,
            networkConfiguration={
                "awsvpcConfiguration": {
                    "subnets": SUBNETS,
                    "securityGroups": SECGRPS,
                    "assignPublicIp": PUBLIC_IP,
                }
            },
            overrides=overrides,
            enableExecuteCommand=False,
        )
    except ClientError as e:
        raise RuntimeError(f"ECS run_task error: {e}")

    failures = resp.get("failures") or []
    if failures:
        raise RuntimeError(f"ECS RunTask failed: {failures}")

    tasks = resp.get("tasks") or []
    if not tasks or "taskArn" not in tasks[0]:
        raise RuntimeError(f"ECS RunTask returned no tasks: {resp}")

    task_arn = tasks[0]["taskArn"]
    log.info("RunTask ok: %s", task_arn)

    if WAIT_FOR_RUNNING > 0:
        _wait_until_running(task_arn, WAIT_FOR_RUNNING)

    return task_arn

def _wait_until_running(task_arn: str, timeout_s: int):
    """Best-effort poller for task lastStatus → RUNNING (optional)."""
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        try:
            d = ecs.describe_tasks(cluster=CLUSTER, tasks=[task_arn])
            tasks = d.get("tasks") or []
            if tasks:
                last = tasks[0].get("lastStatus")
                if last == "RUNNING":
                    log.info("Task %s is RUNNING", task_arn)
                    return
                log.info("Task %s status: %s", task_arn, last)
        except ClientError as e:
            log.warning("describe_tasks error for %s: %s", task_arn, e)
        time.sleep(2)
    log.warning("Timed out waiting for RUNNING; lastStatus=%s", last)

def stop_agent(task_arn: str):
    try:
        ecs.stop_task(cluster=CLUSTER, task=task_arn, reason="room_ended")
        log.info("StopTask sent for %s", task_arn)
    except Exception as e:
        log.warning("StopTask error for %s: %s", task_arn, e)
