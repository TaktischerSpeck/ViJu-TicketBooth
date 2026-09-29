# ViJu-TicketBooth

Lokale Webanwendung für kleine Kino-Erinnerungstickets auf einem HP Sprocket. Das Poster füllt die gesamte Druckfläche; Text liegt direkt darauf. Zielgerät ist ein Raspberry Pi 3B+ mit internem WLAN und Bluetooth.

## Funktionen

- TMDB-Suche, „Aktuell im Kino“ für Deutschland, Zufallsfilm, alternative Poster mit englischer Priorität
- eigener Filmtitel und eigener JPEG/PNG/WebP-Upload für Offline-Betrieb
- optionale Ticketdaten, Live-Vorschau aus demselben serverseitigen Renderer wie der Druck, Bildausschnitt per Drag und Zoom
- Minimal, Soft, Strong und Auto-Lesbarkeit; Textfarbe, Schatten, Position, Safe Area
- PNG-Master, JPEG-Druckdatei, Download, SQLite-Historie, Duplikate und Design-Presets
- persistente Druckwarteschlange mit Idempotency-Key, Mock-Backend und OBEX-Transfer
- gezieltes Pairing/Trust via BlueZ für eine manuell eingetragene MAC; kein allgemeiner Bluetooth-Scanner
- Setup- und Recovery-AP via NetworkManager auf dem internen WLAN-Chip
- Admin-Token für schreibende API-Aufrufe; TMDB-Token verbleibt im Backend

**Pi-Installation:** [DEPLOY_PI.md](DEPLOY_PI.md). Die Hinweise zu WLAN-Umschaltung und dem echten HP Sprocket dort vor der Installation lesen.

## Lokal entwickeln

Python 3.11+, Node.js 18+ und DejaVu Sans werden benötigt. Ohne Pi-Hardware funktioniert das Mock-Druckerbackend. Die lokale Testinstanz legt Dateien unter `data/` an.

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements-dev.txt
cp .env.example .env
# In .env ein zufälliges VIJU_ADMIN_TOKEN setzen und PRINTER_BACKEND=mock belassen.
cd frontend && npm install && npm run build && cd ..
backend/.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

In einem zweiten Terminal:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m app.printing
```

Danach `http://127.0.0.1:8000` öffnen, unter **Einstellungen → Admin-Zugang** das Token aus `.env` eintragen und mit einem eigenen Poster starten. Für TMDB `TMDB_API_TOKEN` in `.env` eintragen und API neu starten. `npm run dev` im Frontend-Verzeichnis startet alternativ den Vite-Entwicklungsserver mit API-Proxy.

Tests:

```bash
PYTHONPATH=backend backend/.venv/bin/pytest -q backend/tests
cd frontend && npm run build
```

## Aufbau

- `backend/app/main.py`: FastAPI-Routen und Admin-Grenze
- `backend/app/movies.py`: TMDB und Poster-Cache
- `backend/app/render.py`: Crop, Textlayout, Kontrast und PNG/JPEG
- `backend/app/printing.py`: SQLite-Queue, Worker und austauschbarer Mock/OBEX-Druck
- `backend/app/bluetooth.py`: BlueZ-D-Bus
- `deploy/network/viju-network`: privilegierter NetworkManager-Helfer für AP/Recovery
- `frontend/`: mobile React-Oberfläche

Die API unter `/docs` dokumentiert die Endpunkte. Zustandsänderungen verlangen `X-Admin-Token`. Die Konfiguration unter `/etc/viju-ticketbooth/app.env` enthält Server-Defaults, der Drucker wird zur Laufzeit in SQLite gespeichert. WLAN-Schlüssel liegen ausschließlich in root-eigenen NetworkManager-Profilen.

## Bekannte Grenzen

- Der OBEX-Befehl `obexftp --nopath --noconn --uuid none --bluetooth MAC --channel N -p datei.jpg` stammt aus dem Bauplan und muss am konkreten Sprocket mit Firmware und Papier kalibriert werden. Ein erfolgreicher Transfer bestätigt nicht zwingend einen tatsächlich abgeschlossenen Ausdruck.
- Der Pi 3B+ nutzt einen WLAN-Chip. Während des Wechsels vom AP ins Heimnetz ist der AP kurz offline; bei Fehlschlag wird er wieder aktiviert. Ein unterbrechungsfreier Test ist mit dieser Ein-Radio-Architektur nicht möglich.
- Das Admin-Token wird für die Browser-Sitzung gespeichert. Für Zugriff jenseits eines vertrauenswürdigen lokalen Netzes HTTPS und VPN/zusätzliche Authentisierung vorsehen.
- Druckbreite und -höhe sind als 600 × 900 Pixel voreingestellt und müssen nach einem Testdruck für das konkrete Gerät angepasst werden.
