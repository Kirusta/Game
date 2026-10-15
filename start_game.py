"""Palaiž Cyber Tower Defense un tā datubāzes serveri kopā."""

import subprocess
import sys
import socket
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


def main():
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=PROJECT_ROOT,
    )
    try:
        # Sagaida, līdz Leaderboard un datubāzes serveris ir pieejams.
        for _ in range(30):
            try:
                with socket.create_connection(("127.0.0.1", 8000), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.1)
        subprocess.run([sys.executable, "CyberTD.PY"], cwd=PROJECT_ROOT, check=False)
    finally:
        server.terminate()
        try:
            server.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    main()
