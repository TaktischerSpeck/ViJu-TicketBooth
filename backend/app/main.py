import asyncio
import hmac
import io
import json
import os
import subprocess
import uuid
import anyio
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends, Header, HTTPException, UploadFile, File, Response, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError
from . import config, movies, bluetooth, printing
from .database import connection, init_db, now, setting, set_setting
from .schemas import Ticket, Printer, Wifi, Preset


@asynccontextmanager
async def lifespan(app):
    init_db()
    app.state.render_limiter = anyio.CapacityLimiter(1)
    yield


app = FastAPI(title="ViJu-TicketBooth", lifespan=lifespan)


def admin(x_admin_token: str = Header("")):
    if not config.ADMIN_TOKEN or not hmac.compare_digest(x_admin_token, config.ADMIN_TOKEN):
        raise HTTPException(403, "Admin token required")


def ticket_row(id):
    with connection() as db:
        row = db.execute("SELECT * FROM tickets WHERE id=?", (id,)).fetchone()
    if not row:
        raise HTTPException(404, "Ticket not found")
    return {"id": row["id"], "created_at": row["created_at"], "updated_at": row["updated_at"], **json.loads(row["body"])}


@app.get("/api/health")
def health():
    with connection() as db:
        db.execute("SELECT 1")
    return {"status": "ok", "database": "ok", "tmdb": "configured" if config.TMDB_TOKEN else "unconfigured", "printer_backend": config.PRINTER_BACKEND}


@app.get("/api/movies/search")
async def search(q: str = ""):
    if len(q.strip()) < 2:
        return []
    data = await movies.tmdb("/search/movie", {"query": q[:100], "language": "de-DE", "include_adult": "false"})
    return data.get("results", [])[:12]


@app.get("/api/movies/now-playing")
async def now_playing():
    return (await movies.tmdb("/movie/now_playing", {"region": "DE", "language": "de-DE"})).get("results", [])[:20]


@app.get("/api/movies/random")
async def random_movie():
    return await movies.random_movie()


@app.get("/api/movies/{movie_id}")
async def movie(movie_id: int):
    return await movies.tmdb(f"/movie/{movie_id}", {"language": "de-DE"})


@app.get("/api/movies/{movie_id}/posters")
async def posters(movie_id: int):
    data = await movies.tmdb(f"/movie/{movie_id}/images", {"include_image_language": "en,null,de"})
    return movies.sorted_posters(data.get("posters", []))


@app.post("/api/uploads/images", dependencies=[Depends(admin)])
async def upload(file: UploadFile = File(...)):
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(415, "Only JPEG, PNG and WebP are supported")
    payload = await file.read(16 * 1024 * 1024 + 1)
    if len(payload) > 16 * 1024 * 1024:
        raise HTTPException(413, "Image exceeds 16 MiB")
    try:
        image = Image.open(io.BytesIO(payload))
        if image.format not in ("JPEG", "PNG", "WEBP"):
            raise ValueError("Invalid image contents")
        image = ImageOps.exif_transpose(image)
        image.thumbnail((3000, 4500), Image.Resampling.LANCZOS)
        image = image.convert("RGB")
    except (UnidentifiedImageError, ValueError, OSError, Image.DecompressionBombError) as exc:
        raise HTTPException(415, "Invalid image contents") from exc
    id = str(uuid.uuid4())
    path = config.DATA / "uploads" / f"{id}.jpg"
    image.save(path, format="JPEG", quality=94)
    with connection() as db:
        db.execute("INSERT INTO assets VALUES (?,?,?)", (id, str(path), now()))
    return {"id": id, "url": f"/api/assets/{id}"}


@app.get("/api/assets/{id}")
def asset(id: uuid.UUID):
    with connection() as db:
        row = db.execute("SELECT path FROM assets WHERE id=?", (str(id),)).fetchone()
    if not row or not Path(row["path"]).exists():
        raise HTTPException(404, "Image not found")
    return FileResponse(row["path"], media_type="image/jpeg")


@app.delete("/api/uploads/{id}", dependencies=[Depends(admin)])
def delete_upload(id: uuid.UUID):
    with connection() as db:
        used = db.execute("SELECT 1 FROM tickets WHERE json_extract(body, '$.asset_id')=? LIMIT 1", (str(id),)).fetchone()
        if used:
            raise HTTPException(409, "Image is used by a ticket")
        row = db.execute("SELECT path FROM assets WHERE id=?", (str(id),)).fetchone()
        db.execute("DELETE FROM assets WHERE id=?", (str(id),))
    if row:
        Path(row["path"]).unlink(missing_ok=True)
    return {"deleted": bool(row)}


