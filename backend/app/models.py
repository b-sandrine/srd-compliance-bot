from __future__ import annotations
from typing import Optional, List, Any
from enum import Enum
from pydantic import BaseModel


class FieldType(str, Enum):
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    DROPDOWN = "dropdown"
    MULTISELECT = "multiselect"
    FILE = "file"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    TEXTAREA = "textarea"
    EMAIL = "email"
    PHONE = "phone"
    UNKNOWN = "unknown"


class SRDField(BaseModel):
    name: str
    label: Optional[str] = None
    field_type: FieldType = FieldType.UNKNOWN
    required: Optional[bool] = None
    hide_expression: Optional[str] = None
    validation_rules: List[str] = []
    options: List[str] = []
    notes: Optional[str] = None
    widget_requirements: Optional[str] = None
    section: Optional[str] = None
    block: Optional[str] = None


class FormField(BaseModel):
    name: Optional[str] = None
    label: Optional[str] = None
    field_type: FieldType = FieldType.UNKNOWN
    required: Optional[bool] = None
    visible: bool = True
    hide_expression: Optional[str] = None
    options: List[str] = []
    attributes: dict = {}


class FieldMismatch(BaseModel):
    field_name: str
    property: str
    srd_value: Any
    form_value: Any
    severity: str = "warning"  # "error" | "warning" | "info"


class ComparisonReport(BaseModel):
    job_id: str
    service_url: str
    srd_source: str
    compliant: bool
    matching_fields: List[str]
    missing_from_form: List[SRDField]
    extra_in_form: List[FormField]
    mismatches: List[FieldMismatch]
    summary: dict
    raw_srd_fields: List[SRDField]
    raw_form_fields: List[FormField]
