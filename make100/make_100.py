# make_100.py
import asyncio, os
from twilio.rest import Client

ACCOUNT_SID = "ACb686cbff7cea4ce41a974ff6367ad578"
AUTH_TOKEN  = "b28cc99572206488d8faaf50ffa30dec"
FROM       = "+917221033260"   
TWIML_URL  = "https://handler.twilio.com/twiml/EHccf7a36ab1c97dfab6db1720dd5c8ab0"        
SIP_URI    = "sip:+17622145814@28p3mcfarjq.sip.livekit.cloud;transport=tls"  # for logs only

client = Client(ACCOUNT_SID, AUTH_TOKEN)

async def place(n):
    call = client.calls.create(
        to=SIP_URI, from_=FROM, url=TWIML_URL, timeout=120
    )
    print(f"[{n}] {call.sid}")

async def main():
    CONCURRENCY = 1   # burst width
    TOTAL = 5
    TASKS = []
    for i in range(TOTAL):
        TASKS.append(asyncio.create_task(place(i)))
        if (i+1) % CONCURRENCY == 0:
            await asyncio.sleep(1.5)
    await asyncio.gather(*TASKS)

asyncio.run(main())