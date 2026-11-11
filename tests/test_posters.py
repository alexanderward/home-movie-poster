from io import BytesIO

import pytest
from PIL import Image

from apps.common.posters.storage import ImageError, normalize_image


def image_bytes(width=120, height=180):
    output = BytesIO()
    Image.new("RGBA", (width, height), (10, 20, 30, 120)).save(output, "PNG")
    return output.getvalue()


def test_normalizes_to_metadata_free_jpeg_without_cropping(tmp_path):
    stored = normalize_image(image_bytes(), tmp_path)
    assert stored.relative_path.endswith(".jpg")
    with Image.open(tmp_path / stored.relative_path) as image:
        assert image.format == "JPEG"
        assert image.size == (120, 180)
        assert image.mode == "RGB"
        assert not image.getexif()


def test_rejects_non_image(tmp_path):
    with pytest.raises(ImageError):
        normalize_image(b"not an image", tmp_path)
