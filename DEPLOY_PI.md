# ViJu-TicketBooth auf einem Raspberry Pi 3B+ installieren

## 1. Voraussetzungen

- Raspberry Pi 3B+, microSD-Karte, Netzteil, Raspberry Pi OS Bookworm mit Desktop oder Lite
- **NetworkManager muss `wlan0` verwalten.** Bei älteren Images erst die Netzwerkverwaltung prüfen und migrieren.
- Internet für Paketinstallation und optional für TMDB, ein temporärer Ethernet-Anschluss oder bereits vorhandener SSH-Zugang für die einmalige Softwareinstallation
- Node.js **18 oder neuer**, npm, Python 3.11+; der Installationshelfer prüft Node.js
- HP Sprocket mit bekannter Bluetooth-MAC, passende Fotopapier-Kassette

Eine völlig unvorbereitete SD-Karte kann kein GitHub-Repository selbst laden. Die einmalige Installation erfolgt daher per Ethernet/SSH oder am Bildschirm. **Danach** ist die Ersteinrichtung des Geräts ohne Bildschirm, Tastatur und USB-WLAN-Stick über den geschützten Setup-AP möglich.

Vorher prüfen:

```bash
nmcli -g GENERAL.STATE device show wlan0
node --version
python3 --version
```

Wenn `wlan0` als „unmanaged“ erscheint, zunächst NetworkManager auf dem Pi korrekt aktivieren. Bei SSH über WLAN vor einer Änderung der Netzwerkverwaltung eine Ethernet-Verbindung bereitstellen.

## 2. Installation

```bash
sudo apt-get update
sudo apt-get install -y git nodejs npm
sudo git clone https://github.com/TaktischerSpeck/ViJu-TicketBooth.git /opt/viju-ticketbooth
cd /opt/viju-ticketbooth
sudo bash deploy/install.sh
```

Das Skript installiert Python-Abhängigkeiten, baut das Frontend, richtet `viju`, nginx, den Druck-Worker und den NetworkManager-Watchdog ein. Es erzeugt einmalig:

```text
/etc/viju-ticketbooth/access.env   # Setup-WLAN-Passwort, root-only
/etc/viju-ticketbooth/app.env      # Backend-Konfiguration, root-only
/var/lib/viju-ticketbooth/          # SQLite, Poster, Uploads, Render und Druckdateien
```

Die Zugangsdaten direkt bei der Installation sicher notieren:

```bash
sudo cat /etc/viju-ticketbooth/access.env
```

Die Datei enthält `SETUP_AP_PASSWORD` für das WPA2-Setup-WLAN. Das Webinterface verlangt kein Admin-Token.

## 3. TMDB und Druckmodus

```bash
sudoedit /etc/viju-ticketbooth/app.env
```

Beispiel:

```env
VIJU_DATA_DIR=/var/lib/viju-ticketbooth
TMDB_API_TOKEN=<eigener TMDB API Read Access Token>
PRINTER_BACKEND=mock
VIJU_NETWORK_HELPER=/usr/local/libexec/viju-network
PRINT_WIDTH=600
PRINT_HEIGHT=900
PRINT_JPEG_QUALITY=92
```

TMDB ist optional. Ohne Token funktionieren eigene Titel und Bilder, Historie, Vorschau und Druck weiterhin. Bei öffentlicher Weitergabe die TMDB-Nutzungs- und Attributionsbedingungen beachten.

Mit `PRINTER_BACKEND=mock` werden Druckdateien erstellt, ohne Bluetooth zu benutzen. Zum echten Druck `obexftp` eintragen. Nach jeder Änderung:

```bash
sudo systemctl restart viju-ticketbooth-api viju-ticketbooth-worker
curl http://127.0.0.1/api/health
```

## 4. Setup-WLAN und erste Bedienung

Wenn `wlan0` nicht mit einem Heim-WLAN verbunden ist, startet der Watchdog nach **90 Sekunden**:

```text
SSID: ViJu-TicketBooth-Setup
IP:   192.168.4.1
URL:  http://192.168.4.1
```

Mit dem Passwort aus `access.env` verbinden. Die Oberfläche öffnen und unter **Netzwerk** die SSID und das Passwort des Heim-WLANs eintragen und **WLAN verbinden** auslösen.

Die Webverbindung bricht während des Umschaltens ab. Nach erfolgreichem Wechsel das Smartphone wieder mit dem Heim-WLAN verbinden und die neue Pi-IP im Router oder per `hostname -I` ermitteln. Bei Fehlschlag aktiviert der Helfer den Setup-AP erneut. Der Watchdog startet ihn auch bei später dauerhaft verlorener WLAN-Verbindung nach 90 Sekunden.

Wenn der Pi weiterhin Ethernet hat, bleibt diese Verbindung während des WLAN-Tests eine zweite Administrationsmöglichkeit. Für Wiederherstellung ohne Netzwerk: Monitor/SSH über Ethernet und

```bash
sudo /usr/local/libexec/viju-network status
sudo /usr/local/libexec/viju-network ap
journalctl -u viju-ticketbooth-network -b
```

