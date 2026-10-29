from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.store import Store
from backend.app.services.import_service import DataImportService
from backend.app.schemas.import_export import ImportValidationResult

router = APIRouter(prefix="/api/imports", tags=["Data Import"])


def get_active_store(db: Session = Depends(get_db)) -> Store:
    store = db.query(Store).filter(Store.is_active == True).first()
    if not store:
        store = db.query(Store).first()
    return store


@router.post("/costs/preview", response_model=ImportValidationResult)
async def preview_costs_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    store: Store = Depends(get_active_store)
):
    service = DataImportService(db, store_id=store.id if store else None)
    contents = await file.read()
    try:
        df = service.parse_file(contents, file.filename)
        return service.validate_product_costs(df)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/costs/commit")
async def commit_costs_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    store: Store = Depends(get_active_store)
):
    service = DataImportService(db, store_id=store.id if store else None)
    contents = await file.read()
    try:
        df = service.parse_file(contents, file.filename)
        res = service.commit_product_costs(df, source_name=f"upload_{file.filename}")
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
