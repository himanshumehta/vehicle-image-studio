import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from config import MAX_REQUEST_BYTES, get_settings
from http_security import BodySizeLimitMiddleware, CrossSiteWriteGuard, SecurityHeadersMiddleware
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

settings = get_settings()
# Starlette runs the last-added middleware first, so read this list bottom-up:
# security headers -> Host check -> body size cap -> CORS -> cross-site write guard -> routes.
app.add_middleware(CrossSiteWriteGuard, allowed_origins=settings.cors_origin_list)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,  # the API uses no cookies or auth headers
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
    expose_headers=["X-Edit-Provider", "X-Edit-Model", "X-Edit-Cost-USD"],
)
app.add_middleware(BodySizeLimitMiddleware, max_bytes=MAX_REQUEST_BYTES)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(images.router)
app.include_router(images.files_router)
app.include_router(processing.router)
