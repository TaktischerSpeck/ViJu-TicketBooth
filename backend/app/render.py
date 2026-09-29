import io
import math
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageStat
from .config import WIDTH, HEIGHT, QUALITY

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def metadata(ticket):
    seat = "".join([ticket.row, ticket.seat])
    primary = [ticket.time, f"Saal {ticket.hall}" if ticket.hall else "", seat, ticket.format]
    secondary = [ticket.date, ticket.cinema, ticket.note]
    return " • ".join(x for x in primary if x), " • ".join(x for x in secondary if x)


def cover(image, crop, width=WIDTH, height=HEIGHT):
    image = ImageOps.exif_transpose(image).convert("RGB")
    scale = max(width / image.width, height / image.height) * crop.zoom
    size = (math.ceil(image.width * scale), math.ceil(image.height * scale))
    image = image.resize(size, Image.Resampling.LANCZOS)
    slack_x, slack_y = size[0] - width, size[1] - height
    left = round(slack_x * (crop.x + 1) / 2)
    top = round(slack_y * (crop.y + 1) / 2)
    return image.crop((left, top, left + width, top + height))


def _wrap(draw, value, font, max_width):
    words = value.upper().split()
    lines = []
    for word in words:
        candidate = (lines[-1] + " " + word) if lines else word
        if lines and draw.textlength(candidate, font=font) > max_width:
            lines.append(word)
        elif lines:
            lines[-1] = candidate
        else:
            lines.append(word)
    return lines


def _title(draw, text, max_width):
    for size in range(round(WIDTH * .069), 15, -2):
        font = ImageFont.truetype(FONT_BOLD, size)
        lines = _wrap(draw, text, font, max_width)
        if len(lines) <= 2 and all(draw.textlength(line, font=font) <= max_width for line in lines):
            return lines, font
    raise ValueError("Title cannot fit in two lines")


def render(ticket, source):
    canvas = cover(Image.open(source), ticket.crop)
    draw = ImageDraw.Draw(canvas)
    margin = round(WIDTH * ticket.design.safe_area)
    max_width = WIDTH - 2 * margin
    lines, title_font = _title(draw, ticket.title, max_width) if ticket.title else ([], ImageFont.truetype(FONT_BOLD, 20))
    meta_font = ImageFont.truetype(FONT_REGULAR, round(WIDTH * .036))
    small_font = ImageFont.truetype(FONT_REGULAR, round(WIDTH * .029))
    first, second = metadata(ticket)
    items = [(line, title_font) for line in lines]
    if first:
        items.append((first, meta_font))
    if second:
        items.append((second, small_font))
    # Fit optional metadata without clipping at the print edge.
    fitted = []
    for value, font in items:
        while draw.textlength(value, font=font) > max_width and font.size > 13:
            font = ImageFont.truetype(FONT_REGULAR if font != title_font else FONT_BOLD, font.size - 1)
        if draw.textlength(value, font=font) > max_width:
            value = value[:max(1, round(len(value) * max_width / draw.textlength(value, font=font)) - 1)] + "…"
        fitted.append((value, font))
    heights = [round(font.size * 1.27) for _, font in fitted]
    total = sum(heights) + (8 if lines and (first or second) else 0)
    top = HEIGHT - margin - total
    area = canvas.crop((margin, max(0, top - 15), WIDTH - margin, HEIGHT - margin))
    gray = ImageStat.Stat(area.convert("L"))
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
        pixels = overlay.load()
        start = max(0, top - round(HEIGHT * .22))
        for y in range(start, HEIGHT):
            a = round(230 * ticket.design.strength * ((y - start) / max(1, HEIGHT - start)) ** 1.4)
            for x in range(WIDTH):
                pixels[x, y] = (0, 0, 0, a)
        canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
    elif mode == "strong":
        layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        box = ImageDraw.Draw(layer)
        box.rounded_rectangle((margin - 13, top - 14, WIDTH - margin + 13, HEIGHT - margin + 12), radius=17, fill=(0, 0, 0, round(130 + 95 * ticket.design.strength)))
        canvas = Image.alpha_composite(canvas.convert("RGBA"), layer).convert("RGB")
    draw = ImageDraw.Draw(canvas)
    y = top
    for i, (value, font) in enumerate(fitted):
        if i == len(lines) and i:
            y += 8
        text_width = draw.textlength(value, font=font)
        pos = ticket.design.position
        x = margin if pos == "bottom-left" else (WIDTH - margin - text_width if pos == "bottom-right" else (WIDTH - text_width) / 2)
        shadow = {"off": 0, "light": 2, "strong": 4}[ticket.design.shadow]
        draw.text((x, y), value, font=font, fill=fill, stroke_width=shadow, stroke_fill=(0, 0, 0) if color == "white" else (255, 255, 255))
        y += heights[i]
    png = io.BytesIO()
    jpg = io.BytesIO()
    canvas.save(png, format="PNG")
    canvas.save(jpg, format="JPEG", quality=QUALITY, optimize=True)
    return png.getvalue(), jpg.getvalue()
