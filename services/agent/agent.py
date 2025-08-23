import os, asyncio, time, logging
from dotenv import load_dotenv

# NOTE: Adjust imports to match your installed Pipecat version.
# The names below reflect common module paths; if they differ, update accordingly.
try:
    from pipecat.pipeline import Pipeline, Stage
    from pipecat.vad import WebRTCVAD
    from pipecat.transports.services.livekit import LiveKitTransport
except Exception as e:
    raise RuntimeError("Please install/configure Pipecat and LiveKit Python packages. Imports failed: %s" % e)

log = logging.getLogger("agent")
logging.basicConfig(level=logging.INFO)
load_dotenv()

LIVEKIT_URL   = os.environ["LIVEKIT_URL"]
LIVEKIT_TOKEN = os.environ["LIVEKIT_TOKEN"]
ROOM_NAME     = os.environ["ROOM_NAME"]

# Simple stage that speaks back quickly
class EchoLite(Stage):
    async def on_user_transcript(self, text: str):
        reply = f"You said: {text}. Got it!"
        # This calls the pipeline's configured TTS output; ensure your TTS is set in Pipeline.
        await self.emit_tts(reply)

async def main():
    # Tight buffers to keep latency low; tune for your environment
    transport = LiveKitTransport(
        url=LIVEKIT_URL,
        token=LIVEKIT_TOKEN,
        room_name=ROOM_NAME,
        params=dict(audio_sample_rate=16000, audio_channels=1, jitter_buffer_ms=40),
    )

    pipeline = Pipeline(
        transport=transport,
        stages=[
            WebRTCVAD(aggressiveness=2, min_voice_ms=120, max_silence_ms=150),
            EchoLite(),
        ],
        # TODO: Configure your low-latency STT/TTS providers here.
        # e.g., stt=YourStreamingSTT(...), tts=YourStreamingTTS(...)
    )

    # Basic E2E latency instrumentation (approximate: user speech -> first agent audio frame)
    t0 = None
    async def on_vad_start():
        nonlocal t0
        t0 = time.perf_counter()

    async def on_first_tts_chunk():
        if t0:
            dt_ms = (time.perf_counter() - t0) * 1000
            log.info(f"[latency] user->tts-first-chunk ~{dt_ms:.1f} ms")

    # Hook into pipeline/transport signals if available in your Pipecat version
    if hasattr(transport, "on_vad_start"):
        transport.on_vad_start = on_vad_start
    if hasattr(transport, "on_first_tts_chunk"):
        transport.on_first_tts_chunk = on_first_tts_chunk

    await pipeline.start()
    await pipeline.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
