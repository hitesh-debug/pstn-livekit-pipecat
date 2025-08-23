import os, json, logging, asyncio, time
from collections import deque
from fastapi import FastAPI, Request
from fastapi.responses import Response
from dotenv import load_dotenv

from utils.token import mint_livekit_token

load_dotenv()
app = FastAPI()
log = logging.getLogger("controller")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

LIVEKIT_URL = os.getenv("LIVEKIT_URL")  # e.g., wss://<subdomain>.livekit.cloud
TOKEN_TTL   = int(os.getenv("CONTROLLER_TOKEN_TTL_SECONDS", "900"))

# In-memory queue + lock (for 1 controller instance). Use Redis/SQS for HA.
JOBS: deque[dict] = deque()
AGENTS_LOCK: dict[str, bool] = {}  # room -> claimed
ASSIGN_TIMEOUT_S = 25              # long-poll window

@app.get("/healthz")
def health():
    return {"ok": True}

@app.post("/livekit/webhook")
async def livekit_webhook(request: Request):
    """
    Expect LiveKit project-level webhooks.
    We care about: room_started / room_ended (names vary slightly).
    """
    try:
        data = await request.json()
    except Exception:
        data = {}

    event = (data.get("event") or data.get("type") or "").lower()
    room = None
    if isinstance(data.get("room"), dict):
        room = (data.get("room") or {}).get("name")
    room = room or data.get("roomName") or data.get("room_name")

    if event in ("room_started", "room_created") and room:
        if AGENTS_LOCK.get(room):
            log.info("already queued/claimed room=%s", room)
            return {"status": "already-queued", "room": room}
        AGENTS_LOCK[room] = True
        JOBS.append({"room": room})
        log.info("queued room=%s (queue=%d)", room, len(JOBS))
        return {"status": "queued", "room": room, "queue": len(JOBS)}

    if event in ("room_ended", "room_finished") and room:
        AGENTS_LOCK.pop(room, None)
        log.info("room ended %s (lock cleared)", room)
        return {"status": "ended", "room": room}

    return {"status": "ignored", "event": event, "room": room}

@app.get("/assign")
async def assign():
    # Immediate job if present
    if JOBS:
        job = JOBS.popleft()
        room = job["room"]
        identity = f"agent-{int(time.time()*1000)}"  # unique identity per join
        token = mint_livekit_token(
            room=room,
            identity=identity,
            ttl_seconds=TOKEN_TTL,
        )
        return {"room": room, "livekit_url": LIVEKIT_URL, "livekit_token": token}

    # Otherwise long-poll briefly to reduce spin
    t0 = time.time()
    while time.time() - t0 < ASSIGN_TIMEOUT_S:
        await asyncio.sleep(0.5)
        if JOBS:
            job = JOBS.popleft()
            room = job["room"]
            identity = f"agent-{int(time.time()*1000)}"
            token = mint_livekit_token(room=room, identity=identity, ttl_seconds=TOKEN_TTL)
            return {"room": room, "livekit_url": LIVEKIT_URL, "livekit_token": token}

    return Response(status_code=204)
