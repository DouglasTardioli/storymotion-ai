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

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "polvo"


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

    def test_existing_examples(self):
        for name in ("polvo.json", "polvo_com_legendas.json"):
            with self.subTest(name=name):
                project = Project.model_validate_json((EXAMPLES / name).read_text(encoding="utf-8"))
                Composition(project, EXAMPLES).validate_assets()
                self.assertEqual(project.scenes[0].camera_easing, "smoothstep")

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg/FFprobe indisponível")
    def test_demo_mp4(self):
        project_file = self.root / "project.json"
        project_file.write_text(json.dumps(self.data), encoding="utf-8")
        output = self.root / "demo.mp4"
        render(project_file, output)
        info = json.loads(subprocess.check_output([
            "ffprobe", "-v", "error", "-show_streams", "-of", "json", str(output)
        ]))
        self.assertEqual(len(info["streams"]), 1)
        video = info["streams"][0]
        self.assertEqual(video["codec_name"], "h264")
        self.assertEqual((video["width"], video["height"]), (64, 96))
        self.assertEqual(video["avg_frame_rate"], "30/1")
        self.assertEqual(int(video["nb_frames"]), 84)
        self.assertAlmostEqual(float(video["duration"]), 2.8, places=2)

    def test_overlapping_transitions_preserve_frame_count(self):
        for kind in ("slide_left", "dip_to_black"):
            with self.subTest(kind=kind):
                self.data["scenes"][0]["transition"] = kind
                project = Project.model_validate(self.data)
                frames = list(iter_frames(project, Composition(project, self.root)))
                self.assertEqual(len(frames), project.total_frames())
                self.assertEqual(len(frames), 84)
                self.assertEqual(frames[24].getpixel((0, 0)), (255, 0, 0))
                self.assertEqual(frames[29].getpixel((0, 0)), (0, 0, 255))
                if kind == "slide_left":
                    self.assertEqual(frames[26].getpixel((0, 0)), (255, 0, 0))
                    self.assertEqual(frames[26].getpixel((63, 0)), (0, 0, 255))
                else:
                    self.assertEqual(frames[26].getpixel((0, 0)), (0, 0, 0))

    def test_camera_curves_have_same_endpoints_and_different_interpolation(self):
        gradient = Image.linear_gradient("L").resize((64, 96)).convert("RGB")
        gradient.save(self.root / "red.png")
        self.data["scenes"][0].update(camera_effect="pan_vertical", intensity=1, layers=[])
        project = Project.model_validate(self.data)
        composition = Composition(project, self.root)
        scene = project.scenes[0]
        media = composition.prepare(scene)
        linear = scene.model_copy(update={"camera_easing": "linear"})
        for index in (0, 29):
            self.assertEqual(composition.frame(scene, media, index).tobytes(),
                             composition.frame(linear, media, index).tobytes())
        for curve in ("smoothstep", "smootherstep", "sine_in_out"):
            eased = scene.model_copy(update={"camera_easing": curve})
            self.assertNotEqual(composition.frame(eased, media, 6).tobytes(),
                                composition.frame(linear, media, 6).tobytes())

    def test_png_animations_settle_and_keep_alpha(self):
        asset = Image.new("RGBA", (16, 10), (255, 255, 255, 128))
        asset.putpixel((0, 0), (0, 0, 0, 0))
        asset.save(self.root / "layer.png")
        project = Project.model_validate(self.data)
        composition = Composition(project, self.root)
        scene = project.scenes[0]
        still = composition.frame(scene, composition.prepare(scene), 20)
        for animation in ("rise_in", "spin_in", "pulse"):
            with self.subTest(animation=animation):
                layer = scene.layers[0].model_copy(update={"animation": animation})
                animated = scene.model_copy(update={"layers": [layer]})
                media = composition.prepare(animated)
                self.assertNotEqual(composition.frame(animated, media, 10).tobytes(), still.tobytes())
                self.assertEqual(composition.frame(animated, media, 20).tobytes(), still.tobytes())
                self.assertEqual(still.getpixel((32, 48)), (255, 128, 128))
