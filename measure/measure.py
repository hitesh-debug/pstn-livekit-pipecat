#!/usr/bin/env python3
import asyncio
import base64
import json
import logging
import os
import signal
import sys
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional, Tuple

import numpy as np
import websockets
from websockets.server import WebSocketServerProtocol

# -------------------------
# Config (env overrides)
# -------------------------
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8082"))
WS_PATH = os.getenv("WS_PATH", "/stream")  # Twilio will connect to wss://host/stream
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
ENERGY_THRESH = float(os.getenv("ENERGY_THRESH", "0.02"))   # RMS threshold for "user started speaking"
PRINT_EVERY = int(os.getenv("PRINT_EVERY", "20"))           # print agg stats every N results
CSV_PATH = os.getenv("CSV_PATH", "")                        # optional: write results to CSV file

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("measure")

# -------------------------
# State & helpers
# -------------------------
class CallState:
    __slots__ = ("t_in_local", "t_in_ts", "done")
    def __init__(self) -> None:
        self.t_in_local: Optional[float] = None  # time.perf_counter() when inbound voice onset detected
        self.t_in_ts: Optional[float] = None     # Twilio-provided timestamp (ms) at inbound onset
        self.done: bool = False                  # set True after first outbound audio detected

STATE: Dict[str, CallState] = defaultdict(CallState)

LAT_MS_LOCAL: Deque[float] = deque(maxlen=10000)  # local RTTs
LAT_MS_TS: Deque[float] = deque(maxlen=10000)     # RTTs via Twilio timestamps
CSV_HEADER_WRITTEN = False

def rms_from_pcm16le(b: bytes) -> float:
    """Compute RMS for 16-bit little-endian PCM mono samples."""
    if not b:
        return 0.0
    arr = np.frombuffer(b, dtype="<i2")
    if arr.size == 0:
        return 0.0
    return float(np.sqrt(np.mean((arr / 32768.0) ** 2)))

def p50_p95(values) -> Tuple[Optional[float], Optional[float]]:
    if not values:
        return None, None
    s = sorted(values)
    n = len(s)
    p50 = s[int(0.50 * (n - 1))]
    p95 = s[int(0.95 * (n - 1))]
    return p50, p95

def to_float_or_none(x) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None

async def write_csv_row(sid: str, rtt_local_ms: float, rtt_ts_ms: Optional[float]) -> None:
    global CSV_HEADER_WRITTEN
    if not CSV_PATH:
        return
    line = None
    if not CSV_HEADER_WRITTEN and not os.path.exists(CSV_PATH):
        header = "streamSid,rtt_local_ms,rtt_ts_ms,ts\n"
        with open(CSV_PATH, "a", encoding="utf-8") as f:
            f.write(header)
        CSV_HEADER_WRITTEN = True
    ts = int(time.time() * 1000)
    line = f"{sid},{rtt_local_ms:.3f},{'' if rtt_ts_ms is None else f'{rtt_ts_ms:.3f}'},{ts}\n"
    try:
        with open(CSV_PATH, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        log.warning("CSV write failed: %s", e)

# -------------------------
# WebSocket handler
# -------------------------
async def handle(ws: WebSocketServerProtocol) -> None:
    """
    Twilio sends JSON messages with events: start, media, stop.
    We detect:
      - first inbound voice onset (energy threshold)
      - first outbound audio after that
    Then compute:
      - RTT via local clock (now - t_in_local)
      - RTT via Twilio timestamps (out_ts - in_ts), if present
    """
    # Path gate: only accept connections to the configured WS_PATH
    path = ws.path or "/"
    if path.rstrip("/") != WS_PATH.rstrip("/"):
        log.warning("Rejecting connection on unexpected path: %s", path)
        # Close with 1008 (policy violation)
        await ws.close(code=1008, reason="invalid path")
        return

    sid: Optional[str] = None
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except Exception:
                # Ignore non-JSON frames
                continue

            ev = msg.get("event")
            if ev == "start":
                sid = msg.get("start", {}).get("streamSid")
                if not sid:
                    # If Twilio didn't include streamSid, fabricate one for safety
                    sid = f"no_sid_{int(time.time()*1000)}"
                STATE[sid] = CallState()
                log.info("start %s", sid)

            elif ev == "media":
                if not sid:
                    continue  # ignore media before 'start'
                st = STATE[sid]
                if st.done:
                    continue

                media = msg.get("media", {})
                track = (media.get("track") or "inbound_track").lower()  # inbound_track/outbound_track
                payload_b64 = media.get("payload") or ""
                payload = base64.b64decode(payload_b64) if payload_b64 else b""

                # Twilio-provided timestamp in ms since stream start (string → float)
                ts_ms = to_float_or_none(media.get("timestamp"))

                energy = rms_from_pcm16le(payload)
                now = time.perf_counter()

                # First inbound speech onset
                if track.startswith("inbound") and st.t_in_local is None and energy > ENERGY_THRESH:
                    st.t_in_local = now
                    st.t_in_ts = ts_ms
                    log.debug("%s inbound onset energy=%.3f ts_ms=%s", sid, energy, st.t_in_ts)

                # First outbound audio after onset → compute RTT once
                if track.startswith("outbound") and st.t_in_local is not None:
                    rtt_local_ms = (now - st.t_in_local) * 1000.0
                    rtt_ts_ms: Optional[float] = None
                    if ts_ms is not None and st.t_in_ts is not None:
                        rtt_ts_ms = ts_ms - st.t_in_ts

                    LAT_MS_LOCAL.append(rtt_local_ms)
                    if rtt_ts_ms is not None:
                        LAT_MS_TS.append(rtt_ts_ms)

                    log.info(
                        "%s RTT local=%.1f ms ts=%s ms",
                        sid,
                        rtt_local_ms,
                        f"{rtt_ts_ms:.1f}" if rtt_ts_ms is not None else "n/a",
                    )

                    await write_csv_row(sid, rtt_local_ms, rtt_ts_ms)

                    st.done = True  # stop after first outbound packet post-onset

                    # Periodic aggregate
                    if len(LAT_MS_LOCAL) % PRINT_EVERY == 0:
                        p50l, p95l = p50_p95(list(LAT_MS_LOCAL))
                        p50t, p95t = p50_p95(list(LAT_MS_TS))
                        log.info(
                            "[agg] local p50=%.1f p95=%.1f | ts p50=%s p95=%s (n=%d)",
                            p50l or -1,
                            p95l or -1,
                            f"{p50t:.1f}" if p50t is not None else "n/a",
                            f"{p95t:.1f}" if p95t is not None else "n/a",
                            len(LAT_MS_LOCAL),
                        )

            elif ev == "stop":
                if sid:
                    log.info("stop %s", sid)

            else:
                # ignore other events
                pass

    except websockets.ConnectionClosedOK:
        pass
    except websockets.ConnectionClosedError:
        pass
    except Exception as e:
        log.exception("WS handler error: %s", e)

# -------------------------
# Server bootstrap
# -------------------------
async def main() -> None:
    stop_event = asyncio.Event()

    def _graceful(*_):
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _graceful)
        except NotImplementedError:
            # Windows
            pass

    log.info("Starting measurement WS on ws://%s:%d%s", HOST, PORT, WS_PATH)
    async with websockets.serve(
        handle,
        HOST,
        PORT,
        subprotocols=["audio"],  # Twilio uses 'audio'
        process_request=None,    # path check happens inside handler
        max_size=2**22,          # safe headroom for frames (~4MB)
    ):
        await stop_event.wait()
    log.info("Server stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
