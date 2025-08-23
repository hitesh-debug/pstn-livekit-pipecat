import os, json, logging
from fastapi import FastAPI, Request, Response
from dotenv import load_dotenv
from utils.token import mint_livekit_token
from launch_agent import launch_agent

load_dotenv()
app = FastAPI()
log = logging.getLogger("controller")
logging.basicConfig(level=logging.INFO)

AGENTS = {}  # room_name -> pid

@app.get("/healthz")
def health():
    return {"ok": True}

@app.post("/livekit/webhook")
async def livekit_webhook(request: Request):
    body = await request.body()
    try:
        data = json.loads(body.decode("utf-8"))
    except Exception:
        data = {}

    # Expecting events like room created/started with room name
    # Adjust these keys to match the webhook you configure in LiveKit
    event = data.get("event") or data.get("type") or "unknown"
    room = None
    if "room" in data and isinstance(data["room"], dict):
        room = data["room"].get("name")
    else:
        room = data.get("roomName") or data.get("room_name")

    if event.lower() in ("room_started", "room_created") and room:
        if room in AGENTS:
            return {"status":"already-running", "room": room}

        token_ttl = int(os.getenv("CONTROLLER_TOKEN_TTL_SECONDS", "900"))
        token = mint_livekit_token(room, identity=f"agent-{room}", ttl_seconds=token_ttl)
        pid = launch_agent(room, token)
        AGENTS[room] = pid
        log.info(f"Launched agent pid={pid} for room={room}")
        return {"status":"launched", "room": room, "pid": pid}

    if event.lower() in ("room_ended", "room_finished") and room:
        # In a real system, track PIDs and terminate here if needed
        AGENTS.pop(room, None)
        log.info(f"Room ended {room}")
        return {"status":"ended", "room": room}

    return {"status":"ignored", "event": event, "room": room}
