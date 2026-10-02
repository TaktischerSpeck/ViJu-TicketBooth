import subprocess

import pytest

from app import config, printing


def obex_result(code, send_line):
    return subprocess.CompletedProcess(
        args=["obexftp"], returncode=code, stdout="",
        stderr=f'Suppressing FBS.\nConnecting...\bdone\nSending "/tmp/ticket.jpg"...\b|\b/\b-{send_line}\nDisconnecting...\bdone\n',
    )


def test_exit_255_with_confirmed_send_counts_as_success(monkeypatch):
    monkeypatch.setattr(config, "PRINTER_BACKEND", "obexftp")
    monkeypatch.setattr(printing, "setting", lambda *_: {"mac": "C4:30:18:38:BD:E1", "channel": 4})
    monkeypatch.setattr(printing.subprocess, "run", lambda *_args, **_kwargs: obex_result(255, "done"))
    printing.print_file("/tmp/ticket.jpg")


def test_exit_255_without_completed_send_is_still_failure(monkeypatch):
    monkeypatch.setattr(config, "PRINTER_BACKEND", "obexftp")
    monkeypatch.setattr(printing, "setting", lambda *_: {"mac": "C4:30:18:38:BD:E1", "channel": 4})
    monkeypatch.setattr(printing.subprocess, "run", lambda *_args, **_kwargs: obex_result(255, "failed: rejected"))
    with pytest.raises(RuntimeError, match="failed: rejected") as error:
        printing.print_file("/tmp/ticket.jpg")
    assert "\b" not in str(error.value)


def test_exit_255_with_only_disconnect_done_is_not_success():
    result = subprocess.CompletedProcess(["obexftp"], 255, "", "Connecting...done\nDisconnecting...done\n")
    success, error = printing.transfer_result(result)
    assert not success
    assert "Sendeabschluss nicht bestätigt" in error


def test_failure_reported_on_stdout_overrides_success_marker():
    result = obex_result(255, "done")
    result.stdout = "The operation failed with return code 255\n"
    success, error = printing.transfer_result(result)
    assert not success
    assert "return code 255" in error
