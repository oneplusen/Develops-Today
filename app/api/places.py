from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.artic import ArticNotFoundError, fetch_artwork
from app.db import get_db
from app.models import ProjectPlace
from app.schemas import PlaceCreate, PlaceOut, PlaceUpdate
from app.services.projects import (
    place_or_404,
    project_counts,
    project_or_404,
    set_visited,
    sync_project_status,
)


router = APIRouter(tags=["places"])


@router.get("/projects/{project_id}/places", response_model=list[PlaceOut])
def list_project_places(
    project_id: int, db: Session = Depends(get_db)
) -> list[PlaceOut]:
    project_or_404(db, project_id)
    places = db.scalars(
        select(ProjectPlace)
        .where(ProjectPlace.project_id == project_id)
        .order_by(ProjectPlace.id)
    ).all()
    return [PlaceOut.model_validate(p) for p in places]


@router.post(
    "/projects/{project_id}/places",
    response_model=PlaceOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_place_to_project(
    project_id: int, payload: PlaceCreate, db: Session = Depends(get_db)
) -> PlaceOut:
    project = project_or_404(db, project_id)
    total, _ = project_counts(db, project.id)
    if total >= 10:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A project cannot have more than 10 places",
        )

    try:
        artwork = await fetch_artwork(payload.external_id)
    except ArticNotFoundError:
        raise HTTPException(
            status_code=422,
            detail=f"External place {payload.external_id} not found",
        ) from None

    place = ProjectPlace(
        project_id=project.id,
        external_id=str(payload.external_id),
        title=artwork.title,
        notes=payload.notes,
    )
    db.add(place)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This external place is already added to the project",
        ) from None

    sync_project_status(db, project)
    db.commit()
    db.refresh(place)
    return PlaceOut.model_validate(place)


@router.get("/projects/{project_id}/places/{place_id}", response_model=PlaceOut)
def get_project_place(
    project_id: int, place_id: int, db: Session = Depends(get_db)
) -> PlaceOut:
    project_or_404(db, project_id)
    place = place_or_404(db, project_id, place_id)
    return PlaceOut.model_validate(place)


@router.patch("/projects/{project_id}/places/{place_id}", response_model=PlaceOut)
def update_project_place(
    project_id: int,
    place_id: int,
    payload: PlaceUpdate,
    db: Session = Depends(get_db),
) -> PlaceOut:
    project = project_or_404(db, project_id)
    place = place_or_404(db, project_id, place_id)

    if payload.notes is not None:
        place.notes = payload.notes

    if payload.visited is not None:
        set_visited(place, payload.visited)

    db.add(place)
    db.flush()
    sync_project_status(db, project)
    db.commit()
    db.refresh(place)
    return PlaceOut.model_validate(place)
