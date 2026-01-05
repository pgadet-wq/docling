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


class MelParser:
    """Parser for MEL markdown documents."""

    def __init__(self, input_file: str):
        self.input_file = input_file
        self.items: List[MelItem] = []
        self.aircraft_registration = ""
        self.aircraft_msn = ""

    def parse(self) -> List[Dict[str, Any]]:
        """Parse the MEL markdown file using MULTILINE regex approach."""
        with open(self.input_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract aircraft info
        reg_match = re.search(r'^(HB-[A-Z]+)', content, re.MULTILINE)
        if reg_match:
            self.aircraft_registration = reg_match.group(1)

        msn_match = re.search(r'\(MSN\s*(\d+)\)', content)
        if msn_match:
            self.aircraft_msn = msn_match.group(1)

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
            remarks = match.group(7) or ""

            # Find conditions between this item and the next
            end_pos = match.end()
            next_pos = sub_items[idx + 1][0] if idx + 1 < len(sub_items) else len(content)

            context_block = content[end_pos:next_pos]
            conditions = []
            for cond_match in condition_pattern.finditer(context_block):
                letter = cond_match.group(1)
                text = cond_match.group(2).strip()
                if not text.startswith('HB-') and not text.startswith('Page:'):
                    conditions.append(f"{letter}. {text}")

            # Extract parent code
            parent_match = re.match(r'^(\d{2}-\d{2}-\d{2}(?:-\d+)?)', full_code)
            parent_code = parent_match.group(1) if parent_match else ""

            item = MelItem(
                fullItemCode=full_code,
                itemTitle=item_title,
                ataChapter=ata_ch,
                ataTitle=ata_title,
                category=category,
                numberInstalled=num_installed,
                numberRequired=num_required,
                requiresMaintenance=bool(m_flag),
                requiresOperations=bool(o_flag),
                remarksText=remarks.strip(),
                conditions=conditions,
                procedures=[],
                airlineSpecific=f"AMAC Corporate Jet - {self.aircraft_registration}" if self.aircraft_registration else None,
                isSubItem=True,
                parentItemCode=parent_code
            )
            self.items.append(item)

        return [asdict(item) for item in self.items]

    def get_statistics(self) -> Dict[str, Any]:
        """Generate statistics about parsed items."""
        stats = {
            'total_items': len(self.items),
            'aircraft_registration': self.aircraft_registration,
            'aircraft_msn': self.aircraft_msn,
            'items_by_chapter': defaultdict(int),
            'items_by_category': defaultdict(int),
            'items_requiring_maintenance': 0,
            'items_requiring_operations': 0,
        }

        for item in self.items:
            chapter_key = f"ATA {item.ataChapter} - {item.ataTitle}"
            stats['items_by_chapter'][chapter_key] += 1

            if item.category:
                stats['items_by_category'][item.category] += 1

            if item.requiresMaintenance:
                stats['items_requiring_maintenance'] += 1

            if item.requiresOperations:
                stats['items_requiring_operations'] += 1

        stats['items_by_chapter'] = dict(stats['items_by_chapter'])
        stats['items_by_category'] = dict(stats['items_by_category'])

        return stats


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

    output_data = {
        'metadata': {
            'source_file': input_file,
            'total_items': stats['total_items'],
            'aircraft_registration': stats['aircraft_registration'],
            'aircraft_msn': stats['aircraft_msn'],
            'operator': 'AMAC Corporate Jet'
        },
        'statistics': stats,
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

    print("\nITEMS PAR CHAPITRE ATA:")
    print("-" * 60)
    for chapter, count in sorted(stats['items_by_chapter'].items()):
        print(f"  {chapter}: {count}")

    print("\nITEMS PAR CATÉGORIE (intervalle de rectification):")
    print("-" * 60)
    for cat, count in sorted(stats['items_by_category'].items()):
        print(f"  {cat}: {count}")

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
