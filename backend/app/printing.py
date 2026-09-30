import json
import logging
import subprocess
import time
import anyio
from pathlib import Path
from . import config
from .database import connection, now, setting
from .render import render
from .movies import cache_poster

log = logging.getLogger(__name__)


def command(mac, channel, path):
    return ["obexftp", "--nopath", "--noconn", "--uuid", "none", "--bluetooth", mac, "--channel", str(channel), "-p", str(path)]


def source_for(ticket):
    if ticket.asset_id:
        with connection() as db:
            row = db.execute("SELECT path FROM assets WHERE id=?", (ticket.asset_id,)).fetchone()
        if not row:
            raise FileNotFoundError("Uploaded poster not found")
        return Path(row["path"])
    return None


def print_file(path):
    printer = setting("printer", {"mac": config.DEFAULT_MAC, "channel": config.DEFAULT_CHANNEL})
    if config.PRINTER_BACKEND == "mock":
        return
    from .schemas import Printer
    printer = Printer.model_validate(printer)
    if not printer.mac:
        raise RuntimeError("Printer MAC not configured")
    result = subprocess.run(command(printer.mac, printer.channel, path), shell=False, capture_output=True, text=True, timeout=config.TIMEOUT, check=False)
    if result.returncode:
        raise RuntimeError(f"OBEX transfer failed (exit {result.returncode}): {result.stderr[-300:]}")


async def render_ticket(ticket, job_id):
    source = await anyio.to_thread.run_sync(source_for, ticket)
    if source is None:
        source = await cache_poster(ticket.poster_path)
    png, jpg = await anyio.to_thread.run_sync(render, ticket, source)
    await anyio.to_thread.run_sync((config.DATA / "renders" / f"{job_id}.png").write_bytes, png)
    await anyio.to_thread.run_sync((config.DATA / "print" / f"{job_id}.jpg").write_bytes, jpg)
    return jpg


async def process_one():
    from .schemas import Ticket
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        job = db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
        if not job:
            return False
        db.execute("UPDATE jobs SET status='rendering', updated_at=? WHERE id=?", (now(), job["id"]))
    try:
        with connection() as db:
            row = db.execute("SELECT body FROM tickets WHERE id=?", (job["ticket_id"],)).fetchone()
        if not row:
            raise RuntimeError("Ticket no longer exists")
        await render_ticket(Ticket.model_validate_json(row["body"]), job["id"])
        with connection() as db:
            db.execute("UPDATE jobs SET status='printing', updated_at=? WHERE id=?", (now(), job["id"]))
        print_file(config.DATA / "print" / f"{job['id']}.jpg")
        with connection() as db:
            db.execute("UPDATE jobs SET status='completed', updated_at=? WHERE id=?", (now(), job["id"]))
    except Exception as exc:
        log.exception("Print job failed: %s", job["id"])
        with connection() as db:
            db.execute("UPDATE jobs SET status='failed', error=?, updated_at=? WHERE id=?", (str(exc)[:500], now(), job["id"]))
    return True


async def worker():
    from .database import init_db, fail_interrupted_jobs
    init_db()
    fail_interrupted_jobs()
    while True:
        if not await process_one():
            await __import__("asyncio").sleep(2)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(worker())
