import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from routers import images, processing
from services.storage import seed_samples, storage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if get_settings().seed_samples:
        copied = seed_samples(storage)
        if copied:
            logger.info("Seeded %d sample image(s) into local storage", copied)
    logger.info("Models lazy-load on the first processing request")
    yield


app = FastAPI(
    title="Vehicle Image Studio API",
    description="Background removal, Real-ESRGAN upscaling and AI inpainting for vehicle photos",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Edit-Provider", "X-Edit-Model", "X-Edit-Cost-USD"],
)

app.include_router(images.router)
app.include_router(images.files_router)
app.include_router(processing.router)
