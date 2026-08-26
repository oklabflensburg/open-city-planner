"""Öffentliche HTTP-Schnittstelle des Referenzmoduls."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.platform.modules.sdk import ModulePrincipal, PermissionDependencyFactory

from ..application.service import (
    CreateReferenceItem,
    ReferenceItemService,
    ReferencePermissionDenied,
)
from ..domain.models import ReferenceItem


class ReferenceItemRead(BaseModel):
    id: str
    title: str
    description: str
    longitude: float
    latitude: float

    model_config = ConfigDict(frozen=True)


class ReferenceItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)

    model_config = ConfigDict(frozen=True)


class PointGeometry(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: tuple[float, float]


class ReferenceFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: str
    properties: dict[str, str]
    geometry: PointGeometry


class ReferenceFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[ReferenceFeature]


def _read(item: ReferenceItem) -> ReferenceItemRead:
    return ReferenceItemRead(
        id=item.id,
        title=item.title,
        description=item.description,
        longitude=item.longitude,
        latitude=item.latitude,
    )


def create_router(
    service: ReferenceItemService,
    permission_dependencies: PermissionDependencyFactory,
) -> APIRouter:
    router = APIRouter()
    require_write = permission_dependencies.require("reference.items-write", csrf=True)

    @router.get("/items", response_model=list[ReferenceItemRead])
    async def list_items() -> list[ReferenceItemRead]:
        return [_read(item) for item in await service.list_items()]

    @router.get("/items.geojson", response_model=ReferenceFeatureCollection)
    async def list_items_geojson() -> ReferenceFeatureCollection:
        return ReferenceFeatureCollection(
            features=[
                ReferenceFeature(
                    id=item.id,
                    properties={"title": item.title, "description": item.description},
                    geometry=PointGeometry(coordinates=(item.longitude, item.latitude)),
                )
                for item in await service.list_items()
            ]
        )

    @router.post("/items", response_model=ReferenceItemRead, status_code=201)
    async def create_item(
        payload: ReferenceItemCreate,
        principal: Annotated[ModulePrincipal, Depends(require_write)],
    ) -> ReferenceItemRead:
        try:
            item = await service.create_item(
                CreateReferenceItem(
                    title=payload.title,
                    description=payload.description,
                    longitude=payload.longitude,
                    latitude=payload.latitude,
                ),
                principal_id=principal.id,
            )
        except ReferencePermissionDenied as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "PERMISSION_REQUIRED",
                        "message": "Berechtigung fehlt.",
                    }
                },
            ) from exc
        return _read(item)

    return router
