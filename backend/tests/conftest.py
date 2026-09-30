import os
from pathlib import Path
import pytest


@pytest.fixture(autouse=True)
def windows_test_fonts(monkeypatch):
    if os.name == "nt":
        from app import render
        fonts = Path(os.environ["WINDIR"]) / "Fonts"
        monkeypatch.setattr(render, "FONT_BOLD", str(fonts / "arialbd.ttf"))
        monkeypatch.setattr(render, "FONT_REGULAR", str(fonts / "arial.ttf"))
        monkeypatch.setattr(render, "FONT_FAMILIES", {
            "serif": ("times.ttf", "timesbd.ttf"),
            "mono": ("cour.ttf", "courbd.ttf"),
        })
