import os, subprocess, sys, shlex

def launch_agent(room_name: str, token: str):
    env = os.environ.copy()
    env["ROOM_NAME"] = room_name
    env["LIVEKIT_TOKEN"] = token
    # Use same LIVEKIT_URL from controller env
    cmd = "python -u agent/agent.py"
    proc = subprocess.Popen(shlex.split(cmd), env=env)
    return proc.pid
