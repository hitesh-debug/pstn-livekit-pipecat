# services/controller/controller.py
import os, json, logging
from fastapi import FastAPI, Request
from dotenv import load_dotenv
from utils.token import mint_livekit_token
from launch_agent import launch_agent, stop_agent

load_dotenv()
app = FastAPI()
log = logging.getLogger("controller")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# Track running ECS tasks per room (room_name -> taskArn)
AGENTS: dict[str, str] = {}

TOKEN_TTL = int(os.getenv("CONTROLLER_TOKEN_TTL_SECONDS", "900"))
LIVEKIT_URL = os.getenv("LIVEKIT_URL")

@app.get("/healthz")
def health():
    return {"ok": True}

@app.post("/livekit/webhook")
async def livekit_webhook(request: Request):
    """
    Handles LiveKit project-level webhooks (JSON).
    """
    body = await request.body()
    try:
        data = json.loads(body.decode("utf-8"))
    except Exception:
        data = {}

    event = (data.get("event") or data.get("type") or "").lower()
    # Room name may appear as data["room"]["name"] or "roomName"/"room_name"
    room = (data.get("room", {}) or {}).get("name") if isinstance(data.get("room"), dict) else None
    if not room:
        room = data.get("roomName") or data.get("room_name")

    if event in ("room_started", "room_created") and room:
        if room in AGENTS:
            log.info("Agent already running for room=%s (task=%s)", room, AGENTS[room])
            return {"status": "already-running", "room": room, "taskArn": AGENTS[room]}

        # Minting a short-lived token the agent will use to join the room
        token = mint_livekit_token(
            room=room,
            identity=f"agent-{room}",
            ttl_seconds=TOKEN_TTL,
        )

        task_arn = launch_agent(
            room_name=room,
            livekit_url=LIVEKIT_URL,
            livekit_token=token,
        )
        AGENTS[room] = task_arn
        log.info("Launched agent task=%s for room=%s", task_arn, room)
        return {"status": "launched", "room": room, "taskArn": task_arn}

    if event in ("room_ended", "room_finished") and room:
        task_arn = AGENTS.pop(room, None)
        if task_arn:
            stop_agent(task_arn)
            log.info("Stopped agent task=%s for ended room=%s", task_arn, room)
            return {"status": "stopped", "room": room, "taskArn": task_arn}
        log.info("Room ended with no tracked agent: %s", room)
        return {"status": "ended-no-agent", "room": room}

    return {"status": "ignored", "event": event, "room": room}
