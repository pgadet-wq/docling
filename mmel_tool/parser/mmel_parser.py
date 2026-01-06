#!/usr/bin/env python3
"""
MMEL Parser - Parse raw MMEL markdown to structured JSON.

Extracts structured data from PC-12 MMEL documents including:
- ATA chapters and titles
- Item codes and titles
- Operation types (CAT, NCO, SPO, ALL)
- MSN effectivity ranges
- Rectification intervals
- Maintenance and operations flags
- Remarks and conditions
"""

import re
import json
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict


@dataclass
class MmelItem:
    """Represents a single MMEL item entry."""
    fullItemCode: str
    itemTitle: str
    ataChapter: str
    ataTitle: str
    operationTypes: List[str] = field(default_factory=list)
    msnEffectivity: Optional[str] = None
    rectificationInterval: Optional[str] = None
    numberInstalled: Optional[str] = None
    numberRequired: Optional[str] = None
    requiresMaintenance: bool = False
    requiresOperations: bool = False
    remarksText: str = ""
    conditions: List[str] = field(default_factory=list)
    note: Optional[str] = None
    isSubItem: bool = False
    parentItemCode: Optional[str] = None


@dataclass
class ValidationWarning:
    """Represents a validation warning."""
    item_code: str
    warning_type: str
    message: str


