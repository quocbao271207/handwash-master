import json

with open('Handwash_Train_Colab.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code' and 'id' in cell['metadata']:
        cell_id = cell['metadata']['id']
        
        if cell_id == 'cell_01_install':
            source = "".join(cell['source'])
            source = source.replace("!pip install -q mediapipe==0.10.21 tqdm scipy scikit-learn seaborn openpyxl",
                                    "!pip install -q \"numpy<2.0\" mediapipe==0.10.21 tqdm scipy scikit-learn seaborn openpyxl")
            cell['source'] = [line + '\n' for line in source.split('\n')]
            if cell['source'][-1] == '\n':
                cell['source'].pop()
            else:
                cell['source'][-1] = cell['source'][-1].rstrip('\n')

with open('Handwash_Train_Colab.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("Numpy patch applied!")
