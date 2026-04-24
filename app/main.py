from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.artic import ArticNotFoundError, fetch_artwork
from app.db import Base, engine, get_db
from app.models import Project, ProjectPlace
from app.schemas import (
    PlaceCreate,
    PlaceOut,
    PlaceUpdate,
    ProjectCreate,
    ProjectDetailOut,
    ProjectOut,
    ProjectUpdate,
)


app = FastAPI(title="Travel Planner API")


@app.on_event("startup")
def _create_tables() -> None:
    Base.metadata.create_all(bind=engine)


def _project_counts(db: Session, project_id: int) -> tuple[int, int]:
    total = (
        db.scalar(
            select(func.count(ProjectPlace.id)).where(
                ProjectPlace.project_id == project_id
            )
        )
        or 0
    )
    visited = (
        db.scalar(
            select(func.count(ProjectPlace.id)).where(
                and_(ProjectPlace.project_id == project_id, ProjectPlace.visited.is_(True))
            )
        )
        or 0
    )
    return int(total), int(visited)


def _sync_project_status(db: Session, project: Project) -> None:
    total, visited = _project_counts(db, project.id)
    project.status = "completed" if total > 0 and visited == total else "active"


def _project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return project


def _place_or_404(db: Session, project_id: int, place_id: int) -> ProjectPlace:
    place = db.get(ProjectPlace, place_id)
    if not place or place.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Place not found"
        )
    return place


@app.get("/projects", response_model=list[ProjectOut])
def list_projects(
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
) -> list[ProjectOut]:
    stmt = (
        select(Project)
        .order_by(Project.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status_filter:
        stmt = stmt.where(Project.status == status_filter)
    projects = db.scalars(stmt).all()

    result: list[ProjectOut] = []
    for p in projects:
        total, visited = _project_counts(db, p.id)
        result.append(
            ProjectOut(
                id=p.id,
                name=p.name,
                description=p.description,
                start_date=p.start_date,
                status=p.status,
                places_count=total,
                visited_places_count=visited,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
        )
    return result


@app.post(
    "/projects",
    response_model=ProjectDetailOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    payload: ProjectCreate, db: Session = Depends(get_db)
) -> ProjectDetailOut:
    if len(payload.places) > 10:
        raise HTTPException(
            status_code=422, detail="A project cannot have more than 10 places"
        )

    seen_external_ids: set[str] = set()
    for pl in payload.places:
        if pl.external_id in seen_external_ids:
            raise HTTPException(status_code=422, detail="Duplicate external_id in request")
        seen_external_ids.add(pl.external_id)

    project = Project(
        name=payload.name,
        description=payload.description,
        start_date=payload.start_date,
    )
    db.add(project)
    db.flush()

    places_out: list[ProjectPlace] = []
    for pl in payload.places:
        try:
            artwork = await fetch_artwork(pl.external_id)
        except ArticNotFoundError:
            raise HTTPException(
                status_code=422,
                detail=f"External place {pl.external_id} not found",
            ) from None
        place = ProjectPlace(
            project_id=project.id,
            external_id=str(pl.external_id),
            title=artwork.title,
            notes=pl.notes,
        )
        db.add(place)
        places_out.append(place)

    _sync_project_status(db, project)
    db.commit()
    db.refresh(project)
    for place in places_out:
        db.refresh(place)

    total, visited = _project_counts(db, project.id)
    return ProjectDetailOut(
        id=project.id,
        name=project.name,
        description=project.description,
        start_date=project.start_date,
        status=project.status,
        places_count=total,
        visited_places_count=visited,
        created_at=project.created_at,
        updated_at=project.updated_at,
        places=[PlaceOut.model_validate(p) for p in places_out],
    )


@app.get("/projects/{project_id}", response_model=ProjectDetailOut)
def get_project(project_id: int, db: Session = Depends(get_db)) -> ProjectDetailOut:
    project = _project_or_404(db, project_id)
    places = db.scalars(
        select(ProjectPlace)
        .where(ProjectPlace.project_id == project.id)
        .order_by(ProjectPlace.id)
    ).all()
    total, visited = _project_counts(db, project.id)
    return ProjectDetailOut(
        id=project.id,
        name=project.name,
        description=project.description,
        start_date=project.start_date,
        status=project.status,
        places_count=total,
        visited_places_count=visited,
        created_at=project.created_at,
        updated_at=project.updated_at,
        places=[PlaceOut.model_validate(p) for p in places],
    )


@app.patch("/projects/{project_id}", response_model=ProjectOut)
def update_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)) -> ProjectOut:
    project = _project_or_404(db, project_id)

    if "name" in payload.model_fields_set and payload.name is not None:
        project.name = payload.name
    if "description" in payload.model_fields_set:
        project.description = payload.description
    if "start_date" in payload.model_fields_set:
        project.start_date = payload.start_date

    db.add(project)
    db.commit()
    db.refresh(project)
    total, visited = _project_counts(db, project.id)
    return ProjectOut(
        id=project.id,
        name=project.name,
        description=project.description,
        start_date=project.start_date,
        status=project.status,
        places_count=total,
        visited_places_count=visited,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@app.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: Session = Depends(get_db)) -> Response:
    project = _project_or_404(db, project_id)
    visited_count = (
        db.scalar(
            select(func.count(ProjectPlace.id)).where(
                and_(ProjectPlace.project_id == project.id, ProjectPlace.visited.is_(True))
            )
        )
        or 0
    )
    if int(visited_count) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete project with visited places",
        )

    db.delete(project)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/projects/{project_id}/places", response_model=list[PlaceOut])
def list_project_places(project_id: int, db: Session = Depends(get_db)) -> list[PlaceOut]:
    _project_or_404(db, project_id)
    places = db.scalars(
        select(ProjectPlace)
        .where(ProjectPlace.project_id == project_id)
        .order_by(ProjectPlace.id)
    ).all()
    return [PlaceOut.model_validate(p) for p in places]


@app.post(
    "/projects/{project_id}/places",
    response_model=PlaceOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_place_to_project(
    project_id: int, payload: PlaceCreate, db: Session = Depends(get_db)
) -> PlaceOut:
    project = _project_or_404(db, project_id)
    total, _ = _project_counts(db, project.id)
    if total >= 10:
        raise HTTPException(status_code=409, detail="A project cannot have more than 10 places")

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
            status_code=409,
            detail="This external place is already added to the project",
        ) from None

    _sync_project_status(db, project)
    db.commit()
    db.refresh(place)
    return PlaceOut.model_validate(place)


@app.get("/projects/{project_id}/places/{place_id}", response_model=PlaceOut)
def get_project_place(project_id: int, place_id: int, db: Session = Depends(get_db)) -> PlaceOut:
    _project_or_404(db, project_id)
    place = _place_or_404(db, project_id, place_id)
    return PlaceOut.model_validate(place)


@app.patch("/projects/{project_id}/places/{place_id}", response_model=PlaceOut)
def update_project_place(
    project_id: int,
    place_id: int,
    payload: PlaceUpdate,
    db: Session = Depends(get_db),
) -> PlaceOut:
    project = _project_or_404(db, project_id)
    place = _place_or_404(db, project_id, place_id)

    if payload.notes is not None:
        place.notes = payload.notes

    if payload.visited is True and not place.visited:
        place.visited = True
        place.visited_at = datetime.now(tz=timezone.utc)
    elif payload.visited is False and place.visited:
        place.visited = False
        place.visited_at = None

    db.add(place)
    db.flush()
    _sync_project_status(db, project)
    db.commit()
    db.refresh(place)
    return PlaceOut.model_validate(place)
