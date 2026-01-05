#!/usr/bin/env python3
"""Script de test pour parser le PDF MMEL avec pypdfium2 (sans modèles ML)."""

import pypdfium2 as pdfium
import os

# Configuration
PDF_DIR = "data/mmel/"
OUTPUT_DIR = "output/parsed"
OUTPUT_FILE = "mmel_pc12_raw.md"

def extract_text_from_pdf(pdf_path):
    """Extrait le texte de toutes les pages d'un PDF."""
    pdf = pdfium.PdfDocument(pdf_path)
    all_text = []
    num_pages = len(pdf)

    for page_num in range(num_pages):
        page = pdf[page_num]
        textpage = page.get_textpage()
        text = textpage.get_text_range()
        all_text.append(f"\n\n## Page {page_num + 1}\n\n{text}")
        textpage.close()
        page.close()

    pdf.close()
    return num_pages, "\n".join(all_text)

def extract_pages_range(pdf_path, start_page, end_page):
    """Extrait le texte d'une plage de pages spécifique."""
    pdf = pdfium.PdfDocument(pdf_path)
    pages_text = []

    for page_num in range(start_page - 1, min(end_page, len(pdf))):
        page = pdf[page_num]
        textpage = page.get_textpage()
        text = textpage.get_text_range()
        pages_text.append(f"\n--- PAGE {page_num + 1} ---\n{text}")
        textpage.close()
        page.close()

    pdf.close()
    return "\n".join(pages_text)

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

    # Parser avec pypdfium2 (sans modèles ML)
    print("Parsing en cours avec pypdfium2...")
    num_pages, md_content = extract_text_from_pdf(pdf_path)

    # Ajouter un header markdown
    md_content = f"# MMEL PC-12 - Extraction PDF\n\nSource: {pdf_files[0]}\n{md_content}"

    # Créer le répertoire de sortie
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)

    # Sauvegarder
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    # Statistiques
    lines = md_content.split("\n")

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
    pages_29_32 = extract_pages_range(pdf_path, 29, 32)
    print(pages_29_32)

if __name__ == "__main__":
    main()
