import re
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator

MAC = re.compile(r"^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
POSTER = re.compile(r"^/[A-Za-z0-9_-]+\.(?:jpg|png|webp)$")


class Crop(BaseModel):
    zoom: float = Field(1, ge=1, le=4)
    x: float = Field(0, ge=-1, le=1)
    y: float = Field(0, ge=-1, le=1)


class TextStyle(BaseModel):
    font_size: float | None = Field(None, ge=4, le=48)
    bold: bool | None = None
    show_label: bool | None = None


class TextStyles(BaseModel):
    title: TextStyle = Field(default_factory=TextStyle)
    date: TextStyle = Field(default_factory=TextStyle)
    time: TextStyle = Field(default_factory=TextStyle)
    cinema: TextStyle = Field(default_factory=TextStyle)
    hall: TextStyle = Field(default_factory=TextStyle)
    row: TextStyle = Field(default_factory=TextStyle)
    seat: TextStyle = Field(default_factory=TextStyle)
    note: TextStyle = Field(default_factory=TextStyle)


class Design(BaseModel):
    readability: Literal["minimal", "soft", "strong", "auto"] = "soft"
    text_color: Literal["auto", "white", "black"] = "auto"
    shadow: Literal["off", "light", "strong"] = "light"
    position: Literal["bottom-left", "bottom-center", "bottom-right"] = "bottom-left"
    strength: float = Field(0.5, ge=0, le=1)
    safe_area: float = Field(0.065, ge=0.03, le=0.15)
    print_inset: float = Field(0.03, ge=0, le=0.10)
    font_family: Literal["barlow", "sans", "serif", "mono"] = "barlow"
    base_font_size: float = Field(15, ge=4, le=24)
    text_styles: TextStyles = Field(default_factory=TextStyles)


class Ticket(BaseModel):
    title: str = Field("", max_length=160)
    tmdb_id: int | None = Field(None, ge=1)
    poster_path: str | None = None
    asset_id: str | None = None
    date: str = Field("", max_length=32)
    time: str = Field("", max_length=16)
    cinema: str = Field("", max_length=80)
    hall: str = Field("", max_length=30)
    row: str = Field("", max_length=20)
    seat: str = Field("", max_length=20)
    note: str = Field("", max_length=120)
    crop: Crop = Field(default_factory=Crop)
    design: Design = Field(default_factory=Design)

    @field_validator("poster_path")
    @classmethod
    def valid_poster(cls, value):
        if value is not None and not POSTER.fullmatch(value):
            raise ValueError("Invalid TMDB poster path")
        return value

    @model_validator(mode="after")
    def has_poster(self):
        if not (self.poster_path or self.asset_id):
            raise ValueError("Choose or upload a poster")
        return self


class Printer(BaseModel):
    mac: str = ""
    channel: int = Field(4, ge=1, le=30)

    @field_validator("mac")
    @classmethod
    def valid_mac(cls, value):
        if value and not MAC.fullmatch(value):
            raise ValueError("Invalid Bluetooth MAC")
        return value.upper()


class Wifi(BaseModel):
    ssid: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=8, max_length=63)


class Preset(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    design: Design
