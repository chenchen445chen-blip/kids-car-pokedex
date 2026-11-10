from typing import List, Optional
from pydantic import BaseModel, Field


class BrandPatchRequest(BaseModel):
    name: Optional[str] = None
    name_zh: Optional[str] = None
    brand_group: Optional[str] = None
    country: Optional[str] = None
    slogan_child: Optional[str] = None
    introduction_child: Optional[str] = None
    sort_order: Optional[int] = None


class SeriesPatchRequest(BaseModel):
    brand_id: Optional[int] = None
    parent_series_id: Optional[int] = None
    name: Optional[str] = None
    name_zh: Optional[str] = None
    series_type: Optional[str] = None
    body_type_label: Optional[str] = None
    introduction_child: Optional[str] = None
    sort_order: Optional[int] = None


class VehiclePatchRequest(BaseModel):
    brand_id: Optional[int] = None
    series_id: Optional[int] = None
    primary_category_id: Optional[int] = None
    category_ids: Optional[List[int]] = None
    model_name: Optional[str] = None
    model_name_zh: Optional[str] = None
    trim_name: Optional[str] = None
    generation: Optional[str] = None
    model_year: Optional[int] = None
    body_style: Optional[str] = None
    power_type: Optional[str] = None
    introduction_child: Optional[str] = None
    introduction_parent: Optional[str] = None
    recognition_features: Optional[str] = None
    usage_description: Optional[str] = None


class ReviewActionRequest(BaseModel):
    reviewed_by: str = Field(default="admin")
    review_note: Optional[str] = None


class InboxResolveRequest(BaseModel):
    action: str = Field(..., description="link_existing | create_draft | ignore")
    resolved_brand_id: Optional[int] = None
    resolved_series_id: Optional[int] = None
    resolved_vehicle_id: Optional[int] = None
    brand_name_zh: Optional[str] = None
    series_name_zh: Optional[str] = None
    model_name: Optional[str] = None
    primary_category_id: Optional[int] = None

