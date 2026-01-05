#!/usr/bin/env python3
"""
MEL vs MMEL Conformity Comparator

Audits a MEL (Minimum Equipment List) against its reference MMEL (Master MEL)
to detect compliance gaps.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime


class ComplianceStatus(Enum):
    """Compliance status categories."""
    COMPLIANT = "COMPLIANT"
    MORE_RESTRICTIVE = "MORE_RESTRICTIVE"
    NON_COMPLIANT = "NON_COMPLIANT"
    MISSING_IN_MEL = "MISSING_IN_MEL"
    EXTRA_IN_MEL = "EXTRA_IN_MEL"


# Rectification interval hierarchy (A is most restrictive)
INTERVAL_HIERARCHY = {"A": 1, "B": 2, "C": 3, "D": 4}


@dataclass
class ComparisonResult:
    """Result of comparing a single MEL item against MMEL."""
    item_code: str
    status: str
    mel_data: Optional[Dict[str, Any]] = None
    mmel_data: Optional[Dict[str, Any]] = None
    issues: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditSummary:
    """Summary of the audit results."""
    total_mmel_items: int = 0
    total_mel_items: int = 0
    compliant: int = 0
    more_restrictive: int = 0
    non_compliant: int = 0
    missing_in_mel: int = 0
    extra_in_mel: int = 0
    compliance_score: float = 0.0


class MelMmelComparator:
    """Compares MEL against MMEL for compliance audit."""

    def __init__(self, mmel_path: str, mel_path: str):
        self.mmel_path = mmel_path
        self.mel_path = mel_path
        self.mmel_data: Dict[str, Any] = {}
        self.mel_data: Dict[str, Any] = {}
        self.mmel_items: Dict[str, Dict] = {}
        self.mel_items: Dict[str, Dict] = {}
        self.results: List[ComparisonResult] = []
        self.summary = AuditSummary()

    def load_data(self) -> None:
        """Load MMEL and MEL JSON files."""
        with open(self.mmel_path, 'r', encoding='utf-8') as f:
            self.mmel_data = json.load(f)
        with open(self.mel_path, 'r', encoding='utf-8') as f:
            self.mel_data = json.load(f)

        # Index items by fullItemCode
        for item in self.mmel_data.get('items', []):
            self.mmel_items[item['fullItemCode']] = item
        for item in self.mel_data.get('items', []):
            self.mel_items[item['fullItemCode']] = item

        self.summary.total_mmel_items = len(self.mmel_items)
        self.summary.total_mel_items = len(self.mel_items)

    def compare_intervals(self, mel_interval: str, mmel_interval: str) -> tuple[str, str]:
        """
        Compare rectification intervals.
        Returns (status, description).
        A < B < C < D (A is most restrictive)
        """
        mel_rank = INTERVAL_HIERARCHY.get(mel_interval, 99)
        mmel_rank = INTERVAL_HIERARCHY.get(mmel_interval, 99)

        if mel_rank == mmel_rank:
            return "EQUAL", f"Both {mel_interval}"
        elif mel_rank < mmel_rank:
            return "MORE_RESTRICTIVE", f"MEL={mel_interval} < MMEL={mmel_interval}"
        else:
            return "LESS_RESTRICTIVE", f"MEL={mel_interval} > MMEL={mmel_interval}"

    def compare_number_required(self, mel_req: str, mmel_req: str) -> tuple[str, str]:
        """
        Compare number required.
        MEL must be >= MMEL (more restrictive = require more).
        """
        try:
            mel_val = int(mel_req) if mel_req and mel_req != '-' else 0
            mmel_val = int(mmel_req) if mmel_req and mmel_req != '-' else 0

            if mel_val == mmel_val:
                return "EQUAL", f"Both require {mel_val}"
            elif mel_val > mmel_val:
                return "MORE_RESTRICTIVE", f"MEL requires {mel_val}, MMEL requires {mmel_val}"
            else:
                return "LESS_RESTRICTIVE", f"MEL requires {mel_val}, MMEL requires {mmel_val}"
        except (ValueError, TypeError):
            return "UNKNOWN", f"MEL={mel_req}, MMEL={mmel_req}"

    def compare_item(self, item_code: str) -> ComparisonResult:
        """Compare a single item between MEL and MMEL."""
        mel_item = self.mel_items.get(item_code)
        mmel_item = self.mmel_items.get(item_code)

        # Case: Item only in MEL (extra)
        if mel_item and not mmel_item:
            return ComparisonResult(
                item_code=item_code,
                status=ComplianceStatus.EXTRA_IN_MEL.value,
                mel_data=mel_item,
                issues=["Item exists in MEL but not in MMEL reference"],
                details={"reason": "No corresponding MMEL item found"}
            )

        # Case: Item only in MMEL (missing from MEL)
        if mmel_item and not mel_item:
            return ComparisonResult(
                item_code=item_code,
                status=ComplianceStatus.MISSING_IN_MEL.value,
                mmel_data=mmel_item,
                issues=["MMEL item not found in MEL"],
                details={
                    "mmel_interval": mmel_item.get('rectificationInterval'),
                    "mmel_title": mmel_item.get('itemTitle')
                }
            )

        # Both exist - compare them
        issues = []
        details = {}
        is_compliant = True
        is_more_restrictive = False

        # Compare rectification interval
        mel_interval = mel_item.get('category') or mel_item.get('rectificationInterval')
        mmel_interval = mmel_item.get('rectificationInterval') or mmel_item.get('category')

        interval_status, interval_desc = self.compare_intervals(mel_interval, mmel_interval)
        details['interval_comparison'] = interval_desc
        details['mel_interval'] = mel_interval
        details['mmel_interval'] = mmel_interval

        if interval_status == "LESS_RESTRICTIVE":
            is_compliant = False
            issues.append(f"Rectification interval less restrictive: {interval_desc}")
        elif interval_status == "MORE_RESTRICTIVE":
            is_more_restrictive = True

        # Compare number required
        mel_req = mel_item.get('numberRequired', '0')
        mmel_req = mmel_item.get('numberRequired', '0')

        req_status, req_desc = self.compare_number_required(mel_req, mmel_req)
        details['required_comparison'] = req_desc
        details['mel_required'] = mel_req
        details['mmel_required'] = mmel_req

        if req_status == "LESS_RESTRICTIVE":
            is_compliant = False
            issues.append(f"Number required less restrictive: {req_desc}")
        elif req_status == "MORE_RESTRICTIVE":
            is_more_restrictive = True

        # Compare maintenance/operations requirements
        mel_maint = mel_item.get('requiresMaintenance', False)
        mmel_maint = mmel_item.get('requiresMaintenance', False)
        mel_ops = mel_item.get('requiresOperations', False)
        mmel_ops = mmel_item.get('requiresOperations', False)

        details['mel_maintenance'] = mel_maint
        details['mmel_maintenance'] = mmel_maint
        details['mel_operations'] = mel_ops
        details['mmel_operations'] = mmel_ops

        # If MMEL requires (M) but MEL doesn't, that's less restrictive
        if mmel_maint and not mel_maint:
            issues.append("MMEL requires maintenance (M) but MEL does not")
            # This might be intentional, not necessarily non-compliant

        # Determine final status
        if not is_compliant:
            status = ComplianceStatus.NON_COMPLIANT.value
        elif is_more_restrictive:
            status = ComplianceStatus.MORE_RESTRICTIVE.value
        else:
            status = ComplianceStatus.COMPLIANT.value

        return ComparisonResult(
            item_code=item_code,
            status=status,
            mel_data=mel_item,
            mmel_data=mmel_item,
            issues=issues,
            details=details
        )

    def run_audit(self) -> None:
        """Run the complete audit comparison."""
        self.load_data()

        # Get all unique item codes
        all_codes = set(self.mmel_items.keys()) | set(self.mel_items.keys())

        for code in sorted(all_codes):
            result = self.compare_item(code)
            self.results.append(result)

            # Update summary counts
            if result.status == ComplianceStatus.COMPLIANT.value:
                self.summary.compliant += 1
            elif result.status == ComplianceStatus.MORE_RESTRICTIVE.value:
                self.summary.more_restrictive += 1
            elif result.status == ComplianceStatus.NON_COMPLIANT.value:
                self.summary.non_compliant += 1
            elif result.status == ComplianceStatus.MISSING_IN_MEL.value:
                self.summary.missing_in_mel += 1
            elif result.status == ComplianceStatus.EXTRA_IN_MEL.value:
                self.summary.extra_in_mel += 1

        # Calculate compliance score
        # Items that are compliant or more restrictive are "OK"
        # Missing items count against compliance
        total_auditable = self.summary.total_mmel_items
        if total_auditable > 0:
            ok_count = self.summary.compliant + self.summary.more_restrictive
            # Missing items are deducted from compliance
            self.summary.compliance_score = (ok_count / total_auditable) * 100

    def get_non_compliant_items(self) -> List[ComparisonResult]:
        """Get all non-compliant items."""
        return [r for r in self.results if r.status == ComplianceStatus.NON_COMPLIANT.value]

    def generate_json_report(self, output_path: str) -> None:
        """Generate detailed JSON audit report."""
        report = {
            "metadata": {
                "audit_date": datetime.now().isoformat(),
                "mmel_file": self.mmel_path,
                "mel_file": self.mel_path,
                "mel_aircraft": self.mel_data.get('metadata', {}).get('aircraft_registration', 'N/A'),
                "mel_operator": self.mel_data.get('metadata', {}).get('operator', 'N/A')
            },
            "summary": {
                "total_mmel_items": self.summary.total_mmel_items,
                "total_mel_items": self.summary.total_mel_items,
                "compliant": self.summary.compliant,
                "more_restrictive": self.summary.more_restrictive,
                "non_compliant": self.summary.non_compliant,
                "missing_in_mel": self.summary.missing_in_mel,
                "extra_in_mel": self.summary.extra_in_mel,
                "compliance_score": round(self.summary.compliance_score, 2)
            },
            "results": [asdict(r) for r in self.results]
        }

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    def generate_non_compliant_json(self, output_path: str) -> None:
        """Generate JSON with only non-compliant items."""
        non_compliant = self.get_non_compliant_items()
        report = {
            "metadata": {
                "audit_date": datetime.now().isoformat(),
                "total_non_compliant": len(non_compliant)
            },
            "items": [asdict(r) for r in non_compliant]
        }

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    def generate_markdown_report(self, output_path: str) -> None:
        """Generate human-readable Markdown audit report."""
        lines = []

        # Header
        lines.append("# MEL vs MMEL Conformity Audit Report")
        lines.append("")
        lines.append(f"**Audit Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        lines.append("## Source Files")
        lines.append(f"- **MMEL (Reference):** `{self.mmel_path}`")
        lines.append(f"- **MEL (Audited):** `{self.mel_path}`")
        mel_meta = self.mel_data.get('metadata', {})
        lines.append(f"- **Aircraft:** {mel_meta.get('aircraft_registration', 'N/A')} (MSN {mel_meta.get('aircraft_msn', 'N/A')})")
        lines.append(f"- **Operator:** {mel_meta.get('operator', 'N/A')}")
        lines.append("")

        # Summary
        lines.append("## Summary")
        lines.append("")
        lines.append(f"| Metric | Count |")
        lines.append("|--------|-------|")
        lines.append(f"| Total MMEL Items | {self.summary.total_mmel_items} |")
        lines.append(f"| Total MEL Items | {self.summary.total_mel_items} |")
        lines.append(f"| ✅ Compliant | {self.summary.compliant} |")
        lines.append(f"| ✅ More Restrictive | {self.summary.more_restrictive} |")
        lines.append(f"| ❌ Non-Compliant | {self.summary.non_compliant} |")
        lines.append(f"| ⚠️ Missing in MEL | {self.summary.missing_in_mel} |")
        lines.append(f"| ➕ Extra in MEL | {self.summary.extra_in_mel} |")
        lines.append("")
        lines.append(f"### Compliance Score: **{self.summary.compliance_score:.1f}%**")
        lines.append("")

        # Status legend
        lines.append("## Status Legend")
        lines.append("")
        lines.append("| Status | Description |")
        lines.append("|--------|-------------|")
        lines.append("| COMPLIANT | MEL matches MMEL requirements |")
        lines.append("| MORE_RESTRICTIVE | MEL is stricter than MMEL (OK) |")
        lines.append("| NON_COMPLIANT | MEL is less restrictive than MMEL ⚠️ |")
        lines.append("| MISSING_IN_MEL | MMEL item not found in operator MEL |")
        lines.append("| EXTRA_IN_MEL | MEL item has no MMEL equivalent |")
        lines.append("")

        # Non-compliant items table
        non_compliant = self.get_non_compliant_items()
        if non_compliant:
            lines.append("## ❌ Non-Compliant Items")
            lines.append("")
            lines.append("| Item Code | Title | Issue | MEL | MMEL |")
            lines.append("|-----------|-------|-------|-----|------|")
            for r in non_compliant:
                title = r.mel_data.get('itemTitle', 'N/A') if r.mel_data else 'N/A'
                title = title[:30] + "..." if len(title) > 30 else title
                issue = "; ".join(r.issues)[:40]
                mel_int = r.details.get('mel_interval', 'N/A')
                mmel_int = r.details.get('mmel_interval', 'N/A')
                lines.append(f"| {r.item_code} | {title} | {issue} | {mel_int} | {mmel_int} |")
            lines.append("")
        else:
            lines.append("## ✅ No Non-Compliant Items Found")
            lines.append("")

        # Missing items
        missing = [r for r in self.results if r.status == ComplianceStatus.MISSING_IN_MEL.value]
        if missing:
            lines.append("## ⚠️ Items Missing from MEL")
            lines.append("")
            lines.append("| Item Code | MMEL Title | MMEL Interval |")
            lines.append("|-----------|------------|---------------|")
            for r in missing[:20]:  # Limit to first 20
                title = r.mmel_data.get('itemTitle', 'N/A') if r.mmel_data else 'N/A'
                title = title[:40] + "..." if len(title) > 40 else title
                interval = r.details.get('mmel_interval', 'N/A')
                lines.append(f"| {r.item_code} | {title} | {interval} |")
            if len(missing) > 20:
                lines.append(f"| ... | *({len(missing) - 20} more items)* | |")
            lines.append("")

        # More restrictive items (sample)
        more_restrictive = [r for r in self.results if r.status == ComplianceStatus.MORE_RESTRICTIVE.value]
        if more_restrictive:
            lines.append("## ✅ More Restrictive Items (Sample)")
            lines.append("")
            lines.append("| Item Code | Title | MEL Interval | MMEL Interval |")
            lines.append("|-----------|-------|--------------|---------------|")
            for r in more_restrictive[:10]:
                title = r.mel_data.get('itemTitle', 'N/A') if r.mel_data else 'N/A'
                title = title[:35] + "..." if len(title) > 35 else title
                mel_int = r.details.get('mel_interval', 'N/A')
                mmel_int = r.details.get('mmel_interval', 'N/A')
                lines.append(f"| {r.item_code} | {title} | {mel_int} | {mmel_int} |")
            if len(more_restrictive) > 10:
                lines.append(f"| ... | *({len(more_restrictive) - 10} more items)* | | |")
            lines.append("")

        # Write file
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

    def print_summary(self) -> None:
        """Print audit summary to console."""
        print("=" * 70)
        print("AUDIT DE CONFORMITÉ MEL vs MMEL")
        print("=" * 70)
        print()

        mel_meta = self.mel_data.get('metadata', {})
        print(f"MMEL (Référence): {self.mmel_path}")
        print(f"MEL (Audité):     {self.mel_path}")
        print(f"Aéronef:          {mel_meta.get('aircraft_registration', 'N/A')} (MSN {mel_meta.get('aircraft_msn', 'N/A')})")
        print(f"Opérateur:        {mel_meta.get('operator', 'N/A')}")
        print()

        print("-" * 70)
        print("RÉSUMÉ")
        print("-" * 70)
        print(f"  Items MMEL (référence):     {self.summary.total_mmel_items}")
        print(f"  Items MEL (audité):         {self.summary.total_mel_items}")
        print()
        print(f"  ✅ COMPLIANT:               {self.summary.compliant}")
        print(f"  ✅ MORE_RESTRICTIVE:        {self.summary.more_restrictive}")
        print(f"  ❌ NON_COMPLIANT:           {self.summary.non_compliant}")
        print(f"  ⚠️  MISSING_IN_MEL:         {self.summary.missing_in_mel}")
        print(f"  ➕ EXTRA_IN_MEL:            {self.summary.extra_in_mel}")
        print()

        # Score
        score = self.summary.compliance_score
        score_bar = "█" * int(score / 5) + "░" * (20 - int(score / 5))
        print(f"  SCORE DE CONFORMITÉ: [{score_bar}] {score:.1f}%")
        print()

        # Non-compliant details
        non_compliant = self.get_non_compliant_items()
        if non_compliant:
            print("-" * 70)
            print(f"TOP 10 ITEMS NON CONFORMES ({len(non_compliant)} total)")
            print("-" * 70)
            for i, r in enumerate(non_compliant[:10], 1):
                title = r.mel_data.get('itemTitle', 'N/A') if r.mel_data else 'N/A'
                print(f"\n  {i}. {r.item_code}: {title}")
                for issue in r.issues:
                    print(f"     ❌ {issue}")
                print(f"     MEL: interval={r.details.get('mel_interval')}, required={r.details.get('mel_required')}")
                print(f"     MMEL: interval={r.details.get('mmel_interval')}, required={r.details.get('mmel_required')}")
        else:
            print("-" * 70)
            print("✅ AUCUN ITEM NON CONFORME DÉTECTÉ")
            print("-" * 70)

        print()


def main():
    """Main entry point."""
    mmel_path = "output/parsed/mmel_pc12_structured.json"
    mel_path = "output/parsed/mel_pc12_structured.json"

    # Check files exist
    if not os.path.exists(mmel_path):
        print(f"ERREUR: Fichier MMEL non trouvé: {mmel_path}")
        return
    if not os.path.exists(mel_path):
        print(f"ERREUR: Fichier MEL non trouvé: {mel_path}")
        return

    # Run audit
    comparator = MelMmelComparator(mmel_path, mel_path)
    comparator.run_audit()

    # Generate reports
    comparator.generate_json_report("output/audit/audit_report.json")
    comparator.generate_markdown_report("output/audit/audit_report.md")
    comparator.generate_non_compliant_json("output/audit/non_compliant_items.json")

    # Print summary
    comparator.print_summary()

    print("=" * 70)
    print("RAPPORTS GÉNÉRÉS:")
    print("  - output/audit/audit_report.json")
    print("  - output/audit/audit_report.md")
    print("  - output/audit/non_compliant_items.json")
    print("=" * 70)


if __name__ == "__main__":
    main()
