"""Imágenes del catálogo del portal (ADR-009): logo de la pyme y foto de producto.

- Se aceptan JPEG, PNG o WebP de hasta `media_max_upload_mb` y se **re-codifican** a WebP con Pillow: se achican
  (512 px el logo, 800 px la foto), se corrige la orientación y se pierden los metadatos EXIF (pueden traer la
  ubicación GPS de quien sacó la foto).
- Se guardan en `storage_dir/media/<pyme_id>/<sha256>.webp`: el nombre es el hash del contenido, así la URL no se
  puede adivinar y el navegador puede cachearla para siempre.
- Se sirven sin sesión (un `<img>` no envía el token) desde `GET /portal/media/<pyme_id>/<archivo>`.
"""

import hashlib
import io
import re
import uuid
import warnings
from enum import Enum
from pathlib import Path
from typing import BinaryIO

from PIL import Image, ImageOps

from app.core.config import get_settings
from app.core.errors import ProblemError

MEDIA_URL = "/api/v1/portal/media"
FILENAME = re.compile(r"^[0-9a-f]{64}\.webp$")
MAX_PIXELS = 40_000_000  # tope contra imágenes "bomba" (se descomprimen a un tamaño enorme)


class Kind(Enum):
    LOGO = 512
    PHOTO = 800


def media_url(pyme_id: uuid.UUID, path: str | None) -> str | None:
    """URL pública de una imagen guardada (`media/<pyme>/<archivo>`), o None si no hay."""
    if not path:
        return None
    return f"{MEDIA_URL}/{pyme_id}/{Path(path).name}"


def _encode(data: bytes, kind: Kind) -> bytes:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            img: Image.Image = Image.open(io.BytesIO(data))
            if img.format not in {"JPEG", "PNG", "WEBP"}:
                raise ValueError(img.format)
            if img.width * img.height > MAX_PIXELS:
                raise ValueError("demasiados píxeles")
            img = ImageOps.exif_transpose(img)
            img.load()
    except (OSError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise ProblemError(
            415, "invalid_image", "No pudimos leer esa imagen", "Usa una foto JPG, PNG o WebP."
        ) from None
    img = img.convert("RGBA" if kind is Kind.LOGO else "RGB")
    img.thumbnail((kind.value, kind.value))
    out = io.BytesIO()
    img.save(out, "WEBP", quality=82, method=6)  # sin exif=: el WebP sale sin metadatos
    return out.getvalue()


def read_upload(stream: BinaryIO) -> bytes:
    """Lee el archivo subido con tope de tamaño (413 si se pasa)."""
    max_bytes = get_settings().media_max_upload_mb * 1024 * 1024
    data = stream.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ProblemError(
            413, "image_too_large", "La imagen es demasiado grande", f"El máximo es {max_bytes // 1048576} MB."
        )
    return data


def save_image(pyme_id: uuid.UUID, data: bytes, kind: Kind) -> str:
    """Re-codifica y guarda la imagen. Devuelve la ruta relativa a `storage_dir`."""
    webp = _encode(data, kind)
    name = f"{hashlib.sha256(webp).hexdigest()}.webp"
    rel = Path("media") / str(pyme_id) / name
    path = get_settings().storage_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(webp)
    return str(rel)


def file_for(pyme_id: uuid.UUID, filename: str) -> Path | None:
    """El archivo pedido por la URL pública, validando el nombre para que no se salga de la carpeta de la pyme."""
    if not FILENAME.match(filename):
        return None
    path = get_settings().storage_dir / "media" / str(pyme_id) / filename
    return path if path.is_file() else None
