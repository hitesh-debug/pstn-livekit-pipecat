# services/agent/agent.py
import os, asyncio, time, logging
from dotenv import load_dotenv

# Install/adjust these imports per your Pipecat version
try:
    from pipecat.pipeline import Pipeline, Stage
    from pipecat.vad import WebRTCVAD
    from pipecat.transports.services.livekit import LiveKitTransport
except Exception as e:
    raise RuntimeError(f"Pipecat/LiveKit imports failed: {e}")

load_dotenv()
log = logging.getLogger("agent")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

LIVEKIT_URL   = os.environ["LIVEKIT_URL"]     # provided via overrides
LIVEKIT_TOKEN = os.environ["LIVEKIT_TOKEN"]   # provided via overrides
ROOM_NAME     = os.environ["ROOM_NAME"]       # provided via overrides

class EchoLite(Stage):
    async def on_user_transcript(self, text: str):
        # minimal low-latency reply
        await self.emit_tts(f"You said: {text}. Got it!")

async def main():
    transport = LiveKitTransport(
        url=LIVEKIT_URL,
        token=LIVEKIT_TOKEN,
        room_name=ROOM_NAME,
        params=dict(
            audio_sample_rate=16000,
            audio_channels=1,
            jitter_buffer_ms=40,
            # enable barge-in if supported in your version:
            # enable_barge_in=True,
        ),
    )

    pipeline = Pipeline(
        transport=transport,
        stages=[
            WebRTCVAD(aggressiveness=2, min_voice_ms=120, max_silence_ms=150),
            EchoLite(),
        ],
        # TODO: plug your streaming STT/TTS here for <600 ms roundtrip
        # stt=YourStreamingSTT(...),
        # tts=YourStreamingTTS(...),
    )

    # simple latency probe
    t0 = None
    async def on_vad_start():
        nonlocal t0
        t0 = time.perf_counter()
    async def on_first_tts_chunk():
        if t0:
            log.info("[latency] user->tts-first ~%.1f ms", (time.perf_counter() - t0) * 1000)

    if hasattr(transport, "on_vad_start"):
        transport.on_vad_start = on_vad_start
    if hasattr(transport, "on_first_tts_chunk"):
        transport.on_first_tts_chunk = on_first_tts_chunk

    await pipeline.start()
    await pipeline.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
