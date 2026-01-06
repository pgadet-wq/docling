"""
Audit endpoints for MEL vs MMEL comparison.
"""

import os
import json
import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from ..models.schemas import (
    AuditRequest,
    AuditResponse,
    AuditSummary,
    AuditReportFull,
)

router = APIRouter(prefix="/audit", tags=["Audit"])

# Paths
AUDIT_OUTPUT_DIR = "output/audit"


@router.post("", response_model=AuditResponse)
async def run_audit(request: AuditRequest):
    """
    Run a conformity audit comparing MEL against MMEL.

    Args:
        request: Contains paths to MMEL and MEL JSON files

    Returns:
        Audit results with compliance score and summary
    """
    # Validate input files exist
    if not os.path.exists(request.mmel_file):
        raise HTTPException(status_code=404, detail=f"MMEL file not found: {request.mmel_file}")

    if not os.path.exists(request.mel_file):
        raise HTTPException(status_code=404, detail=f"MEL file not found: {request.mel_file}")

    # Generate report ID
    report_id = str(uuid.uuid4())[:8]

    # Output paths
    os.makedirs(AUDIT_OUTPUT_DIR, exist_ok=True)
    json_report = os.path.join(AUDIT_OUTPUT_DIR, f"audit_{report_id}.json")
    md_report = os.path.join(AUDIT_OUTPUT_DIR, f"audit_{report_id}.md")
    non_compliant_report = os.path.join(AUDIT_OUTPUT_DIR, f"non_compliant_{report_id}.json")

    try:
        from mmel_tool.audit.comparator import MelMmelComparator

        comparator = MelMmelComparator(request.mmel_file, request.mel_file)
        comparator.run_audit()

        # Generate reports with custom paths
        comparator.generate_json_report(json_report)
        comparator.generate_markdown_report(md_report)
        comparator.generate_non_compliant_json(non_compliant_report)

        summary = AuditSummary(
            total_mmel_items=comparator.summary.total_mmel_items,
            total_mel_items=comparator.summary.total_mel_items,
            compliant=comparator.summary.compliant,
            more_restrictive=comparator.summary.more_restrictive,
            non_compliant=comparator.summary.non_compliant,
            missing_in_mel=comparator.summary.missing_in_mel,
            extra_in_mel=comparator.summary.extra_in_mel,
            compliance_score=comparator.summary.compliance_score,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audit failed: {str(e)}")

    return AuditResponse(
        status="success",
        report_id=report_id,
        compliance_score=summary.compliance_score,
        summary=summary,
        message=f"Audit complete. Score: {summary.compliance_score:.1f}%",
        report_files={
            "json": json_report,
            "markdown": md_report,
            "non_compliant": non_compliant_report,
        }
    )


@router.get("/{report_id}", response_model=AuditReportFull)
async def get_audit_report(report_id: str):
    """
    Get a full audit report by ID.

    Args:
        report_id: The report ID returned from the audit endpoint
    """
    json_path = os.path.join(AUDIT_OUTPUT_DIR, f"audit_{report_id}.json")

    if not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail=f"Audit report not found: {report_id}")

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read report: {str(e)}")

    # Convert to response model
    summary = AuditSummary(**data['summary'])

    return AuditReportFull(
        metadata=data['metadata'],
        summary=summary,
        results=data['results']
    )


@router.get("/{report_id}/download")
async def download_audit_report(report_id: str, format: str = "md"):
    """
    Download an audit report.

    Args:
        report_id: The report ID
        format: "md" for Markdown, "json" for JSON
    """
    if format == "md":
        file_path = os.path.join(AUDIT_OUTPUT_DIR, f"audit_{report_id}.md")
        media_type = "text/markdown"
        filename = f"audit_report_{report_id}.md"
    elif format == "json":
        file_path = os.path.join(AUDIT_OUTPUT_DIR, f"audit_{report_id}.json")
        media_type = "application/json"
        filename = f"audit_report_{report_id}.json"
    else:
        raise HTTPException(status_code=400, detail="Format must be 'md' or 'json'")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Report not found: {report_id}")

    return FileResponse(
        file_path,
        media_type=media_type,
        filename=filename
    )


