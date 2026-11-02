from PIL import Image
import io


def bytes_to_pil(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


def pil_to_bytes(img: Image.Image, fmt: str = "PNG") -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt, quality=95)
    buf.seek(0)
    return buf.read()
