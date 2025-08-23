# agent.py
import os, asyncio, logging, time
from pipecat.pipeline.pipeline import Pipeline
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.frames.frames import TranscriptionFrame, TextFrame, FrameDirection
from pipecat.transports.services.livekit import LiveKitTransport, LiveKitParams
from pipecat.audio.vad.silero import SileroVADAnalyzer

# STT/TTS services
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("agent")

LIVEKIT_URL   = os.environ["LIVEKIT_URL"]
LIVEKIT_TOKEN = os.environ["LIVEKIT_TOKEN"]
ROOM_NAME     = os.environ["ROOM_NAME"]

DEEPGRAM_API_KEY = os.environ["DEEPGRAM_API_KEY"]
DG_MODEL         = os.getenv("DG_MODEL", "nova-3-general")

ELEVEN_API_KEY   = os.environ["ELEVEN_API_KEY"]
ELEVEN_VOICE_ID  = os.environ["ELEVEN_VOICE_ID"]

# Optional, but recommended
try:
    VAD = SileroVADAnalyzer()
except Exception:
    VAD = None  # falls back to transport defaults

class EchoLite(FrameProcessor):
    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, TranscriptionFrame) and frame.text:
            # Simple "echo with twist" reply
            reply = f"You said: {frame.text}. Got it!"
            await self.push_frame(TextFrame(reply), FrameDirection.DOWNSTREAM)
        # Always forward original frames
        await self.push_frame(frame, direction)

async def main():
    # LiveKit full-duplex transport (audio in/out on)
    transport = LiveKitTransport(
        url=LIVEKIT_URL,
        token=LIVEKIT_TOKEN,
        room_name=ROOM_NAME,
        params=LiveKitParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=VAD,    # enables better turn-taking
            # You can add smart-turn detection / interruption strategy here as needed
        ),
    )

    # Streaming STT (Deepgram)
    stt = DeepgramSTTService(
        api_key=DEEPGRAM_API_KEY,
        model=DG_MODEL,
        interim_results=True,       # emit InterimTranscriptionFrame too
        punctuation=True,
    )

    # Streaming TTS (ElevenLabs over WebSocket)
    tts = ElevenLabsTTSService(
        api_key=ELEVEN_API_KEY,
        voice_id=ELEVEN_VOICE_ID,
        # You can tune speed/stability/etc. here if you like
    )

    pipeline = Pipeline([
        transport.input(),  # room → audio frames
        stt,                # audio → TranscriptionFrame (streaming)
        EchoLite(),         # TranscriptionFrame → TextFrame
        tts,                # TextFrame → AudioFrame (streaming)
        transport.output(), # AudioFrame → room
    ])

    # (Optional) quick latency probe
    t0 = {"start": None}
    @transport.event_handler("on_audio_track_subscribed")
    async def _on_audio(_t, participant_id):
        t0["start"] = time.perf_counter()

    @tts.event_handler("on_first_audio_chunk")
    async def _on_first_tts_chunk(*_):
        if t0["start"]:
            log.info("[latency] user→tts-first ~%.1f ms", (time.perf_counter() - t0["start"]) * 1000)

    await pipeline.start()
    await pipeline.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
