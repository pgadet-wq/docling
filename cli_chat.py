#!/usr/bin/env python3
"""
CLI Chat interface for MEL/MMEL assistant.

Usage:
    python cli_chat.py [--mmel FILE] [--mel FILE] [--audit FILE]

Commands:
    /quit, /exit    - Exit the chat
    /help           - Show help
    /items          - List loaded items count
    /audit          - Show audit summary
    /clear          - Clear conversation history
    /dispatch CODE  - Check dispatch for item code
    /explain CODE   - Explain an item
    /compare CODE   - Compare MEL vs MMEL for an item
"""

import argparse
import glob
import os
import sys
from typing import Optional


def find_latest_file(pattern: str) -> Optional[str]:
    """Find the most recently modified file matching pattern."""
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def print_header():
    """Print the welcome header."""
    print("\n" + "=" * 60)
    print("  MEL/MMEL Assistant - Interface conversationnelle")
    print("=" * 60)
    print("\nCommandes disponibles:")
    print("  /help           - Afficher l'aide")
    print("  /items          - Afficher le nombre d'items chargés")
    print("  /audit          - Afficher le résumé d'audit")
    print("  /clear          - Effacer l'historique de conversation")
    print("  /dispatch CODE  - Vérifier le dispatch pour un item")
    print("  /explain CODE   - Expliquer un item en détail")
    print("  /compare CODE   - Comparer MEL vs MMEL pour un item")
    print("  /quit, /exit    - Quitter")
    print("\nOu posez une question en langage naturel...")
    print("-" * 60 + "\n")


def print_sources(sources: list):
    """Print source references."""
    if sources:
        print("\n  Sources: " + ", ".join(sources))


