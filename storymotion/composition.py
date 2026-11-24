import math

from PIL import Image, ImageOps

from .motion import ease

RESAMPLE = Image.Resampling.LANCZOS


def load_image(path):
    try:
        with Image.open(path) as source:
            if source.format not in {"PNG", "JPEG"}:
                raise ValueError("Formato esperado: JPG ou PNG.")
            return ImageOps.exif_transpose(source).convert("RGBA")
    except (OSError, ValueError, Image.DecompressionBombError) as error:
        raise ValueError(f"{path}: {error}") from error


class Composition:
    def __init__(self, project, root):
        self.project = project
        self.root = root
        self.size = project.width, project.height

    def validate_assets(self):
        paths = {scene.background for scene in self.project.scenes}
        paths.update(layer.asset for scene in self.project.scenes for layer in scene.layers)
        for path in sorted(paths):
            load_image(self.root / path).close()

    def prepare(self, scene):
        return (
            load_image(self.root / scene.background),
            [(layer, load_image(self.root / layer.asset)) for layer in scene.layers],
        )

    def frame(self, scene, media, index):
        width, height = self.size
        background, layers = media
        progress = ease(index / max(1, self.project.frames(scene.duration) - 1), scene.camera_easing)
        amount = scene.intensity
        effect = scene.camera_effect
        zoom = {
            "none": 1,
            "zoom_in": 1 + amount * progress,
            "zoom_out": 1 + amount * (1 - progress),
            "ken_burns": 1 + amount * (.4 + .6 * progress),
            "cinematic_zoom": 1 + amount * (.15 + .85 * progress),
            "drift": 1 + amount * .35,
        }.get(effect, 1 + amount)
        crop_width = min(background.width, background.height * width / height) / zoom
        crop_height = crop_width * height / width
        x = .5 + (progress - .5) * amount if effect in {"pan_horizontal", "ken_burns", "drift"} else .5
        y = .5 + (progress - .5) * amount if effect == "pan_vertical" else .5
        left = max(0, background.width - crop_width) * x
        top = max(0, background.height - crop_height) * y
        box = (left, top, min(background.width, left + crop_width), min(background.height, top + crop_height))
        frame = Image.new("RGBA", self.size, "black")
        frame.alpha_composite(background.resize(self.size, RESAMPLE, box=box))
        time = index / self.project.fps
        for layer, image in layers:
            if time < layer.start:
                continue
            phase = ease((time - layer.start) / layer.duration)
            if layer.animation == "pulse":
                scale = 1 + .18 * math.sin(math.pi * phase) ** 2
            elif layer.animation == "pop_in":
                # slight overshoot followed by a smooth settling
                scale = .3 + .7 * phase + .12 * math.sin(math.pi * phase)
            else:
                scale = 1
            layer_width = max(1, round(width * layer.width * scale))
            layer_height = max(1, round(layer_width * image.height / image.width))
            overlay = image.resize((layer_width, layer_height), RESAMPLE)
            if layer.animation == "spin_in" and phase < 1:
                overlay = overlay.rotate(90 * (1 - phase), Image.Resampling.BICUBIC, expand=True)
            opacity = layer.opacity * (phase if layer.animation in {"fade_in", "float_in", "rise_in", "spin_in"} else 1)
            if opacity < 1:
                overlay.putalpha(overlay.getchannel("A").point(lambda alpha: round(alpha * opacity)))
            x_center = layer.x * width
            if layer.animation == "float_in":
                x_center -= (1 - phase) * width * .12
            if layer.animation == "slide_in":
                x_center = -layer_width / 2 + (x_center + layer_width / 2) * phase
            y_center = layer.y * height
            if layer.animation == "rise_in":
                y_center += (1 - phase) * height * .15
            frame.alpha_composite(overlay, (round(x_center - overlay.width / 2),
                                            round(y_center - overlay.height / 2)))
        return frame.convert("RGB")
