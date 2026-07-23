import os
import glob
import numpy as np
import torch
from torch.utils.data import Dataset

class CombinedHandwashDataset(Dataset):
    def __init__(self, data01_dir, data02_dir, seq_length=32, step_size=16, is_train=True, stage='all'):
        self.seq_length = seq_length
        self.is_train = is_train
        self.stage = stage
        self.samples = []
        
        # --- LOAD DATA_01 ---
        if data01_dir and os.path.exists(data01_dir):
            classes_01 = sorted([d for d in os.listdir(data01_dir) if os.path.isdir(os.path.join(data01_dir, d))])
            for c_name in classes_01:
                if c_name == '0': 
                    continue # Bỏ qua background của Data_01
                
                # Map class 1->0, 2->1 ... 6->5 (tương ứng B1->B6)
                base_lbl = int(c_name) - 1 
                
                files = glob.glob(os.path.join(data01_dir, c_name, "*.npy"))
                for f in files:
                    self._process_file(f, base_lbl, step_size)
                    
        # --- LOAD DATA_02 ---
        if data02_dir and os.path.exists(data02_dir):
            classes_02 = sorted([d for d in os.listdir(data02_dir) if os.path.isdir(os.path.join(data02_dir, d))])
            for c_name in classes_02:
                base_lbl = int(c_name) # Đã là 0-5
                files = glob.glob(os.path.join(data02_dir, c_name, "*.npy"))
                for f in files:
                    self._process_file(f, base_lbl, step_size)
                    
        # Oversampling Class B3 (Label 2) trong lúc train vì ít dữ liệu
        if self.is_train:
            class_b3_samples = [s for s in self.samples if s[2] == 2]
            self.samples.extend(class_b3_samples * 2)
            
        # --- HIERARCHICAL STAGE MAPPING ---
        # Label gốc: 0(B1), 1(B2), 2(B3), 3(B4), 4(B5), 5(B6)
        # Stage 1: Gộp B1 và B3 (vì đều là chà 2 lòng bàn tay). 
        #          B3 gộp vào B1. Các class sau lùi lại 1 index.
        #          0->0, 1->1, 2(B3)->0, 3(B4)->2, 4(B5)->3, 5(B6)->4
        # Stage 2: Chỉ lấy B1 và B3.
        #          0(B1)->0, 2(B3)->1
        
        processed_samples = []
        for img_feat, skel_feat, lbl in self.samples:
            if self.stage == 'stage1':
                if lbl == 2: new_idx = 0
                elif lbl == 3: new_idx = 2
                elif lbl == 4: new_idx = 3
                elif lbl == 5: new_idx = 4
                else: new_idx = lbl
                processed_samples.append((img_feat, skel_feat, new_idx))
            elif self.stage == 'stage2':
                if lbl == 0:
                    processed_samples.append((img_feat, skel_feat, 0))
                elif lbl == 2:
                    processed_samples.append((img_feat, skel_feat, 1))
            else: # 'all'
                processed_samples.append((img_feat, skel_feat, lbl))
        self.samples = processed_samples
        
    def _process_file(self, f, label, step_size):
        data = np.load(f, allow_pickle=True).item()
        img_feat = data['img_feat']
        skel_feat = data['skel_feat']
        
        T = img_feat.shape[0]
        if T < self.seq_length:
            pad_len = self.seq_length - T
            img_feat = np.pad(img_feat, ((0, pad_len), (0, 0)))
            skel_feat = np.pad(skel_feat, ((0, pad_len), (0, 0)))
            self.samples.append((img_feat, skel_feat, label))
        else:
            for start in range(0, T - self.seq_length + 1, step_size):
                i_f = img_feat[start:start+self.seq_length]
                s_f = skel_feat[start:start+self.seq_length]
                self.samples.append((i_f, s_f, label))

    def _normalize_skeleton(self, skel_feat):
        T = skel_feat.shape[0]
        skel_reshaped = skel_feat.reshape(T, 2, 21, 3)
        for t in range(T):
            left_wrist = skel_reshaped[t, 0, 0].copy()
            right_wrist = skel_reshaped[t, 1, 0].copy()
            left_valid = not np.all(left_wrist == 0)
            right_valid = not np.all(right_wrist == 0)
            
            if not left_valid and not right_valid: continue
                
            if not left_valid: center = right_wrist
            elif not right_valid: center = left_wrist
            else: center = (left_wrist + right_wrist) / 2.0
                
            skel_reshaped[t] = skel_reshaped[t] - center
            
            scales = []
            if left_valid:
                scale_l = np.linalg.norm(skel_reshaped[t, 0, 9] - skel_reshaped[t, 0, 0])
                if scale_l > 1e-6: scales.append(scale_l)
            if right_valid:
                scale_r = np.linalg.norm(skel_reshaped[t, 1, 9] - skel_reshaped[t, 1, 0])
                if scale_r > 1e-6: scales.append(scale_r)
            
            if len(scales) > 0:
                global_scale = np.mean(scales)
                skel_reshaped[t] = skel_reshaped[t] / global_scale
        return skel_reshaped.reshape(T, 126)

    def _augment_skeleton_3d(self, skel_feat):
        T = skel_feat.shape[0]
        skel_reshaped = skel_feat.reshape(T, 42, 3)
        angle_x = np.random.uniform(-0.26, 0.26)
        angle_y = np.random.uniform(-0.26, 0.26)
        angle_z = np.random.uniform(-0.26, 0.26)
        
        Rx = np.array([[1, 0, 0], [0, np.cos(angle_x), -np.sin(angle_x)], [0, np.sin(angle_x), np.cos(angle_x)]], dtype=np.float32)
        Ry = np.array([[np.cos(angle_y), 0, np.sin(angle_y)], [0, 1, 0], [-np.sin(angle_y), 0, np.cos(angle_y)]], dtype=np.float32)
        Rz = np.array([[np.cos(angle_z), -np.sin(angle_z), 0], [np.sin(angle_z), np.cos(angle_z), 0], [0, 0, 1]], dtype=np.float32)
        R = Rz @ Ry @ Rx
        skel_rotated = skel_reshaped @ R.T
        return skel_rotated.reshape(T, 126)

    def __len__(self):
        return len(self.samples)
        
    def __getitem__(self, idx):
        img_feat, skel_feat, label = self.samples[idx]
        skel_feat = self._normalize_skeleton(skel_feat)
        
        if self.is_train:
            skel_feat = self._augment_skeleton_3d(skel_feat)
            noise = np.random.normal(0, 0.05, skel_feat.shape).astype(np.float32)
            skel_feat = skel_feat + noise
            
            T = img_feat.shape[0]
            mask_prob = 0.2
            mask = np.random.rand(T) > mask_prob
            mask = mask[:, np.newaxis]
            
            img_feat = img_feat * mask
            skel_feat = skel_feat * mask
            
        return torch.tensor(img_feat, dtype=torch.float32), \
               torch.tensor(skel_feat, dtype=torch.float32), \
               torch.tensor(label, dtype=torch.long)