class MmelParser:
    """Parser for MMEL markdown documents."""

    def __init__(self, input_file: str):
        """Initialize parser with input file path."""
        self.input_file = input_file
        self.items: List[MmelItem] = []
        self.warnings: List[ValidationWarning] = []

    def preprocess_content(self, content: str) -> str:
        """Remove page markers, headers, and footers."""
        lines = content.split('\n')
        cleaned_lines = []

        for line in lines:
            stripped = line.strip()

            # Skip page markers
            if re.match(r'^##\s*Page\s+\d+', stripped, re.IGNORECASE):
                continue
            if re.match(r'^Page\s+\d+\s+of\s+\d+', stripped, re.IGNORECASE):
                continue
            if re.match(r'^Page:\s*\d+', stripped, re.IGNORECASE):
                continue

            # Skip common headers/footers
            if stripped.startswith('Document Number:'):
                continue
            if stripped.startswith('Issue date:'):
                continue
            if 'EASA approved' in stripped:
                continue
            if stripped == 'ITEM':
                continue
            if stripped == '(continued)':
                continue
            if re.match(r'^Revision:\s*\d+', stripped):
                continue
            if re.match(r'^\d{4}-\d{2}-\d{2}$', stripped):  # Date only lines
                continue

            cleaned_lines.append(line)

        return '\n'.join(cleaned_lines)

    def parse(self) -> List[Dict[str, Any]]:
        """Parse the MMEL markdown file and return structured data."""
        with open(self.input_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Pre-process content
        content = self.preprocess_content(content)

        # Current context
        current_ata_chapter = ""
        current_ata_title = ""
        current_item_title = ""
        current_note = ""

        # Regex patterns
        ata_pattern = re.compile(r'ATA CHAPTER:\s*(\d+)\s+([A-Za-z][^\n]+)')

        # Main item title: XX-XX-XX or XX-XX-XX-X followed by title (no letter suffix)
        item_title_pattern = re.compile(
            r'^(\d{2}-\d{2}-\d{2}(?:-\d+)?)\s+'  # Item code
            r'([A-Z][^(\n]*?)'  # Title starting with capital letter
            r'(?:\s*\(\*{3}\))?'  # Optional (***)
            r'(?:\s*Note:\s*(.+))?$'  # Optional Note
        )

        # Sub-item pattern: XX-XX-XX[A-Z] with operation type and details
        sub_item_pattern = re.compile(
            r'^(\d{2}-\d{2}-\d{2}(?:-\d+)?[A-Z])\s+'  # Item code with letter
            r'(?:\(([A-Z/]+)\)\s*)?'  # Operation type
            r'(?:\((MSN[^)]+)\)\s*)?'  # MSN effectivity
            r'([ABCD-])\s+'  # Rectification interval
            r'([\d-]+)\s+'  # Number installed
            r'(\d+)\s*'  # Number required
            r'(\(M\))?\s*(\(O\))?\s*'  # Flags
            r'(.*)$'  # Remarks
        )

        # Condition pattern
        condition_pattern = re.compile(r'^\(([a-z])\)\s*(.+)$')

        # Next item pattern to detect end of remarks
        next_item_pattern = re.compile(r'^\d{2}-\d{2}-\d{2}')

        # Process line by line
        lines = content.split('\n')
        i = 0
        total_lines = len(lines)

        while i < total_lines:
            line = lines[i].strip()

            # Skip empty lines
            if not line:
                i += 1
                continue

            # Check for ATA chapter
            ata_match = ata_pattern.search(line)
            if ata_match:
                current_ata_chapter = ata_match.group(1)
                current_ata_title = ata_match.group(2).strip().rstrip('.')
                i += 1
                continue

            # Skip if no ATA chapter yet
            if not current_ata_chapter:
                i += 1
                continue

            # Check for main item title (no letter suffix in code)
            if re.match(r'^\d{2}-\d{2}-\d{2}(?:-\d+)?\s+[A-Z]', line):
                # Check it's not a sub-item (has letter suffix)
                code_match = re.match(r'^(\d{2}-\d{2}-\d{2}(?:-\d+)?)([A-Z])?', line)
                if code_match and not code_match.group(2):
                    # This is a main item title
                    title_match = item_title_pattern.match(line)
                    if title_match:
                        current_item_title = title_match.group(2).strip()
                        current_note = title_match.group(3) or ""
                    else:
                        # Extract title manually
                        parts = line.split(None, 1)
                        if len(parts) > 1:
                            current_item_title = parts[1].split('Note:')[0].strip()
                            if 'Note:' in line:
                                current_note = line.split('Note:')[1].strip()
                            else:
                                current_note = ""
                    i += 1
                    continue

            # Check for sub-item
            sub_match = sub_item_pattern.match(line)
            if sub_match:
                item = self._create_item(
                    sub_match, current_ata_chapter, current_ata_title,
                    current_item_title, current_note
                )

                # Collect conditions and full remarks from following lines
                conditions = []
                remarks_parts = [item.remarksText] if item.remarksText else []
                j = i + 1

                while j < total_lines:
                    next_line = lines[j].strip()

                    if not next_line:
                        j += 1
                        continue

                    # Check if next item or section starts
                    if next_item_pattern.match(next_line):
                        break
                    if next_line.startswith('ATA CHAPTER'):
                        break

                    # Check for condition
                    cond_match = condition_pattern.match(next_line)
                    if cond_match:
                        cond_text = cond_match.group(2)
                        # Check for continuation on next lines
                        k = j + 1
                        while k < total_lines:
                            cont_line = lines[k].strip()
                            if not cont_line:
                                k += 1
                                continue
                            if condition_pattern.match(cont_line):
                                break
                            if next_item_pattern.match(cont_line):
                                break
                            if cont_line.startswith('ATA CHAPTER'):
                                break
                            # Skip header remnants
                            if cont_line.startswith('(1)') or cont_line.startswith('(2)'):
                                k += 1
                                continue
                            cond_text += ' ' + cont_line
                            k += 1
                        conditions.append(f"({cond_match.group(1)}) {cond_text.strip()}")
                        j = k
                        continue

                    # Skip header table remnants
                    if next_line.startswith('(1)') or next_line.startswith('(2)'):
                        j += 1
                        continue

                    # Otherwise, might be remarks continuation
                    remarks_parts.append(next_line)
                    j += 1

                item.conditions = conditions

                # Join remarks properly
                full_remarks = ' '.join(remarks_parts).strip()
                # Clean up double spaces
                full_remarks = re.sub(r'\s+', ' ', full_remarks)
                item.remarksText = full_remarks

                self.items.append(item)
                i = j
                continue

            # Check for multi-line sub-item (code on one line, details on next)
            if re.match(r'^\d{2}-\d{2}-\d{2}(?:-\d+)?[A-Z]\s+\([A-Z/]+\)', line):
                # Might be a split item, try to combine with next line
                combined = line
                if i + 1 < total_lines:
                    next_line = lines[i + 1].strip()
                    if re.match(r'^[ABCD-]\s+[\d-]+\s+\d+', next_line):
                        combined = line + ' ' + next_line
                        sub_match = sub_item_pattern.match(combined)
                        if sub_match:
                            item = self._create_item(
                                sub_match, current_ata_chapter, current_ata_title,
                                current_item_title, current_note
                            )
                            self.items.append(item)
                            i += 2
                            continue

            i += 1

        # Run validation
        self._validate_items()

        return [asdict(item) for item in self.items]

    def _create_item(self, match: re.Match, ata_chapter: str, ata_title: str,
                     item_title: str, note: str) -> MmelItem:
        """Create an MmelItem from a regex match."""
        full_code = match.group(1)
        op_types_str = match.group(2) or "ALL"
        msn = match.group(3)
        rect_interval = match.group(4)
        num_installed = match.group(5)
        num_required = match.group(6)
        m_flag = match.group(7)
        o_flag = match.group(8)
        remarks = match.group(9) or ""

        # Parse operation types
        op_types = [t.strip() for t in op_types_str.split('/')]

        # Extract parent item code
        parent_match = re.match(r'^(\d{2}-\d{2}-\d{2}(?:-\d+)?)', full_code)
        parent_code = parent_match.group(1) if parent_match else ""

        return MmelItem(
            fullItemCode=full_code,
            itemTitle=item_title,
            ataChapter=ata_chapter,
            ataTitle=ata_title,
            operationTypes=op_types,
            msnEffectivity=msn.strip() if msn else None,
            rectificationInterval=rect_interval if rect_interval != '-' else None,
            numberInstalled=num_installed,
            numberRequired=num_required,
            requiresMaintenance=bool(m_flag),
            requiresOperations=bool(o_flag),
            remarksText=remarks.strip(),
            conditions=[],
            note=note if note else None,
            isSubItem=True,
            parentItemCode=parent_code
        )

    def _validate_items(self) -> None:
        """Validate parsed items and generate warnings."""
        truncation_patterns = [
            (r'provided\s*$', 'ends with "provided"'),
            (r'\bthat\s*$', 'ends with "that"'),
            (r'\band\s*$', 'ends with "and"'),
            (r'\bor\s*$', 'ends with "or"'),
            (r'\bthe\s*$', 'ends with "the"'),
            (r'\bis\s*$', 'ends with "is"'),
            (r'\bare\s*$', 'ends with "are"'),
            (r':\s*$', 'ends with ":"'),
        ]

        for item in self.items:
            # Check for truncated remarks
            remarks = item.remarksText.strip()
            for pattern, msg in truncation_patterns:
                if re.search(pattern, remarks, re.IGNORECASE):
                    self.warnings.append(ValidationWarning(
                        item_code=item.fullItemCode,
                        warning_type='TRUNCATED_REMARKS',
                        message=f'Remarks may be truncated: {msg}'
                    ))
                    break

            # Check for page markers in remarks
            if '## Page' in remarks or 'Page ' in remarks:
                self.warnings.append(ValidationWarning(
                    item_code=item.fullItemCode,
                    warning_type='PAGE_MARKER_IN_REMARKS',
                    message='Remarks contain page marker'
                ))

            # Check for empty operation types
            if not item.operationTypes or item.operationTypes == ['']:
                self.warnings.append(ValidationWarning(
                    item_code=item.fullItemCode,
                    warning_type='MISSING_OPERATION_TYPES',
                    message='No operation types found'
                ))

    def get_statistics(self) -> Dict[str, Any]:
        """Generate statistics about parsed items."""
        stats = {
            'total_items': len(self.items),
            'items_by_chapter': defaultdict(int),
            'items_by_operation_type': defaultdict(int),
            'items_by_rectification': defaultdict(int),
            'items_requiring_maintenance': 0,
            'items_requiring_operations': 0,
            'items_with_msn_effectivity': 0,
        }

        for item in self.items:
            chapter_key = f"ATA {item.ataChapter} - {item.ataTitle}"
            stats['items_by_chapter'][chapter_key] += 1

            for op_type in item.operationTypes:
                stats['items_by_operation_type'][op_type] += 1

            if item.rectificationInterval:
                stats['items_by_rectification'][item.rectificationInterval] += 1

            if item.requiresMaintenance:
                stats['items_requiring_maintenance'] += 1

            if item.requiresOperations:
                stats['items_requiring_operations'] += 1

            if item.msnEffectivity:
                stats['items_with_msn_effectivity'] += 1

        stats['items_by_chapter'] = dict(stats['items_by_chapter'])
        stats['items_by_operation_type'] = dict(stats['items_by_operation_type'])
        stats['items_by_rectification'] = dict(stats['items_by_rectification'])

        return stats

    def get_validation_report(self) -> Dict[str, Any]:
        """Generate validation report."""
        report = {
            'total_warnings': len(self.warnings),
            'warnings_by_type': defaultdict(int),
            'items_with_warnings': set(),
            'warnings': []
        }

        for w in self.warnings:
            report['warnings_by_type'][w.warning_type] += 1
            report['items_with_warnings'].add(w.item_code)
            report['warnings'].append({
                'item_code': w.item_code,
                'type': w.warning_type,
                'message': w.message
            })

        report['warnings_by_type'] = dict(report['warnings_by_type'])
        report['items_with_warnings'] = list(report['items_with_warnings'])

        return report


def main():
    """Main entry point."""
    input_file = "output/parsed/mmel_pc12_raw.md"
    output_file = "output/parsed/mmel_pc12_structured.json"

    if not os.path.exists(input_file):
        print(f"ERREUR: Fichier d'entrée non trouvé: {input_file}")
        return

    print(f"Parsing MMEL from: {input_file}")
    print("=" * 60)

    parser = MmelParser(input_file)
    items = parser.parse()
    stats = parser.get_statistics()
    validation = parser.get_validation_report()

    output_data = {
        'metadata': {
            'source_file': input_file,
            'total_items': stats['total_items'],
        },
        'statistics': stats,
        'validation': validation,
        'items': items
    }

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"Fichier JSON sauvegardé: {output_file}")
    print("=" * 60)

    print("\nSTATISTIQUES:")
    print(f"  Total items parsés: {stats['total_items']}")
    print(f"  Items nécessitant maintenance (M): {stats['items_requiring_maintenance']}")
    print(f"  Items nécessitant opérations (O): {stats['items_requiring_operations']}")
    print(f"  Items avec MSN effectivity: {stats['items_with_msn_effectivity']}")

    print("\nITEMS PAR CHAPITRE ATA:")
    print("-" * 60)
    for chapter, count in sorted(stats['items_by_chapter'].items()):
        print(f"  {chapter}: {count}")

    print("\nITEMS PAR TYPE D'OPÉRATION:")
    print("-" * 60)
    for op_type, count in sorted(stats['items_by_operation_type'].items()):
        print(f"  {op_type}: {count}")

    print("\nITEMS PAR INTERVALLE DE RECTIFICATION:")
    print("-" * 60)
    for interval, count in sorted(stats['items_by_rectification'].items()):
        print(f"  {interval}: {count}")

    # Validation report
    print("\n" + "=" * 60)
    print("RAPPORT DE VALIDATION:")
    print("=" * 60)
    print(f"  Total avertissements: {validation['total_warnings']}")
    print(f"  Items avec avertissements: {len(validation['items_with_warnings'])}")

    if validation['warnings_by_type']:
        print("\n  Par type:")
        for wtype, count in validation['warnings_by_type'].items():
            print(f"    {wtype}: {count}")

    if validation['warnings'][:10]:
        print("\n  Premiers avertissements:")
        for w in validation['warnings'][:10]:
            print(f"    [{w['item_code']}] {w['type']}: {w['message']}")

    print("\n" + "=" * 60)
    print("EXEMPLES D'ITEMS PARSÉS (5 premiers):")
    print("=" * 60)
    for item in items[:5]:
        print(f"\n{item['fullItemCode']}:")
        print(f"  Title: {item['itemTitle']}")
        print(f"  ATA: {item['ataChapter']} - {item['ataTitle']}")
        print(f"  Operations: {item['operationTypes']}")
        print(f"  MSN: {item['msnEffectivity']}")
        print(f"  Rectification: {item['rectificationInterval']}")
        print(f"  Installed/Required: {item['numberInstalled']}/{item['numberRequired']}")
        print(f"  (M): {item['requiresMaintenance']}, (O): {item['requiresOperations']}")
        remarks = item['remarksText']
        print(f"  Remarks: {remarks[:80]}..." if len(remarks) > 80 else f"  Remarks: {remarks}")
        if item['conditions']:
            print(f"  Conditions ({len(item['conditions'])}):")
            for cond in item['conditions'][:3]:
                print(f"    - {cond[:60]}..." if len(cond) > 60 else f"    - {cond}")


if __name__ == "__main__":
    main()
