# services/agent/agent.py
import os, asyncio, time, logging
from dotenv import load_dotenv

from pipecat.pipeline.pipeline import Pipeline
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.transports.services.livekit import LiveKitTransport, LiveKitParams
from pipecat.frames.frames import TranscriptionFrame, TextFrame
# Optional: lower-latency/accurate VAD (requires: pip install "pipecat-ai[silero]")
try:
    from pipecat.audio.vad.silero import SileroVADAnalyzer  # optional
    VAD = SileroVADAnalyzer()
except Exception:
    VAD = None  # use transport default

load_dotenv()
log = logging.getLogger("agent")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

LIVEKIT_URL   = os.environ["LIVEKIT_URL"]
LIVEKIT_TOKEN = os.environ["LIVEKIT_TOKEN"]
ROOM_NAME     = os.environ["ROOM_NAME"]

class EchoLite(FrameProcessor):
    async def process_frame(self, frame, direction):
        # Always call parent first to keep system frames sane
        await super().process_frame(frame, direction)

        # When the user transcription arrives, emit a TextFrame for TTS
        if isinstance(frame, TranscriptionFrame) and frame.text:
            await self.push_frame(TextFrame(f"You said: {frame.text}. Got it!"),
                                  FrameDirection.DOWNSTREAM)

        # Forward the original frame to the next processors
        await self.push_frame(frame, direction)

async def main():
    transport = LiveKitTransport(
        url=LIVEKIT_URL,
        token=LIVEKIT_TOKEN,
        room_name=ROOM_NAME,
        params=LiveKitParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=VAD,  # None = default; or Silero if available
        ),
    )

    # TODO: insert your streaming STT/TTS services here (e.g., OpenAI STT/TTS)
    # e.g. stt = OpenAITranscriptionService(...)
    #      tts = OpenAITTSService(...)

    pipeline = Pipeline([
        transport.input(),   # audio from participants
        # stt,
        EchoLite(),
        # tts,
        transport.output(),  # audio to participants
    ])

    t0 = None
    @transport.event_handler("on_audio_track_subscribed")
    async def _on_vad_start(transport, participant_id):
        nonlocal t0
        t0 = time.perf_counter()

    @transport.event_handler("on_data_received")
    async def _on_first_tts_chunk(transport, data, participant_id):
        # Example hook: replace with actual event you wire from your TTS service
        if t0:
            log.info("[latency] user->tts-first ~%.1f ms", (time.perf_counter() - t0) * 1000)

    # Run your pipeline (see your runner/invocation pattern)
    # await pipeline.start()
    # await pipeline.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
