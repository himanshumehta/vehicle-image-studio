import pytest
from PIL import Image
from services.studio_compositor import (
    _create_gradient_background,
    _apply_vignette,
    composite_studio,
    composite_with_template,
)


def test_gradient_background_dimensions():
    bg = _create_gradient_background(200, 100)
    assert bg.size == (200, 100)
    assert bg.mode == "RGB"


def test_gradient_background_top_is_white():
    bg = _create_gradient_background(100, 100)
    # Top-left pixel should be near white (value 255)
    r, g, b = bg.getpixel((0, 0))
    assert r > 250 and g > 250 and b > 250


def test_gradient_background_bottom_is_darker():
    bg = _create_gradient_background(100, 100)
    top = bg.getpixel((50, 0))[0]
    bottom = bg.getpixel((50, 99))[0]
    assert bottom < top


def test_vignette_darkens_edges():
    bg = _create_gradient_background(200, 200)
    before_corner = bg.getpixel((0, 0))
    result = _apply_vignette(bg)
    after_corner = result.getpixel((0, 0))
    # Corner should be slightly darker after vignette
    assert after_corner[0] <= before_corner[0]


def test_composite_studio_preserves_dimensions():
    subject = Image.new("RGBA", (300, 200), (255, 0, 0, 255))
    result = composite_studio(subject)
    assert result.size == (300, 200)
    assert result.mode == "RGB"


def test_composite_studio_converts_rgb_input():
    subject = Image.new("RGB", (100, 100), (255, 0, 0))
    result = composite_studio(subject)
    assert result.size == (100, 100)


def test_composite_with_template_covers():
    subject = Image.new("RGBA", (200, 150), (255, 0, 0, 128))
    template = Image.new("RGB", (400, 300), (0, 0, 255))
    result = composite_with_template(subject, template)
    assert result.size == (200, 150)
    assert result.mode == "RGB"


def test_composite_with_template_scales_small_template():
    subject = Image.new("RGBA", (200, 150), (255, 0, 0, 128))
    template = Image.new("RGB", (50, 50), (0, 0, 255))
    result = composite_with_template(subject, template)
    assert result.size == (200, 150)