@router.get("/{report_id}/non-compliant")
async def get_non_compliant_items(report_id: str):
    """
    Get only non-compliant items from an audit report.

    Args:
        report_id: The report ID
    """
    json_path = os.path.join(AUDIT_OUTPUT_DIR, f"non_compliant_{report_id}.json")

    if not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail=f"Report not found: {report_id}")

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read report: {str(e)}")

    return data


@router.post("/quick")
async def quick_audit():
    """
    Quick audit using already-parsed files in output/parsed/.

    Automatically finds the latest MMEL and MEL JSON files and runs the audit.
    No need to specify file paths.

    Returns:
        Audit results with compliance score and summary
    """
    import glob
    from datetime import datetime

    parsed_dir = "output/parsed"

    # Find latest MMEL file
    mmel_files = glob.glob(os.path.join(parsed_dir, "mmel_*_structured.json"))
    if not mmel_files:
        raise HTTPException(
            status_code=404,
            detail="No parsed MMEL files found. Run POST /api/v1/parse/all first."
        )
    mmel_file = max(mmel_files, key=os.path.getmtime)

    # Find latest MEL file
    mel_files = glob.glob(os.path.join(parsed_dir, "mel_*_structured.json"))
    if not mel_files:
        raise HTTPException(
            status_code=404,
            detail="No parsed MEL files found. Run POST /api/v1/parse/all first."
        )
    mel_file = max(mel_files, key=os.path.getmtime)

    # Generate report ID
    report_id = str(uuid.uuid4())[:8]

    # Output paths
    os.makedirs(AUDIT_OUTPUT_DIR, exist_ok=True)
    json_report = os.path.join(AUDIT_OUTPUT_DIR, f"audit_{report_id}.json")
    md_report = os.path.join(AUDIT_OUTPUT_DIR, f"audit_{report_id}.md")
    non_compliant_report = os.path.join(AUDIT_OUTPUT_DIR, f"non_compliant_{report_id}.json")

    try:
        from mmel_tool.audit.comparator import MelMmelComparator

        comparator = MelMmelComparator(mmel_file, mel_file)
        comparator.run_audit()

        # Generate reports
        comparator.generate_json_report(json_report)
        comparator.generate_markdown_report(md_report)
        comparator.generate_non_compliant_json(non_compliant_report)

        summary = AuditSummary(
            total_mmel_items=comparator.summary.total_mmel_items,
            total_mel_items=comparator.summary.total_mel_items,
            compliant=comparator.summary.compliant,
            more_restrictive=comparator.summary.more_restrictive,
            non_compliant=comparator.summary.non_compliant,
            missing_in_mel=comparator.summary.missing_in_mel,
            extra_in_mel=comparator.summary.extra_in_mel,
            compliance_score=comparator.summary.compliance_score,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audit failed: {str(e)}")

    return AuditResponse(
        status="success",
        report_id=report_id,
        compliance_score=summary.compliance_score,
        summary=summary,
        message=f"Quick audit complete. Used {os.path.basename(mmel_file)} vs {os.path.basename(mel_file)}. Score: {summary.compliance_score:.1f}%",
        report_files={
            "json": json_report,
            "markdown": md_report,
            "non_compliant": non_compliant_report,
            "mmel_used": mmel_file,
            "mel_used": mel_file,
        }
    )


@router.get("/reports/list")
async def list_audit_reports():
    """List all audit reports."""
    reports = []

    if os.path.exists(AUDIT_OUTPUT_DIR):
        for f in os.listdir(AUDIT_OUTPUT_DIR):
            if f.startswith('audit_') and f.endswith('.json'):
                report_id = f.replace('audit_', '').replace('.json', '')
                json_path = os.path.join(AUDIT_OUTPUT_DIR, f)

                # Get basic info from report
                try:
                    with open(json_path, 'r') as file:
                        data = json.load(file)
                        reports.append({
                            "report_id": report_id,
                            "audit_date": data.get('metadata', {}).get('audit_date'),
                            "compliance_score": data.get('summary', {}).get('compliance_score'),
                            "mel_aircraft": data.get('metadata', {}).get('mel_aircraft'),
                        })
                except:
                    reports.append({"report_id": report_id})

    return {"total": len(reports), "reports": reports}
