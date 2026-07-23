import json

with open('Handwash_Train_Colab.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

new_cell_6_source = """# ============================================================
# CELL 6: GỘP DATA KAGGLE VÀ BAO_DATA
# ============================================================
import numpy as np
import os
import shutil

MERGED_DIR = '/content/merged_features'

print('='*60)
print('🔀 GỘP DỮ LIỆU KAGGLE VÀ BAO DATA')
print('='*60)

# Xóa thư mục cũ nếu có
if os.path.exists(MERGED_DIR):
    shutil.rmtree(MERGED_DIR)

for cls in range(7):
    os.makedirs(os.path.join(MERGED_DIR, str(cls)), exist_ok=True)

# 1. Copy Kaggle Data
kaggle_count = 0
for cls in range(7):
    src = os.path.join(KAGGLE_DIR, str(cls))
    dst = os.path.join(MERGED_DIR, str(cls))
    if os.path.exists(src):
        for f in os.listdir(src):
            if f.endswith('.npy'):
                shutil.copy2(os.path.join(src, f), os.path.join(dst, f))
                kaggle_count += 1

# 2. Copy bao_data
bao_count = 0
for cls in range(7):
    src = os.path.join(BAO_PROCESSED_OUT, str(cls))
    dst = os.path.join(MERGED_DIR, str(cls))
    if os.path.exists(src):
        for f in os.listdir(src):
            if f.endswith('.npy'):
                shutil.copy2(os.path.join(src, f), os.path.join(dst, f))
                bao_count += 1

print(f'✅ Đã copy {kaggle_count} files Kaggle vào thư mục huấn luyện.')
print(f'✅ Đã copy {bao_count} files bao_data vào thư mục huấn luyện.')
print(f'   Tổng cộng: {kaggle_count + bao_count} files.')

# Lấy danh sách subjects cho LOSO
subjects = set()
for cls in range(7):
    cls_dir = os.path.join(MERGED_DIR, str(cls))
    if not os.path.exists(cls_dir): continue
    for f in os.listdir(cls_dir):
        if f.startswith('BAO'):
            parts = f.split('_')
            if len(parts) >= 2:
                subjects.add(parts[1])
        else:
            parts = f.replace('.npy', '').split('_')
            for i, p in enumerate(parts):
                if p == 'G' and i+1 < len(parts) and parts[i+1].isdigit():
                    subjects.add(f'G_{parts[i+1]}')
                    break

def sort_key(x):
    try:
        return int(x.replace('BAO', ''))
    except:
        return x

print(f'\\nSubjects dùng cho CV (LOSO): {sorted(list(subjects), key=sort_key)}')
"""

for cell in nb.get('cells', []):
    if cell.get('cell_type') == 'code' and 'id' in cell.get('metadata', {}):
        if cell['metadata']['id'] == 'cell_06_merge_validate':
            cell['source'] = [line + '\n' for line in new_cell_6_source.split('\n')]
            if cell['source'][-1].endswith('\n'):
                cell['source'][-1] = cell['source'][-1].rstrip('\n')

with open('Handwash_Train_Colab.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("Cell 6 patched to include Kaggle data!")
