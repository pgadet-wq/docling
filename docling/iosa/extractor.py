"""IOSA Standards Extractor
===========================

Extracts IOSA compliance standards and requirements from aviation documents.

IOSA Standard Codes:
- ORG: Organization and Management System
- FLT: Flight Operations
- DSP: Operational Control and Flight Dispatch
- MNT: Aircraft Engineering and Maintenance
- CAB: Cabin Operations
- GRH: Ground Handling
- CGO: Cargo Operations
- SEC: Security Management
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Pattern, Set, Tuple

from docling_core.types.doc import DoclingDocument, TextItem

from docling.iosa.models import (
    ComplianceItem,
    ComplianceStatus,
    IOSASection,
    IOSAStandardCode,
)

_log = logging.getLogger(__name__)


class IOSAStandard(str, Enum):
    """IOSA Standard areas."""

    ORG = "ORG"
    FLT = "FLT"
    DSP = "DSP"
    MNT = "MNT"
    CAB = "CAB"
    GRH = "GRH"
    CGO = "CGO"
    SEC = "SEC"


@dataclass
class StandardPattern:
    """Pattern for matching IOSA standards."""

    code: IOSAStandard
    pattern: Pattern
    description: str


class IOSAExtractor:
    """Extracts IOSA standards and compliance items from documents.

    This extractor identifies:
    - Standard reference codes (e.g., ORG 1.1.1, FLT 2.3.4)
    - Requirement text with "shall", "should", "may" indicators
    - Guidance material (GM) references
    - Cross-references between standards
    """

    # Standard code patterns
    STANDARD_PATTERNS = {
        IOSAStandard.ORG: r"ORG\s*[\d\.]+",
        IOSAStandard.FLT: r"FLT\s*[\d\.]+",
        IOSAStandard.DSP: r"DSP\s*[\d\.]+",
        IOSAStandard.MNT: r"MNT\s*[\d\.]+",
        IOSAStandard.CAB: r"CAB\s*[\d\.]+",
        IOSAStandard.GRH: r"GRH\s*[\d\.]+",
        IOSAStandard.CGO: r"CGO\s*[\d\.]+",
        IOSAStandard.SEC: r"SEC\s*[\d\.]+",
    }

    # Combined pattern for any standard reference
    ANY_STANDARD_PATTERN = re.compile(
        r"(ORG|FLT|DSP|MNT|CAB|GRH|CGO|SEC)\s*([\d]+(?:\.[\d]+)*)",
        re.IGNORECASE,
    )

    # Requirement priority patterns
    SHALL_PATTERN = re.compile(r"\bshall\b", re.IGNORECASE)
    SHOULD_PATTERN = re.compile(r"\bshould\b", re.IGNORECASE)
    MAY_PATTERN = re.compile(r"\bmay\b", re.IGNORECASE)

    # Guidance material pattern
    GM_PATTERN = re.compile(r"GM\s*([\d]+(?:\.[\d]+)*)", re.IGNORECASE)

    # Reference patterns
    REFERENCE_PATTERN = re.compile(
        r"(?:refer(?:s|ence)?(?:\s+to)?|see|per)\s+"
        r"(ORG|FLT|DSP|MNT|CAB|GRH|CGO|SEC)\s*([\d]+(?:\.[\d]+)*)",
        re.IGNORECASE,
    )

    def __init__(
        self,
        target_standards: Optional[List[IOSAStandard]] = None,
        extract_guidance: bool = True,
        extract_references: bool = True,
    ):
        """Initialize the extractor.

        Args:
            target_standards: Standards to extract (None = all)
            extract_guidance: Whether to extract guidance material
            extract_references: Whether to extract cross-references
        """
        self.target_standards = target_standards or list(IOSAStandard)
        self.extract_guidance = extract_guidance
        self.extract_references = extract_references

        # Compile patterns for target standards
        self._compiled_patterns: Dict[IOSAStandard, Pattern] = {}
        for std in self.target_standards:
            pattern_str = self.STANDARD_PATTERNS.get(std)
            if pattern_str:
                self._compiled_patterns[std] = re.compile(pattern_str, re.IGNORECASE)

    def extract_from_document(
        self, document: DoclingDocument
    ) -> Tuple[List[ComplianceItem], List[IOSASection]]:
        """Extract IOSA standards from a DoclingDocument.

        Args:
            document: Parsed DoclingDocument

        Returns:
            Tuple of (compliance_items, sections)
        """
        compliance_items: List[ComplianceItem] = []
        sections: List[IOSASection] = []
        current_section: Optional[IOSASection] = None

        # Track found standards to avoid duplicates
        found_standards: Set[str] = set()

        # Iterate through document items
        for item, level in document.iterate_items():
            if isinstance(item, TextItem):
                text = item.text if hasattr(item, "text") else str(item)
                page_no = self._get_page_number(item)

                # Check for section headers
                if self._is_section_header(item, level):
                    if current_section:
                        sections.append(current_section)
                    current_section = self._create_section(item, text, page_no, level)

                # Extract standard references
                items = self._extract_standards_from_text(text, page_no, found_standards)
                compliance_items.extend(items)

                # Add to current section
                if current_section and items:
                    current_section.compliance_items.extend(items)

        # Add final section
        if current_section:
            sections.append(current_section)

        _log.info(
            f"Extracted {len(compliance_items)} compliance items, "
            f"{len(sections)} sections"
        )

        return compliance_items, sections

    def extract_from_text(self, text: str, page_no: int = 0) -> List[ComplianceItem]:
        """Extract IOSA standards from raw text.

        Args:
            text: Text to extract from
            page_no: Page number for reference

        Returns:
            List of extracted compliance items
        """
        found_standards: Set[str] = set()
        return self._extract_standards_from_text(text, page_no, found_standards)

    def _extract_standards_from_text(
        self,
        text: str,
        page_no: int,
        found_standards: Set[str],
    ) -> List[ComplianceItem]:
        """Extract standards from text content.

        Args:
            text: Text to extract from
            page_no: Page number
            found_standards: Set of already found standards (for deduplication)

        Returns:
            List of compliance items
        """
        items: List[ComplianceItem] = []

        # Find all standard references
        for match in self.ANY_STANDARD_PATTERN.finditer(text):
            code_str = match.group(1).upper()
            number = match.group(2)
            ref_number = f"{code_str} {number}"

            # Skip duplicates
            if ref_number in found_standards:
                continue
            found_standards.add(ref_number)

            # Check if this standard is in our target list
            try:
                std_code = IOSAStandardCode(code_str)
            except ValueError:
                continue

            if IOSAStandard(code_str) not in self.target_standards:
                continue

            # Extract context around the match
            context = self._extract_context(text, match.start(), match.end())

            # Determine priority
            priority = self._determine_priority(context)

            # Extract related references
            related = []
            if self.extract_references:
                related = self._extract_related_references(context)

            # Extract guidance
            guidance = None
            if self.extract_guidance:
                guidance = self._extract_guidance(context)

            item = ComplianceItem(
                standard_code=std_code,
                reference_number=ref_number,
                requirement_text=context,
                guidance_text=guidance,
                status=ComplianceStatus.UNKNOWN,
                page_references=[page_no],
                related_items=related,
                priority=priority,
            )
            items.append(item)

        return items

    def _extract_context(
        self,
        text: str,
        start: int,
        end: int,
        context_chars: int = 500,
    ) -> str:
        """Extract context around a match.

        Args:
            text: Full text
            start: Match start position
            end: Match end position
            context_chars: Characters of context to extract

        Returns:
            Context string
        """
        # Find sentence boundaries
        context_start = max(0, start - context_chars)
        context_end = min(len(text), end + context_chars)

        # Adjust to sentence boundaries if possible
        text_before = text[context_start:start]
        text_after = text[end:context_end]

        # Find last sentence break before match
        sentence_breaks = [". ", ".\n", "! ", "? "]
        for sb in sentence_breaks:
            idx = text_before.rfind(sb)
            if idx != -1:
                context_start = context_start + idx + len(sb)
                break

        # Find first sentence break after match
        for sb in sentence_breaks:
            idx = text_after.find(sb)
            if idx != -1:
                context_end = end + idx + 1
                break

        return text[context_start:context_end].strip()

    def _determine_priority(self, text: str) -> Optional[str]:
        """Determine requirement priority from text.

        Args:
            text: Text to analyze

        Returns:
            Priority string or None
        """
        if self.SHALL_PATTERN.search(text):
            return "shall"
        if self.SHOULD_PATTERN.search(text):
            return "should"
        if self.MAY_PATTERN.search(text):
            return "may"
        return None

    def _extract_related_references(self, text: str) -> List[str]:
        """Extract related standard references from text.

        Args:
            text: Text to search

        Returns:
            List of related reference numbers
        """
        related = []
        for match in self.REFERENCE_PATTERN.finditer(text):
            code = match.group(1).upper()
            number = match.group(2)
            related.append(f"{code} {number}")
        return related

    def _extract_guidance(self, text: str) -> Optional[str]:
        """Extract guidance material references.

        Args:
            text: Text to search

        Returns:
            Guidance material reference or None
        """
        match = self.GM_PATTERN.search(text)
        if match:
            return f"GM {match.group(1)}"
        return None

    def _is_section_header(self, item: TextItem, level: int) -> bool:
        """Check if item is a section header.

        Args:
            item: Text item to check
            level: Item level in document

        Returns:
            True if item is a section header
        """
        # Check for heading-like properties
        if hasattr(item, "label"):
            label = item.label.lower() if item.label else ""
            if "heading" in label or "title" in label:
                return True

        # Check for standard code at start of text
        if hasattr(item, "text"):
            text = item.text.strip()
            # Section headers often start with standard codes
            if self.ANY_STANDARD_PATTERN.match(text):
                return True

        return level <= 2  # Top-level items are likely headers

    def _create_section(
        self,
        item: TextItem,
        text: str,
        page_no: int,
        level: int,
    ) -> IOSASection:
        """Create an IOSASection from a header item.

        Args:
            item: Header item
            text: Header text
            page_no: Page number
            level: Heading level

        Returns:
            New IOSASection
        """
        # Extract standard code if present
        std_code = None
        match = self.ANY_STANDARD_PATTERN.match(text)
        if match:
            try:
                std_code = IOSAStandardCode(match.group(1).upper())
            except ValueError:
                pass

        return IOSASection(
            section_id=f"sec_{page_no}_{hash(text) % 10000}",
            title=text[:200],  # Truncate long titles
            level=level,
            content="",
            page_start=page_no,
            page_end=page_no,
            standard_code=std_code,
        )

    def _get_page_number(self, item: TextItem) -> int:
        """Get page number from a text item.

        Args:
            item: Text item

        Returns:
            Page number (0 if not found)
        """
        if hasattr(item, "prov") and item.prov:
            return item.prov[0].page_no if item.prov[0].page_no else 0
        return 0

    def get_summary(
        self, items: List[ComplianceItem]
    ) -> Dict[str, Dict[str, int]]:
        """Get summary statistics for extracted items.

        Args:
            items: List of compliance items

        Returns:
            Summary statistics by standard code
        """
        summary: Dict[str, Dict[str, int]] = {}

        for item in items:
            code = item.standard_code.value
            if code not in summary:
                summary[code] = {
                    "total": 0,
                    "shall": 0,
                    "should": 0,
                    "may": 0,
                    "unknown": 0,
                }

            summary[code]["total"] += 1
            if item.priority:
                summary[code][item.priority] += 1
            else:
                summary[code]["unknown"] += 1

        return summary


# Utility functions for common extraction patterns
def find_all_standards(text: str) -> List[str]:
    """Find all IOSA standard references in text.

    Args:
        text: Text to search

    Returns:
        List of standard reference strings
    """
    pattern = IOSAExtractor.ANY_STANDARD_PATTERN
    return [f"{m.group(1).upper()} {m.group(2)}" for m in pattern.finditer(text)]


def categorize_requirement(text: str) -> str:
    """Categorize a requirement by its priority.

    Args:
        text: Requirement text

    Returns:
        Priority category ("shall", "should", "may", or "informational")
    """
    text_lower = text.lower()
    if "shall" in text_lower:
        return "shall"
    if "should" in text_lower:
        return "should"
    if "may" in text_lower:
        return "may"
    return "informational"