@app.post("/api/tickets", dependencies=[Depends(admin)])
def create_ticket(ticket: Ticket):
    id = str(uuid.uuid4())
    with connection() as db:
        db.execute("INSERT INTO tickets VALUES (?,?,?,?)", (id, ticket.model_dump_json(), now(), now()))
    return ticket_row(id)


@app.get("/api/tickets")
def list_tickets():
    with connection() as db:
        rows = db.execute("SELECT id, body, created_at, updated_at FROM tickets ORDER BY updated_at DESC LIMIT 200").fetchall()
    return [{"id": r["id"], "created_at": r["created_at"], "updated_at": r["updated_at"], **json.loads(r["body"])} for r in rows]


@app.get("/api/tickets/{id}")
def get_ticket(id: uuid.UUID):
    return ticket_row(str(id))


@app.put("/api/tickets/{id}", dependencies=[Depends(admin)])
def update_ticket(id: uuid.UUID, ticket: Ticket):
    with connection() as db:
        cursor = db.execute("UPDATE tickets SET body=?, updated_at=? WHERE id=?", (ticket.model_dump_json(), now(), str(id)))
    if not cursor.rowcount:
        raise HTTPException(404, "Ticket not found")
    return ticket_row(str(id))


@app.delete("/api/tickets/{id}", dependencies=[Depends(admin)])
def delete_ticket(id: uuid.UUID):
    with connection() as db:
        if db.execute("SELECT 1 FROM jobs WHERE ticket_id=? AND status IN ('queued','rendering','printing')", (str(id),)).fetchone():
            raise HTTPException(409, "Ticket has an active print job")
        db.execute("DELETE FROM jobs WHERE ticket_id=?", (str(id),))
        result = db.execute("DELETE FROM tickets WHERE id=?", (str(id),))
    return {"deleted": bool(result.rowcount)}


@app.post("/api/tickets/{id}/duplicate", dependencies=[Depends(admin)])
def duplicate(id: uuid.UUID):
    original = ticket_row(str(id))
    original.pop("id")
    original.pop("created_at")
    original.pop("updated_at")
    return create_ticket(Ticket.model_validate(original))


@app.post("/api/preview")
async def preview(ticket: Ticket, request: Request):
    from .render import render
    try:
        async with request.app.state.render_limiter:
            if await request.is_disconnected():
                return Response(status_code=204)
            source = await anyio.to_thread.run_sync(printing.source_for, ticket)
            if source is None:
                source = await movies.cache_poster(ticket.poster_path)
            if await request.is_disconnected():
                return Response(status_code=204)
            # Keep the limiter until the thread finishes, including on disconnect.
            png, _ = await anyio.to_thread.run_sync(render, ticket, source)
    except (ValueError, OSError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return Response(png, media_type="image/png", headers={"Cache-Control": "no-store"})


@app.post("/api/tickets/{id}/render", dependencies=[Depends(admin)])
async def render_saved(id: uuid.UUID, request: Request):
    ticket = Ticket.model_validate(ticket_row(str(id)))
    try:
        async with request.app.state.render_limiter:
            await printing.render_ticket(ticket, str(id))
    except (ValueError, OSError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"png": f"/api/renders/{id}?format=png", "jpeg": f"/api/renders/{id}?format=jpeg"}


@app.get("/api/renders/{id}")
def download(id: uuid.UUID, format: str = "png"):
    if format not in ("png", "jpeg"):
        raise HTTPException(422, "Invalid format")
    path = config.DATA / ("renders" if format == "png" else "print") / f"{id}.{ 'png' if format == 'png' else 'jpg'}"
    if not path.exists():
        raise HTTPException(404, "Render not found")
    return FileResponse(path, media_type="image/png" if format == "png" else "image/jpeg", filename=f"ViJu-TicketBooth-{id}.{path.suffix[1:]}")


def queue(ticket_id, key=None):
    id = str(uuid.uuid4())
    if key:
        with connection() as db:
            row = db.execute("SELECT id FROM jobs WHERE idempotency_key=?", (key,)).fetchone()
        if row:
            return job_row(row["id"])
    try:
        with connection() as db:
            db.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?)", (id, ticket_id, "queued", None, now(), now(), key))
    except __import__("sqlite3").IntegrityError:
        with connection() as retry:
            row = retry.execute("SELECT id FROM jobs WHERE idempotency_key=?", (key,)).fetchone()
        return job_row(row["id"])
    return job_row(id)


