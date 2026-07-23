import json

with open('Handwash_Train_Colab.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

# The new content for Cell 6
cell_6_content = """# ============================================================
# CELL 6: CHUẨN BỊ ĐƯỜNG DẪN DATASET
# ============================================================
print('='*60)
print('🔀 ĐÃ CHUYỂN SANG CHẾ ĐỘ AUTO-MERGE BẰNG DATASET CLASS')
print('='*60)
print(f"Kaggle Data Path: {KAGGLE_PROCESSED}")
print(f"Bao Data Path: {BAO_PROCESSED_OUT}")
print("\\n(Thay vì copy file vật lý tốn thời gian, Dataset class ở Cell 8 sẽ tự động gộp file khi Train)")
"""

# The new content for Cell 8 (Dataset Definition)
cell_8_content = """# ============================================================
# CELL 8: ĐỊNH NGHĨA DATASET
# ============================================================
from torch.utils.data import Dataset, DataLoader
import numpy as np
import os
import glob
import torch

class MergedHandwashDataset(Dataset):
    def __init__(self, data_dirs, seq_length=32, step_size=16,
                 subject_exclude=None, subject_include=None, is_train=True):
        self.seq_length = seq_length
        self.is_train = is_train
        self.samples = []
        
        if isinstance(data_dirs, str):
            data_dirs = [data_dirs]
            
        for data_dir in data_dirs:
            if not os.path.exists(data_dir): continue
            
            classes = sorted([d for d in os.listdir(data_dir)
                              if os.path.isdir(os.path.join(data_dir, d))])
            for c_name in classes:
                try: c_idx = int(c_name)
                except: continue
                
                files = glob.glob(os.path.join(data_dir, c_name, '*.npy'))
                for f in files:
                    basename = os.path.basename(f)
                    
                    # Loại bỏ class 0 của Kaggle
                    if c_idx == 0 and not basename.startswith('BAO'):
                        continue
                        
                    subject_id = self._get_subject(basename)
                    
                    if subject_exclude and subject_id in subject_exclude:
                        continue
                    if subject_include and subject_id not in subject_include:
                        continue
                        
                    try:
                        data = np.load(f, allow_pickle=True).item()
                        img_feat = data['img_feat'].astype(np.float32)
                        skel_feat = data['skel_feat'].astype(np.float32)
                    except:
                        continue
                        
                    T = img_feat.shape[0]
                    if T < seq_length:
                        pad = seq_length - T
                        img_feat = np.pad(img_feat, ((0, pad), (0, 0)))
                        skel_feat = np.pad(skel_feat, ((0, pad), (0, 0)))
                        self.samples.append((img_feat, skel_feat, c_idx))
                    else:
                        for start in range(0, T - seq_length + 1, step_size):
                            self.samples.append((
                                img_feat[start:start+seq_length],
                                skel_feat[start:start+seq_length],
                                c_idx
                            ))
                            
        if is_train:
            self._oversample()

    def _get_subject(self, basename):
        if basename.startswith('BAO'):
            parts = basename.split('_')
            if len(parts) >= 2:
                return parts[1]
            return 'BAO'
        parts = basename.replace('.npy', '').split('_')
        for i, p in enumerate(parts):
            if p == 'G' and i+1 < len(parts) and parts[i+1].isdigit():
                return f'G_{parts[i+1]}'
        return 'unknown'

    def _oversample(self):
        class_counts = {}
        for _, _, lbl in self.samples:
            class_counts[lbl] = class_counts.get(lbl, 0) + 1
            
        if not class_counts: return
        
        max_count = max(class_counts.values())
        new_samples = []
        for c, count in class_counts.items():
            c_samples = [s for s in self.samples if s[2] == c]
            if count < max_count:
                num_to_add = max_count - count
                idxs = np.random.choice(len(c_samples), num_to_add, replace=True)
                new_samples.extend([c_samples[i] for i in idxs])
        self.samples.extend(new_samples)

    def _normalize_skeleton(self, skel):
        skel = skel.copy()
        for i in range(skel.shape[0]):
            for hand_idx in range(2):
                pts = skel[i, hand_idx*21*3 : (hand_idx+1)*21*3].reshape(-1, 3)
                if np.all(pts == 0): continue
                wrist = pts[0].copy()
                pts = pts - wrist
                scale = np.max(np.linalg.norm(pts, axis=1))
                if scale > 1e-5: pts = pts / scale
                skel[i, hand_idx*21*3 : (hand_idx+1)*21*3] = pts.flatten()
        return skel

    def _augment_skeleton_3d(self, skel):
        theta = np.random.uniform(-0.1, 0.1)
        cos_t, sin_t = np.cos(theta), np.sin(theta)
        R = np.array([
            [cos_t, -sin_t, 0],
            [sin_t, cos_t, 0],
            [0, 0, 1]
        ])
        for i in range(skel.shape[0]):
            for h in range(2):
                pts = skel[i, h*63:(h+1)*63].reshape(-1, 3)
                if np.all(pts == 0): continue
                pts = pts.dot(R.T)
                skel[i, h*63:(h+1)*63] = pts.flatten()
        return skel

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        img_feat, skel_feat, lbl = self.samples[idx]
        skel_feat = self._normalize_skeleton(skel_feat)
        if self.is_train:
            skel_feat = self._augment_skeleton_3d(skel_feat)
        return torch.tensor(img_feat), torch.tensor(skel_feat), torch.tensor(lbl, dtype=torch.long)

def get_bao_subjects(data_dir):
    subjects = set()
    for cls in range(7):
        cls_dir = os.path.join(data_dir, str(cls))
        if not os.path.exists(cls_dir): continue
        for f in os.listdir(cls_dir):
            if f.startswith('BAO'):
                parts = f.split('_')
                if len(parts) >= 2:
                    subjects.add(parts[1])
    def sort_key(x):
        try: return int(x.replace('BAO', ''))
        except: return x
    return sorted(list(subjects), key=sort_key)

print('✅ Đã định nghĩa MergedHandwashDataset và hàm lấy danh sách BAO subjects!')
"""

# The new content for Cell 10 (Training Loop 3 Experiments)
cell_10_content = """# ============================================================
# CELL 10: CHẠY 3 KỊCH BẢN THỬ NGHIỆM (3 EXPERIMENTS)
# ============================================================
from sklearn.metrics import classification_report
import pandas as pd
import time

bao_subjects = get_bao_subjects(BAO_PROCESSED_OUT)
print(f'🚀 Tìm thấy {len(bao_subjects)} BAO Subjects: {bao_subjects}')

BATCH_SIZE = 128
NUM_EPOCHS = 40
num_classes = 7
results_exp1 = []
results_exp2 = []
results_exp3 = []

def eval_model_on_subject(model, val_subject):
    val_ds = MergedHandwashDataset([BAO_PROCESSED_OUT], subject_include=[val_subject], is_train=False)
    if len(val_ds) == 0: return 0.0
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False)
    correct = total = 0
    model.eval()
    with torch.no_grad():
        for img, skel, lbl in val_loader:
            img, skel, lbl = img.to(device), skel.to(device), lbl.to(device)
            out = model(img, skel)
            preds = torch.argmax(out, 1)
            correct += (preds == lbl).sum().item()
            total += lbl.size(0)
    return correct / max(total, 1) * 100

# ------------------------------------------------------------
# EXPERIMENT 1: BAO ONLY (Train: BAO, Test: BAO)
# ------------------------------------------------------------
print('\\n' + '='*60)
print('🔥 KỊCH BẢN 1: BAO ONLY (LOSO trên tập dữ liệu BAO)')
print('='*60)
for fold_idx, val_subject in enumerate(bao_subjects):
    print(f'\\n--- EXP 1 | FOLD {fold_idx+1}/{len(bao_subjects)} | Val Subject: {val_subject} ---')
    train_ds = MergedHandwashDataset([BAO_PROCESSED_OUT], subject_exclude=[val_subject], is_train=True)
    val_ds = MergedHandwashDataset([BAO_PROCESSED_OUT], subject_include=[val_subject], is_train=False)
    
    if len(train_ds) == 0 or len(val_ds) == 0: continue
    print(f'Train: {len(train_ds)} samples | Val: {len(val_ds)} samples')
    
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, pin_memory=True)
    
    model, _, best_acc = train_single_model(
        train_loader, val_loader, num_classes, NUM_EPOCHS, device, f'EXP1_{val_subject}')
    results_exp1.append({'subject': val_subject, 'acc': best_acc})

# ------------------------------------------------------------
# EXPERIMENT 2: KAGGLE ONLY (Train 1 lần trên toàn bộ Kaggle, Test BAO)
# ------------------------------------------------------------
print('\\n' + '='*60)
print('🔥 KỊCH BẢN 2: KAGGLE ONLY (Train Toàn bộ Kaggle, Test trên từng video BAO)')
print('='*60)
print('▶ Bước 1: Huấn luyện 1 Model duy nhất bằng TOÀN BỘ dữ liệu Kaggle...')
train_ds_kaggle = MergedHandwashDataset([KAGGLE_PROCESSED], is_train=True)
train_loader_k = DataLoader(train_ds_kaggle, batch_size=BATCH_SIZE, shuffle=True, pin_memory=True)

if len(train_ds_kaggle) > 0:
    # Cần 1 dummy val_loader cho hàm train_single_model chạy
    dummy_val_ds = MergedHandwashDataset([BAO_PROCESSED_OUT], subject_include=[bao_subjects[0]], is_train=False)
    dummy_val_loader = DataLoader(dummy_val_ds, batch_size=BATCH_SIZE, shuffle=False)
    
    kaggle_model, _, _ = train_single_model(
        train_loader_k, dummy_val_loader, num_classes, NUM_EPOCHS, device, 'EXP2_Kaggle_All')
    
    print('\\n▶ Bước 2: Đánh giá Model Kaggle này trên từng BAO subject (Test set thay đổi 14 lần)...')
    for fold_idx, val_subject in enumerate(bao_subjects):
        acc = eval_model_on_subject(kaggle_model, val_subject)
        print(f'   + Test {val_subject} (Fold {fold_idx+1}): {acc:.2f}%')
        results_exp2.append({'subject': val_subject, 'acc': acc})
else:
    print('❌ Không tìm thấy dữ liệu Kaggle để train kịch bản 2!')

# ------------------------------------------------------------
# EXPERIMENT 3: KAGGLE + BAO (Gộp Chung - Train: Kaggle+13 BAO, Test: 1 BAO)
# ------------------------------------------------------------
print('\\n' + '='*60)
print('🔥 KỊCH BẢN 3: KAGGLE + BAO (LOSO trên tập BAO + Data Kaggle)')
print('='*60)
for fold_idx, val_subject in enumerate(bao_subjects):
    print(f'\\n--- EXP 3 | FOLD {fold_idx+1}/{len(bao_subjects)} | Val Subject: {val_subject} ---')
    train_ds = MergedHandwashDataset([KAGGLE_PROCESSED, BAO_PROCESSED_OUT], subject_exclude=[val_subject], is_train=True)
    val_ds = MergedHandwashDataset([BAO_PROCESSED_OUT], subject_include=[val_subject], is_train=False)
    
    if len(train_ds) == 0 or len(val_ds) == 0: continue
    print(f'Train: {len(train_ds)} samples (Kaggle + BAO) | Val: {len(val_ds)} samples (Chỉ BAO)')
    
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, pin_memory=True)
    
    model, _, best_acc = train_single_model(
        train_loader, val_loader, num_classes, NUM_EPOCHS, device, f'EXP3_{val_subject}')
    results_exp3.append({'subject': val_subject, 'acc': best_acc})

# ============================================================
# TỔNG KẾT BÁO CÁO 3 KỊCH BẢN
# ============================================================
print('\\n' + '='*80)
print('🏆 BẢNG TỔNG KẾT SO SÁNH 3 KỊCH BẢN (ACCURACY %)')
print('='*80)

df_res = pd.DataFrame({'Subject (Val)': bao_subjects})
df_res['Exp 1 (BAO Only)'] = [next((r['acc'] for r in results_exp1 if r['subject'] == s), 0) for s in bao_subjects]
df_res['Exp 2 (Kaggle Only)'] = [next((r['acc'] for r in results_exp2 if r['subject'] == s), 0) for s in bao_subjects]
df_res['Exp 3 (Kaggle + BAO)'] = [next((r['acc'] for r in results_exp3 if r['subject'] == s), 0) for s in bao_subjects]

print(df_res.to_string(index=False, float_format="%.2f"))

print('\\n📊 TRUNG BÌNH TOÀN BỘ (MEAN ACCURACY):')
print(f"   ▶ Kịch bản 1 (BAO Only)   : {df_res['Exp 1 (BAO Only)'].mean():.2f}%")
print(f"   ▶ Kịch bản 2 (Kaggle Only): {df_res['Exp 2 (Kaggle Only)'].mean():.2f}%")
print(f"   ▶ Kịch bản 3 (Kaggle+BAO) : {df_res['Exp 3 (Kaggle + BAO)'].mean():.2f}%")
print('='*80)
"""

for cell in nb.get('cells', []):
    if cell.get('cell_type') == 'code' and 'id' in cell.get('metadata', {}):
        if cell['metadata']['id'] == 'cell_06_merge_validate':
            cell['source'] = [line + '\n' for line in cell_6_content.split('\n')]
            cell['source'][-1] = cell['source'][-1].rstrip('\n')
        elif cell['metadata']['id'] == 'cell_08_dataset':
            cell['source'] = [line + '\n' for line in cell_8_content.split('\n')]
            cell['source'][-1] = cell['source'][-1].rstrip('\n')
        elif cell['metadata']['id'] == 'cell_09_training':
            cell['source'] = [line + '\n' for line in cell_10_content.split('\n')]
            cell['source'][-1] = cell['source'][-1].rstrip('\n')

with open('Handwash_Train_Colab.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("Successfully updated notebook with 3 experiments!")
