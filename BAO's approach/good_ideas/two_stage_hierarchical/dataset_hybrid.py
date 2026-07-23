import os
import glob
import numpy as np
import torch
from torch.utils.data import Dataset

class HandwashNumpyDataset(Dataset):
    def __init__(self, data_dir, seq_length=32, step_size=16, subject_exclude=None, subject_include=None, is_train=True, stage='all'):
        self.seq_length = seq_length
        self.is_train = is_train
        self.stage = stage
        self.samples = []
        
        classes = sorted([d for d in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, d))])
        for c_idx, c_name in enumerate(classes):
            files = glob.glob(os.path.join(data_dir, c_name, "*.npy"))
            for f in files:
                # Trích xuất Subject ID để chống data leakage
                basename = os.path.basename(f)
                parts = basename.replace('.npy', '').split('_')
                subject_id = "unknown"
                for i, p in enumerate(parts):
                    if p == 'G' and i+1 < len(parts):
                        subject_id = f"G_{parts[i+1]}"
                        break
                        
                if subject_exclude and subject_id in subject_exclude:
                    continue
                if subject_include and subject_id not in subject_include:
                    continue
                    
                data = np.load(f, allow_pickle=True).item()
                img_feat = data['img_feat']
                skel_feat = data['skel_feat']
                
                T = img_feat.shape[0]
                # Sliding window để cắt video thành các chuỗi con dài seq_length
                if T < seq_length:
                    # Pad
                    pad_len = seq_length - T
                    img_feat = np.pad(img_feat, ((0, pad_len), (0, 0)))
                    skel_feat = np.pad(skel_feat, ((0, pad_len), (0, 0)))
                    self.samples.append((img_feat, skel_feat, c_idx))
                else:
                    for start in range(0, T - seq_length + 1, step_size):
                        i_f = img_feat[start:start+seq_length]
                        s_f = skel_feat[start:start+seq_length]
                        self.samples.append((i_f, s_f, c_idx))
                        
        # Oversampling Class 3 (Chà kẽ ngón tay) để khắc phục tình trạng quá ít data
        if self.is_train:
            class_3_samples = [s for s in self.samples if s[2] == 3]
            # Nhân đôi số lượng mẫu Class 3
            self.samples.extend(class_3_samples * 2)
            
        # Remap or filter samples based on stage
        processed_samples = []
        for img_feat, skel_feat, c_idx in self.samples:
            if self.stage == 'stage1':
                # Map 6 classes: 0->0, 1->1, 2->2, 3->1 (macro), 4->3, 5->4, 6->5
                if c_idx == 3: new_idx = 1
                elif c_idx == 4: new_idx = 3
                elif c_idx == 5: new_idx = 4
                elif c_idx == 6: new_idx = 5
                else: new_idx = c_idx
                processed_samples.append((img_feat, skel_feat, new_idx))
            elif self.stage == 'stage2':
                # Only keep class 1 and 3, map to 0 and 1
                if c_idx == 1:
                    processed_samples.append((img_feat, skel_feat, 0))
                elif c_idx == 3:
                    processed_samples.append((img_feat, skel_feat, 1))
            else:
                processed_samples.append((img_feat, skel_feat, c_idx))
        self.samples = processed_samples
                        
    def _normalize_skeleton(self, skel_feat):
        # skel_feat: [T, 126] (2 tay * 21 điểm * 3 tọa độ)
        # Reshape để dễ xử lý: [T, 2, 21, 3]
        T = skel_feat.shape[0]
        skel_reshaped = skel_feat.reshape(T, 2, 21, 3)
        
        for t in range(T):
            # Lấy bản sao tọa độ cổ tay để kiểm tra
            left_wrist = skel_reshaped[t, 0, 0].copy()
            right_wrist = skel_reshaped[t, 1, 0].copy()
            
            left_valid = not np.all(left_wrist == 0)
            right_valid = not np.all(right_wrist == 0)
            
            # Nếu cả 2 tay đều bị mất, bỏ qua
            if not left_valid and not right_valid:
                continue
                
            # Xác định tâm dời tọa độ (Global Center)
            if not left_valid:
                center = right_wrist
            elif not right_valid:
                center = left_wrist
            else:
                center = (left_wrist + right_wrist) / 2.0
                
            # Dời hệ tọa độ về gốc center (Translation Invariance)
            skel_reshaped[t] = skel_reshaped[t] - center
            
            # Tính scale để chuẩn hóa kích thước (Scale Invariance)
            scales = []
            if left_valid:
                # Ngón giữa - Cổ tay
                scale_l = np.linalg.norm(skel_reshaped[t, 0, 9] - skel_reshaped[t, 0, 0])
                if scale_l > 1e-6:
                    scales.append(scale_l)
            if right_valid:
                scale_r = np.linalg.norm(skel_reshaped[t, 1, 9] - skel_reshaped[t, 1, 0])
                if scale_r > 1e-6:
                    scales.append(scale_r)
            
            if len(scales) > 0:
                global_scale = np.mean(scales)
                skel_reshaped[t] = skel_reshaped[t] / global_scale
                
        return skel_reshaped.reshape(T, 126)

    def _augment_skeleton_3d(self, skel_feat):
        # skel_feat shape: [T, 126] -> [T, 42, 3]
        T = skel_feat.shape[0]
        skel_reshaped = skel_feat.reshape(T, 42, 3)
        
        # Random angles between -15 and 15 degrees in radians (~0.26 rad)
        angle_x = np.random.uniform(-0.26, 0.26)
        angle_y = np.random.uniform(-0.26, 0.26)
        angle_z = np.random.uniform(-0.26, 0.26)
        
        # Rotation matrices
        Rx = np.array([[1, 0, 0],
                       [0, np.cos(angle_x), -np.sin(angle_x)],
                       [0, np.sin(angle_x), np.cos(angle_x)]], dtype=np.float32)
                       
        Ry = np.array([[np.cos(angle_y), 0, np.sin(angle_y)],
                       [0, 1, 0],
                       [-np.sin(angle_y), 0, np.cos(angle_y)]], dtype=np.float32)
                       
        Rz = np.array([[np.cos(angle_z), -np.sin(angle_z), 0],
                       [np.sin(angle_z), np.cos(angle_z), 0],
                       [0, 0, 1]], dtype=np.float32)
                       
        R = Rz @ Ry @ Rx
        
        skel_rotated = skel_reshaped @ R.T
        
        return skel_rotated.reshape(T, 126)

    def __len__(self):
        return len(self.samples)
        
    def __getitem__(self, idx):
        img_feat, skel_feat, label = self.samples[idx]
        
        # 1. Áp dụng Scale Normalization
        skel_feat = self._normalize_skeleton(skel_feat)
        
        # 2. Data Augmentation trong lúc Train
        if self.is_train:
            # Random 3D Rotation cho skeleton
            skel_feat = self._augment_skeleton_3d(skel_feat)
            
            # Thêm nhiễu Gaussian chuẩn nhỏ cho skeleton
            noise = np.random.normal(0, 0.05, skel_feat.shape).astype(np.float32)
            skel_feat = skel_feat + noise
            
            # Temporal Masking: Xóa ngẫu nhiên ~20% số frame (gán bằng 0) để ép GRU không phụ thuộc vào 1 frame cụ thể
            T = img_feat.shape[0]
            mask_prob = 0.2
            mask = np.random.rand(T) > mask_prob
            mask = mask[:, np.newaxis] # [T, 1] để broadcast
            
            img_feat = img_feat * mask
            skel_feat = skel_feat * mask
            
        return torch.tensor(img_feat, dtype=torch.float32), \
               torch.tensor(skel_feat, dtype=torch.float32), \
               torch.tensor(label, dtype=torch.long)