Der AP läuft bewusst **nicht dauerhaft parallel** zum Heim-WLAN. Das WLAN-Passwort geht nicht an den Browser zurück und wird nur als root-eigene NetworkManager-Verbindung gespeichert. Netzwerkprofile liegen unter `/etc/NetworkManager/system-connections/`.

## 5. HP Sprocket

1. Drucker laden und einschalten. Bluetooth am Pi aktivieren: `systemctl status bluetooth`.
2. In **Einstellungen → HP Sprocket** die MAC-Adresse und den OBEX-Channel eintragen, z. B. Channel 4. Die MAC muss zum eigenen Gerät gehören.
3. **Pairing** löst nur eine kurzzeitige Suche nach *dieser* MAC über BlueZ aus. Es gibt keine Geräteliste. Anschließend **Vertrauen** und **Verbindung prüfen** verwenden.
4. Die Verbindungsprüfung öffnet kurz den konfigurierten Bluetooth-Druckkanal, ohne Daten zu senden. Der normale Status zeigt bis dahin „Nicht geprüft“. `Connected: false` ist in Ruhe normal; Pairing und Vertrauen allein belegen nicht, dass der Drucker eingeschaltet ist.
5. `PRINTER_BACKEND=obexftp` setzen, API und Worker neu starten und **Testdruck** auslösen.
6. In **Historie → Druckaufträge** den Status prüfen. Bei Fehlern: `journalctl -u viju-ticketbooth-worker -f`.

Das Backend übergibt das JPEG ohne Shell an:

```bash
obexftp --nopath --noconn --uuid none --bluetooth C4:30:18:38:BD:E1 --channel 4 -p test.jpg
```

Dieser Weg ist hardwareabhängig und wurde hier nicht am echten Sprocket verifiziert. Papiergröße, Ausrichtung, Beschnitt, Bluetooth-Pairing und OBEX-Channel durch einen physischen Testdruck bestätigen. Die Voreinstellung 600 × 900 Pixel und 6,5 % Safe Area sind Startwerte.

## 6. Betrieb, Updates und Sicherung

```bash
systemctl status viju-ticketbooth-api viju-ticketbooth-worker viju-ticketbooth-network nginx
journalctl -u viju-ticketbooth-api -f
journalctl -u viju-ticketbooth-worker -f
journalctl -u viju-ticketbooth-network -f
```

Ein Update aus dem Repository:

```bash
cd /opt/viju-ticketbooth
sudo git pull --ff-only
sudo bash deploy/install.sh
sudo systemctl restart viju-ticketbooth-api viju-ticketbooth-worker viju-ticketbooth-network
```

`install.sh` erhält das Setup-WLAN-Passwort und Laufzeitdaten; vorhandene `VIJU_ADMIN_TOKEN`-Einträge werden entfernt. Für eine Sicherung die API/den Worker kurz stoppen oder SQLite über dessen Backup-API sichern; danach `/var/lib/viju-ticketbooth/`, `/etc/viju-ticketbooth/` und gegebenenfalls NetworkManager-Profile sichern. `journalctl` wird durch die übliche systemd-Journal-Rotation begrenzt; `SystemMaxUse` bei Bedarf in `/etc/systemd/journald.conf` setzen.

## 7. Sicherheit und Grenzen

- Die Website und API haben keine Anmeldung. Jeder erreichbare Client kann Tickets, Drucker- und Netzwerkeinstellungen verwalten. HTTP im Heim-LAN ist unverschlüsselt; das Gerät nur in einem vertrauenswürdigen privaten Netzwerk betreiben und nicht ins Internet weiterleiten.
- Der API-Dienst läuft als `viju`; nur die beiden fest installierten Helfer können über eng begrenzte sudoers-Regeln WLAN beziehungsweise BlueZ verändern.
- Uploads sind auf 16 MiB begrenzt und werden als validierte Bilder mit zufälligem Dateinamen gespeichert. TMDB-Poster werden nur von `image.tmdb.org` geladen.
- Der Print-Worker arbeitet Jobs seriell ab. Nach einem Neustart wird ein unterbrochener Transfer als fehlgeschlagen markiert, weil unbekannt ist, ob das Gerät bereits gedruckt hat. Ein erneuter Druck muss bewusst gestartet werden.
- Alte Render und Upload-Dateien werden nicht automatisch entfernt; Speicherbelegung auf kleinen SD-Karten beobachten. Historie und aktive Poster bleiben für Offline-Nutzung erhalten.

## Update

```bash
cd /opt/viju-ticketbooth
git status --short
git pull --ff-only origin mvp
backend/.venv/bin/python -m pip install -r backend/requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
sudo systemctl restart viju-ticketbooth-api viju-ticketbooth-worker
```

```bash
cd /opt/viju-ticketbooth && git status --short && git pull --ff-only origin mvp && backend/.venv/bin/python -m pip install -r backend/requirements.txt && npm --prefix frontend ci && npm --prefix frontend run build &&sudo systemctl restart viju-ticketbooth-api viju-ticketbooth-worker
```
