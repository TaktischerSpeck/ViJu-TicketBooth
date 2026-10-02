import io
import math
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageStat
from .config import WIDTH, HEIGHT, QUALITY

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BARLOW_FONTS = (Path(__file__).resolve().parent / "fonts" / "BarlowCondensed-Regular.ttf",
                Path(__file__).resolve().parent / "fonts" / "BarlowCondensed-SemiBold.ttf")
FONT_FAMILIES = {
    "serif": ("DejaVuSerif.ttf", "DejaVuSerif-Bold.ttf"),
    "mono": ("DejaVuSansMono.ttf", "DejaVuSansMono-Bold.ttf"),
}
PRIMARY = ("time", "hall", "row", "seat")
SECONDARY = ("date", "cinema", "note")
LABELS = {"date": "Datum", "time": "Uhrzeit", "cinema": "Kino", "hall": "Saal",
          "row": "Reihe", "seat": "Sitzplatz", "note": "Zusatztext"}


def element_text(ticket, key):
    value = getattr(ticket, key).strip()
    if not value:
        return ""
    if key == "date":
        match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", value)
        if match:
            value = f"{match[3]}.{match[2]}.{match[1]}"
    style = getattr(ticket.design.text_styles, key)
    show_label = style.show_label if style.show_label is not None else key in ("hall", "row", "seat")
    return f"{LABELS[key]} {value}" if show_label and key in LABELS else value


def metadata(ticket):
    return tuple(" • ".join(value for key in keys if (value := element_text(ticket, key)))
                 for keys in (PRIMARY, SECONDARY))


def font_points(design, key):
    override = getattr(design.text_styles, key).font_size
    ratio = 1.9 if key == "title" else (0.8 if key in SECONDARY else 1)
    return override if override is not None else design.base_font_size * ratio


def element_font(design, key):
    style = getattr(design.text_styles, key)
    bold = style.bold if style.bold is not None else key == "title"
    path = FONT_BOLD if bold else FONT_REGULAR
    if design.font_family == "barlow":
        path = str(BARLOW_FONTS[int(bold)])
    elif design.font_family in FONT_FAMILIES:
        path = str(Path(FONT_REGULAR).parent / FONT_FAMILIES[design.font_family][int(bold)])
    # Preserve former default sizes and scale with print resolution.
    size = max(1, round(font_points(design, key) * 2.16 * WIDTH / 600))
    return ImageFont.truetype(path, size)


def cover(image, crop, width=WIDTH, height=HEIGHT):
    image = ImageOps.exif_transpose(image).convert("RGB")
    scale = max(width / image.width, height / image.height) * crop.zoom
    size = (math.ceil(image.width * scale), math.ceil(image.height * scale))
    image = image.resize(size, Image.Resampling.LANCZOS)
    slack_x, slack_y = size[0] - width, size[1] - height
    left = round(slack_x * (crop.x + 1) / 2)
    top = round(slack_y * (crop.y + 1) / 2)
    return image.crop((left, top, left + width, top + height))


