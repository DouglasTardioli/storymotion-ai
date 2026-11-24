"""Legendas SRT e por palavra desenhadas nos quadros do vídeo."""
import re
from dataclasses import dataclass
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from .motion import ease

_TIMESTAMP = re.compile(r"^(\d{2,}):(\d{2}):(\d{2})[,.](\d{3})$")

@dataclass(frozen=True)
class Word:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class Cue:
    start: float
    end: float
    text: str
    words: tuple[Word, ...] = ()


def _seconds(value: str) -> float:
    match = _TIMESTAMP.match(value.strip())
    if not match:
        raise ValueError(f"Tempo SRT inválido: {value!r}")
    h, m, s, ms = map(int, match.groups())
    if m >= 60 or s >= 60:
        raise ValueError(f"Tempo SRT inválido: {value!r}")
    return h * 3600 + m * 60 + s + ms / 1000


def read_srt(path: Path) -> list[Cue]:
    try:
        contents = path.read_text(encoding="utf-8-sig")
    except OSError as error:
        raise ValueError(f"Não foi possível ler legendas {path}: {error}") from error
    cues = []
    for block in re.split(r"\n\s*\n", contents.replace("\r\n", "\n").strip()):
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not lines:
            continue
        time_idx = next((i for i, l in enumerate(lines) if "-->" in l), -1)
        if time_idx == -1:
            raise ValueError(f"Bloco SRT sem intervalo de tempo: {block[:60]}")
        bounds = lines[time_idx].split("-->")
        if len(bounds) != 2:
            raise ValueError("Intervalo SRT inválido")
        start, end = (_seconds(v) for v in bounds)
        if end <= start:
            raise ValueError("Legenda SRT deve terminar após começar")
        text = " ".join(lines[time_idx + 1:])
        if text:
            cues.append(Cue(start, end, text))
    return sorted(cues, key=lambda cue: cue.start)


def _timestamp(seconds):
    whole, millis = divmod(round(seconds * 1000), 1000)
    minutes, seconds = divmod(whole, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def format_srt(cues, duration):
    blocks = []
    for cue in cues:
        end = min(cue.end, duration)
        if round(end * 1000) > round(cue.start * 1000):
            blocks.append(f"{len(blocks) + 1}\n{_timestamp(cue.start)} --> {_timestamp(end)}\n{cue.text}\n")
    return "\n".join(blocks)


class SubtitlePainter:
    def __init__(self, cues, width, height, settings):
        self.cues = cues
        self.settings = settings
        self.width = width
        self.height = height
        path = settings.font_file
        candidates = [path] if path else [
            Path("C:/Windows/Fonts/arialbd.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ]
        self.font = None
        for candidate in candidates:
            if candidate and Path(candidate).is_file():
                self.font = ImageFont.truetype(str(candidate), settings.font_size)
                break
        if self.font is None:
            if path:
                raise ValueError(f"Fonte das legendas não encontrada: {path}")
            self.font = ImageFont.load_default(size=settings.font_size)

    def paint(self, frame: Image.Image, timestamp: float) -> Image.Image:
        cue = next((c for c in self.cues if c.start <= timestamp < c.end), None)
        if cue is None:
            return frame
        draw = ImageDraw.Draw(frame)
        if self.settings.style == "karaoke":
            self._paint_words(draw, cue, timestamp)
            return frame
        settings = self.settings
        # wrap using pixel width rather than characters
        words = cue.text.split()
        lines = []
        current = ""
        limit = int(self.width * .84)
        for word in words:
            trial = f"{current} {word}".strip()
            if current and draw.textbbox((0, 0), trial, font=self.font, stroke_width=settings.outline_width)[2] > limit:
                lines.append(current)
                current = word
            else:
                current = trial
        if current:
            lines.append(current)
        spacing = int(settings.font_size * 1.24)
        total = len(lines) * spacing
        first_y = self.height - settings.margin_bottom - total
        for idx, line in enumerate(lines):
            # TikTok-inspired phrase reveal: subtle entry movement.
            elapsed = timestamp - cue.start
            rise = round(10 * max(0.0, 1 - elapsed / .18)) if settings.style == "dynamic" else 0
            y = first_y + idx * spacing + rise
            draw.text((self.width / 2, y), line, anchor="mt", font=self.font,
                      fill=settings.color, stroke_width=settings.outline_width,
                      stroke_fill=settings.outline_color)
        return frame


    def _paint_words(self, draw, cue, timestamp):
        settings = self.settings
        space = draw.textlength(" ", font=self.font)
        lines = [[]]
        widths = [0]
        for word in cue.words:
            width = draw.textlength(word.text, font=self.font)
            line = lines[-1]
            gap = space if line else 0
            if line and widths[-1] + gap + width + 2 * settings.outline_width > self.width * .84:
                lines.append([])
                widths.append(0)
                gap = 0
            offset = widths[-1] + gap
            lines[-1].append((word, offset))
            widths[-1] = offset + width

        active = next((word for word in reversed(cue.words)
                       if word.start <= timestamp < word.end), None)
        spacing = int(settings.font_size * 1.24)
        for index, (line, width) in enumerate(zip(lines, widths)):
            x = (self.width - width) / 2
            y = self.height - settings.margin_bottom - (len(lines) - index) * spacing
            for word, offset in line:
                selected = word is active
                rise = 0
                if selected:
                    phase = ease((timestamp - word.start) / min(.12, word.end - word.start))
                    rise = round(settings.font_size * .12 * (1 - phase))
                draw.text((x + offset, y - rise), word.text, anchor="la", font=self.font,
                          fill=settings.highlight_color if selected else settings.color,
                          stroke_width=settings.outline_width, stroke_fill=settings.outline_color)
