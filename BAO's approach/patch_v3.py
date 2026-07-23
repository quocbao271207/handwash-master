import json
import re

with open('Handwash_Train_Colab.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb.get('cells', []):
    if cell.get('cell_type') == 'code' and 'id' in cell.get('metadata', {}):
        cell_id = cell['metadata']['id']
        
        if cell_id == 'cell_04_extract_bao':
            source = "".join(cell['source'])
            
            # Replace the float check
            source = re.sub(
                r'if isinstance\(start_val,\s*float\)\s*and\s*start_val\s*<\s*1000:',
                r'if float(start_val) < 1000:',
                source
            )
            
            # Replace the int casts inside the if block
            source = re.sub(
                r'start_frame\s*=\s*int\(start_val\s*\*\s*fps\)',
                r'start_frame = int(float(start_val) * fps)',
                source
            )
            source = re.sub(
                r'end_frame\s*=\s*int\(end_val\s*\*\s*fps\)',
                r'end_frame = int(float(end_val) * fps)',
                source
            )
            
            cell['source'] = [line + '\n' for line in source.split('\n')]
            if cell['source'][-1].endswith('\n'):
                cell['source'][-1] = cell['source'][-1].rstrip('\n')
                
        if cell_id == 'cell_08_dataset':
            source = "".join(cell['source'])
            
            # Insert Kaggle class 0 ignore logic
            if 'Bỏ class 0 của kaggle' not in source:
                insert_str = "subject_id = self._get_subject(basename)"
                replace_str = "subject_id = self._get_subject(basename)\n\n                # Bỏ class 0 của kaggle\n                if c_idx == 0 and not basename.startswith('BAO'):\n                    continue"
                source = source.replace(insert_str, replace_str)
                
            cell['source'] = [line + '\n' for line in source.split('\n')]
            if cell['source'][-1].endswith('\n'):
                cell['source'][-1] = cell['source'][-1].rstrip('\n')

with open('Handwash_Train_Colab.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("Patch applied successfully!")
