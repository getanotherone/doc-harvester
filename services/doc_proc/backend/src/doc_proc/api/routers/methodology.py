"""Methodology CRUD endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from doc_proc.api.schemas import MethodologyCreate, MethodologyResponse, MethodologyUpdate
from doc_proc.db.models import Methodology
from doc_proc.db.session import get_db

router = APIRouter()


@router.get("", response_model=list[MethodologyResponse])
async def list_methodologies(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Methodology).order_by(Methodology.name))
    return result.scalars().all()


@router.post("", response_model=MethodologyResponse, status_code=201)
async def create_methodology(
    request: MethodologyCreate,
    db: AsyncSession = Depends(get_db),
):
    methodology = Methodology(
        name=request.name,
        description=request.description,
        file_types=request.file_types,
        config=request.config,
    )
    db.add(methodology)
    await db.flush()
    await db.refresh(methodology)
    return methodology


@router.get("/{method_id}", response_model=MethodologyResponse)
async def get_methodology(method_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Methodology).where(Methodology.id == method_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(404, "Methodology not found")
    return m


@router.put("/{method_id}", response_model=MethodologyResponse)
async def update_methodology(
    method_id: uuid.UUID,
    request: MethodologyUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Methodology).where(Methodology.id == method_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(404, "Methodology not found")

    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(m, field, value)

    await db.flush()
    await db.refresh(m)
    return m


@router.delete("/{method_id}")
async def delete_methodology(method_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Methodology).where(Methodology.id == method_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(404, "Methodology not found")
    await db.delete(m)
    return {"deleted": True}


@router.post("/{method_id}/set-default")
async def set_default(method_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Methodology).where(Methodology.id == method_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(404, "Methodology not found")

    # Clear all defaults
    all_methods = (await db.execute(select(Methodology))).scalars().all()
    for method in all_methods:
        method.is_default = method.id == method_id

    await db.flush()
    return {"default": str(method_id)}
