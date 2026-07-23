import os
import sys
import time
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix, classification_report
import copy
from scipy.ndimage import median_filter
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from dataset_hybrid import HandwashNumpyDataset
from model_hybrid import HybridTCNGRU

class FocalLoss(nn.Module):
    def __init__(self, weight=None, gamma=2.0, label_smoothing=0.0):
        super(FocalLoss, self).__init__()
        self.gamma = gamma
        self.weight = weight
        self.ce = nn.CrossEntropyLoss(label_smoothing=label_smoothing, reduction='none')

    def forward(self, inputs, targets):
        ce_loss = self.ce(inputs, targets)
        p_t = torch.exp(-ce_loss)
        loss = ((1 - p_t) ** self.gamma) * ce_loss
        
        if self.weight is not None:
            w = self.weight[targets]
            loss = loss * w
            
        return loss.mean()

def train_single_model(train_loader, val_loader, num_classes, num_epochs, device, trial_run, model_name):
    print(f"--- Training {model_name} ({num_classes} classes) ---")
    model = HybridTCNGRU(num_classes=num_classes).to(device)
    
    # Calculate Class Weights
    class_counts = np.zeros(num_classes)
    for _, _, lbl in train_loader.dataset.samples:
        class_counts[lbl] += 1
        
    weights = np.zeros(num_classes)
    valid_idx = class_counts > 0
    weights[valid_idx] = 1.0 / class_counts[valid_idx]
    if weights.sum() > 0:
        weights = weights / weights.sum() * num_classes 
    else:
        weights = np.ones(num_classes)
    class_weights_tensor = torch.tensor(weights, dtype=torch.float32).to(device)
    print(f"   => {model_name} Class Counts: {class_counts.astype(int)}")
    print(f"   => {model_name} Class Weights: {np.round(weights, 2)}")
    
    criterion = FocalLoss(weight=class_weights_tensor, gamma=2.0, label_smoothing=0.1)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.0003, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='max', factor=0.5, patience=3)
    
    best_acc = 0.0
    patience_counter = 0
    early_stop_patience = 8
    best_model_wts = copy.deepcopy(model.state_dict())
    
    for epoch in range(num_epochs):
        # TRAIN
        model.train()
        train_loss = 0.0
        for batch in train_loader:
            img, skel, lbl = [x.to(device) for x in batch]
            optimizer.zero_grad()
            out = model(img, skel)
            loss = criterion(out, lbl)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
            if trial_run: break
                
        avg_train_loss = train_loss / max(len(train_loader), 1)
                
        # VALIDATE
        model.eval()
        val_loss = 0.0
        epoch_preds = []
        epoch_labels = []
        with torch.no_grad():
            for batch in val_loader:
                img, skel, lbl = [x.to(device) for x in batch]
                out = model(img, skel)
                loss = criterion(out, lbl)
                val_loss += loss.item()
                preds = torch.argmax(out, dim=1)
                epoch_preds.extend(preds.cpu().numpy())
                epoch_labels.extend(lbl.cpu().numpy())
                if trial_run: break
                    
        avg_val_loss = val_loss / max(len(val_loader), 1)
        epoch_preds = np.array(epoch_preds)
        epoch_labels = np.array(epoch_labels)
        smoothed_preds = median_filter(epoch_preds, size=3) if len(epoch_preds) > 3 else epoch_preds
        acc = (smoothed_preds == epoch_labels).sum() / max(len(epoch_labels), 1) * 100
        
        print(f"Epoch {epoch+1:02d}/{num_epochs} | Train Loss: {avg_train_loss:.4f} | Val Loss: {avg_val_loss:.4f} | Val Acc: {acc:.2f}%")
        
        if acc > best_acc:
            best_acc = acc
            best_model_wts = copy.deepcopy(model.state_dict())
            print(f"   => Best {model_name} model recorded (Acc: {best_acc:.2f}%)")
            patience_counter = 0
        else:
            patience_counter += 1
            
        scheduler.step(acc)
        if patience_counter >= early_stop_patience:
            print(f"🛑 Early Stopping: Validation Accuracy has not improved for {early_stop_patience} epochs.")
            break
        if trial_run: break
            
    model.load_state_dict(best_model_wts)
    return model

