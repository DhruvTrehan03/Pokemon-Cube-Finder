import asyncio
import json
from datetime import datetime
from dataclasses import dataclass, field
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.adapters.cube_sources.base import ImportedCube
from app.adapters.cube_sources.cubekoga import CubeKogaImportError, CubeKogaSource
from app.adapters.cube_sources.manual import parse_manual_cube
from app.database import SessionLocal, get_session, init_db
from app.models import Collection, Cube, CubeCard, OwnedCard
from app.services.card_normalisation import (
    normalise_card_name,
    normalise_collector_number,
    normalise_set_code,
)
from app.services.collection_import import detect_columns, parse_collection_csv, sniff_csv
from app.services.cube_comparison import compare_cube
from app.services.exports import missing_cards_csv
from app.services.ranking import rank_cubes
from app.services.ranking_cache import load_saved_rankings, refresh_saved_rankings


app = FastAPI(title="Pokemon Cube Finder")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@dataclass
class BulkImportStatus:
    running: bool = False
    total: int | None = None
    imported: int = 0
    failed: int = 0
    current_cube: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    errors: list[str] = field(default_factory=list)


bulk_import_status = BulkImportStatus()
bulk_import_task: asyncio.Task[None] | None = None


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    sort: str = "copy_completion",
    session: Session = Depends(get_session),
) -> HTMLResponse:
    saved_rankings, rankings_computed_at = load_saved_rankings(session)
    comparisons = rank_cubes(saved_rankings, sort)
    collection = session.scalars(
        select(Collection).order_by(Collection.imported_at.desc())
    ).first()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "comparisons": comparisons,
            "collection": collection,
            "rankings_computed_at": rankings_computed_at,
            "sort": sort,
        },
    )


@app.post("/rankings/refresh")
async def rankings_refresh(session: Session = Depends(get_session)) -> RedirectResponse:
    refresh_saved_rankings(session)
    return RedirectResponse("/", status_code=303)


@app.get("/collection", response_class=HTMLResponse)
async def collection_form(
    request: Request, session: Session = Depends(get_session)
) -> HTMLResponse:
    collection = session.scalars(
        select(Collection).order_by(Collection.imported_at.desc())
    ).first()
    cards = []
    if collection:
        cards = session.scalars(
            select(OwnedCard)
            .where(OwnedCard.collection_id == collection.id)
            .order_by(OwnedCard.original_name)
            .limit(100)
        ).all()
    return templates.TemplateResponse(
        request,
        "collection.html",
        {"request": request, "collection": collection, "cards": cards, "error": None},
    )


@app.post("/collection/preview", response_class=HTMLResponse)
async def collection_preview(
    request: Request,
    file: Annotated[UploadFile, File()],
) -> HTMLResponse:
    raw = (await file.read()).decode("utf-8-sig")
    headers, rows = sniff_csv(raw)
    detection = detect_columns(headers)
    return templates.TemplateResponse(
        request,
        "collection_preview.html",
        {
            "request": request,
            "filename": file.filename,
            "raw_csv": raw,
            "headers": headers,
            "sample_rows": rows[:10],
            "detection": detection,
        },
    )


@app.post("/collection/confirm")
async def collection_confirm(
    raw_csv: Annotated[str, Form()],
    filename: Annotated[str, Form()],
    name: Annotated[str, Form()] = "My Collection",
    card_name: Annotated[str | None, Form()] = None,
    set_name: Annotated[str | None, Form()] = None,
    set_code: Annotated[str | None, Form()] = None,
    collector_number: Annotated[str | None, Form()] = None,
    quantity: Annotated[str | None, Form()] = None,
    printing: Annotated[str | None, Form()] = None,
    condition: Annotated[str | None, Form()] = None,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    mapping = {
        "name": card_name,
        "set_name": set_name,
        "set_code": set_code,
        "collector_number": collector_number,
        "quantity": quantity,
        "printing": printing,
        "condition": condition,
    }
    cards = parse_collection_csv(raw_csv, mapping)
    session.execute(delete(OwnedCard))
    session.execute(delete(Collection))
    collection = Collection(name=name or "My Collection", source_filename=filename)
    session.add(collection)
    session.flush()
    for card in cards:
        session.add(
            OwnedCard(
                collection_id=collection.id,
                original_name=card.original_name,
                normalised_name=card.normalised_name,
                set_name=card.set_name,
                normalised_set_name=card.normalised_set_name,
                set_code=card.set_code,
                collector_number=card.collector_number,
                quantity=card.quantity,
                printing=card.printing,
                condition=card.condition,
                raw_import_data=json.dumps(card.raw_import_data),
            )
        )
    session.commit()
    return RedirectResponse("/", status_code=303)


@app.get("/cubes/new", response_class=HTMLResponse)
async def cube_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "cube_new.html", {"error": None})


