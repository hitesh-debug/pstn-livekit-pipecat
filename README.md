# PSTN → LiveKit (SIP) → Pipecat Agent (Full Duplex, <600ms)

Minimal, reproducible skeleton to accept inbound **PSTN** calls on **Twilio**, bridge to **LiveKit** (SIP), and join a **Pipecat** agent in the LiveKit room with **barge-in**. Includes a controller that listens to LiveKit webhooks, mints join tokens, and launches agent workers per call.

> ⚠️ This is a **starter** repo. You must plug in your preferred **low-latency STT/TTS** inside `services/agent/agent.py` via Pipecat.


## Architecture

```
Twilio PSTN -> TwiML (this repo) -> SIP Dial to LiveKit Inbound Trunk
                                       |
                                      Room (auto-created via LiveKit Dispatch Rule; e.g., pstn-${callSid})
                                       |
                             LiveKit Webhook -> Controller -> Mint Agent Token & spawn Agent worker
                                       |
                                 Pipecat Agent joins same room (full duplex, barge-in)
```

### Latency knobs (to stay under ~600 ms roundtrip)
- Keep Twilio number geo, LiveKit region, and agents **in the same region**.
- Use **streaming STT/TTS** with first audio chunk <150–200 ms.
- Keep jitter buffer tight (40–60 ms), mono 16k.
- Enable **barge-in** by interrupting TTS when VAD detects user speech.


## Quick Start

1. **Create** LiveKit SIP Inbound Trunk and a **Dispatch Rule** that creates a room like `pstn-${callSid}` and sends webhooks to `https://YOUR_CONTROLLER_DOMAIN/livekit/webhook`.
2. **Point** your Twilio number’s **Voice webhook** to `https://YOUR_TWIML_DOMAIN/voice` (served by this repo). It returns TwiML that dials your LiveKit SIP URI.
3. Copy `.env.sample` to `.env` and fill in your **LIVEKIT_URL / API_KEY / API_SECRET / LIVEKIT_SIP_URI**.
4. Run locally:
   ```bash
   docker compose up --build
   ```
5. Expose ports (ngrok, Cloudflared, etc.) so Twilio (Voice webhook) and LiveKit (webhook) can reach your services.


## Services

- **twiml_server**: Serves a tiny TwiML `<Dial><Sip>` that bridges caller to LiveKit SIP.
- **controller**: Receives LiveKit webhooks (room created/ended), mints a token, and launches an agent worker for that room.
- **agent**: Minimal Pipecat-based echo bot (replace with your logic & STT/TTS).

> For scale (100 concurrent), run controller stateless and use a queue/K8s Job per call instead of local subprocesses.


## Routes

- `POST /livekit/webhook`: Controller endpoint for LiveKit webhooks.
- `GET  /healthz`: Health check (controller).
- `GET  /voice`: TwiML endpoint (twiml_server) for Twilio **Incoming Calls** (or use POST; both are accepted).


## Token minting

We mint a short-lived **LiveKit Room Join** token for the agent. This example uses a compact JWT helper. If you prefer, swap to LiveKit’s official token helpers.


## Pipecat

`services/agent/agent.py` is a minimal Pipecat pipeline that:
- Listens for user speech (VAD).
- Emits a short TTS reply starting quickly (streaming).

Replace with your logic; wire your STT/TTS providers via environment variables.


## Docker

```bash
docker compose up --build
```

- Controller on `:8080`
- TwiML server on `:8081`


## K8s (sketch)

See `k8s/` for Deployment & HPA stubs. In production, prefer spawning **one agent worker per call** as a Job or via your own queue/worker logic.


## Security

- Restrict controller to accept LiveKit webhook IPs (or verify HMAC if available).
- Use **short TTL** tokens (e.g., 10–15 minutes).
- Validate webhook event types/room names.


## License

MIT