def job_row(id):
    with connection() as db:
        row = db.execute("SELECT * FROM jobs WHERE id=?", (id,)).fetchone()
    if not row:
        raise HTTPException(404, "Job not found")
    return dict(row)


@app.post("/api/tickets/{id}/print", dependencies=[Depends(admin)])
def print_ticket(id: uuid.UUID, idempotency_key: str | None = Header(None)):
    ticket_row(str(id))
    if idempotency_key and len(idempotency_key) > 100:
        raise HTTPException(422, "Idempotency key too long")
    return queue(str(id), idempotency_key)


@app.get("/api/print-jobs")
def jobs():
    with connection() as db:
        return [dict(r) for r in db.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT 100")]


@app.get("/api/print-jobs/{id}")
def get_job(id: uuid.UUID):
    return job_row(str(id))


@app.post("/api/print-jobs/{id}/retry", dependencies=[Depends(admin)])
def retry(id: uuid.UUID):
    previous = job_row(str(id))
    if previous["status"] not in ("failed", "completed", "cancelled"):
        raise HTTPException(409, "Job is still active")
    return queue(previous["ticket_id"])


@app.delete("/api/print-jobs/{id}", dependencies=[Depends(admin)])
def delete_job(id: uuid.UUID):
    with connection() as db:
        row = db.execute("SELECT status FROM jobs WHERE id=?", (str(id),)).fetchone()
        if row and row["status"] in ("rendering", "printing"):
            raise HTTPException(409, "Transfer in progress")
        if row and row["status"] == "queued":
            db.execute("UPDATE jobs SET status='cancelled', updated_at=? WHERE id=?", (now(), str(id)))
        else:
            db.execute("DELETE FROM jobs WHERE id=?", (str(id),))
    return {"cancelled": bool(row)}


@app.get("/api/printer")
def printer():
    return setting("printer", {"mac": config.DEFAULT_MAC, "channel": config.DEFAULT_CHANNEL})


@app.put("/api/printer", dependencies=[Depends(admin)])
def set_printer(value: Printer):
    set_setting("printer", value.model_dump())
    return value


async def printer_status(probe=False):
    value = Printer.model_validate(printer())
    bt = await bluetooth.status(value.mac)
    available = bluetooth.obex_available()
    setup_ready = bool(value.mac) and bt["adapter_available"] and bt["device_known"] and bt["paired"] and bt["trusted"] and available
    reachable, check_error = None, None
    if probe and config.PRINTER_BACKEND != "mock":
        if not value.mac:
            check_error = "Zuerst die Drucker-MAC speichern."
        elif not bt["adapter_available"]:
            check_error = "Bluetooth-Adapter nicht verfügbar."
        else:
            with connection() as db:
                printing_now = db.execute("SELECT 1 FROM jobs WHERE status='printing' LIMIT 1").fetchone()
            if printing_now:
                check_error = "Während eines Druckauftrags ist keine Verbindungsprüfung möglich."
            else:
                reachable, check_error = await anyio.to_thread.run_sync(bluetooth.probe_rfcomm, value.mac, value.channel)
    return {"configured": bool(value.mac), "backend": config.PRINTER_BACKEND, "bluetooth": bt,
            "obexftp": {"available": available, "channel": value.channel},
            "setup_ready": setup_ready, "reachable": reachable, "check_error": check_error,
            "ready": config.PRINTER_BACKEND == "mock" or (setup_ready and reachable is True)}


@app.get("/api/printer/status")
async def get_printer_status():
    return await printer_status()


@app.post("/api/printer/setup", dependencies=[Depends(admin)])
async def setup_printer():
    value = Printer.model_validate(printer())
    if not value.mac:
        raise HTTPException(422, "Configure printer MAC first")
    return bluetooth_action("pair", value.mac)


@app.post("/api/printer/trust", dependencies=[Depends(admin)])
async def trust_printer():
    value = Printer.model_validate(printer())
    return bluetooth_action("trust", value.mac)


@app.post("/api/printer/check", dependencies=[Depends(admin)])
async def check_printer():
    return await printer_status(probe=True)


@app.post("/api/printer/forget", dependencies=[Depends(admin)])
async def forget_printer(remove_from_bluez: bool = False):
    value = Printer.model_validate(printer())
    if remove_from_bluez and value.mac:
        bluetooth_action("forget", value.mac)
    set_setting("printer", {"mac": "", "channel": 4})
    return {"forgotten": True}


def bluetooth_action(action, mac):
    if not config.NETWORK_HELPER:
        raise HTTPException(503, "Hardware helper not configured")
    result = subprocess.run(["sudo", "-n", "/usr/local/libexec/viju-bluetooth", action, mac],
                            capture_output=True, text=True, timeout=35, check=False)
    if result.returncode:
        raise HTTPException(502, (result.stderr.strip() or "Bluetooth action failed")[-300:])
    return json.loads(result.stdout)


@app.post("/api/printer/test-print", dependencies=[Depends(admin)])
def test_print():
    from PIL import ImageDraw, ImageFont
    image = Image.new("RGB", (config.WIDTH, config.HEIGHT), "#181d2b")
    d = ImageDraw.Draw(image)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
    d.text((40, 100), "ViJu-TicketBooth", font=font, fill="white")
    d.text((40, 160), "Printer Test", fill="white")
    d.text((40, 205), now(), fill="white")
    id = str(uuid.uuid4())
    path = config.DATA / "print" / f"{id}.jpg"
    image.save(path, quality=config.QUALITY)
    # Test transfers run off the event loop, with a durable status record.
    with connection() as db:
        db.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?)", (id, None, "printing", None, now(), now(), None))
    import threading
    def run():
        try:
            printing.print_file(path)
            state, error = "completed", None
        except Exception as exc:
            state, error = "failed", str(exc)[:500]
        with connection() as db:
            db.execute("UPDATE jobs SET status=?, error=?, updated_at=? WHERE id=?", (state, error, now(), id))
    threading.Thread(target=run, daemon=True).start()
    return job_row(id)


