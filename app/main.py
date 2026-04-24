from fastapi import FastAPI

from app.api.places import router as places_router
from app.api.projects import router as projects_router
from app.db import Base, engine


app = FastAPI(title="Travel Planner API")


@app.on_event("startup")
def _create_tables() -> None:
    Base.metadata.create_all(bind=engine)


app.include_router(projects_router)
app.include_router(places_router)
