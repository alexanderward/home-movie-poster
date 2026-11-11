from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_INPUT_BYTES = 15 * 1024 * 1024
MAX_WIDTH = 2160
MAX_HEIGHT = 3840
MAX_PIXELS = 40_000_000


class ImageError(ValueError):
    pass


@dataclass(frozen=True)
class StoredImage:
    relative_path: str
    width: int
    height: int
    digest: str


def normalize_image(contents: bytes, root: Path, *, namespace: str = "posters") -> StoredImage:
    if not contents or len(contents) > MAX_INPUT_BYTES:
        raise ImageError("Poster must be a non-empty JPEG or PNG no larger than 15 MB.")
    digest = sha256(contents).hexdigest()
    relative = Path(namespace) / digest[:2] / f"{digest}.jpg"
    destination = root / relative
    try:
        with Image.open(BytesIO(contents)) as source:
            if source.width * source.height > MAX_PIXELS:
                raise ImageError("Poster dimensions are too large.")
            source.verify()
        with Image.open(BytesIO(contents)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((MAX_WIDTH, MAX_HEIGHT), Image.Resampling.LANCZOS)
            width, height = image.size
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                temporary = destination.with_suffix(".tmp")
                image.save(temporary, format="JPEG", quality=91, optimize=True, progressive=True)
                temporary.replace(destination)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ImageError("Poster is not a valid supported image.") from error
    return StoredImage(relative.as_posix(), width, height, digest)
