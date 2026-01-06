"""
MEL/MMEL conversational assistant using Mistral AI.
"""

import json
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
            # Index by item_number
            if "item_number" in item:
                index[item["item_number"]] = item
                # Also index without suffix letter
                base_num = item["item_number"].rstrip("ABCDEFGHIJ")
                if base_num not in index:
                    index[base_num] = item

            # Index by ata_chapter-sequence
            if "ata_chapter" in item and "sequence" in item:
                key = f"{item['ata_chapter']}-{item['sequence']}"
                index[key] = item

        return index

    def _find_item(self, item_code: str) -> tuple:
        """
        Find an item in both MEL and MMEL data.

        Returns:
            Tuple of (mmel_item, mel_item)
        """
        # Normalize the code
        code = item_code.strip().upper().replace(" ", "-")

        mmel_item = self._mmel_index.get(code)
        mel_item = self._mel_index.get(code)

        # Try alternative formats
        if not mmel_item and not mel_item:
            # Try with different separators
            for sep in ["-", "_", ""]:
                alt_code = code.replace("-", sep)
                mmel_item = mmel_item or self._mmel_index.get(alt_code)
                mel_item = mel_item or self._mel_index.get(alt_code)

        return mmel_item, mel_item

    def _get_context(self) -> str:
        """Get current data context for prompts."""
        return get_context_prompt(self.mmel_data, self.mel_data, self.audit_data)

    def _get_items_context(self, item_code: str) -> str:
        """Get detailed context for a specific item."""
        mmel_item, mel_item = self._find_item(item_code)

        context_parts = []

        if mmel_item:
            context_parts.append(f"""
Item MMEL {item_code}:
- Numéro: {mmel_item.get('item_number', 'N/A')}
- Description: {mmel_item.get('description', 'N/A')}
- Intervalle: {mmel_item.get('rectification_interval', 'N/A')}
- Quantité installée: {mmel_item.get('number_installed', 'N/A')}
- Quantité requise: {mmel_item.get('number_required', 'N/A')}
- Remarques: {mmel_item.get('remarks', 'N/A')}
""")

        if mel_item:
            context_parts.append(f"""
Item MEL {item_code}:
- Numéro: {mel_item.get('item_number', 'N/A')}
- Description: {mel_item.get('description', 'N/A')}
- Intervalle: {mel_item.get('rectification_interval', 'N/A')}
- Quantité installée: {mel_item.get('number_installed', 'N/A')}
- Quantité requise: {mel_item.get('number_required', 'N/A')}
- Remarques: {mel_item.get('remarks', 'N/A')}
""")

        if not context_parts:
            return f"Aucun item trouvé pour le code '{item_code}'."

        return "\n".join(context_parts)

    def ask(self, question: str, include_history: bool = True) -> str:
        """
        Ask a question about MEL/MMEL data.

        Args:
            question: Natural language question
            include_history: Whether to include conversation history

        Returns:
            The assistant's response
        """
        # Build system prompt with context
        system_prompt = SYSTEM_PROMPT_EXPERT + "\n\n" + self._get_context()

        # Check if question is about a specific item
        import re
        item_match = re.search(r'\b(\d{2}-\d{2}-\d{2}[A-Z]?)\b', question)
        if item_match:
            item_context = self._get_items_context(item_match.group(1))
            system_prompt += "\n\n" + item_context

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
            result["error"] = f"Item {item_code} not found in MEL or MMEL"
            return result

        result["source"] = "MEL" if mel_item else "MMEL"
        result["description"] = item.get("description", "")
        result["rectification_interval"] = item.get("rectification_interval")
        result["remarks"] = item.get("remarks")

        # Check if dispatch is possible
        num_required = item.get("number_required", 0)
        if isinstance(num_required, str):
            num_required = 0 if num_required == "-" else int(num_required)

        # If 0 required, dispatch is possible
        result["can_dispatch"] = num_required == 0

        # Extract conditions from remarks
        remarks = item.get("remarks", "") or ""
        if "(O)" in remarks:
            result["conditions"].append("Operations procedure required")
        if "(M)" in remarks:
            result["conditions"].append("Maintenance procedure required")

        # Use AI for detailed explanation
        question = f"Puis-je dispatcher l'avion avec l'item {item_code} ({item.get('description', '')}) inopérant?"
        system_prompt = SYSTEM_PROMPT_DISPATCHER + "\n\n" + self._get_items_context(item_code)

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
        item_context = self._get_items_context(item_code)

        if "Aucun item trouvé" in item_context:
            return item_context

        question = f"""Explique en détail l'item {item_code}:
1. À quoi sert cet équipement?
2. Quelles sont les conditions pour voler avec cet équipement inopérant?
3. Quel est l'intervalle de rectification et que signifie-t-il?
4. Y a-t-il des procédures (O) ou (M) à respecter?
5. Quelles sont les implications opérationnelles?"""

        system_prompt = SYSTEM_PROMPT_EXPERT + "\n\n" + item_context

        return self.client.simple_query(question, system_prompt)

    def get_non_compliant_summary(self) -> str:
        """
        Get a summary of non-compliant items from the audit.

        Returns:
            Summary of non-conformities
        """
        if not self.audit_data:
            return "Aucune donnée d'audit disponible. Lancez d'abord un audit."

        # Extract non-compliant items
        results = self.audit_data.get("results", [])
        non_compliant = [r for r in results if r.get("status") == "NON_COMPLIANT"]

        if not non_compliant:
            return "Aucun item non conforme trouvé. Tous les items sont conformes ou plus restrictifs."

        # Build context
        context = f"Items non conformes ({len(non_compliant)}):\n"
        for item in non_compliant[:10]:  # Limit to 10 for context
            context += f"""
- {item.get('item_number', 'N/A')}: {item.get('description', 'N/A')}
  Raison: {item.get('reason', 'N/A')}
"""

        question = """Résume les non-conformités détectées:
1. Combien d'items sont non conformes?
2. Quels sont les problèmes les plus critiques?
3. Quelles actions correctives recommandes-tu?
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
            return f"Item {item_code} non trouvé dans la MEL ni la MMEL."

        context = self._get_items_context(item_code)

        # Check audit results for this item
        audit_result = None
        if self.audit_data and "results" in self.audit_data:
            for result in self.audit_data["results"]:
                if result.get("item_number", "").startswith(item_code.split("-")[0]):
                    if item_code in result.get("item_number", ""):
                        audit_result = result
                        break

        if audit_result:
            context += f"""
Résultat d'audit pour cet item:
- Statut: {audit_result.get('status', 'N/A')}
- Raison: {audit_result.get('reason', 'N/A')}
"""

        question = f"""Compare l'item {item_code} entre la MEL et la MMEL:
1. Quelles sont les différences d'intervalle de rectification?
2. Les remarques sont-elles identiques?
3. La MEL est-elle conforme, plus restrictive, ou non conforme?
4. Y a-t-il des risques opérationnels?"""

        system_prompt = SYSTEM_PROMPT_AUDIT + "\n\n" + context

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
        import re
        sources = []

        # Find item codes
        item_codes = re.findall(r'\b(\d{2}-\d{2}-\d{2}[A-Z]?)\b', response)
        sources.extend([f"Item {code}" for code in set(item_codes)])

        # Find ATA chapters
        ata_chapters = re.findall(r'\bATA\s*(\d{2})\b', response, re.IGNORECASE)
        sources.extend([f"ATA Chapter {ch}" for ch in set(ata_chapters)])

        return sources
