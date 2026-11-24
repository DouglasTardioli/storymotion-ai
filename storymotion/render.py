import logging
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from .composition import Composition
from .models import Project
from .motion import transition_frame
from .subtitles import SubtitlePainter, format_srt, read_srt
from .transcription import transcribe

LOG = logging.getLogger(__name__)


def iter_frames(project, composition, subtitles=None):
    black = Image.new("RGB", composition.size)
    scenes = project.scenes
    current = composition.prepare(scenes[0])
    consumed = 0
    global_frame = 0
    for index, scene in enumerate(scenes):
        LOG.info("Cena %d/%d — %s", index + 1, len(scenes), scene.id)
        count = project.frames(scene.duration)
        following = scenes[index + 1] if index + 1 < len(scenes) else None
        transition = project.transition_frames(index)
        overlap = project.overlap_frames(index)
        upcoming = composition.prepare(following) if overlap else None
        for position in range(consumed, count):
            frame = composition.frame(scene, current, position)
            if transition and position >= count - transition:
                offset = position - (count - transition)
                target = composition.frame(following, upcoming, offset) if upcoming else black
                frame = transition_frame(frame, target, black, scene.transition, offset,
                                         transition, scene.transition_easing)
            if subtitles:
                frame = subtitles.paint(frame, global_frame / project.fps)
            yield frame
            global_frame += 1
        if following:
            current = upcoming if upcoming else composition.prepare(following)
        consumed = overlap


def render(project_file: Path, output: Path, *, ffmpeg=None, crf=20, export_srt: Path | None = None):
    output = output.resolve()
    if output.suffix.lower() != ".mp4":
        raise ValueError("O nome de saída deve terminar em .mp4.")
    if not 0 <= crf <= 51:
        raise ValueError("Use CRF entre 0 e 51.")
    encoder = ffmpeg or shutil.which("ffmpeg")
    if not encoder:
        raise ValueError("Adicione FFmpeg ao PATH ou forneça --ffmpeg.")
    project_file = project_file.resolve()
    project = Project.model_validate_json(project_file.read_text(encoding="utf-8-sig"))
    composition = Composition(project, project_file.parent)
    composition.validate_assets()
    audio_path = project_file.parent / project.audio if project.audio else None
    if audio_path and (not audio_path.is_file() or audio_path.suffix.lower() not in {".mp3", ".wav", ".m4a"}):
        raise ValueError(f"Arquivo de narração inválido ou ausente: {audio_path}")
    settings = project.subtitles
    if export_srt is not None:
        if not settings or not settings.transcription:
            raise ValueError("--export-srt requer subtitles.transcription.")
        export_srt = export_srt.resolve()
        if export_srt.suffix.lower() != ".srt":
            raise ValueError("A saída das legendas deve terminar em .srt.")
        if export_srt.exists():
            raise FileExistsError(f"O arquivo de legendas já existe: {export_srt}")
    subtitles = None
    duration = project.total_frames() / project.fps
    if settings:
        if settings.font_file and not settings.font_file.is_absolute():
            settings = settings.model_copy(update={"font_file": project_file.parent / settings.font_file})
        if settings.transcription:
            LOG.info("Transcrevendo narração com Faster-Whisper...")
            cues = transcribe(audio_path, settings.transcription)
        else:
            cues = read_srt(project_file.parent / settings.file)
        subtitles = SubtitlePainter(cues, project.width, project.height, settings)
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="storymotion-", dir=output.parent) as temporary:
        encoded = Path(temporary) / "video.mp4"
        log = Path(temporary) / "ffmpeg.log"
        command = [
            encoder, "-hide_banner", "-loglevel", "error", "-f", "rawvideo",
            "-pixel_format", "rgb24", "-video_size", f"{project.width}x{project.height}",
            "-framerate", str(project.fps), "-i", "pipe:0", "-an",
            "-c:v", "libx264", "-crf", str(crf), "-preset", "fast",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(encoded),
        ]
        try:
            with log.open("wb") as errors, subprocess.Popen(command, stdin=subprocess.PIPE, stderr=errors) as process:
                try:
                    for frame in iter_frames(project, composition, subtitles):
                        process.stdin.write(frame.tobytes())
                    process.stdin.close()
                    if process.wait():
                        raise subprocess.CalledProcessError(process.returncode, command)
                except BaseException:
                    if process.poll() is None:
                        process.kill()
                    raise
        except (BrokenPipeError, subprocess.CalledProcessError) as error:
            message = log.read_text(encoding="utf-8", errors="replace").strip()
            raise RuntimeError(message or "Falha ao codificar vídeo com FFmpeg.") from error
        if audio_path:
            combined = Path(temporary) / "with_audio.mp4"
            # apad extends short narration with silence; -t prevents overflow
            cmd = [encoder, "-hide_banner", "-loglevel", "error", "-y",
                   "-i", str(encoded), "-i", str(audio_path), "-map", "0:v:0", "-map", "1:a:0",
                   "-c:v", "copy", "-c:a", "aac", "-af", "apad",
                   "-t", f"{duration:.6f}", "-movflags", "+faststart", str(combined)]
            process = subprocess.run(cmd, capture_output=True, text=True)
            if process.returncode:
                raise RuntimeError(f"Erro ao incluir narração: {process.stderr.strip()}")
            encoded = combined
        os.replace(encoded, output)
    if export_srt is not None:
        export_srt.parent.mkdir(parents=True, exist_ok=True)
        with export_srt.open("x", encoding="utf-8") as sidecar:
            sidecar.write(format_srt(cues, duration))
