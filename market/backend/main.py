from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.controllers import auth, countries, health, jobs, mailbox, profile, resumes, sends, stats
from backend.db import init_db

logger = logging.getLogger(__name__)


def _guard_package() -> None:
    import backend

    expected = Path(__file__).resolve().parent
    loaded = Path(backend.__file__).resolve().parent
    if loaded != expected:
        raise RuntimeError(
            f"Loaded the wrong backend package from {loaded}. Start the server from the market folder."
        )


_guard_package()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Apply Desk API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for controller in (health, auth, stats, profile, countries, mailbox, jobs, resumes, sends):
    app.include_router(controller.router, prefix="/api")


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8001, reload=True)
