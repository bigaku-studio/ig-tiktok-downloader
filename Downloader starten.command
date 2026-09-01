#!/bin/bash
cd "$(dirname "$0")"

if [ ! -f "venv/bin/python" ]; then
  echo "Fehler: venv wurde nicht gefunden. Bitte zuerst einrichten mit:"
  echo "  python3 -m venv venv && ./venv/bin/pip install -r requirements.txt"
  read -p "Fenster mit Enter schließen..."
  exit 1
fi

echo "Starte Instagram & TikTok Downloader..."
echo "Dieses Fenster offen lassen, solange du die Seite nutzen willst."
echo "Zum Beenden: Fenster schließen oder Ctrl+C drücken."
echo ""

./venv/bin/python app.py &
SERVER_PID=$!

sleep 2
open "http://127.0.0.1:5050"

wait $SERVER_PID
