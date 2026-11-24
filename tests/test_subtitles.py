import json
import shutil
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path

from PIL import Image
from storymotion.models import Project
from storymotion.render import render
from storymotion.subtitles import read_srt, SubtitlePainter

class SubtitleTests(unittest.TestCase):
    def test_srt_and_draw(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "subtitle.srt"
            path.write_text("1\n00:00:00,100 --> 00:00:00,900\nOlá, polvo!\n", encoding="utf-8")
            cues = read_srt(path)
            self.assertEqual(len(cues), 1)
            settings = Project.model_validate({"project_name":"A", "width": 320, "height": 568,
                "subtitles":{"file":"subtitle.srt", "font_size":26,"margin_bottom":90},
                "scenes":[{"id":"one","background":"a.png","duration":1}]}).subtitles
            painter = SubtitlePainter(cues, 320, 568, settings)
            frame = Image.new("RGB", (320, 568), "navy")
            before = frame.tobytes()
            painter.paint(frame, .5)
            self.assertNotEqual(before, frame.tobytes())

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg não disponível")
    def test_render_with_audio_and_subtitles(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            Image.new("RGB", (80, 140), "#174466").save(root / "image.png")
            (root / "sub.srt").write_text("1\n00:00:00,000 --> 00:00:00,500\nO polvo tem três corações!\n",encoding="utf-8")
            with wave.open(str(root / "voice.wav"), "wb") as audio:
                audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(8000)
                audio.writeframes(b"\0\0" * 4000)
            (root / "project.json").write_text(json.dumps({
                "project_name":"Test", "width":160, "height":288, "fps":30, "audio":"voice.wav",
                "subtitles":{"file":"sub.srt", "font_size":22,"margin_bottom":65},
                "scenes":[{"id":"one", "background":"image.png", "duration":1,
                           "camera_effect":"cinematic_zoom"}]}),encoding="utf-8")
            render(root / "project.json", root / "video.mp4")
            probe = json.loads(subprocess.check_output(["ffprobe","-v","error","-show_streams","-of","json",str(root / "video.mp4")]))
            self.assertEqual({stream["codec_type"] for stream in probe["streams"]}, {"audio", "video"})
