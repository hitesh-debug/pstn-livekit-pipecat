import os
from fastapi import FastAPI
from fastapi.responses import Response
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

LIVEKIT_SIP_URI = os.environ.get("LIVEKIT_SIP_URI", "sip:inbound-xyz@sip.livekit.cloud")

@app.get("/voice")
@app.post("/voice")
def voice():
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Dial answerOnBridge="true">
    <Sip>{LIVEKIT_SIP_URI}</Sip>
  </Dial>
</Response>
"""
    return Response(content=twiml, media_type="application/xml")

@app.get("/healthz")
def healthz():
    return {"ok": True}
