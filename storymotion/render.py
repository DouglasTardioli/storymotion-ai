import logging
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from .composition import Composition, ease
from .models import Project
from .subtitles import read_srt, SubtitlePainter

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
        upcoming = composition.prepare(following) if transition and scene.transition == "crossfade" else None
        for position in range(consumed, count):
            frame = composition.frame(scene, current, position)
            if transition and position >= count - transition:
                offset = position - (count - transition)
                target = composition.frame(following, upcoming, offset) if upcoming else black
                frame = Image.blend(frame, target, ease(offset / (transition - 1)))
            if subtitles:
                frame = subtitles.paint(frame, global_frame / project.fps)
            yield frame
            global_frame += 1
        if following:
            current = upcoming if upcoming else composition.prepare(following)
        consumed = transition if upcoming else 0


def render(project_file: Path, output: Path, *, ffmpeg=None, crf=20):
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
    subtitles = None
    if project.subtitles:
        subtitle_file = project_file.parent / project.subtitles.file
        if project.subtitles.font_file and not project.subtitles.font_file.is_absolute():
            settings = project.subtitles.model_copy(update={"font_file": project_file.parent / project.subtitles.font_file})
        else:
            settings = project.subtitles
        subtitles = SubtitlePainter(read_srt(subtitle_file), project.width, project.height, settings)
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
            total_frames = sum(project.frames(scene.duration) for scene in project.scenes) - sum(
                project.transition_frames(i) for i, scene in enumerate(project.scenes)
                if scene.transition == "crossfade"
            )
            cmd = [encoder, "-hide_banner", "-loglevel", "error", "-y",
                   "-i", str(encoded), "-i", str(audio_path), "-map", "0:v:0", "-map", "1:a:0",
                   "-c:v", "copy", "-c:a", "aac", "-af", "apad",
                   "-t", f"{total_frames / project.fps:.6f}", "-movflags", "+faststart", str(combined)]
            process = subprocess.run(cmd, capture_output=True, text=True)
            if process.returncode:
                raise RuntimeError(f"Erro ao incluir narração: {process.stderr.strip()}")
            encoded = combined
        os.replace(encoded, output)
