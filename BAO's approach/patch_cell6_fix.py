import json

with open('Handwash_Train_Colab.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb.get('cells', []):
    if cell.get('cell_type') == 'code' and 'id' in cell.get('metadata', {}):
        if cell['metadata']['id'] == 'cell_06_merge_validate':
            source = "".join(cell['source'])
            source = source.replace("src = os.path.join(KAGGLE_DIR, str(cls))",
                                    "src = os.path.join(KAGGLE_DIR, 'processed_features', str(cls))")
            cell['source'] = [line + '\n' for line in source.split('\n')]
            if cell['source'][-1].endswith('\n'):
                cell['source'][-1] = cell['source'][-1].rstrip('\n')

with open('Handwash_Train_Colab.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("Kaggle directory path fixed in Cell 6!")
