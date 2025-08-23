import os, time
from datetime import timedelta
from typing import Optional

# We use the official LiveKit Python helper to mint tokens
# (install via controller/requirements.txt)
from livekit import AccessToken, VideoGrants  # type: ignore

LK_API_KEY    = os.environ["LIVEKIT_API_KEY"]
LK_API_SECRET = os.environ["LIVEKIT_API_SECRET"]

def mint_livekit_token(room: str, identity: str, ttl_seconds: int = 900, name: Optional[str] = None) -> str:
    """
    Create a LiveKit access token that can join/publish/subscribe in `room`.
    Identity must be unique per participant instance to avoid DuplicateIdentity.
    """
    grants = VideoGrants(
        room_join=True,
        room=room,
        can_subscribe=True,
        can_publish=True,
        can_publish_data=True,
    )
    at = AccessToken(LK_API_KEY, LK_API_SECRET, identity=identity, name=name or identity)
    at.add_grants(grants)
    at.ttl = timedelta(seconds=ttl_seconds)
    return at.to_jwt()
