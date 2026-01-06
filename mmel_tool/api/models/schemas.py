"""
Pydantic models for the MEL/MMEL Audit API.
"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class ComplianceStatus(str, Enum):
    """Compliance status categories."""
    COMPLIANT = "COMPLIANT"
    MORE_RESTRICTIVE = "MORE_RESTRICTIVE"
    NON_COMPLIANT = "NON_COMPLIANT"
    MISSING_IN_MEL = "MISSING_IN_MEL"
    EXTRA_IN_MEL = "EXTRA_IN_MEL"


# ============== Upload Schemas ==============

class UploadResponse(BaseModel):
    """Response after file upload."""
    file_id: str
    filename: str
    status: str
    message: str
    file_path: Optional[str] = None


# ============== Parse Schemas ==============

class ParseRequest(BaseModel):
    """Request to parse a file."""
    file_id: str


class ParseResponse(BaseModel):
    """Response after parsing."""
    status: str
    file_id: str
    items_count: int
    output_file: str
    message: str
    statistics: Optional[Dict[str, Any]] = None


# ============== Item Schemas ==============

class MmelItemSchema(BaseModel):
    """MMEL item structure."""
    fullItemCode: str
    itemTitle: str
    ataChapter: str
    ataTitle: str
    operationTypes: List[str] = []
    msnEffectivity: Optional[str] = None
    rectificationInterval: Optional[str] = None
    numberInstalled: Optional[str] = None
    numberRequired: Optional[str] = None
    requiresMaintenance: bool = False
    requiresOperations: bool = False
    remarksText: str = ""
    conditions: List[str] = []
    note: Optional[str] = None
    isSubItem: bool = False
    parentItemCode: Optional[str] = None


class MelItemSchema(BaseModel):
    """MEL item structure."""
    fullItemCode: str
    itemTitle: str
    ataChapter: str
    ataTitle: str
    operationTypes: List[str] = []
    category: Optional[str] = None
    numberInstalled: Optional[str] = None
    numberRequired: Optional[str] = None
    requiresMaintenance: bool = False
    requiresOperations: bool = False
    remarksText: str = ""
    conditions: List[str] = []
    procedures: List[str] = []
    airlineSpecific: Optional[str] = None
    isSubItem: bool = False
    parentItemCode: Optional[str] = None


class ItemsListResponse(BaseModel):
    """Response for listing items."""
    total_items: int
    filters_applied: Dict[str, Any]
    items: List[Dict[str, Any]]


# ============== Audit Schemas ==============

class AuditRequest(BaseModel):
    """Request to run an audit."""
    mmel_file: str = Field(..., description="Path to MMEL JSON file")
    mel_file: str = Field(..., description="Path to MEL JSON file")


class AuditSummary(BaseModel):
    """Summary of audit results."""
    total_mmel_items: int
    total_mel_items: int
    compliant: int
    more_restrictive: int
    non_compliant: int
    missing_in_mel: int
    extra_in_mel: int
    compliance_score: float


class ComparisonResult(BaseModel):
    """Result of comparing a single item."""
    item_code: str
    status: str
    mel_data: Optional[Dict[str, Any]] = None
    mmel_data: Optional[Dict[str, Any]] = None
    issues: List[str] = []
    details: Dict[str, Any] = {}


class AuditResponse(BaseModel):
    """Response after running audit."""
    status: str
    report_id: str
    compliance_score: float
    summary: AuditSummary
    message: str
    report_files: Dict[str, str]


class AuditReportFull(BaseModel):
    """Full audit report."""
    metadata: Dict[str, Any]
    summary: AuditSummary
    results: List[ComparisonResult]


# ============== Health Check ==============

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    timestamp: datetime
    services: Dict[str, str]


# ============== Error Schemas ==============

class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    detail: str
    status_code: int
