import io
import pytest
from PIL import Image, ImageDraw, ImageChops
from pydantic import ValidationError
from app import render as renderer
from app.schemas import Ticket, Design


def ticket(**kwargs):
    return Ticket(asset_id="test", title="Cinema", **kwargs)


def test_relative_sizes_and_independent_overrides():
    design = Design()
    assert renderer.font_points(design, "row") == 15
    assert renderer.font_points(design, "title") == 28.5
    design.text_styles.seat.font_size = 12
    design.base_font_size = 15
    assert renderer.font_points(design, "row") == 15
    assert renderer.font_points(design, "title") == 28.5
    assert renderer.font_points(design, "note") == 12
    assert renderer.font_points(design, "seat") == 12
    design.text_styles.seat.font_size = None
    assert renderer.font_points(design, "seat") == 15
    assert Design.model_validate_json(design.model_dump_json()) == design


def test_labels_can_be_disabled_individually_and_empty_values_stay_empty():
    value = ticket(hall="2", row="3", seat="5")
    assert renderer.metadata(value)[0] == "Saal 2 • Reihe 3 • Sitzplatz 5"
    value.design.text_styles.row.show_label = False
    assert renderer.metadata(value)[0] == "Saal 2 • 3 • Sitzplatz 5"
    value.design.text_styles.seat.show_label = False
    assert renderer.metadata(value)[0] == "Saal 2 • 3 • 5"
    value.seat = ""
    assert renderer.metadata(value)[0] == "Saal 2 • 3"


def test_legacy_iso_date_uses_german_print_format():
    value = ticket(date="1999-09-02")
    assert renderer.metadata(value)[1] == "02.09.1999"


@pytest.mark.parametrize("family", ["barlow", "sans", "serif", "mono"])
@pytest.mark.parametrize("position", ["bottom-left", "bottom-center", "bottom-right"])
def test_rendered_text_stays_in_safe_area(tmp_path, family, position):
    source = tmp_path / "poster.png"
    Image.new("RGB", (600, 900), "white").save(source)
    value = ticket(time="20:15", row="3", seat="5", note="gyp ÄÖÜ j",
                   design={"font_family": family, "position": position,
                           "readability": "minimal", "text_color": "black",
                           "shadow": "strong", "print_inset": 0,
                           "text_styles": {"seat": {"font_size": 22}}})
    png, _ = renderer.render(value, source)
    image = Image.open(io.BytesIO(png))
    box = ImageChops.difference(image, Image.new("RGB", image.size, "white")).getbbox()
    mx = round(renderer.WIDTH * value.design.safe_area)
    my = round(renderer.HEIGHT * value.design.safe_area)
    assert box and box[0] >= mx and box[2] <= renderer.WIDTH - mx
    assert box[1] >= my and box[3] <= renderer.HEIGHT - my


def test_long_metadata_wraps_without_losing_characters():
    value = ticket(cinema="A" * 80, note="A long note with spaces")
    draw = ImageDraw.Draw(Image.new("RGB", (600, 900)))
    layout, _, _ = renderer.text_layout(value, draw)
    text = "".join(part[0] for part in layout)
    assert "A" * 80 in text
    assert "A long note with spaces" in text
    value.design.base_font_size = 24
    value.title = "A" * 160
    value.cinema = "A" * 80
    value.note = "A" * 120
    with pytest.raises(ValueError, match="safe area"):
        renderer.text_layout(value, draw)


def test_print_inset_preserves_canvas_size_and_moves_content():
    canvas = Image.new("RGB", (renderer.WIDTH, renderer.HEIGHT), "red")
    framed = renderer.apply_print_inset(canvas, .03)
    assert framed.size == canvas.size
    assert framed.getpixel((0, 0)) == (0, 0, 0)
    assert framed.getpixel((renderer.WIDTH // 2, round(renderer.HEIGHT * .03))) == (255, 0, 0)
    assert renderer.apply_print_inset(canvas, 0) is canvas


def test_old_tickets_receive_defaults_and_invalid_fonts_are_rejected():
    old = ticket(design={"safe_area": .08})
    assert old.design.font_family == "barlow"
    assert old.design.base_font_size == 15
    assert old.design.text_styles.seat.font_size is None
    with pytest.raises(ValidationError):
        Design(font_family="/tmp/font.ttf")
    with pytest.raises(ValidationError):
        Design(text_styles={"seat": {"font_size": 100}})
