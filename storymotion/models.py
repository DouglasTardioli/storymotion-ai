from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


Easing = Literal["linear", "smoothstep", "smootherstep", "sine_in_out"]
OVERLAP_TRANSITIONS = frozenset({"crossfade", "dip_to_black", "slide_left"})


class TranscriptionSettings(Settings):
    model: str = Field("base", min_length=1)
    language: str | None = Field(None, min_length=2)
    words_per_cue: int = Field(5, ge=1, le=12)


class SubtitleSettings(Settings):
    file: Path | None = None
    transcription: TranscriptionSettings | None = None
    style: Literal["clean", "dynamic", "karaoke"] = "dynamic"
    font_size: int = Field(60, ge=12, le=180)
    font_file: Path | None = None
    color: str = "#FFFFFF"
    highlight_color: str = "#FFE44D"
    outline_color: str = "#000000"
    outline_width: int = Field(4, ge=0, le=15)
    margin_bottom: int = Field(320, ge=0, le=1600)

    @model_validator(mode="after")
    def validate_source(self):
        if (self.file is None) == (self.transcription is None):
            raise ValueError("Informe subtitles.file ou subtitles.transcription.")
        if self.style == "karaoke" and self.transcription is None:
            raise ValueError("O estilo karaoke requer subtitles.transcription.")
        return self


class Layer(Settings):
    asset: Path
    animation: Literal["none", "fade_in", "slide_in", "pop_in", "float_in", "rise_in", "spin_in", "pulse"] = "none"
    start: float = Field(0, ge=0, le=86400)
    duration: float = Field(.5, gt=0, le=86400)
    x: float = Field(.5, ge=0, le=1)
    y: float = Field(.5, ge=0, le=1)
    width: float = Field(.35, gt=0, le=1)
    opacity: float = Field(1, ge=0, le=1)


class Scene(Settings):
    id: str = Field(min_length=1)
    background: Path
    duration: float = Field(gt=0, le=86400)
    camera_effect: Literal["none", "zoom_in", "zoom_out", "pan_horizontal", "pan_vertical", "ken_burns", "cinematic_zoom", "drift"] = "none"
    camera_easing: Easing = "smoothstep"
    intensity: float = Field(.25, ge=0, le=1)
    layers: list[Layer] = Field(default_factory=list)
    transition: Literal["cut", "crossfade", "fade_to_black", "dip_to_black", "slide_left"] = "cut"
    transition_easing: Easing = "smoothstep"
    transition_duration: float = Field(.4, gt=0, le=86400)


class Project(Settings):
    project_name: str = Field(min_length=1)
    width: int = Field(1080, ge=2, le=3840, multiple_of=2)
    height: int = Field(1920, ge=2, le=3840, multiple_of=2)
    fps: Literal[24, 30, 60] = 30
    audio: Path | None = None
    subtitles: SubtitleSettings | None = None
    scenes: list[Scene] = Field(min_length=1)

    def frames(self, seconds: float) -> int:
        return round(seconds * self.fps)

    def transition_frames(self, index: int) -> int:
        scene = self.scenes[index]
        if index + 1 == len(self.scenes) or scene.transition == "cut":
            return 0
        return self.frames(scene.transition_duration)

    def overlap_frames(self, index: int) -> int:
        if self.scenes[index].transition in OVERLAP_TRANSITIONS:
            return self.transition_frames(index)
        return 0

    def total_frames(self) -> int:
        return sum(self.frames(scene.duration) - self.overlap_frames(index)
                   for index, scene in enumerate(self.scenes))

    @model_validator(mode="after")
    def validate_timeline(self):
        if len({scene.id for scene in self.scenes}) != len(self.scenes):
            raise ValueError("Os identificadores das cenas devem ser únicos.")
        if self.subtitles and self.subtitles.transcription and self.audio is None:
            raise ValueError("A transcrição automática requer audio no projeto.")
        incoming = 0
        for index, scene in enumerate(self.scenes):
            length = self.frames(scene.duration)
            outgoing = self.transition_frames(index)
            has_transition = index + 1 < len(self.scenes) and scene.transition != "cut"
            if has_transition and outgoing < 2:
                raise ValueError(f"{scene.id}: a transição precisa de pelo menos dois quadros.")
            if has_transition and scene.transition == "dip_to_black" and outgoing < 3:
                raise ValueError(f"{scene.id}: dip_to_black precisa de pelo menos três quadros.")
            if length <= incoming + outgoing:
                raise ValueError(f"{scene.id}: duração insuficiente para a montagem.")
            if any(layer.start > (length - 1) / self.fps for layer in scene.layers):
                raise ValueError(f"{scene.id}: camada começa fora da cena.")
            incoming = self.overlap_frames(index)
        return self
