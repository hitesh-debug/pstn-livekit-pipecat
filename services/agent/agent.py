import os, asyncio, logging, time
import aiohttp

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.pipeline.runner import PipelineRunner

# Frames
from pipecat.frames.frames import TranscriptionFrame, TextFrame

# Processor + direction
from pipecat.processors.frame_processor import FrameProcessor
try:
    from pipecat.processors.frame_processor import FrameDirection
except ImportError:
    from pipecat.processors.frame_processor import Direction as FrameDirection

# LiveKit transport (Pipecat 0.0.80)
from pipecat.transports.services.livekit import LiveKitTransport, LiveKitParams

# Optional VAD
try:
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    VAD = SileroVADAnalyzer()
except Exception:
    VAD = None

# STT/TTS
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("agent")

# ---------- Env (shared defaults) ----------
LIVEKIT_URL = os.environ.get("LIVEKIT_URL")                   # e.g., wss://<subdomain>.livekit.cloud
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY")
DG_MODEL = os.environ.get("DG_MODEL", "nova-3-general")
ELEVEN_API_KEY = os.environ.get("ELEVEN_API_KEY")
ELEVEN_VOICE_ID = os.environ.get("ELEVEN_VOICE_ID")

# Single-shot (legacy) fields — only used if POOL_MODE=false
LIVEKIT_TOKEN = os.environ.get("LIVEKIT_TOKEN")
ROOM_NAME = os.environ.get("ROOM_NAME")

# Pool mode
POOL_MODE = os.getenv("POOL_MODE", "false").lower() == "true"
ASSIGN_URL = os.environ.get("ASSIGN_URL")   # e.g., http://controller:8080/assign
ASSIGN_BACKOFF_S = float(os.getenv("ASSIGN_BACKOFF_S", "1.0"))

class EchoLite(FrameProcessor):
    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, TranscriptionFrame) and frame.text:
            reply = f"You said: {frame.text}. Got it!"
            await self.push_frame(TextFrame(reply), FrameDirection.DOWNSTREAM)
        await self.push_frame(frame, direction)

async def build_and_run(room_name: str, livekit_url: str, livekit_token: str):
    # LiveKit transport
    transport = LiveKitTransport(
        url=livekit_url,
        token=livekit_token,
        room_name=room_name,
        params=LiveKitParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=VAD,
        ),
    )

    # STT / TTS
    stt = DeepgramSTTService(
        api_key=DEEPGRAM_API_KEY,
        model=DG_MODEL,
        interim_results=True,
        punctuation=True,
    )
    tts = ElevenLabsTTSService(api_key=ELEVEN_API_KEY, voice_id=ELEVEN_VOICE_ID)

    # Pipeline
    pipeline = Pipeline([
        transport.input(),
        stt,
        EchoLite(),
        tts,
        transport.output(),
    ])

    # Simple latency probe for debugging
    t0 = {"start": None}
    @transport.event_handler("on_audio_track_subscribed")
    async def _on_audio(_t, participant_id):
        t0["start"] = time.perf_counter()

    @tts.event_handler("on_first_audio_chunk")
    async def _on_first(*_):
        if t0["start"]:
            log.info("[latency] user→tts-first ~%.1f ms", (time.perf_counter() - t0["start"]) * 1000)

    task = PipelineTask(pipeline)
    runner = PipelineRunner()
    await runner.run(task)  # returns when room ends / disconnect

async def poll_assign(session: aiohttp.ClientSession):
    try:
        async with session.get(ASSIGN_URL, timeout=35) as r:
            if r.status == 204:
                return None
            r.raise_for_status()
            return await r.json()
    except Exception as e:
        log.warning("assign poll error: %s", e)
        return None

async def main():
    if not POOL_MODE:
        # Legacy single-shot (for manual runs / local test)
        if not (ROOM_NAME and LIVEKIT_URL and LIVEKIT_TOKEN):
            raise RuntimeError("Single-shot mode needs ROOM_NAME, LIVEKIT_URL, LIVEKIT_TOKEN")
        await build_and_run(ROOM_NAME, LIVEKIT_URL, LIVEKIT_TOKEN)
        return

    if not (ASSIGN_URL and LIVEKIT_URL and DEEPGRAM_API_KEY and ELEVEN_API_KEY and ELEVEN_VOICE_ID):
        raise RuntimeError("POOL_MODE=true requires ASSIGN_URL, LIVEKIT_URL, DEEPGRAM_API_KEY, ELEVEN_API_KEY, ELEVEN_VOICE_ID")

    async with aiohttp.ClientSession() as session:
        log.info("Pool mode ON. Polling %s", ASSIGN_URL)
        while True:
            job = await poll_assign(session)
            if not job:
                await asyncio.sleep(ASSIGN_BACKOFF_S)
                continue
            room = job.get("room")
            url  = job.get("livekit_url") or LIVEKIT_URL
            tok  = job.get("livekit_token")
            if not (room and url and tok):
                log.warning("bad job payload: %s", job)
                await asyncio.sleep(ASSIGN_BACKOFF_S)
                continue
            log.info("Starting room=%s", room)
            await build_and_run(room, url, tok)
            log.info("Finished room=%s (waiting for next)", room)

if __name__ == "__main__":
    asyncio.run(main())
