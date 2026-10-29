from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.store import Store
from backend.app.models.sync import SyncLog
from backend.app.services.woocommerce_client import WooCommerceClient
from backend.app.services.sync_service import SyncService
from backend.app.schemas.woocommerce import StoreConnectionConfig, ConnectionTestResult, SyncTriggerRequest

router = APIRouter(prefix="/api/sync", tags=["WooCommerce Synchronization"])


@router.post("/test-connection", response_model=ConnectionTestResult)
def test_connection(config: StoreConnectionConfig):
    client = WooCommerceClient(
        store_url=config.store_url,
        consumer_key=config.consumer_key,
        consumer_secret=config.consumer_secret,
        verify_ssl=config.verify_ssl
    )
    result = client.test_connection()
    return ConnectionTestResult(**result)


@router.post("/connect-store")
def connect_or_update_store(config: StoreConnectionConfig, db: Session = Depends(get_db)):
    client = WooCommerceClient(
        store_url=config.store_url,
        consumer_key=config.consumer_key,
        consumer_secret=config.consumer_secret,
        verify_ssl=config.verify_ssl
    )
    test_res = client.test_connection()
    if not test_res["success"]:
        raise HTTPException(status_code=400, detail=f"Connection verification failed: {test_res['message']}")

    # Check existing store
    store = db.query(Store).filter(Store.store_url == config.store_url.rstrip("/")).first()
    if not store:
        store = Store(
            store_url=config.store_url.rstrip("/"),
            name=test_res.get("store_name") or "WooCommerce Store",
            consumer_key=config.consumer_key,
            consumer_secret=config.consumer_secret,
            currency=test_res.get("currency") or "USD",
            timezone=test_res.get("timezone") or "UTC",
            is_active=True
        )
        db.add(store)
    else:
        store.consumer_key = config.consumer_key
        store.consumer_secret = config.consumer_secret
        store.currency = test_res.get("currency") or store.currency
        store.is_active = True

    db.commit()
    db.refresh(store)
    return {"success": True, "message": "Store successfully connected and saved.", "store_id": store.id}


@router.post("/trigger")
def trigger_sync(
    request: SyncTriggerRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    store = db.query(Store).filter(Store.is_active == True).first()
    if not store:
        raise HTTPException(status_code=404, detail="No active store found to synchronize.")

    sync_service = SyncService(db, store)
    # Run sync
    log = sync_service.run_sync(sync_type=request.sync_type)

    return {
        "success": log.status == "success",
        "sync_log_id": log.id,
        "records_fetched": log.records_fetched,
        "records_inserted": log.records_inserted,
        "records_updated": log.records_updated,
        "status": log.status,
        "error": log.error_message
    }


@router.get("/logs")
def get_sync_logs(limit: int = 10, db: Session = Depends(get_db)):
    logs = db.query(SyncLog).order_by(SyncLog.started_at.desc()).limit(limit).all()
    return [
        {
            "id": l.id,
            "sync_type": l.sync_type,
            "status": l.status,
            "records_fetched": l.records_fetched,
            "records_inserted": l.records_inserted,
            "records_updated": l.records_updated,
            "error_message": l.error_message,
            "started_at": l.started_at,
            "completed_at": l.completed_at
        }
        for l in logs
    ]
