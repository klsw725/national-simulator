from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.ontology.versioning import OntologyVersioning

router = APIRouter(prefix="/api/ontology", tags=["ontology"])

_versioning = OntologyVersioning()


class VersionRegisterRequest(BaseModel):
    version: str
    schema_data: dict[str, Any]
    change_summary: str = ""
    created_by: str = "system"


class ValidateRequest(BaseModel):
    schema_data: dict[str, Any]


@router.get("/versions")
async def list_versions(limit: int = 50, offset: int = 0):
    versions = await _versioning.list_versions(limit=limit, offset=offset)
    return {"count": len(versions), "versions": versions}


@router.post("/versions", status_code=201)
async def register_version(data: VersionRegisterRequest):
    result = await _versioning.register(
        version=data.version,
        schema_json=data.schema_data,
        change_summary=data.change_summary,
        created_by=data.created_by,
    )
    return result


@router.get("/versions/latest")
async def get_latest_version():
    latest = await _versioning.get_latest()
    if not latest:
        raise HTTPException(status_code=404, detail="No versions registered")
    return latest


@router.get("/versions/diff")
async def diff_versions(from_version: str, to_version: str):
    try:
        result = await _versioning.diff(from_version, to_version)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return result


@router.get("/versions/{version}")
async def get_version(version: str):
    v = await _versioning.get_version(version)
    if not v:
        raise HTTPException(status_code=404, detail=f"Version '{version}' not found")
    return v


@router.post("/versions/validate")
async def validate_schema(data: ValidateRequest):
    result = await _versioning.validate(data.schema_data)
    return result
