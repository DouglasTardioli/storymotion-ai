"""Curvas de movimento e composição de transições."""
import math

from PIL import Image


def ease(value, curve="smoothstep"):
    value = min(1, max(0, value))
    if curve == "smootherstep":
        return value ** 3 * (value * (6 * value - 15) + 10)
    if curve == "sine_in_out":
        return (1 - math.cos(math.pi * value)) / 2
    if curve == "linear":
        return value
    return value * value * (3 - 2 * value)


def transition_frame(source, target, black, kind, offset, count, curve):
    if kind == "dip_to_black":
        midpoint = (count - 1) // 2
        if offset <= midpoint:
            return Image.blend(source, black, ease(offset / midpoint, curve))
        return Image.blend(black, target, ease((offset - midpoint) / (count - 1 - midpoint), curve))

    phase = ease(offset / (count - 1), curve)
    if kind == "slide_left":
        shift = round(source.width * phase)
        result = source.copy()
        result.paste(source, (-shift, 0))
        result.paste(target, (source.width - shift, 0))
        return result
    return Image.blend(source, target, phase)
