#!/usr/bin/env python3
"""
MEL Parser - Parse raw MEL markdown to structured JSON.

Extracts structured data from PC-12 MEL (operator-specific) documents.
"""

import re
import json
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from collections import defaultdict


@dataclass
class MelItem:
    """Represents a single MEL item entry."""
    fullItemCode: str
    itemTitle: str
    ataChapter: str
    ataTitle: str
    operationTypes: List[str] = field(default_factory=list)
    category: Optional[str] = None
    numberInstalled: Optional[str] = None
    numberRequired: Optional[str] = None
    requiresMaintenance: bool = False
    requiresOperations: bool = False
    remarksText: str = ""
    conditions: List[str] = field(default_factory=list)
    procedures: List[str] = field(default_factory=list)
    airlineSpecific: Optional[str] = None
    isSubItem: bool = False
    parentItemCode: Optional[str] = None


@dataclass
class ValidationWarning:
    """Represents a validation warning."""
    item_code: str
    warning_type: str
    message: str


class MelParser:
    """Parser for MEL markdown documents."""

    def __init__(self, input_file: str):
        self.input_file = input_file
        self.items: List[MelItem] = []
        self.warnings: List[ValidationWarning] = []
        self.aircraft_registration = ""
        self.aircraft_msn = ""

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
            if stripped.startswith('MEL_PC-12'):
                continue
            if re.match(r'^ISS\d+\s+REV\d+', stripped):
                continue

            # Skip "cont'd" lines (table continuation markers) - handle both apostrophe types
            if re.match(r"^(cont[\u0027\u2019]d\s*)+$", stripped, re.IGNORECASE):
                continue

            # Skip copyright lines
            if stripped.startswith('© AMAC') or stripped.startswith('(C) AMAC'):
                continue

            # Skip column header lines
            if '1. System & Sequence numbers' in stripped:
                continue
            if stripped.startswith('1. System &'):
                continue

            cleaned_lines.append(line)

        return '\n'.join(cleaned_lines)

    def clean_remarks(self, remarks: str) -> str:
        """Clean garbage from remarks text."""
        # Remove everything after "cont'd" (table continuation marker indicates end of actual content)
        # Handle both straight apostrophe (U+0027) and curly apostrophe (U+2019)
        remarks = re.sub(r"\s*cont[\u0027\u2019]?d.*", '', remarks, flags=re.IGNORECASE | re.DOTALL)

        # Remove copyright and footer text (anywhere in string)
        remarks = re.sub(r'©\s*AMAC.*', '', remarks, flags=re.IGNORECASE)
        remarks = re.sub(r'\(C\)\s*AMAC.*', '', remarks, flags=re.IGNORECASE)

        # Remove column header remnants (more aggressive)
        remarks = re.sub(r'\.\s*Category.*', '', remarks, flags=re.IGNORECASE)
        remarks = re.sub(r'\.\s*System.*', '', remarks, flags=re.IGNORECASE)
        remarks = re.sub(r'\.\s*Item\s+\d.*', '', remarks, flags=re.IGNORECASE)
        remarks = re.sub(r'\.\s*Number.*', '', remarks, flags=re.IGNORECASE)
        remarks = re.sub(r'\.\s*Remarks.*', '', remarks, flags=re.IGNORECASE)
        remarks = re.sub(r'\d+\.\s*(System|Item|Category|Number|Remarks).*', '', remarks, flags=re.IGNORECASE)

        # Remove date patterns like "05.05.2023"
        remarks = re.sub(r'\d{2}\.\d{2}\.\d{4}', '', remarks)

        # Remove aircraft registration
        remarks = re.sub(r'\bHB-[A-Z]+\b', '', remarks)

        # Remove page number patterns
        remarks = re.sub(r'Page:\s*\d+\s*/\s*\d+', '', remarks)

        # Remove "Item Base Relief" table header text
        remarks = re.sub(r'Item Base Relief', '', remarks)

        # Clean up multiple spaces and trim
        remarks = re.sub(r'\s+', ' ', remarks).strip()

        # Remove trailing punctuation artifacts
        remarks = re.sub(r'\s*[.,;]\s*$', '', remarks)

        # Remove trailing isolated digits (page remnants)
        remarks = re.sub(r'\s+\d+\s*$', '', remarks)

        return remarks

    def extract_operation_types(self, text: str) -> List[str]:
        """Extract operation types from text: (CAT), (NCO), (SPO), (ALL)."""
        op_types = []

        # Look for explicit operation type markers
        if '(CAT)' in text or 'CAT' in text.upper():
            if re.search(r'\bCAT\b', text):
                op_types.append('CAT')
        if '(NCO)' in text:
            op_types.append('NCO')
        if '(SPO)' in text:
            op_types.append('SPO')
        if '(ALL)' in text:
            op_types.append('ALL')

        # Also check for combined format like (CAT/NCO)
        combined_match = re.search(r'\(([A-Z]+(?:/[A-Z]+)+)\)', text)
        if combined_match:
            op_types.extend(combined_match.group(1).split('/'))

        return list(set(op_types)) if op_types else []

    def parse(self) -> List[Dict[str, Any]]:
        """Parse the MEL markdown file using MULTILINE regex approach."""
        with open(self.input_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract aircraft info before preprocessing
        reg_match = re.search(r'^(HB-[A-Z]+)', content, re.MULTILINE)
        if reg_match:
            self.aircraft_registration = reg_match.group(1)

        msn_match = re.search(r'\(MSN\s*(\d+)\)', content)
        if msn_match:
            self.aircraft_msn = msn_match.group(1)

        # Pre-process content
        content = self.preprocess_content(content)

        # Pre-process: join split item codes
        content = re.sub(r'(\d{2}-\d{2}-)\n(\d{2}(?:-\d+)?[A-Z])', r'\1\2', content)

        # Find all sub-items using MULTILINE regex
        sub_item_pattern = re.compile(
            r'^(\d{2}-\d{2}-\d{2}(?:-\d+)?[A-Z])\s*'
            r'(?:\(Cont\'?d\)\s*)?'
            r'([ABCD])\s+'
            r'([\d-]+)\s+'
            r'(\d+)\s*'
            r'(\(M\))?\s*(\(O\))?\s*'
            r'(.*)$',
            re.MULTILINE
        )

        # Find all ATA chapters (format: "21 AIR CONDITIONING AND PRESSURIZATION")
        ata_pattern = re.compile(r'^(\d{2})\s+([A-Z][A-Z /&]+)$', re.MULTILINE)
        ata_chapters = [(m.start(), m.group(1), m.group(2).strip()) for m in ata_pattern.finditer(content)]

        # Find all main item titles (format: "21-30-01 Cabin pressurization system")
        item_title_pattern = re.compile(
            r'^(\d{2}-\d{2}-\d{2}(?:-\d+)?)\s+([A-Z][a-zA-Z][^\n]*?)$',
            re.MULTILINE
        )
        item_titles = [(m.start(), m.group(1), m.group(2).strip()) for m in item_title_pattern.finditer(content)]

        # Find all sub-items with positions
        sub_items = [(m.start(), m) for m in sub_item_pattern.finditer(content)]

        # Next item pattern for finding remarks end
        next_item_pattern = re.compile(r'^\d{2}-\d{2}-\d{2}', re.MULTILINE)

        def get_context(pos):
            """Get ATA chapter and item title for a given position."""
            ata_ch, ata_title = "", ""
            item_title = ""

            for start, ch, title in ata_chapters:
                if start < pos:
                    ata_ch, ata_title = ch, title
                else:
                    break

            for start, code, title in item_titles:
                if start < pos:
                    item_title = title
                else:
                    break

            return ata_ch, ata_title, item_title

        # Condition pattern
        condition_pattern = re.compile(r'\n([a-z])\.\s*([^\n]+)')

        for idx, (pos, match) in enumerate(sub_items):
            ata_ch, ata_title, item_title = get_context(pos)

            full_code = match.group(1)
            category = match.group(2)
            num_installed = match.group(3)
            num_required = match.group(4)
            m_flag = match.group(5)
            o_flag = match.group(6)
            initial_remarks = match.group(7) or ""

            # Find end position for context block
            end_pos = match.end()
            next_pos = sub_items[idx + 1][0] if idx + 1 < len(sub_items) else len(content)

            # Also check for next ATA chapter
            for ata_start, _, _ in ata_chapters:
                if ata_start > end_pos and ata_start < next_pos:
                    next_pos = ata_start
                    break

            context_block = content[end_pos:next_pos]

            # Extract full remarks (until first condition or next item)
            remarks_parts = [initial_remarks] if initial_remarks else []

            # Split context block into lines
            context_lines = context_block.split('\n')
            in_conditions = False

            for line in context_lines:
                stripped = line.strip()
                if not stripped:
                    continue

                # Check if we hit a condition
                if re.match(r'^[a-z]\.\s', stripped):
                    in_conditions = True
                    break

                # Check if we hit a new item
                if re.match(r'^\d{2}-\d{2}-\d{2}', stripped):
                    break

                # Check if we hit an ATA header
                if re.match(r'^\d{2}\s+[A-Z][A-Z]', stripped):
                    break

                # Otherwise, it's part of remarks
                if not in_conditions:
                    remarks_parts.append(stripped)

            # Join remarks and clean garbage
            full_remarks = ' '.join(remarks_parts).strip()
            full_remarks = re.sub(r'\s+', ' ', full_remarks)
            full_remarks = self.clean_remarks(full_remarks)

            # Extract conditions
            conditions = []
            for cond_match in condition_pattern.finditer(context_block):
                letter = cond_match.group(1)
                text = cond_match.group(2).strip()
                if not text.startswith('HB-') and not text.startswith('Page:'):
                    conditions.append(f"{letter}. {text}")

            # Extract operation types from remarks and conditions
            op_types = self.extract_operation_types(full_remarks)
            for cond in conditions:
                op_types.extend(self.extract_operation_types(cond))
            op_types = list(set(op_types))

            # Extract parent code
            parent_match = re.match(r'^(\d{2}-\d{2}-\d{2}(?:-\d+)?)', full_code)
            parent_code = parent_match.group(1) if parent_match else ""

            item = MelItem(
                fullItemCode=full_code,
                itemTitle=item_title,
                ataChapter=ata_ch,
                ataTitle=ata_title,
                operationTypes=op_types,
                category=category,
                numberInstalled=num_installed,
                numberRequired=num_required,
                requiresMaintenance=bool(m_flag),
                requiresOperations=bool(o_flag),
                remarksText=full_remarks,
                conditions=conditions,
                procedures=[],
                airlineSpecific=f"AMAC Corporate Jet - {self.aircraft_registration}" if self.aircraft_registration else None,
                isSubItem=True,
                parentItemCode=parent_code
            )
            self.items.append(item)

        # Run validation
        self._validate_items()

        return [asdict(item) for item in self.items]

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

            # Check for empty operation types (info only, not a warning for MEL)
            # MEL might not have operation types as they are operator-specific

    def get_statistics(self) -> Dict[str, Any]:
        """Generate statistics about parsed items."""
        stats = {
            'total_items': len(self.items),
            'aircraft_registration': self.aircraft_registration,
            'aircraft_msn': self.aircraft_msn,
            'items_by_chapter': defaultdict(int),
            'items_by_category': defaultdict(int),
            'items_by_operation_type': defaultdict(int),
            'items_requiring_maintenance': 0,
            'items_requiring_operations': 0,
            'items_with_operation_types': 0,
            'items_without_operation_types': 0,
        }

        for item in self.items:
            chapter_key = f"ATA {item.ataChapter} - {item.ataTitle}"
            stats['items_by_chapter'][chapter_key] += 1

            if item.category:
                stats['items_by_category'][item.category] += 1

            if item.operationTypes:
                stats['items_with_operation_types'] += 1
                for op_type in item.operationTypes:
                    stats['items_by_operation_type'][op_type] += 1
            else:
                stats['items_without_operation_types'] += 1

            if item.requiresMaintenance:
                stats['items_requiring_maintenance'] += 1

            if item.requiresOperations:
                stats['items_requiring_operations'] += 1

        stats['items_by_chapter'] = dict(stats['items_by_chapter'])
        stats['items_by_category'] = dict(stats['items_by_category'])
        stats['items_by_operation_type'] = dict(stats['items_by_operation_type'])

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
    input_file = "output/parsed/mel_pc12_raw.md"
    output_file = "output/parsed/mel_pc12_structured.json"
    mmel_file = "output/parsed/mmel_pc12_structured.json"

    if not os.path.exists(input_file):
        print(f"ERREUR: Fichier d'entrée non trouvé: {input_file}")
        return

    print(f"Parsing MEL from: {input_file}")
    print("=" * 60)

    parser = MelParser(input_file)
    items = parser.parse()
    stats = parser.get_statistics()
    validation = parser.get_validation_report()

    output_data = {
        'metadata': {
            'source_file': input_file,
            'total_items': stats['total_items'],
            'aircraft_registration': stats['aircraft_registration'],
            'aircraft_msn': stats['aircraft_msn'],
            'operator': 'AMAC Corporate Jet',
            'defaultOperationType': 'NCO'  # Non-Commercial Operations (private aircraft HB-FVT)
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

    print(f"\nAIRCRAFT: {stats['aircraft_registration']} (MSN {stats['aircraft_msn']})")
    print("\nSTATISTIQUES MEL:")
    print(f"  Total items parsés: {stats['total_items']}")
    print(f"  Items nécessitant maintenance (M): {stats['items_requiring_maintenance']}")
    print(f"  Items nécessitant opérations (O): {stats['items_requiring_operations']}")
    print(f"  Items avec operation types: {stats['items_with_operation_types']}")
    print(f"  Items sans operation types: {stats['items_without_operation_types']}")

    print("\nITEMS PAR CHAPITRE ATA:")
    print("-" * 60)
    for chapter, count in sorted(stats['items_by_chapter'].items()):
        print(f"  {chapter}: {count}")

    print("\nITEMS PAR CATÉGORIE (intervalle de rectification):")
    print("-" * 60)
    for cat, count in sorted(stats['items_by_category'].items()):
        print(f"  {cat}: {count}")

    if stats['items_by_operation_type']:
        print("\nITEMS PAR TYPE D'OPÉRATION:")
        print("-" * 60)
        for op_type, count in sorted(stats['items_by_operation_type'].items()):
            print(f"  {op_type}: {count}")

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

    # Compare with MMEL
    if os.path.exists(mmel_file):
        print("\n" + "=" * 60)
        print("COMPARAISON MEL vs MMEL:")
        print("=" * 60)

        with open(mmel_file, 'r') as f:
            mmel_data = json.load(f)

        mmel_total = mmel_data['statistics']['total_items']
        mel_total = stats['total_items']

        print(f"\n  MMEL items: {mmel_total}")
        print(f"  MEL items:  {mel_total}")
        print(f"  Différence: {mel_total - mmel_total}")

        # Compare by category
        print("\n  Par catégorie:")
        mmel_cats = mmel_data['statistics'].get('items_by_rectification', {})
        mel_cats = stats['items_by_category']
        for cat in ['A', 'B', 'C', 'D']:
            mmel_count = mmel_cats.get(cat, 0)
            mel_count = mel_cats.get(cat, 0)
            diff = mel_count - mmel_count
            print(f"    {cat}: MMEL={mmel_count}, MEL={mel_count}, diff={diff:+d}")

    # Show sample items
    print("\n" + "=" * 60)
    print("EXEMPLES D'ITEMS MEL (5 premiers):")
    print("=" * 60)
    for item in items[:5]:
        print(f"\n{item['fullItemCode']}:")
        print(f"  Title: {item['itemTitle']}")
        print(f"  ATA: {item['ataChapter']} - {item['ataTitle']}")
        print(f"  Category: {item['category']}")
        print(f"  Operation Types: {item['operationTypes']}")
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
