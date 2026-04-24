from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.places import router as places_router
from app.api.projects import router as projects_router
from app.db import Base, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Travel Planner API", lifespan=lifespan)


app.include_router(projects_router)
app.include_router(places_router)
