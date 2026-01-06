import json
import glob

# Trouver le fichier MMEL
mmel_files = glob.glob('output/parsed/mmel_*_structured.json')
print(f"Fichiers MMEL trouvés: {mmel_files}")

if mmel_files:
    with open(mmel_files[0]) as f:
        mmel = json.load(f)
    
    print(f"\nTotal items MMEL: {len(mmel['items'])}")
    
    print("\nItems 21-30-02*:")
    for item in mmel['items']:
        code = item.get('fullItemCode', '')
        if '21-30-02' in code:
            print(f"  {code}: {item.get('itemTitle', '')}")
    
    if len(mmel['items']) < 300:
        print("\n⚠️ ATTENTION: Moins de 300 items - le parsing n'est pas à jour!")
        print("   Attendu: ~314 items")
else:
    print("Aucun fichier MMEL trouvé!")