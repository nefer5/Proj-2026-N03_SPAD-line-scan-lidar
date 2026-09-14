from pathlib import Path
import argparse
import json
import socket
import sys
import threading
import time
from urllib.request import ProxyHandler, build_opener
import webbrowser

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

URL_OPENER = build_opener(ProxyHandler({}))


def is_lidar_server(url):
    try:
        with URL_OPENER.open(url + "/openapi.json", timeout=1) as response:
            schema = json.load(response)
        return schema.get("info", {}).get("title") == "SPAD Line-Scanning LiDAR Model"
    except (OSError, ValueError):
        return False


def open_when_ready(url):
    # Wait for successful application startup, rather than opening an error page.
    for _ in range(60):
        if is_lidar_server(url):
            webbrowser.open(url)
            return
        time.sleep(0.5)
    print("Browser not opened: startup timed out. Check the server log above.", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Start the LiDAR modeling server")
    parser.add_argument("--reload", action="store_true", help="Reload when Python source changes")
    parser.add_argument("--open", action="store_true", dest="open_browser", help="Open the browser when ready")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")

    url = f"http://127.0.0.1:{args.port}"
    with socket.socket() as probe:
        probe.settimeout(1)
        occupied = probe.connect_ex(("127.0.0.1", args.port)) == 0
    if occupied:
        if args.open_browser and is_lidar_server(url):
            print(f"LiDAR server already running: {url}")
            print("Reusing it. Restart its original launcher to change reload settings.")
            webbrowser.open(url)
            return
        parser.exit(1, f"Port {args.port} is already in use. Choose another --port.\n")

    try:
        import uvicorn
        import spad_lidar.api  # Check application dependencies before starting.
    except ImportError as exc:
        print(f"Missing dependency: {exc}")
        print('Install dependencies with this Python: python -m pip install -e .')
        return 1

    print(f"LiDAR model: {url}", flush=True)
    print("Keep this console open. Press Ctrl+C to stop the server.", flush=True)
    if args.reload:
        print("Python changes reload automatically. Refresh the browser for HTML/CSS/JS changes.", flush=True)
    if args.open_browser:
        threading.Thread(target=open_when_ready, args=(url,), daemon=True).start()
    uvicorn.run(
        "spad_lidar.api:app", host="127.0.0.1", port=args.port,
        reload=args.reload,
        reload_dirs=[str(ROOT / "src")] if args.reload else None,
    )


if __name__ == "__main__":
    sys.exit(main())
