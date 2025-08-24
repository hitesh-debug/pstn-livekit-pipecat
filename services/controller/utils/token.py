
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.environ["LIVEKIT_API_KEY"]
API_SECRET = os.environ["LIVEKIT_API_SECRET"]

def mint_livekit_token(room: str, identity: str, ttl_seconds: int = 900) -> str:
    """
    Creates an access token that lets the agent join `room` with pub/sub.
    """
    try:
        from livekit import AccessToken, VideoGrant
        grant = VideoGrant(room=room, room_join=True, room_admin=False,
                           can_publish=True, can_subscribe=True)
        at = AccessToken(API_KEY, API_SECRET, identity=identity, ttl=timedelta(seconds=ttl_seconds))
        at.add_grant(grant)
        return at.to_jwt()
    except Exception:
        # Fallback: build JWT manually via PyJWT
        import time, jwt, uuid
        now = int(time.time())
        payload = {
            "jti": str(uuid.uuid4()),
            "iss": API_KEY,
            "sub": identity,
            "nbf": now - 10,
            "exp": now + ttl_seconds,
            "video": {  # LiveKit video grant
                "room": room,
                "roomJoin": True,
                "canPublish": True,
                "canSubscribe": True,
            },
        }
        return jwt.encode(payload, API_SECRET, algorithm="HS256")

