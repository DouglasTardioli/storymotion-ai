import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from pydantic import ValidationError

from storymotion.composition import Composition
from storymotion.models import Project
from storymotion.render import iter_frames, render

DEMO = Path(__file__).resolve().parents[1] / "examples" / "demo.json"


class RenderTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for color in ("red", "blue", "green"):
            Image.new("RGB", (64, 96), color).save(self.root / f"{color}.png")
        Image.new("RGBA", (16, 16), (255, 255, 255, 128)).save(self.root / "layer.png")
        self.data = dict(project_name="Teste", width=64, height=96, fps=30, scenes=[
            dict(id="a", duration=1, background="red.png", transition="crossfade", transition_duration=.2,
                 layers=[dict(asset="layer.png", start=.1, width=.25)]),
            dict(id="b", duration=1, background="blue.png", transition="fade_to_black", transition_duration=.2),
            dict(id="c", duration=1, background="green.png"),
        ])

    def test_timeline_and_transparency(self):
        project = Project.model_validate(self.data)
        frames = list(iter_frames(project, Composition(project, self.root)))
        self.assertEqual(len(frames), 84)
        self.assertEqual(frames[0].getpixel((32, 48)), (255, 0, 0))
        self.assertEqual(frames[4].getpixel((32, 48)), (255, 128, 128))
        self.assertEqual(frames[29].getpixel((0, 0)), (0, 0, 255))
        self.assertEqual(frames[53].getpixel((0, 0)), (0, 0, 0))

    def test_invalid_transition(self):
        self.data["scenes"][0]["transition_duration"] = 1.2
        with self.assertRaises(ValidationError):
            Project.model_validate(self.data)

    def test_corrupt_media(self):
        (self.root / "red.png").write_bytes(b"invalid")
        with self.assertRaisesRegex(ValueError, "red.png"):
            Composition(Project.model_validate(self.data), self.root).validate_assets()

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe") and DEMO.exists(), "Demo ausente ou FFmpeg/FFprobe indisponível")
    def test_demo_mp4(self):
        output = self.root / "demo.mp4"
        render(DEMO, output)
        info = json.loads(subprocess.check_output([
            "ffprobe", "-v", "error", "-show_streams", "-of", "json", str(output)
        ]))
        self.assertEqual(len(info["streams"]), 1)
        video = info["streams"][0]
        self.assertEqual(video["codec_name"], "h264")
        self.assertEqual((video["width"], video["height"]), (1080, 1920))
        self.assertEqual(video["avg_frame_rate"], "30/1")
        self.assertEqual(int(video["nb_frames"]), 168)
        self.assertAlmostEqual(float(video["duration"]), 5.6, places=2)
