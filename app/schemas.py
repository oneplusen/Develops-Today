from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class PlaceCreate(BaseModel):
    external_id: str = Field(min_length=1, max_length=64)
    notes: str | None = Field(default=None, max_length=10_000)


class PlaceUpdate(BaseModel):
    notes: str | None = Field(default=None, max_length=10_000)
    visited: bool | None = None


class PlaceOut(BaseModel):
    id: int
    project_id: int
    external_id: str
    title: str | None
    notes: str | None
    visited: bool
    visited_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=50_000)
    start_date: date | None = None
    places: list[PlaceCreate] = Field(default_factory=list, max_length=10)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=50_000)
    start_date: date | None = None


class ProjectOut(BaseModel):
    id: int
    name: str
    description: str | None
    start_date: date | None
    status: str
    places_count: int
    visited_places_count: int
    created_at: datetime
    updated_at: datetime


class ProjectDetailOut(ProjectOut):
    places: list[PlaceOut]

