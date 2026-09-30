import asyncio
import hashlib
import io
import threading
from concurrent.futures import ThreadPoolExecutor
import httpx
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app import config, database, movies, printing
from app.main import app


def test_health_responds_during_render_and_renders_are_serial(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB", tmp_path / "test.sqlite3")
    monkeypatch.setattr(config, "ADMIN_TOKEN", "test")
    monkeypatch.setattr(printing, "source_for", lambda ticket: tmp_path / "poster.png")
    started, release = threading.Event(), threading.Event()
    lock = threading.Lock()
    active = maximum = 0

    def slow_render(ticket, source):
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        started.set()
        try:
            assert release.wait(5)
            return b"png", b"jpg"
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr("app.render.render", slow_render)
    with TestClient(app) as client, ThreadPoolExecutor(3) as pool:
        def preview():
            return client.post('/api/preview', json={"poster_path": "/poster.jpg"}, headers={"X-Admin-Token": "test"})
        first = pool.submit(preview)
        try:
            assert started.wait(2)
            second = pool.submit(preview)
            health = pool.submit(client.get, '/api/health')
            assert health.result(timeout=2).status_code == 200
            assert not first.done()
        finally:
            release.set()
        assert first.result(timeout=3).status_code == 200
        assert second.result(timeout=3).status_code == 200
        assert maximum == 1


def test_poster_cache_uses_size_variant_and_reuses_valid_image(tmp_path, monkeypatch):
    monkeypatch.setattr(movies, "DATA", tmp_path)
    (tmp_path / 'cache').mkdir()
    old = tmp_path / 'cache' / (hashlib.sha256(b'/poster.jpg').hexdigest() + '.img')
    old.write_bytes(b'original-cache')
    content = io.BytesIO()
    Image.new('RGB', (20, 30)).save(content, 'JPEG')
    urls = []

    def handle(request):
        urls.append(str(request.url))
        return httpx.Response(200, content=content.getvalue())

    client = httpx.AsyncClient
    monkeypatch.setattr(movies.httpx, 'AsyncClient', lambda **kwargs: client(transport=httpx.MockTransport(handle), **kwargs))

    async def run():
        target = await movies.cache_poster('/poster.jpg')
        assert target != old
        assert await movies.cache_poster('/poster.jpg') == target
        assert Image.open(target).size == (20, 30)
    asyncio.run(run())
    assert urls == [movies.IMAGE + 'w780/poster.jpg']
    assert old.read_bytes() == b'original-cache'
    assert not list((tmp_path / 'cache').glob('*.tmp'))


def test_missing_poster_path_is_validation_error():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        asyncio.run(movies.cache_poster(None))
    assert error.value.status_code == 422
