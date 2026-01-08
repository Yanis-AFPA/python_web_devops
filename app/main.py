from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from app.database import init_db
from contextlib import asynccontextmanager
import logging

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Démarrage de WikiFlow...")
    await init_db()
    yield
    # Shutdown
    logger.info("Arrêt de WikiFlow...")

app = FastAPI(title="WikiFlow", lifespan=lifespan)

# Mount Static Files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Placeholder for seeding (will be called in initialization or manual script)

from app.routers import views, api, users, storage
app.include_router(views.router)
app.include_router(api.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(storage.router, prefix="/api")

@app.get("/")
async def root():
    return RedirectResponse(url="/dashboard")