def main():
    parser = argparse.ArgumentParser(description="MEL/MMEL Chat Assistant")
    parser.add_argument("--mmel", help="Path to MMEL JSON file")
    parser.add_argument("--mel", help="Path to MEL JSON file")
    parser.add_argument("--audit", help="Path to audit JSON file")
    parser.add_argument("--model", default="mistral-small-latest", help="Mistral model to use")
    args = parser.parse_args()

    # Find default files if not specified
    # Prefer files with most items (check file size as proxy)
    mmel_file = args.mmel or find_latest_file("output/parsed/mmel_*_structured.json")
    mel_file = args.mel or find_latest_file("output/parsed/mel_*_structured.json")
    audit_file = args.audit or find_latest_file("output/audit/audit_*.json")

    # Validate files have enough items
    import json
    if mel_file:
        try:
            with open(mel_file, 'r') as f:
                mel_check = json.load(f)
                mel_item_count = len(mel_check.get('items', []))
                if mel_item_count < 100:
                    print(f"\n  WARNING: MEL file has only {mel_item_count} items (expected ~162)")
                    # Try to find a better file
                    all_mel_files = glob.glob("output/parsed/mel_*_structured.json")
                    for f_path in all_mel_files:
                        with open(f_path, 'r') as f:
                            check_data = json.load(f)
                            if len(check_data.get('items', [])) >= 100:
                                mel_file = f_path
                                print(f"  Using instead: {os.path.basename(mel_file)}")
                                break
        except Exception:
            pass

    if not mmel_file:
        print("Erreur: Aucun fichier MMEL trouvé. Lancez d'abord le parsing.")
        sys.exit(1)

    if not mel_file:
        print("Erreur: Aucun fichier MEL trouvé. Lancez d'abord le parsing.")
        sys.exit(1)

    print(f"\nChargement des données...")
    print(f"  MMEL: {os.path.basename(mmel_file)}")
    print(f"  MEL:  {os.path.basename(mel_file)}")
    if audit_file:
        print(f"  Audit: {os.path.basename(audit_file)}")

    # Initialize assistant
    try:
        from mmel_tool.mistral.assistant import MmelAssistant

        assistant = MmelAssistant(
            mmel_data=mmel_file,
            mel_data=mel_file,
            audit_data=audit_file,
            model=args.model,
        )
    except ValueError as e:
        print(f"\nErreur: {e}")
        print("Assurez-vous que MISTRAL_API_KEY est défini dans .env ou comme variable d'environnement.")
        sys.exit(1)
    except Exception as e:
        print(f"\nErreur lors de l'initialisation: {e}")
        sys.exit(1)

    # Print stats
    mmel_count = len(assistant.mmel_data.get("items", [])) if assistant.mmel_data else 0
    mel_count = len(assistant.mel_data.get("items", [])) if assistant.mel_data else 0
    print(f"\n  Items MMEL: {mmel_count}")
    print(f"  Items MEL:  {mel_count}")
    print(f"  MEL index size: {len(assistant._mel_index)}")
    print(f"  MMEL index size: {len(assistant._mmel_index)}")

    # Verify 21-30-02D lookup as debug
    test_code = "21-30-02D"
    mmel_test, mel_test = assistant._find_item(test_code)
    print(f"\n  DEBUG: {test_code} in MEL: {mel_test is not None}, in MMEL: {mmel_test is not None}")

    print_header()

    # Main loop
    while True:
        try:
            user_input = input("\nVous: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nAu revoir!")
            break

        if not user_input:
            continue

        # Handle commands
        if user_input.lower() in ["/quit", "/exit", "/q"]:
            print("\nAu revoir!")
            break

        elif user_input.lower() == "/help":
            print_header()
            continue

        elif user_input.lower() == "/items":
            print(f"\n  Items MMEL: {mmel_count}")
            print(f"  Items MEL:  {mel_count}")
            if assistant.audit_data:
                summary = assistant.audit_data.get("summary", {})
                print(f"  Score audit: {summary.get('compliance_score', 0):.1f}%")
            continue

        elif user_input.lower() == "/audit":
            print("\nRécupération du résumé d'audit...")
            try:
                summary = assistant.get_non_compliant_summary()
                print(f"\nAssistant: {summary}")
            except Exception as e:
                print(f"\nErreur: {e}")
            continue

        elif user_input.lower() == "/clear":
            assistant.clear_history()
            print("\nHistorique de conversation effacé.")
            continue

        elif user_input.lower().startswith("/dispatch "):
            item_code = user_input[10:].strip()
            print(f"\nVérification dispatch pour {item_code}...")
            try:
                result = assistant.can_dispatch(item_code)
                print(f"\nRésultat:")
                print(f"  Dispatch possible: {'Oui' if result['can_dispatch'] else 'Non'}")
                print(f"  Source: {result.get('source', 'N/A')}")
                print(f"  Intervalle: {result.get('rectification_interval', 'N/A')}")
                if result.get('conditions'):
                    print(f"  Conditions: {', '.join(result['conditions'])}")
                if result.get('ai_explanation'):
                    print(f"\n  Explication: {result['ai_explanation']}")
                if result.get('error'):
                    print(f"\n  Erreur: {result['error']}")
            except Exception as e:
                print(f"\nErreur: {e}")
            continue

        elif user_input.lower().startswith("/explain "):
            item_code = user_input[9:].strip()
            print(f"\nExplication de l'item {item_code}...")
            try:
                explanation = assistant.explain_item(item_code)
                print(f"\nAssistant: {explanation}")
            except Exception as e:
                print(f"\nErreur: {e}")
            continue

        elif user_input.lower().startswith("/compare "):
            item_code = user_input[9:].strip()
            print(f"\nComparaison MEL/MMEL pour {item_code}...")
            try:
                comparison = assistant.compare_items(item_code)
                print(f"\nAssistant: {comparison}")
            except Exception as e:
                print(f"\nErreur: {e}")
            continue

        elif user_input.startswith("/"):
            print("\nCommande non reconnue. Tapez /help pour l'aide.")
            continue

        # Regular question
        print("\nRéflexion en cours...")
        try:
            response = assistant.ask(user_input)
            sources = assistant.get_sources(response)
            print(f"\nAssistant: {response}")
            print_sources(sources)
        except Exception as e:
            print(f"\nErreur: {e}")


if __name__ == "__main__":
    main()
