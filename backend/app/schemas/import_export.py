from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class ImportPreviewItem(BaseModel):
    row_index: int
    data: Dict[str, Any]
    status: str  # valid, warning, error
    message: Optional[str] = None


class ImportValidationResult(BaseModel):
    total_rows: int
    valid_rows: int
    error_rows: int
    preview_data: List[Dict[str, Any]]
    errors: List[Dict[str, Any]]
    ready_to_import: bool


class CostUploadItem(BaseModel):
    sku: Optional[str] = None
    product_id: Optional[int] = None
    product_name: Optional[str] = None
    unit_cost: float
    effective_date: Optional[str] = None
