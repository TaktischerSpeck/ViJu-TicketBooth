import hashlib
import random
import asyncio
import os
import tempfile
import httpx
from fastapi import HTTPException
from .config import TMDB_TOKEN, DATA
from .schemas import POSTER

BASE = "https://api.themoviedb.org/3"
IMAGE = "https://image.tmdb.org/t/p/"
POSTER_SIZE = "w780"


def store_poster(target, content):
    from PIL import Image
    import io
    with Image.open(io.BytesIO(content)) as image:
        image.verify()
    # Atomic publication also protects readers in the separate print worker.
    fd, temporary = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(content)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


async def tmdb(path, params=None):
    if not TMDB_TOKEN:
        raise HTTPException(503, "TMDB token not configured; manual tickets are available")
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.get(BASE + path, params=params or {}, headers={"Authorization": f"Bearer {TMDB_TOKEN}"})
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(502, "TMDB is unavailable") from exc


def sorted_posters(data):
    priority = {"en": 0, None: 1, "de": 2}
    return sorted(
        [p for p in data if POSTER.fullmatch(p.get("file_path", ""))],
        key=lambda p: (priority.get(p.get("iso_639_1"), 3), -(p.get("height") or 0), abs((p.get("width") or 2) / max(p.get("height") or 3, 1) - 2 / 3), -(p.get("vote_count") or 0)),
    )


async def cache_poster(path):
    if not isinstance(path, str) or not POSTER.fullmatch(path):
        raise HTTPException(422, "Invalid poster path")
    target = DATA / "cache" / (hashlib.sha256((POSTER_SIZE + path).encode()).hexdigest() + ".img")
    if not target.exists():
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
                response = await client.get(IMAGE + POSTER_SIZE + path)
                response.raise_for_status()
                if len(response.content) > 16 * 1024 * 1024:
                    raise HTTPException(413, "Poster exceeds size limit")
                await asyncio.to_thread(store_poster, target, response.content)
        except (httpx.HTTPError, OSError, ValueError) as exc:
            raise HTTPException(502, "Poster unavailable") from exc
    return target


async def random_movie():
    data = await tmdb("/movie/now_playing", {"region": "DE", "language": "de-DE"})
    candidates = [movie for movie in data.get("results", []) if movie.get("poster_path")]
    if not candidates:
        raise HTTPException(404, "No movies with posters")
    return random.choice(candidates)
