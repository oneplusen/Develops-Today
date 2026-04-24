from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.artic import ArticNotFoundError, fetch_artwork
from app.db import get_db
from app.models import Project, ProjectPlace
from app.schemas import (
    PlaceOut,
    ProjectCreate,
    ProjectDetailOut,
    ProjectOut,
    ProjectUpdate,
)
from app.services.projects import (
    ensure_project_deletable,
    project_counts,
    project_or_404,
)


router = APIRouter(tags=["projects"])


@router.get("/projects", response_model=list[ProjectOut])
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
        total, visited = project_counts(db, p.id)
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


@router.post(
    "/projects",
    response_model=ProjectDetailOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    payload: ProjectCreate, db: Session = Depends(get_db)
) -> ProjectDetailOut:
    seen_external_ids: set[str] = set()
    for pl in payload.places:
        if pl.external_id in seen_external_ids:
            raise HTTPException(
                status_code=422, detail="Duplicate external_id in request"
            )
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

    from app.services.projects import sync_project_status

    sync_project_status(db, project)
    db.commit()
    db.refresh(project)
    for place in places_out:
        db.refresh(place)

    total, visited = project_counts(db, project.id)
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


@router.get("/projects/{project_id}", response_model=ProjectDetailOut)
def get_project(project_id: int, db: Session = Depends(get_db)) -> ProjectDetailOut:
    project = project_or_404(db, project_id)
    places = db.scalars(
        select(ProjectPlace)
        .where(ProjectPlace.project_id == project.id)
        .order_by(ProjectPlace.id)
    ).all()
    total, visited = project_counts(db, project.id)
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


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)
) -> ProjectOut:
    project = project_or_404(db, project_id)

    if "name" in payload.model_fields_set and payload.name is not None:
        project.name = payload.name
    if "description" in payload.model_fields_set:
        project.description = payload.description
    if "start_date" in payload.model_fields_set:
        project.start_date = payload.start_date

    db.add(project)
    db.commit()
    db.refresh(project)
    total, visited = project_counts(db, project.id)
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


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: Session = Depends(get_db)) -> Response:
    project = project_or_404(db, project_id)
    ensure_project_deletable(db, project)
    db.delete(project)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
