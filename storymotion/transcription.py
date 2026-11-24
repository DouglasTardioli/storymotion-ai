"""Transcrição local e agrupamento de palavras em legendas."""
import math
from pathlib import Path

from .models import TranscriptionSettings
from .subtitles import Cue, Word


def transcribe(audio: Path, settings: TranscriptionSettings) -> list[Cue]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as error:
        raise RuntimeError("Instale Faster-Whisper com pip install -r requirements.txt.") from error

    cues = []
    try:
        model = WhisperModel(settings.model, device="cpu", compute_type="int8")
        segments, _ = model.transcribe(str(audio), language=settings.language,
                                       word_timestamps=True, vad_filter=True)
        for segment in segments:
            group = []
            for item in segment.words or ():
                text = item.word.strip()
                if not text or item.start is None or item.end is None:
                    continue
                if not (math.isfinite(item.start) and math.isfinite(item.end)):
                    continue
                start = max(0, item.start)
                end = max(start + .01, item.end)
                if group and (len(group) >= settings.words_per_cue or start - group[-1].end > .5):
                    cues.append(_cue(group))
                    group = []
                group.append(Word(start, end, text))
            if group:
                cues.append(_cue(group))
    except Exception as error:
        raise RuntimeError(f"Falha na transcrição de {audio.name}: {error}") from error
    return sorted(cues, key=lambda cue: cue.start)


def _cue(group):
    return Cue(group[0].start, max(word.end for word in group),
               " ".join(word.text for word in group), tuple(group))
