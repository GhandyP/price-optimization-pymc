"""Command line entry point: serve the API and open the web interface."""

from __future__ import annotations

import argparse
import threading
import time
import webbrowser

import uvicorn

BROWSER_OPEN_TIMEOUT_SECONDS = 60.0
BROWSER_POLL_INTERVAL_SECONDS = 0.2


def _open_browser_when_ready(server: uvicorn.Server, url: str) -> None:
    """Open the browser only once uvicorn is actually serving.

    Importing PyMC takes several seconds, so opening the browser right after
    launching would show a connection error while the app is still loading.
    """
    deadline = time.monotonic() + BROWSER_OPEN_TIMEOUT_SECONDS
    while not server.started and time.monotonic() < deadline:
        time.sleep(BROWSER_POLL_INTERVAL_SECONDS)

    if server.started:
        webbrowser.open(url)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Levanta la API y abre la interfaz web de optimizacion de precios."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Interfaz de red donde escuchar (default: 127.0.0.1).")
    parser.add_argument("--port", type=int, default=8000, help="Puerto donde escuchar (default: 8000).")
    parser.add_argument("--no-open", action="store_true", help="No abrir el navegador automaticamente.")
    args = parser.parse_args()

    config = uvicorn.Config("price_optimizer.api:app", host=args.host, port=args.port)
    server = uvicorn.Server(config)

    if not args.no_open:
        print(f"Abriendo {args.host}:{args.port} en el navegador cuando el servidor este listo...", flush=True)
        threading.Thread(
            target=_open_browser_when_ready,
            args=(server, f"http://{args.host}:{args.port}"),
            daemon=True,
        ).start()

    print("Importando PyMC: la primera carga puede tardar unos segundos.", flush=True)
    server.run()
