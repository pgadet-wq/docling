# Voir le contexte complet autour de 21-30-02D
with open('output/parsed/mmel_pc12_raw.md', encoding='utf-8') as f:
    raw = f.read()

# Position de l'item réel (pas celui du changelog)
idx = raw.find('21-30-02D (NCO/SPO)')
if idx > 0:
    print("=== CONTEXTE 21-30-02D (500 caractères) ===")
    print(raw[idx:idx+500])
    print("\n=== LIGNES SÉPARÉES ===")
    lines = raw[idx:idx+500].split('\n')
    for i, line in enumerate(lines[:15]):
        print(f"  Ligne {i}: [{line}]")