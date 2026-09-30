# Preview-Fix im mvp-Branch

Der Posterwechsel invalidiert jetzt die alte Vorschau sofort. Laufende Browserrequests werden abgebrochen; verspätete Antworten und Blob-Auswertungen dürfen keine neuere Auswahl überschreiben. Ein stabiler Poster-Fallback zeigt Ladezustand oder Fehler. Blob-URLs und Timer werden aufgeräumt. Schnelle Filmwechsel brechen außerdem alte Posterlisten-Abfragen ab.

Preview- und gespeichertes Rendering laufen außerhalb des API-Eventloops. Die API lässt jeweils nur einen Renderpfad zu; wartende Preview-Anfragen prüfen vor Download und Rendering, ob der Client bereits getrennt wurde. Ein schon laufender Renderthread wird nicht durch einen Browserabbruch gestoppt. nginx muss einen Client-Abbruch zum Upstream weitergeben, damit wartende Arbeit verworfen werden kann.

TMDB-Quelldateien verwenden `w780` und einen größenabhängigen Cache-Key. Validierung und atomare Veröffentlichung der Cachedatei erfolgen außerhalb des Eventloops. Bereits vorhandene Originaldateien werden nicht gelöscht. Die JPEG-Qualität bleibt konfigurationsabhängig.

## Verifikation

```bash
npm --prefix frontend ci
npm --prefix frontend test
npm --prefix frontend run build
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q
```

Die Frontendtests benötigen Node >=20.19 bzw. >=22.12; sie sind Entwicklungswerkzeuge, nicht Teil des Browserbundles. Unter Windows verwenden die Render-Tests Arial, auf dem Pi weiterhin die vorhandenen DejaVu-Fonts.

Race-Tests prüfen alte Antworten, verzögerte Blob-Auswertung, Posterentfernung, Rückwechsel A → B → A, Fehlerbehandlung und Aufräumen. Der Backendtest hält einen Renderer gezielt an und prüft parallel die Health-Antwort sowie maximal einen gleichzeitigen Render. Cachetests prüfen Varianten, Wiederverwendung und ungültige Pfade.

## Auf dem Pi anwenden

Vorhandene lokale Änderungen prüfen, dann den aktualisierten Branch beziehen:

```bash
cd /opt/viju-ticketbooth
git status --short
git pull --ff-only origin mvp
backend/.venv/bin/python -m pip install -r backend/requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
sudo systemctl restart viju-ticketbooth-api viju-ticketbooth-worker
```

Nach dem Neustart die API-Startphase abwarten und `/api/health` prüfen. Für die Tests kann `requirements-dev.txt` anstelle von `requirements.txt` installiert werden. Kein pauschaler Neuinstallationslauf ist erforderlich.

Browserabnahme: Seite neu laden, Poster langsam und schnell wechseln, Ticketdetails ändern, Poster entfernen, Ticket speichern und erneut öffnen. Die angezeigte Preview muss stets zur aktuellen Auswahl passen; ein Fehler darf nicht als endloser Ladezustand erscheinen. Während eines Renders Health und Print-Jobs prüfen. Kalten/warmen Cache und Pi-Throttling dokumentieren.

Hardware-Throttling, der browserseitige `kwift.CHROME.js`-Fehler und echter Druck im Gegensatz zum Mock-Modus bleiben separate Prüfpunkte. Diese Änderung wurde lokal getestet; sie belegt noch keine Bereitstellung oder visuelle Abnahme auf dem Pi.
