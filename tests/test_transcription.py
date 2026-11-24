import json
import shutil
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image
from pydantic import ValidationError

from storymotion.models import Project, SubtitleSettings, TranscriptionSettings
from storymotion.render import render
from storymotion.subtitles import Cue, SubtitlePainter, Word, read_srt
from storymotion.transcription import transcribe


class TranscriptionTests(unittest.TestCase):
    def test_local_model_and_word_grouping(self):
        words = [SimpleNamespace(start=start, end=end, word=text)
                 for start, end, text in [(0, .2, " Olá,"), (.2, .4, " polvo!"),
                                          (.95, 1, " Pausa"), (1, 1.2, " aqui"),
                                          (1.2, 1.3, " mesmo")]]
        engine = Mock()
        engine.transcribe.return_value = (iter([SimpleNamespace(words=words)]), None)
        factory = Mock(return_value=engine)
        with patch.dict("sys.modules", {"faster_whisper": SimpleNamespace(WhisperModel=factory)}):
            cues = transcribe(Path("narração.mp3"),
                              TranscriptionSettings(language="pt", words_per_cue=2))
        factory.assert_called_once_with("base", device="cpu", compute_type="int8")
        engine.transcribe.assert_called_once_with("narração.mp3", language="pt",
                                                  word_timestamps=True, vad_filter=True)
        self.assertEqual([cue.text for cue in cues], ["Olá, polvo!", "Pausa aqui", "mesmo"])
        self.assertEqual(cues[0].words[1], Word(.2, .4, "polvo!"))

    def test_silence_and_lazy_inference_error(self):
        engine = Mock()
        engine.transcribe.return_value = (iter(()), None)

        def failed_segments():
            yield SimpleNamespace(words=[])
            raise OSError("decoder failed")

        with patch.dict("sys.modules", {"faster_whisper": SimpleNamespace(WhisperModel=Mock(return_value=engine))}):
            self.assertEqual(transcribe(Path("silence.wav"), TranscriptionSettings()), [])
            engine.transcribe.return_value = (failed_segments(), None)
            with self.assertRaisesRegex(RuntimeError, "decoder failed"):
                transcribe(Path("bad.wav"), TranscriptionSettings())

    def test_config_validation(self):
        for values in ({}, {"file": "manual.srt", "transcription": {}},
                       {"file": "manual.srt", "style": "karaoke"}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                SubtitleSettings.model_validate(values)
        with self.assertRaisesRegex(ValidationError, "requer audio"):
            Project.model_validate({"project_name": "Teste", "subtitles": {"transcription": {}},
                                    "scenes": [{"id": "a", "background": "a.png", "duration": 1}]})

    def test_highlight_follows_half_open_word_intervals(self):
        settings = SubtitleSettings(transcription={}, style="karaoke", font_size=24,
                                    margin_bottom=40, highlight_color="#FF0000")
        cue = Cue(.1, .9, "Olá polvo", (Word(.1, .35, "Olá"), Word(.5, .9, "polvo")))
        painter = SubtitlePainter([cue], 240, 144, settings)

        def highlighted_x(timestamp):
            frame = painter.paint(Image.new("RGB", (240, 144)), timestamp)
            return [x for y in range(frame.height) for x in range(frame.width)
                    if frame.getpixel((x, y)) == (255, 0, 0)]

        self.assertLess(max(highlighted_x(.1)), min(highlighted_x(.5)))
        self.assertEqual(highlighted_x(.35), [])
        self.assertEqual(highlighted_x(.9), [])

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg/FFprobe indisponível")
    def test_export_audio_video_and_srt_after_overlap(self):
        with tempfile.TemporaryDirectory(prefix="narração ") as folder:
            root = Path(folder)
            Image.new("RGB", (160, 288), "navy").save(root / "fundo.png")
            with wave.open(str(root / "voz.wav"), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(8000)
                audio.writeframes(b"\0\0" * 16000)
            data = {
                "project_name": "Teste", "width": 160, "height": 288, "audio": "voz.wav",
                "subtitles": {"transcription": {}, "style": "karaoke", "font_size": 20, "margin_bottom": 55},
                "scenes": [
                    {"id": "a", "duration": .6, "background": "fundo.png",
                     "transition": "slide_left", "transition_duration": .2},
                    {"id": "b", "duration": .6, "background": "fundo.png"},
                ],
            }
            project = root / "história.json"
            project.write_text(json.dumps(data), encoding="utf-8")
            video = root / "vídeo.mp4"
            srt = root / "legenda.srt"
            cue = Cue(.8, 1.2, "Olá!", (Word(.8, 1.2, "Olá!"),))
            with patch("storymotion.render.transcribe", return_value=[cue]) as inference:
                render(project, video, export_srt=srt)
            self.assertEqual(inference.call_args.args[0], root / "voz.wav")
            self.assertEqual(read_srt(srt), [Cue(.8, 1, "Olá!")])
            probe = json.loads(subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(video)]))
            self.assertEqual({stream["codec_name"] for stream in probe["streams"]}, {"h264", "aac"})
            for stream in probe["streams"]:
                self.assertAlmostEqual(float(stream["duration"]), 1, places=2)
