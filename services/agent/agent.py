import os, asyncio, logging, time

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.pipeline.runner import PipelineRunner
from pipecat.frames.frames import TranscriptionFrame, TextFrame

from pipecat.processors.frame_processor import FrameProcessor
try:
    from pipecat.processors.frame_processor import FrameDirection
except ImportError:
    from pipecat.processors.frame_processor import Direction as FrameDirection

from pipecat.transports.services.livekit import LiveKitTransport, LiveKitParams

try:
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    VAD = SileroVADAnalyzer()
except Exception:
    VAD = None
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

try:
    VAD = SileroVADAnalyzer()
except Exception:
    VAD = None  

class EchoLite(FrameProcessor):
    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, TranscriptionFrame) and frame.text:
            # Simple "echo with twist" reply
            reply = f"You said: {frame.text}. Got it!"
            await self.push_frame(TextFrame(reply), FrameDirection.DOWNSTREAM)
        # Forwarding original frames
        await self.push_frame(frame, direction)

async def main():

    transport = LiveKitTransport(
        url=LIVEKIT_URL,
        token=LIVEKIT_TOKEN,
        room_name=ROOM_NAME,
        params=LiveKitParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=VAD,    # enables better turn-taking
        ),
    )

    # Streaming STT (Deepgram)
    stt = DeepgramSTTService(
        api_key=DEEPGRAM_API_KEY,
        model=DG_MODEL,
        interim_results=True, 
        punctuation=True,
    )

    # Streaming TTS (ElevenLabs over WebSocket)
    tts = ElevenLabsTTSService(
        api_key=ELEVEN_API_KEY,
        voice_id=ELEVEN_VOICE_ID,
    )

    pipeline = Pipeline([
        transport.input(),  # room → audio frames
        stt,                # audio → TranscriptionFrame (streaming)
        EchoLite(),         # TranscriptionFrame → TextFrame
        tts,                # TextFrame → AudioFrame (streaming)
        transport.output(), # AudioFrame → room
    ])

    t0 = {"start": None}
    @transport.event_handler("on_audio_track_subscribed")
    async def _on_audio(_t, participant_id):
        t0["start"] = time.perf_counter()

    @tts.event_handler("on_first_audio_chunk")
    async def _on_first_tts_chunk(*_):
        if t0["start"]:
            log.info("[latency] user→tts-first ~%.1f ms", (time.perf_counter() - t0["start"]) * 1000)

    task = PipelineTask(pipeline)     # manage lifecycle & events
    runner = PipelineRunner()         # runs the task
    await runner.run(task) 

if __name__ == "__main__":
    asyncio.run(main())
