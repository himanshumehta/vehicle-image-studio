import io
import os
import tempfile

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

# Isolate tests from any real .env and storage before app modules are imported.
_TMP_STORAGE = tempfile.mkdtemp(prefix="vis-test-storage-")
os.environ["STORAGE_BACKEND"] = "local"
os.environ["LOCAL_STORAGE_DIR"] = _TMP_STORAGE
os.environ["SEED_SAMPLES"] = "false"
os.environ["OPENAI_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""


def make_png(width=100, height=100, mode="RGB", color=(255, 0, 0)) -> bytes:
    if mode == "RGBA" and len(color) == 3:
        color = color + (255,)
    buf = io.BytesIO()
    Image.new(mode, (width, height), color).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def storage_root():
    return _TMP_STORAGE


@pytest.fixture
async def client():
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
