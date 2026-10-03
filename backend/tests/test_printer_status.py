import socket

from fastapi.testclient import TestClient

from app import bluetooth, config, database
from app.database import set_setting
from app.main import app


def test_rfcomm_probe_connects_only_to_configured_channel(monkeypatch):
    calls = []

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            calls.append("closed")

        def settimeout(self, timeout):
            calls.append(timeout)

        def connect(self, address):
            calls.append(address)

    monkeypatch.setattr(socket, "AF_BLUETOOTH", 31, raising=False)
    monkeypatch.setattr(socket, "BTPROTO_RFCOMM", 3, raising=False)
    monkeypatch.setattr(socket, "socket", lambda *_: FakeSocket())
    assert bluetooth.probe_rfcomm("C4:30:18:38:BD:E1", 4) == (True, None)
    assert calls == [6, ("C4:30:18:38:BD:E1", 4), "closed"]


def test_connection_check_updates_live_status(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB", tmp_path / "test.sqlite3")
    monkeypatch.setattr(config, "PRINTER_BACKEND", "obexftp")
    async def paired(_):
        return {"adapter_available": True, "device_known": True, "paired": True,
                "trusted": True, "connected": False}
    monkeypatch.setattr(bluetooth, "status", paired)
    monkeypatch.setattr(bluetooth, "obex_available", lambda: True)
    reachable = True
    calls = []
    def probe(mac, channel):
        calls.append((mac, channel))
        return reachable, None if reachable else "Drucker ist aus."
    monkeypatch.setattr(bluetooth, "probe_rfcomm", probe)
    with TestClient(app) as client:
        set_setting("printer", {"mac": "C4:30:18:38:BD:E1", "channel": 4})
        passive = client.get("/api/printer/status").json()
        assert passive["reachable"] is None and passive["ready"] is False
        online = client.post("/api/printer/check").json()
        assert online["reachable"] is True and online["ready"] is True
        reachable = False
        offline = client.post("/api/printer/check").json()
        assert offline["reachable"] is False and offline["ready"] is False
        assert offline["check_error"] == "Drucker ist aus."
    assert calls == [("C4:30:18:38:BD:E1", 4)] * 2
