from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, HttpUrl


class StoreConnectionConfig(BaseModel):
    store_url: str
    consumer_key: str
    consumer_secret: str
    verify_ssl: bool = True


class ConnectionTestResult(BaseModel):
    success: bool
    message: str
    store_name: Optional[str] = None
    currency: Optional[str] = None
    timezone: Optional[str] = None
    woocommerce_version: Optional[str] = None


class SyncTriggerRequest(BaseModel):
    sync_type: str = "incremental"  # full, incremental, orders_only, products_only
    force_all: bool = False


class SyncStatusResponse(BaseModel):
    last_sync_timestamp: Optional[datetime] = None
    status: str
    orders_synced: int = 0
    products_synced: int = 0
    customers_synced: int = 0
    error_message: Optional[str] = None
