"""Start Case Sparring Partner:  python run.py   (then open http://localhost:8000 in Chrome)

    python run.py --port 8010      # if 8000 is taken
    python run.py --no-browser     # don't open a browser tab
"""

import argparse
import threading
import webbrowser

import uvicorn

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    from app import llm  # noqa: F401  (fails fast with a clear message if PORTKEY_API_KEY is missing)
    llm.build_model()

    url = f"http://localhost:{args.port}"
    print(f"\n  Case Sparring Partner is running at {url}  (use Chrome for voice)\n  Press Ctrl+C to stop.\n")
    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run("app.main:app", host="127.0.0.1", port=args.port, log_level="warning")