@app.get("/api/presets")
def presets():
    with connection() as db:
        return [{"id": r["id"], "name": r["name"], "design": json.loads(r["design"])} for r in db.execute("SELECT * FROM presets ORDER BY name")]


@app.post("/api/presets", dependencies=[Depends(admin)])
def create_preset(preset: Preset):
    id = str(uuid.uuid4())
    with connection() as db:
        db.execute("INSERT INTO presets VALUES (?,?,?)", (id, preset.name, preset.design.model_dump_json()))
    return {"id": id, **preset.model_dump()}


@app.put("/api/presets/{id}", dependencies=[Depends(admin)])
def update_preset(id: uuid.UUID, preset: Preset):
    with connection() as db:
        result = db.execute("UPDATE presets SET name=?, design=? WHERE id=?", (preset.name, preset.design.model_dump_json(), str(id)))
    if not result.rowcount:
        raise HTTPException(404, "Preset not found")
    return {"id": str(id), **preset.model_dump()}


@app.delete("/api/presets/{id}", dependencies=[Depends(admin)])
def delete_preset(id: uuid.UUID):
    with connection() as db:
        result = db.execute("DELETE FROM presets WHERE id=?", (str(id),))
    return {"deleted": bool(result.rowcount)}


@app.get("/api/settings")
def settings():
    return {"print_width": config.WIDTH, "print_height": config.HEIGHT, "jpeg_quality": config.QUALITY, "printer_backend": config.PRINTER_BACKEND}


def helper(*args):
    if not config.NETWORK_HELPER:
        raise HTTPException(503, "Network helper not configured")
    cmd = ["sudo", "-n", config.NETWORK_HELPER, *args]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=12, check=False)
    if result.returncode:
        raise HTTPException(502, "Network helper unavailable")
    return json.loads(result.stdout)


@app.get("/api/network/status")
def network_status():
    return helper("status")


@app.post("/api/network/connect", dependencies=[Depends(admin)])
def network_connect(wifi: Wifi):
    # The helper performs the switch and restores the AP on failure.
    if not config.NETWORK_HELPER:
        raise HTTPException(503, "Network helper not configured")
    process = subprocess.Popen(["sudo", "-n", config.NETWORK_HELPER, "connect"], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True, start_new_session=True)
    process.stdin.write(wifi.model_dump_json())
    process.stdin.close()
    return {"status": "connecting", "message": "Reconnect via the home Wi-Fi; on failure the setup AP returns automatically."}


dist = Path(__file__).parents[2] / "frontend" / "dist"
if dist.exists():
    app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
