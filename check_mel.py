import json
import glob

# Trouver le fichier MEL
mel_files = glob.glob('output/parsed/mel*.json')
print(f"Fichiers MEL: {mel_files}")

if mel_files:
    with open(mel_files[0], encoding='utf-8') as f:
        mel = json.load(f)
    
    print(f"Total items MEL: {len(mel['items'])}")
    
    print("\nItems 21-30-02*:")
    found = False
    for item in mel['items']:
        code = item.get('fullItemCode', '')
        if '21-30-02' in code:
            print(f"  {code}: {item.get('itemTitle', '')}")
            found = True
    
    if not found:
        print("  AUCUN item 21-30-02* trouvé!")