import re

# Lire le raw
with open('output/parsed/mmel_pc12_raw.md', encoding='utf-8') as f:
    raw = f.read()

# Chercher les items 21-30-02*
print("=== Recherche 21-30-02* dans le raw ===")
for match in re.finditer(r'21-30-02[A-Z]?[^\n]*', raw):
    print(f"  Position {match.start()}: {match.group()[:80]}")

# Compter tous les codes items potentiels
print("\n=== Statistiques des codes dans le raw ===")
patterns = [
    (r'\d{2}-\d{2}-\d{2}-\d+[A-Z]', 'XX-XX-XX-NA (ex: 21-40-01-2E)'),
    (r'\d{2}-\d{2}-\d{2}[A-Z]', 'XX-XX-XXA (ex: 21-30-02D)'),
    (r'\d{2}-\d{2}-\d{2}(?!\d)', 'XX-XX-XX (ex: 21-30-02)'),
]

for pattern, desc in patterns:
    matches = set(re.findall(pattern, raw))
    print(f"  {desc}: {len(matches)} uniques")

# Cherche spécifiquement le contexte de 21-30-02D
print("\n=== Contexte de 21-30-02D ===")
idx = raw.find('21-30-02D')
if idx > 0:
    context = raw[idx:idx+200]
    print(context)
else:
    print("21-30-02D NON TROUVÉ dans le raw!")
    
    # Cherche les variantes
    print("\nRecherche de variantes...")
    for variant in ['21-30-02 D', '21-30-02-D', '21 30 02D']:
        if variant in raw:
            print(f"  Trouvé: {variant}")