from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models import Project, ProjectPlace


def project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return project


def place_or_404(db: Session, project_id: int, place_id: int) -> ProjectPlace:
    place = db.get(ProjectPlace, place_id)
    if not place or place.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Place not found"
        )
    return place


def project_counts(db: Session, project_id: int) -> tuple[int, int]:
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
                and_(
                    ProjectPlace.project_id == project_id,
                    ProjectPlace.visited.is_(True),
                )
            )
        )
        or 0
    )
    return int(total), int(visited)


def sync_project_status(db: Session, project: Project) -> None:
    total, visited = project_counts(db, project.id)
    if total > 0 and visited == total:
        project.status = "completed"
    else:
        project.status = "active"


def set_visited(place: ProjectPlace, visited: bool) -> None:
    if visited and not place.visited:
        place.visited = True
        place.visited_at = datetime.now(tz=timezone.utc)
    elif not visited and place.visited:
        place.visited = False
        place.visited_at = None


def ensure_project_deletable(db: Session, project: Project) -> None:
    visited_count = (
        db.scalar(
            select(func.count(ProjectPlace.id)).where(
                and_(
                    ProjectPlace.project_id == project.id,
                    ProjectPlace.visited.is_(True),
                )
            )
        )
        or 0
    )
    if int(visited_count) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete project with visited places",
        )
