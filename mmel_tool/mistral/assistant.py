"""
MEL/MMEL conversational assistant using Mistral AI.
"""

import json
import re
from typing import Optional, Dict, List, Any
from .client import MistralClient
from .prompts import (
    SYSTEM_PROMPT_EXPERT,
    SYSTEM_PROMPT_AUDIT,
    SYSTEM_PROMPT_DISPATCHER,
    get_context_prompt,
)


class MmelAssistant:
    """Conversational assistant for MEL/MMEL queries."""

    def __init__(
        self,
        mmel_data: Optional[Dict] = None,
        mel_data: Optional[Dict] = None,
        audit_data: Optional[Dict] = None,
        api_key: Optional[str] = None,
        model: str = "mistral-small-latest",
    ):
        """
        Initialize the MEL/MMEL assistant.

        Args:
            mmel_data: Parsed MMEL JSON data (dict or path to JSON file)
            mel_data: Parsed MEL JSON data (dict or path to JSON file)
            audit_data: Audit results JSON data (dict or path to JSON file)
            api_key: Mistral API key (optional, uses env var if not provided)
            model: Mistral model to use
        """
        # Load data from files if paths provided
        self.mmel_data = self._load_data(mmel_data)
        self.mel_data = self._load_data(mel_data)
        self.audit_data = self._load_data(audit_data)

        # Initialize client
        self.client = MistralClient(api_key=api_key, model=model)

        # Build indexes for fast lookup
        self._mmel_index = self._build_index(self.mmel_data)
        self._mel_index = self._build_index(self.mel_data)

        # Conversation history
        self.history: List[Dict[str, str]] = []

    def _load_data(self, data) -> Optional[Dict]:
        """Load data from dict or file path."""
        if data is None:
            return None
        if isinstance(data, dict):
            return data
        if isinstance(data, str):
            with open(data, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def _build_index(self, data: Optional[Dict]) -> Dict[str, Dict]:
        """Build index of items by various keys for fast lookup."""
        index = {}
        if not data or "items" not in data:
            return index

        for item in data["items"]:
            # Get the item code (try both field names)
            item_code = item.get("fullItemCode") or item.get("item_number", "")

            if item_code:
                # Index by full code (e.g., "21-40-01-2E")
                index[item_code] = item
                index[item_code.upper()] = item

                # Index by simplified code (remove trailing letter)
                base_code = item_code.rstrip("ABCDEFGHIJ")
                if base_code not in index:
                    index[base_code] = item

                # Index by partial code (first 3 parts: XX-XX-XX)
                parts = item_code.split("-")
                if len(parts) >= 3:
                    partial = "-".join(parts[:3])
                    if partial not in index:
                        index[partial] = item

            # Index by ATA chapter
            ata = item.get("ataChapter") or item.get("ata_chapter")
            if ata:
                key = f"ata_{ata}"
                if key not in index:
                    index[key] = []
                if isinstance(index[key], list):
                    index[key].append(item)

        return index

    def _normalize_item_code(self, item_code: str) -> str:
        """Normalize an item code for lookup."""
        return item_code.strip().upper().replace(" ", "-").replace("_", "-")

    def _find_item(self, item_code: str) -> tuple:
        """
        Find an item in both MEL and MMEL data.

        Returns:
            Tuple of (mmel_item, mel_item)
        """
        code = self._normalize_item_code(item_code)

        mmel_item = self._mmel_index.get(code)
        mel_item = self._mel_index.get(code)

        # Try without trailing letter
        if not mmel_item or not mel_item:
            base_code = code.rstrip("ABCDEFGHIJ")
            mmel_item = mmel_item or self._mmel_index.get(base_code)
            mel_item = mel_item or self._mel_index.get(base_code)

        # Try partial match (first 3 parts)
        if not mmel_item or not mel_item:
            parts = code.split("-")
            if len(parts) >= 3:
                partial = "-".join(parts[:3])
                mmel_item = mmel_item or self._mmel_index.get(partial)
                mel_item = mel_item or self._mel_index.get(partial)

        # Try searching in all items
        if not mmel_item or not mel_item:
            search_code = code.replace("-", "")
            for key, item in self._mmel_index.items():
                if isinstance(item, dict) and search_code in key.replace("-", ""):
                    mmel_item = mmel_item or item
                    break
            for key, item in self._mel_index.items():
                if isinstance(item, dict) and search_code in key.replace("-", ""):
                    mel_item = mel_item or item
                    break

        return mmel_item, mel_item

    def _format_item_data(self, item: Dict, source: str) -> str:
        """Format item data as readable text."""
        if not item:
            return f"Aucune donnée {source} disponible."

        # Handle both field name conventions
        item_code = item.get("fullItemCode") or item.get("item_number", "N/A")
        title = item.get("itemTitle") or item.get("description", "N/A")
        ata = item.get("ataChapter") or item.get("ata_chapter", "N/A")
        ata_title = item.get("ataTitle") or item.get("ata_title", "")
        interval = item.get("rectificationInterval") or item.get("rectification_interval", "N/A")
        num_installed = item.get("numberInstalled") or item.get("number_installed", "N/A")
        num_required = item.get("numberRequired") or item.get("number_required", "N/A")
        remarks = item.get("remarksText") or item.get("remarks", "")
        ops = item.get("operationTypes") or item.get("operation_types", [])
        requires_m = item.get("requiresMaintenance", False)
        requires_o = item.get("requiresOperations", False)
        conditions = item.get("conditions", [])

        text = f"""
=== {source} ===
Code item: {item_code}
Titre: {title}
Chapitre ATA: {ata} - {ata_title}
Intervalle de rectification: {interval}
Quantité installée: {num_installed}
Quantité requise pour dispatch: {num_required}
Types d'opération: {', '.join(ops) if ops else 'N/A'}
Procédure (M) requise: {'Oui' if requires_m else 'Non'}
Procédure (O) requise: {'Oui' if requires_o else 'Non'}
Remarques: {remarks if remarks else 'Aucune'}
"""
        if conditions:
            text += f"Conditions: {'; '.join(conditions)}\n"

        return text

    def _get_item_json(self, item: Dict) -> str:
        """Get item as formatted JSON string."""
        if not item:
            return "{}"
        # Select relevant fields only
        relevant = {
            "code": item.get("fullItemCode") or item.get("item_number"),
            "titre": item.get("itemTitle") or item.get("description"),
            "chapitre_ata": item.get("ataChapter") or item.get("ata_chapter"),
            "intervalle": item.get("rectificationInterval") or item.get("rectification_interval"),
            "quantite_installee": item.get("numberInstalled") or item.get("number_installed"),
            "quantite_requise": item.get("numberRequired") or item.get("number_required"),
            "remarques": item.get("remarksText") or item.get("remarks"),
            "procedure_M": item.get("requiresMaintenance", False),
            "procedure_O": item.get("requiresOperations", False),
            "conditions": item.get("conditions", []),
        }
        return json.dumps(relevant, indent=2, ensure_ascii=False)

    def _get_items_context(self, item_code: str) -> str:
        """Get detailed context for a specific item with full data."""
        mmel_item, mel_item = self._find_item(item_code)

        if not mmel_item and not mel_item:
            # Try to find similar items
            similar = self._find_similar_items(item_code)
            if similar:
                return f"Item '{item_code}' non trouvé. Items similaires: {', '.join(similar[:5])}"
            return f"Aucun item trouvé pour le code '{item_code}'. Vérifiez le format (ex: 21-40-01A)."

        context_parts = []

        context_parts.append(f"\n### DONNÉES DE L'ITEM {item_code} ###\n")

        # Explicit status for each source
        if mmel_item:
            context_parts.append("**TROUVÉ DANS MMEL** (Référence constructeur/EASA):")
            context_parts.append(self._format_item_data(mmel_item, "MMEL"))
            context_parts.append(f"\nJSON MMEL:\n{self._get_item_json(mmel_item)}\n")
        else:
            context_parts.append("**ABSENT DE MMEL** - Cet item n'existe pas dans la MMEL de référence.")
            context_parts.append("  (Possibilité: item spécifique opérateur ou parsing incomplet)\n")

        if mel_item:
            context_parts.append("**TROUVÉ DANS MEL** (Liste opérateur):")
            context_parts.append(self._format_item_data(mel_item, "MEL"))
            context_parts.append(f"\nJSON MEL:\n{self._get_item_json(mel_item)}\n")
        else:
            context_parts.append("**ABSENT DE MEL** - Cet item n'existe pas dans la MEL opérateur.")
            context_parts.append("  (L'item MMEL n'a pas été repris dans la MEL)\n")

        return "\n".join(context_parts)

    def _find_similar_items(self, item_code: str) -> List[str]:
        """Find similar item codes."""
        code = self._normalize_item_code(item_code)
        parts = code.split("-")
        similar = []

        # Search by ATA chapter
        if parts:
            ata = parts[0]
            for key in list(self._mmel_index.keys()) + list(self._mel_index.keys()):
                if isinstance(key, str) and key.startswith(ata) and key not in similar:
                    if not key.startswith("ata_"):
                        similar.append(key)
                        if len(similar) >= 10:
                            break

        return similar

    def _get_context(self) -> str:
        """Get current data context for prompts."""
        return get_context_prompt(self.mmel_data, self.mel_data, self.audit_data)

    def _extract_item_codes(self, text: str) -> List[str]:
        """Extract item codes from text."""
        # Pattern: XX-XX-XX or XX-XX-XX-X or XX-XX-XXX
        patterns = [
            r'\b(\d{2}-\d{2}-\d{2}-\d+[A-Z]?)\b',  # 21-40-01-2E
            r'\b(\d{2}-\d{2}-\d{2}[A-Z]?)\b',       # 21-40-01A
            r'\b(\d{2}-\d{2}-\d{3}[A-Z]?)\b',       # 21-40-001A
        ]
        codes = []
        for pattern in patterns:
            codes.extend(re.findall(pattern, text, re.IGNORECASE))
        return list(set(codes))

    def _detect_equipment_query(self, question: str) -> Optional[str]:
        """Detect if question is about specific equipment and find item code."""
        question_lower = question.lower()

        # Keywords to equipment mapping
        equipment_map = {
            "fms": ["34-50", "34-51"],
            "gps": ["34-50", "34-52"],
            "autopilot": ["22-10", "22-11"],
            "pilote automatique": ["22-10", "22-11"],
            "chauffage": ["21-40"],
            "heating": ["21-40"],
            "heater": ["21-40"],
            "pressurisation": ["21-30"],
            "pressurization": ["21-30"],
            "oxygen": ["35-10", "35-20"],
            "oxygène": ["35-10", "35-20"],
            "radio": ["23-10", "23-11"],
            "com": ["23-10", "23-11"],
            "nav": ["34-10", "34-20"],
            "radar": ["34-40"],
            "weather radar": ["34-40"],
            "transponder": ["34-55"],
            "transpondeur": ["34-55"],
            "apu": ["49-10"],
            "engine": ["70", "71", "72", "73"],
            "moteur": ["70", "71", "72", "73"],
            "fuel": ["28-10", "28-20"],
            "carburant": ["28-10", "28-20"],
            "landing gear": ["32-10", "32-20"],
            "train": ["32-10", "32-20"],
            "flaps": ["27-50"],
            "volets": ["27-50"],
        }

        for keyword, ata_codes in equipment_map.items():
            if keyword in question_lower:
                # Find first matching item
                for ata in ata_codes:
                    for key, item in self._mel_index.items():
                        if isinstance(item, dict) and key.startswith(ata):
                            return key
                    for key, item in self._mmel_index.items():
                        if isinstance(item, dict) and key.startswith(ata):
                            return key

        return None

    def ask(self, question: str, include_history: bool = True) -> str:
        """
        Ask a question about MEL/MMEL data.

        Args:
            question: Natural language question
            include_history: Whether to include conversation history

        Returns:
            The assistant's response
        """
        # Build base system prompt with context
        system_prompt = SYSTEM_PROMPT_EXPERT + "\n\n" + self._get_context()

        # Check if question mentions specific item codes
        item_codes = self._extract_item_codes(question)

        # If no explicit codes, try to detect equipment query
        if not item_codes:
            detected_code = self._detect_equipment_query(question)
            if detected_code:
                item_codes = [detected_code]

        # Add item data to context
        if item_codes:
            system_prompt += "\n\n### DONNÉES DES ITEMS MENTIONNÉS ###\n"
            for code in item_codes[:3]:  # Limit to 3 items
                item_context = self._get_items_context(code)
                system_prompt += item_context

        # Build messages
        messages = []
        if include_history:
            messages.extend(self.history[-10:])  # Last 10 messages
        messages.append({"role": "user", "content": question})

        # Get response
        response = self.client.chat(messages, system_prompt=system_prompt)

        # Update history
        self.history.append({"role": "user", "content": question})
        self.history.append({"role": "assistant", "content": response})

        return response

    def can_dispatch(self, item_code: str) -> Dict[str, Any]:
        """
        Check if dispatch is possible with an inoperative item.

        Args:
            item_code: The MEL/MMEL item code (e.g., "34-50-01A")

        Returns:
            Dict with dispatch decision and details
        """
        mmel_item, mel_item = self._find_item(item_code)

        result = {
            "item_code": item_code,
            "can_dispatch": False,
            "conditions": [],
            "rectification_interval": None,
            "remarks": None,
            "source": None,
        }

        # Use MEL if available, otherwise MMEL
        item = mel_item or mmel_item
        if not item:
            result["error"] = f"Item {item_code} non trouvé. {self._find_similar_items(item_code)[:5]}"
            return result

        result["source"] = "MEL" if mel_item else "MMEL"
        result["description"] = item.get("itemTitle") or item.get("description", "")
        result["rectification_interval"] = item.get("rectificationInterval") or item.get("rectification_interval")
        result["remarks"] = item.get("remarksText") or item.get("remarks")

        # Check if dispatch is possible
        num_required = item.get("numberRequired") or item.get("number_required", 0)
        if isinstance(num_required, str):
            num_required = 0 if num_required in ["-", "0", ""] else int(num_required)

        # If 0 required, dispatch is possible
        result["can_dispatch"] = num_required == 0

        # Extract conditions
        if item.get("requiresOperations"):
            result["conditions"].append("Procédure opérationnelle (O) requise")
        if item.get("requiresMaintenance"):
            result["conditions"].append("Procédure maintenance (M) requise")

        # Use AI for detailed explanation with full item data
        item_context = self._get_items_context(item_code)
        question = f"""L'équipement '{result['description']}' (item {item_code}) est inopérant.
Puis-je dispatcher l'avion ? Explique les conditions et restrictions."""

        system_prompt = SYSTEM_PROMPT_DISPATCHER + "\n\n" + item_context

        result["ai_explanation"] = self.client.simple_query(question, system_prompt)

        return result

    def explain_item(self, item_code: str) -> str:
        """
        Get a detailed explanation of an item.

        Args:
            item_code: The MEL/MMEL item code

        Returns:
            Detailed explanation
        """
        mmel_item, mel_item = self._find_item(item_code)

        if not mmel_item and not mel_item:
            similar = self._find_similar_items(item_code)
            if similar:
                return f"Item '{item_code}' non trouvé. Items similaires disponibles: {', '.join(similar[:10])}"
            return f"Item '{item_code}' non trouvé dans la MEL ni la MMEL."

        # Build comprehensive context with full item data
        item_context = self._get_items_context(item_code)

        # Determine the interval from whichever source has the item
        interval = "N/A"
        if mmel_item:
            interval = mmel_item.get('rectificationInterval') or mmel_item.get('category', 'N/A')
        elif mel_item:
            interval = mel_item.get('rectificationInterval') or mel_item.get('category', 'N/A')

        # Build status summary
        status_summary = []
        if mel_item:
            status_summary.append(f"TROUVÉ dans MEL: {mel_item.get('itemTitle', '')}")
        else:
            status_summary.append("ABSENT de MEL")
        if mmel_item:
            status_summary.append(f"TROUVÉ dans MMEL: {mmel_item.get('itemTitle', '')}")
        else:
            status_summary.append("ABSENT de MMEL (peut être un problème de parsing)")

        question = f"""L'item {item_code} a été recherché dans les bases de données:
- {status_summary[0]}
- {status_summary[1]}

Voici les données complètes disponibles pour cet item.

Explique cet item de manière claire et structurée:
1. À quoi sert cet équipement dans l'avion?
2. Peut-on voler avec cet équipement inopérant? Si oui, sous quelles conditions?
3. Quel est l'intervalle de rectification ({interval}) et que signifie-t-il concrètement?
4. Quelles procédures (O) ou (M) doivent être accomplies avant le vol?
5. Y a-t-il des implications opérationnelles importantes?

IMPORTANT: L'item EXISTE dans au moins une des bases. Base ta réponse sur les données fournies."""

        system_prompt = SYSTEM_PROMPT_EXPERT + "\n\n" + item_context

        return self.client.simple_query(question, system_prompt)

    def get_non_compliant_summary(self) -> str:
        """
        Get a summary of non-compliant items from the audit.

        Returns:
            Summary of non-conformities
        """
        if not self.audit_data:
            return "Aucune donnée d'audit disponible. Lancez d'abord un audit avec POST /api/v1/audit/quick"

        # Extract non-compliant items
        results = self.audit_data.get("results", [])
        non_compliant = [r for r in results if r.get("status") == "NON_COMPLIANT"]

        if not non_compliant:
            summary = self.audit_data.get("summary", {})
            return f"""Aucun item non conforme trouvé.

Résumé de l'audit:
- Score de conformité: {summary.get('compliance_score', 0):.1f}%
- Items conformes: {summary.get('compliant', 0)}
- Items plus restrictifs: {summary.get('more_restrictive', 0)}
- Items manquants dans MEL: {summary.get('missing_in_mel', 0)}
- Items en surplus dans MEL: {summary.get('extra_in_mel', 0)}"""

        # Build detailed context
        context = f"### ITEMS NON CONFORMES ({len(non_compliant)}) ###\n\n"
        for item in non_compliant:
            context += f"""
Item: {item.get('item_number', 'N/A')}
Description: {item.get('description', 'N/A')}
Statut: NON_COMPLIANT
Raison: {item.get('reason', 'N/A')}
Intervalle MMEL: {item.get('mmel_interval', 'N/A')}
Intervalle MEL: {item.get('mel_interval', 'N/A')}
---
"""

        question = """Analyse les items non conformes ci-dessus:
1. Combien d'items sont non conformes et quels sont-ils?
2. Quels sont les problèmes les plus critiques du point de vue sécurité?
3. Quelles actions correctives recommandes-tu en priorité?
4. Y a-t-il des tendances par chapitre ATA?"""

        system_prompt = SYSTEM_PROMPT_AUDIT + "\n\n" + self._get_context() + "\n\n" + context

        return self.client.simple_query(question, system_prompt)

    def compare_items(self, item_code: str) -> str:
        """
        Compare MEL vs MMEL for a specific item.

        Args:
            item_code: The item code to compare

        Returns:
            Comparison analysis
        """
        mmel_item, mel_item = self._find_item(item_code)

        if not mmel_item and not mel_item:
            similar = self._find_similar_items(item_code)
            if similar:
                return f"Item '{item_code}' non trouvé. Items similaires: {', '.join(similar[:10])}"
            return f"Item {item_code} non trouvé dans la MEL ni la MMEL."

        # Get full item context
        item_context = self._get_items_context(item_code)

        # Check audit results for this item
        audit_info = ""
        if self.audit_data and "results" in self.audit_data:
            for result in self.audit_data["results"]:
                result_code = result.get("item_number", "")
                if item_code in result_code or result_code in item_code:
                    audit_info = f"""
### RÉSULTAT D'AUDIT ###
Statut: {result.get('status', 'N/A')}
Raison: {result.get('reason', 'N/A')}
"""
                    break

        question = f"""Compare l'item {item_code} entre la MEL et la MMEL.

Analyse:
1. Les intervalles de rectification sont-ils identiques? Si non, quelle est la différence?
2. Les remarques et conditions sont-elles équivalentes?
3. La MEL est-elle conforme, plus restrictive, ou non conforme par rapport à la MMEL?
4. Y a-t-il des risques opérationnels ou de conformité?

Base ton analyse sur les données exactes fournies."""

        system_prompt = SYSTEM_PROMPT_AUDIT + "\n\n" + item_context + audit_info

        return self.client.simple_query(question, system_prompt)

    def clear_history(self):
        """Clear conversation history."""
        self.history = []

    def get_sources(self, response: str) -> List[str]:
        """
        Extract source references from a response.

        Args:
            response: The assistant's response

        Returns:
            List of source references (item codes, chapters, etc.)
        """
        sources = []

        # Find item codes
        item_codes = self._extract_item_codes(response)
        sources.extend([f"Item {code}" for code in set(item_codes)])

        # Find ATA chapters
        ata_chapters = re.findall(r'\bATA\s*(\d{2})\b', response, re.IGNORECASE)
        sources.extend([f"ATA Chapter {ch}" for ch in set(ata_chapters)])

        return sources
