#!/usr/bin/env python3
"""Script de test pour parser le PDF MMEL avec Docling."""

from docling.document_converter import DocumentConverter
import os

# Configuration
PDF_DIR = "data/mmel/"
OUTPUT_DIR = "output/parsed"
OUTPUT_FILE = "mmel_pc12_raw.md"

def main():
    # Vérifier que le répertoire existe
    if not os.path.exists(PDF_DIR):
        print(f"ERREUR: Le répertoire '{PDF_DIR}' n'existe pas!")
        print("Créez-le et placez-y votre PDF MMEL.")
        return

    # Trouver le PDF
    pdf_files = [f for f in os.listdir(PDF_DIR) if f.endswith('.pdf')]

    if not pdf_files:
        print(f"ERREUR: Aucun fichier PDF trouvé dans '{PDF_DIR}'")
        print("Placez votre PDF MMEL dans ce répertoire.")
        return

    pdf_path = os.path.join(PDF_DIR, pdf_files[0])
    print(f"PDF trouvé: {pdf_files[0]}")
    print(f"Chemin complet: {pdf_path}")
    print("=" * 60)

    # Parser avec Docling
    print("Parsing en cours avec Docling...")
    converter = DocumentConverter()
    result = converter.convert(pdf_path)

    # Export markdown
    md_content = result.document.export_to_markdown()

    # Créer le répertoire de sortie
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)

    # Sauvegarder
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    # Statistiques
    lines = md_content.split("\n")
    num_pages = len(result.document.pages) if hasattr(result.document, 'pages') else "N/A"

    print("=" * 60)
    print("STATISTIQUES:")
    print(f"  - Nombre de pages détectées: {num_pages}")
    print(f"  - Nombre total de caractères: {len(md_content):,}")
    print(f"  - Nombre de lignes: {len(lines):,}")
    print(f"  - Fichier sauvegardé: {output_path}")
    print("=" * 60)

    # Afficher les 100 premières lignes
    print("\nEXTRAIT (100 premières lignes):")
    print("-" * 60)
    print("\n".join(lines[:100]))
    print("-" * 60)

    # Extraire le contenu des pages 29-32 (ATA chapitre 21)
    print("\n" + "=" * 60)
    print("CONTENU PAGES 29-32 (début ATA chapitre 21):")
    print("=" * 60)

    # Méthode 1: Si le document a des pages accessibles
    if hasattr(result.document, 'pages') and result.document.pages:
        pages = result.document.pages
        for page_num in range(28, min(32, len(pages))):  # 0-indexed, donc 28-31 pour pages 29-32
            if page_num < len(pages):
                page = pages[page_num]
                print(f"\n--- PAGE {page_num + 1} ---")
                # Essayer d'extraire le texte de la page
                if hasattr(page, 'export_to_markdown'):
                    print(page.export_to_markdown())
                elif hasattr(page, 'text'):
                    print(page.text)
                else:
                    print(f"[Structure page: {type(page)}]")
    else:
        # Méthode alternative: chercher des marqueurs dans le markdown
        print("\nRecherche de marqueurs 'ATA 21' ou 'Chapter 21' dans le contenu...")
        for i, line in enumerate(lines):
            if 'ATA 21' in line.upper() or 'CHAPTER 21' in line.upper() or '21-' in line:
                start = max(0, i - 2)
                end = min(len(lines), i + 20)
                print(f"\nTrouvé à la ligne {i + 1}:")
                print("\n".join(lines[start:end]))
                print("...")
                break
        else:
            # Afficher une portion approximative (pages 29-32 ~ lignes 700-900 pour un doc standard)
            print("\nExtrait approximatif (lignes 700-900):")
            print("\n".join(lines[700:900]) if len(lines) > 900 else "\n".join(lines[700:]))

if __name__ == "__main__":
    main()
