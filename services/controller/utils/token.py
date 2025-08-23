import os, time, uuid, jwt

def mint_livekit_token(room_name: str, identity: str, ttl_seconds: int = 900):
    api_key = os.environ["LIVEKIT_API_KEY"]
    api_secret = os.environ["LIVEKIT_API_SECRET"]

    now = int(time.time())
    payload = {
        "iss": api_key,
        "sub": identity,
        "nbf": now - 5,
        "iat": now,
        "exp": now + ttl_seconds,
        "jti": str(uuid.uuid4()),
        "video": {
            "room": room_name,
            "roomJoin": True,
            "canPublish": True,
            "canSubscribe": True,
        },
    }
    token = jwt.encode(payload, api_secret, algorithm="HS256")
    return token
