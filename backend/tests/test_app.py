import io
import asyncio
import importlib.machinery
import importlib.util
import json
from PIL import Image
from fastapi.testclient import TestClient

from app import config, database
from app.main import app
from app.movies import sorted_posters
from app.printing import command, process_one
from app.render import metadata, render
from app.schemas import Ticket, Crop, Printer


def example(asset_id):
    return {"title": "A Very Long Cinematic Title About Space", "asset_id": asset_id,
            "time": "20:15", "hall": "4", "row": "G", "seat": "12"}


def test_poster_priority_and_validation():
    posters = [{"file_path": "/de.jpg", "iso_639_1": "de", "height": 1000, "width": 667},
               {"file_path": "/neutral.jpg", "iso_639_1": None, "height": 1000, "width": 667},
               {"file_path": "/en.jpg", "iso_639_1": "en", "height": 500, "width": 333}]
    assert [p["file_path"] for p in sorted_posters(posters)] == ["/en.jpg", "/neutral.jpg", "/de.jpg"]
    assert Printer(mac="c4:30:18:38:bd:e1", channel=4).mac == "C4:30:18:38:BD:E1"
    assert command("C4:30:18:38:BD:E1", 4, "/tmp/test.jpg")[-4:] == ["--channel", "4", "-p", "/tmp/test.jpg"]


def test_render_crop_metadata(tmp_path):
    poster = tmp_path / "poster.png"
    Image.new("RGB", (800, 400), "white").save(poster)
    ticket = Ticket.model_validate({**example("sample"), "crop": {"zoom": 1.5, "x": .25, "y": -.25}, "design": {"readability": "strong", "text_color": "white"}})
    assert metadata(ticket)[0] == "20:15 • Saal 4 • Reihe G • Sitzplatz 12"
    png, jpg = render(ticket, poster)
    assert Image.open(io.BytesIO(png)).size == (config.WIDTH, config.HEIGHT)
    assert Image.open(io.BytesIO(jpg)).format == "JPEG"
    assert Image.open(io.BytesIO(png)).getpixel((0, 0)) == (0, 0, 0)


def test_upload_render_print_and_idempotency(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(database, "DB", tmp_path / "test.sqlite3")
    monkeypatch.setattr(config, "PRINTER_BACKEND", "mock")
    for name in ("uploads", "cache", "renders", "print"):
        (tmp_path / name).mkdir()
    image = io.BytesIO()
    Image.new("RGB", (800, 1200), "#394555").save(image, "PNG")
    with TestClient(app) as client:
        unauthenticated = client.post("/api/tickets", json={**example("missing")})
        assert unauthenticated.status_code == 200
        assert client.delete("/api/tickets/" + unauthenticated.json()["id"]).status_code == 200
        uploaded = client.post("/api/uploads/images", files={"file": ("poster.png", image.getvalue(), "image/png")})
        assert uploaded.status_code == 200
        asset_id = uploaded.json()["id"]
        bad = client.post("/api/uploads/images", files={"file": ("bad.png", b"not-an-image", "image/png")})
        assert bad.status_code == 415
        body = example(asset_id)
        preview = client.post("/api/preview", json=body)
        assert preview.status_code == 200
        ticket = client.post("/api/tickets", json=body)
        assert ticket.status_code == 200
        ticket_id = ticket.json()["id"]
        first = client.post(f"/api/tickets/{ticket_id}/print", headers={"Idempotency-Key": "one"})
        second = client.post(f"/api/tickets/{ticket_id}/print", headers={"Idempotency-Key": "one"})
        assert first.json()["id"] == second.json()["id"]
        assert asyncio.run(process_one())
        job = client.get("/api/print-jobs/" + first.json()["id"]).json()
        assert job["status"] == "completed"
        assert (tmp_path / "renders" / (job["id"] + ".png")).exists()
        assert (tmp_path / "print" / (job["id"] + ".jpg")).exists()
        assert client.post(f"/api/tickets/{ticket_id}/duplicate").status_code == 200


def test_wifi_switch_failure_restores_ap(tmp_path, monkeypatch):
    loader = importlib.machinery.SourceFileLoader("viju_network", "deploy/network/viju-network")
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    monkeypatch.setattr(module, "NM_DIR", tmp_path)
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(module.sys, "stdin", io.StringIO(json.dumps({"ssid": "home", "password": "wrong-passphrase"})))
    commands = []
    def fake_nm(*args, **kwargs):
        commands.append(args)
        if "up" in args:
            raise RuntimeError("Authentication failed")
    monkeypatch.setattr(module, "nm", fake_nm)
    monkeypatch.setattr(module, "ap", lambda: commands.append(("restore-ap",)))
    import pytest
    with pytest.raises(RuntimeError):
        module.connect()
    assert ("restore-ap",) in commands
    assert not list(tmp_path.glob("*.nmconnection"))
