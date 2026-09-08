#!/usr/bin/env python3
"""Avvia la dashboard e apre il browser.

Uso:  python avvia.py [--porta 8000] [--no-browser]
"""
from __future__ import annotations

import argparse
import socket
import sys
import threading
import webbrowser


def porta_libera(porta: int, tentativi: int = 20) -> int:
    for candidata in range(porta, porta + tentativi):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", candidata)) != 0:
                return candidata
    return porta


def main() -> int:
    parser = argparse.ArgumentParser(description="Prospetto Immobili")
    parser.add_argument("--porta", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-browser", action="store_true")
    argomenti = parser.parse_args()

    try:
        import uvicorn
    except ImportError:
        print("Dipendenze mancanti. Esegui:  pip install -r requirements.txt", file=sys.stderr)
        return 1

    porta = porta_libera(argomenti.porta)
    indirizzo = f"http://{argomenti.host}:{porta}"

    if not argomenti.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(indirizzo)).start()

    print(f"\n  Prospetto Immobili e' attivo su  {indirizzo}")
    print("  Premi CTRL+C per chiudere.\n")
    uvicorn.run("app.main:app", host=argomenti.host, port=porta, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