def train(trial_run=False):
    data_dir = "data/processed_features"
    if not os.path.exists(data_dir):
        # Kiểm tra thử đường dẫn thư mục hiện tại
        print(f"Không tìm thấy thư mục {data_dir}. Vui lòng chạy ở thư mục gốc chứa 'data'.")
        return

    print(f"🚀 Khởi động Training Pipeline Hybrid TCN-GRU (Hierarchical Two-Stage)...")
    
    all_subjects = set()
    classes = sorted([d for d in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, d))])
    for c_name in classes:
        c_dir = os.path.join(data_dir, c_name)
        if not os.path.isdir(c_dir): continue
        for f in os.listdir(c_dir):
            if f.endswith('.npy'):
                parts = f.replace('.npy', '').split('_')
                for i, p in enumerate(parts):
                    if p == 'G' and i+1 < len(parts):
                        all_subjects.add(f"G_{parts[i+1]}")
                        break
    all_subjects = sorted(list(all_subjects))
    if not all_subjects:
        all_subjects = ["unknown"]

    print(f"✅ Đã tìm thấy các subjects cho CV: {all_subjects}")
    
    device = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
    print(f"💻 Đang sử dụng thiết bị: {device}")
    
    fold = 1
    total_folds = len(all_subjects)
    num_epochs = 35 if not trial_run else 1
    
    for val_sub in all_subjects:
        print(f"\n=========================================")
        print(f"Bắt đầu Fold {fold}/{total_folds} - Validation Subject: {val_sub}")
        print(f"=========================================")
        
        # Datasets cho Stage 1 (6 classes)
        train_ds_stage1 = HandwashNumpyDataset(data_dir, subject_exclude=[val_sub], is_train=True, stage='stage1')
        val_ds_stage1 = HandwashNumpyDataset(data_dir, subject_include=[val_sub], is_train=False, stage='stage1')
        
        # Datasets cho Stage 2 (2 classes: chỉ lọc Class 1 và 3)
        train_ds_stage2 = HandwashNumpyDataset(data_dir, subject_exclude=[val_sub], is_train=True, stage='stage2')
        val_ds_stage2 = HandwashNumpyDataset(data_dir, subject_include=[val_sub], is_train=False, stage='stage2')
        
        # Dataset Validation gốc cho Evaluation cuối cùng (7 classes)
        val_ds_all = HandwashNumpyDataset(data_dir, subject_include=[val_sub], is_train=False, stage='all')
        
        if trial_run and (len(train_ds_stage1) == 0 or len(val_ds_stage1) == 0):
            print(f"⚠️ Cảnh báo: Không đủ dữ liệu thực cho fold {val_sub}. Bỏ qua fold này.")
            continue
            
        train_loader_stage1 = DataLoader(train_ds_stage1, batch_size=128, shuffle=True, num_workers=4, pin_memory=True)
        val_loader_stage1 = DataLoader(val_ds_stage1, batch_size=128, shuffle=False, num_workers=4, pin_memory=True)
        
        train_loader_stage2 = DataLoader(train_ds_stage2, batch_size=128, shuffle=True, num_workers=4, pin_memory=True)
        val_loader_stage2 = DataLoader(val_ds_stage2, batch_size=128, shuffle=False, num_workers=4, pin_memory=True)
        
        val_loader_all = DataLoader(val_ds_all, batch_size=128, shuffle=False, num_workers=4, pin_memory=True)
        
        # 1. Train Stage 1
        model_stage1 = train_single_model(train_loader_stage1, val_loader_stage1, num_classes=6, num_epochs=num_epochs, device=device, trial_run=trial_run, model_name="Stage 1")
        
        # 2. Train Stage 2
        model_stage2 = train_single_model(train_loader_stage2, val_loader_stage2, num_classes=2, num_epochs=num_epochs, device=device, trial_run=trial_run, model_name="Stage 2")
        
        # ==============================================================
        # --- BẮT ĐẦU VẼ BIỂU ĐỒ ĐÁNH GIÁ (HIERARCHICAL INFERENCE) ---
        # ==============================================================
        if not trial_run:
            print(f"📊 Đang tạo biểu đồ đánh giá cho Fold {fold} (Hierarchical Mode)...")
            os.makedirs("results", exist_ok=True)
            
            model_stage1.eval()
            model_stage2.eval()
            
            all_preds = []
            all_labels = []
            
            with torch.no_grad():
                for batch in val_loader_all:
                    img, skel, lbl = [x.to(device) for x in batch]
                    
                    # Chạy qua Stage 1
                    out1 = model_stage1(img, skel)
                    preds1 = torch.argmax(out1, dim=1) # Các giá trị từ 0 đến 5
                    
                    # Chạy qua Stage 2
                    out2 = model_stage2(img, skel)
                    preds2 = torch.argmax(out2, dim=1) # Các giá trị từ 0 đến 1
                    
                    # Combine dự đoán
                    final_preds = torch.zeros_like(preds1)
                    for i in range(len(preds1)):
                        p1 = preds1[i].item()
                        if p1 == 0:
                            final_preds[i] = 0
                        elif p1 == 1:
                            # Macro class 1_3 -> Gọi Stage 2
                            p2 = preds2[i].item()
                            if p2 == 0:
                                final_preds[i] = 1 # Trở về Class 1 ban đầu
                            else:
                                final_preds[i] = 3 # Trở về Class 3 ban đầu
                        elif p1 == 2:
                            final_preds[i] = 2
                        elif p1 == 3:
                            final_preds[i] = 4 # Do lúc map, class 4 thành 3
                        elif p1 == 4:
                            final_preds[i] = 5 # class 5 thành 4
                        elif p1 == 5:
                            final_preds[i] = 6 # class 6 thành 5
                            
                    all_preds.extend(final_preds.cpu().numpy())
                    all_labels.extend(lbl.cpu().numpy())
                    
            all_preds = np.array(all_preds)
            all_labels = np.array(all_labels)
            
            # --- Áp dụng Median Filter ---
            all_preds = median_filter(all_preds, size=3) if len(all_preds) > 3 else all_preds
            
            class_names = classes if len(classes) == 7 else [f"Class {i}" for i in range(7)]
            
            # 2. Bảng Accuracy
            report = classification_report(all_labels, all_preds, target_names=class_names, zero_division=0)
            print(f"\n--- BÁO CÁO CHI TIẾT FOLD {fold} ({val_sub}) ---")
            print(report)
            with open(f"results/accuracy_report_fold_{val_sub}.txt", "w") as f:
                f.write(report)
                
            # 3. Vẽ Confusion Matrix
            plt.figure(figsize=(10, 8))
            cm = confusion_matrix(all_labels, all_preds)
            sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=class_names, yticklabels=class_names)
            plt.ylabel('Thực tế (Ground Truth)')
            plt.xlabel('Dự đoán (AI Prediction)')
            plt.title(f'Confusion Matrix - Fold {fold} ({val_sub})')
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            plt.savefig(f"results/confusion_matrix_fold_{val_sub}.png")
            plt.close()
            
            # 4. Vẽ Action Timeline
            plt.figure(figsize=(16, 6))
            plt.step(range(len(all_labels)), all_labels, label='GT (Thực tế)', color='#9cd9a4', linewidth=7, where='post')
            plt.step(range(len(all_preds)), all_preds, label='AI (Hierarchical)', color='#e34a33', linestyle='--', linewidth=2, where='post')
            plt.yticks(range(len(class_names)), class_names)
            plt.xlabel('Thời gian (Cửa sổ 32-frames)')
            plt.ylabel('Hành động')
            plt.title(f'PHÂN TÍCH TIMELINE VÀ ĐỘ TRỄ: {val_sub}')
            plt.grid(True, linestyle=':', alpha=0.6)
            plt.legend(loc='upper right')
            plt.tight_layout()
            plt.savefig(f"results/timeline_fold_{val_sub}.png")
            plt.close()
            
            print(f"✅ Đã lưu các biểu đồ và báo cáo tại thư mục 'results/'.\n")
        
        if trial_run:
            print("🛑 Hoàn thành chạy thử (Trial Run) không lỗi.")
            break
            
        fold += 1

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--trial", action="store_true", help="Chạy thử 1 batch để check lỗi")
    args = parser.parse_args()
    train(trial_run=args.trial)
