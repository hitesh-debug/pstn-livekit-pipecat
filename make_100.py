# make_100.py
import asyncio, os
from twilio.rest import Client

ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
AUTH_TOKEN  = os.environ["TWILIO_AUTH_TOKEN"]
FROM       = os.environ["TWILIO_NUMBER"]     # verified/purchased number
TWIML_URL  = os.environ["TWIML_URL"]         # points to the XML above
SIP_URI    = "sip:+17622145814@28p3mcfarjq.sip.livekit.cloud;transport=tls"  # for logs only

client = Client(ACCOUNT_SID, AUTH_TOKEN)

async def place(n):
    call = client.calls.create(
        to=SIP_URI, from_=FROM, url=TWIML_URL, timeout=120
    )
    print(f"[{n}] {call.sid}")

async def main():
    CONCURRENCY = 20   # burst width
    TOTAL = 100
    TASKS = []
    for i in range(TOTAL):
        TASKS.append(asyncio.create_task(place(i)))
        if (i+1) % CONCURRENCY == 0:
            await asyncio.sleep(1.5)  # gentle ramp for CPS
    await asyncio.gather(*TASKS)

asyncio.run(main())