def text_layout(ticket, draw):
    design = ticket.design
    stroke = {"off": 0, "light": 2, "strong": 4}[design.shadow]
    margin_x = round(WIDTH * design.safe_area)
    margin_y = round(HEIGHT * design.safe_area)
    max_width = WIDTH - 2 * margin_x
    gap = max(4, round(WIDTH * .012))
    rows = []

    def width(parts):
        return sum(draw.textlength(value, font=font) for value, font in parts) + 2 * stroke

    def append_row(parts):
        if parts:
            height = max(draw.textbbox((0, 0), value, font=font, anchor="lt", stroke_width=stroke)[3]
                         for value, font in parts) + stroke
            rows.append((parts.copy(), height))

    for keys in (("title",), PRIMARY, SECONDARY):
        parts = []
        first = True
        for key in keys:
            value = element_text(ticket, key)
            if not value:
                continue
            if key == "title":
                value = value.upper()
            font = element_font(design, key)
            prefix = "" if first else " • "
            first = False
            # Keep each complete element together if it fits on a fresh line.
            candidate = (prefix + value, font)
            if width(parts + [candidate]) <= max_width:
                parts.append(candidate)
                continue
            if parts:
                append_row(parts)
                parts = []
            if width([(value, font)]) <= max_width:
                parts = [(value, font)]
                continue
            # Wrap long values and unbroken words without dropping content.
            segment = ""
            for word in value.split():
                trial = (segment + " " + word).strip()
                if width([(trial, font)]) <= max_width:
                    segment = trial
                    continue
                if segment:
                    append_row([(segment, font)])
                    segment = ""
                for char in word:
                    if segment and width([(segment + char, font)]) > max_width:
                        append_row([(segment, font)])
                        segment = ""
                    segment += char
            if segment:
                parts = [(segment, font)]
        append_row(parts)

    total = sum(height for _, height in rows) + gap * max(0, len(rows) - 1)
    if total > HEIGHT - 2 * margin_y:
        raise ValueError("Text does not fit in the safe area. Reduce font sizes or shorten the text.")
    top = HEIGHT - margin_y - total
    positioned = []
    y = top
    for parts, height in rows:
        row_width = width(parts)
        x = margin_x if design.position == "bottom-left" else (
            WIDTH - margin_x - row_width if design.position == "bottom-right" else (WIDTH - row_width) / 2)
        for value, font in parts:
            positioned.append((value, font, x + stroke, y + stroke))
            x += draw.textlength(value, font=font)
        y += height + gap
    return positioned, (margin_x, top, WIDTH - margin_x, HEIGHT - margin_y), stroke


def apply_print_inset(canvas, inset):
    # Reserve sacrificial edges for enlargement by edge-to-edge printer firmware.
    if not inset:
        return canvas
    mx, my = round(WIDTH * inset), round(HEIGHT * inset)
    framed = Image.new("RGB", (WIDTH, HEIGHT), "black")
    framed.paste(canvas.resize((WIDTH - 2 * mx, HEIGHT - 2 * my), Image.Resampling.LANCZOS), (mx, my))
    return framed


def render(ticket, source):
    with Image.open(source) as image:
        canvas = cover(image, ticket.crop)
    items, bounds, stroke = text_layout(ticket, ImageDraw.Draw(canvas))
    left, top, right, bottom = bounds
    if items:
        gray = ImageStat.Stat(canvas.crop((left, max(0, top - 15), right, bottom)).convert("L"))
        mean, deviation = gray.mean[0], gray.stddev[0]
        mode = ticket.design.readability
        if mode == "auto":
            mode = "strong" if deviation > 58 else ("minimal" if mean < 92 or mean > 186 else "soft")
        color = ticket.design.text_color
        if color == "auto":
            color = "black" if mode == "minimal" and mean > 165 and deviation < 45 else "white"
        fill = (0, 0, 0) if color == "black" else (255, 255, 255)
        if mode == "soft":
            overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            start = max(0, top - round(HEIGHT * .22))
            for y in range(start, HEIGHT):
                alpha = round(230 * ticket.design.strength * ((y - start) / max(1, HEIGHT - start)) ** 1.4)
                overlay_draw.line((0, y, WIDTH, y), fill=(0, 0, 0, alpha))
            canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
        elif mode == "strong":
            layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
            ImageDraw.Draw(layer).rounded_rectangle(
                (left - 13, top - 14, right + 13, bottom + 12), radius=17,
                fill=(0, 0, 0, round(130 + 95 * ticket.design.strength)))
            canvas = Image.alpha_composite(canvas.convert("RGBA"), layer).convert("RGB")
        draw = ImageDraw.Draw(canvas)
        for value, font, x, y in items:
            draw.text((x, y), value, font=font, anchor="lt", fill=fill, stroke_width=stroke,
                      stroke_fill=(0, 0, 0) if color == "white" else (255, 255, 255))
    canvas = apply_print_inset(canvas, ticket.design.print_inset)
    png, jpg = io.BytesIO(), io.BytesIO()
    # Preview, downloads and the worker share this exact framed image.
    canvas.save(png, format="PNG")
    canvas.save(jpg, format="JPEG", quality=QUALITY, optimize=True)
    return png.getvalue(), jpg.getvalue()