@app.post("/cubes/manual")
async def cube_manual_import(
    name: Annotated[str, Form()],
    cards_text: Annotated[str, Form()],
    author: Annotated[str | None, Form()] = None,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    imported = parse_manual_cube(name=name, text=cards_text, author=author)
    cube = save_imported_cube(session, imported)
    return RedirectResponse(f"/cubes/{cube.id}", status_code=303)


@app.post("/cubes/cubekoga", response_class=HTMLResponse)
async def cube_cubekoga_import(
    request: Request,
    url: Annotated[str, Form()],
    session: Session = Depends(get_session),
) -> Response:
    try:
        imported = await CubeKogaSource().fetch_cube(url)
        cube = save_imported_cube(session, imported)
    except (CubeKogaImportError, ValueError, HTTPException) as exc:
        return templates.TemplateResponse(
            request, "cube_new.html", {"error": str(exc)}, status_code=400
        )
    return RedirectResponse(f"/cubes/{cube.id}", status_code=303)


@app.post("/cubes/cubekoga/all")
async def cube_cubekoga_import_all(
    max_cubes: Annotated[int | None, Form()] = None,
) -> RedirectResponse:
    global bulk_import_task
    if bulk_import_task and not bulk_import_task.done():
        return RedirectResponse("/cubes/import/status", status_code=303)
    bulk_import_task = asyncio.create_task(import_all_cubekoga_cubes(max_cubes=max_cubes))
    return RedirectResponse("/cubes/import/status", status_code=303)


@app.get("/cubes/import/status", response_class=HTMLResponse)
async def cube_import_status(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "cube_import_status.html", {"status": bulk_import_status}
    )


@app.get("/cubes/{cube_id}", response_class=HTMLResponse)
async def cube_detail(
    cube_id: int, request: Request, session: Session = Depends(get_session)
) -> HTMLResponse:
    cube = session.get(Cube, cube_id)
    if not cube:
        raise HTTPException(status_code=404, detail="Cube not found")
    comparison = compare_cube(session, cube)
    return templates.TemplateResponse(
        request, "cube_detail.html", {"cube": cube, "comparison": comparison}
    )


@app.get("/cubes/{cube_id}/missing.csv")
async def cube_missing_export(cube_id: int, session: Session = Depends(get_session)) -> Response:
    cube = session.get(Cube, cube_id)
    if not cube:
        raise HTTPException(status_code=404, detail="Cube not found")
    comparison = compare_cube(session, cube)
    csv_body = missing_cards_csv(comparison)
    return PlainTextResponse(
        csv_body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="cube-{cube_id}-missing.csv"'},
    )


def save_imported_cube(
    session: Session, imported: ImportedCube, scan_cubekoga_id: bool = True
) -> Cube:
    existing = None
    if imported.source_url:
        existing = session.scalars(
            select(Cube).where(Cube.source_url == imported.source_url)
        ).first()
    if existing is None and imported.source_type == "cubekoga" and scan_cubekoga_id:
        cube_id = _imported_cubekoga_id(imported)
        if cube_id:
            existing = _find_existing_cubekoga_cube(session, cube_id)

    cube = existing or Cube(source_type=imported.source_type)
    cube.name = imported.name
    cube.author = imported.author
    cube.description = imported.description
    cube.source_type = imported.source_type
    cube.source_url = imported.source_url
    cube.refreshed_at = datetime.utcnow() if existing else None
    cube.raw_source_data = json.dumps(imported.raw_source_data)
    session.add(cube)
    session.flush()

    if existing:
        session.execute(delete(CubeCard).where(CubeCard.cube_id == cube.id))

    for card in imported.cards:
        session.add(
            CubeCard(
                cube_id=cube.id,
                original_name=card.name,
                normalised_name=normalise_card_name(card.name),
                set_name=card.set_name,
                set_code=normalise_set_code(card.set_code),
                collector_number=normalise_collector_number(card.collector_number),
                required_quantity=card.quantity,
                raw_source_data=json.dumps(card.raw_source_data),
            )
        )
    session.commit()
    return cube


def _imported_cubekoga_id(imported: ImportedCube) -> str | None:
    metadata = imported.raw_source_data.get("metadata")
    if not isinstance(metadata, dict):
        return None
    cube_id = metadata.get("cube_ID") or metadata.get("cubeId") or metadata.get("id")
    return str(cube_id) if cube_id else None


def _find_existing_cubekoga_cube(session: Session, cube_id: str) -> Cube | None:
    for cube in session.scalars(select(Cube).where(Cube.source_type == "cubekoga")):
        try:
            raw = json.loads(cube.raw_source_data)
        except ValueError:
            continue
        metadata = raw.get("metadata")
        if not isinstance(metadata, dict):
            continue
        existing_id = metadata.get("cube_ID") or metadata.get("cubeId") or metadata.get("id")
        if str(existing_id) == cube_id:
            return cube
    return None


def _backfill_cubekoga_source_urls(session: Session) -> None:
    changed = False
    for cube in session.scalars(select(Cube).where(Cube.source_type == "cubekoga")):
        cube_id = _cubekoga_id_from_raw_data(cube.raw_source_data)
        if cube_id and cube.source_url != f"https://cubekoga.net/cube/{cube_id}":
            cube.source_url = f"https://cubekoga.net/cube/{cube_id}"
            changed = True
    if changed:
        session.commit()


def _cubekoga_id_from_raw_data(raw_source_data: str | None) -> str | None:
    if not raw_source_data:
        return None
    try:
        raw = json.loads(raw_source_data)
    except ValueError:
        return None
    metadata = raw.get("metadata")
    if not isinstance(metadata, dict):
        return None
    cube_id = metadata.get("cube_ID") or metadata.get("cubeId") or metadata.get("id")
    return str(cube_id) if cube_id else None


async def import_all_cubekoga_cubes(max_cubes: int | None = None) -> None:
    source = CubeKogaSource()
    bulk_import_status.running = True
    bulk_import_status.total = None
    bulk_import_status.imported = 0
    bulk_import_status.failed = 0
    bulk_import_status.current_cube = None
    bulk_import_status.started_at = datetime.utcnow()
    bulk_import_status.finished_at = None
    bulk_import_status.errors.clear()
    try:
        bulk_import_status.total = await source.public_cube_count()
        if max_cubes is not None:
            bulk_import_status.total = (
                min(max_cubes, bulk_import_status.total)
                if bulk_import_status.total is not None
                else max_cubes
            )
        with SessionLocal() as session:
            _backfill_cubekoga_source_urls(session)
        async for imported in source.iter_public_cubes(
            page_size=50, delay_seconds=0.15, max_cubes=max_cubes
        ):
            bulk_import_status.current_cube = imported.name
            try:
                with SessionLocal() as session:
                    save_imported_cube(session, imported, scan_cubekoga_id=False)
                bulk_import_status.imported += 1
            except Exception as exc:  # noqa: BLE001 - keep batch import moving.
                bulk_import_status.failed += 1
                if len(bulk_import_status.errors) < 20:
                    bulk_import_status.errors.append(f"{imported.name}: {exc}")
    except Exception as exc:  # noqa: BLE001 - surface batch-level failure in UI.
        bulk_import_status.failed += 1
        bulk_import_status.errors.append(str(exc))
    finally:
        bulk_import_status.running = False
        bulk_import_status.current_cube = None
        bulk_import_status.finished_at = datetime.utcnow()
