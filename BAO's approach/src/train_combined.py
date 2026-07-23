import os
import sys
import copy
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from scipy.ndimage import median_filter
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from dataset_combined import CombinedHandwashDataset
from model_hybrid import HybridTCNGRU
from train_hybrid import FocalLoss, train_single_model

def train_combined_model(trial_run=False):
    data01_dir = "Data_01/processed_features"
    data02_train = "Data_02_features/train"
    data02_test = "Data_02_features/test"
    
    device = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
    print(f"💻 Đang sử dụng thiết bị: {device}")
    
    print(f"🚀 Khởi động Training Pipeline GỘP (Data_01 + Data_02)...")
    
    # 1. Dataset Stage 1 (Gộp B1 và B3, tổng 5 classes)
    train_ds_s1 = CombinedHandwashDataset(data01_dir, data02_train, is_train=True, stage='stage1')
    test_ds_s1 = CombinedHandwashDataset(None, data02_test, is_train=False, stage='stage1')
    
    # 2. Dataset Stage 2 (Chỉ lọc B1 và B3, tổng 2 classes)
    train_ds_s2 = CombinedHandwashDataset(data01_dir, data02_train, is_train=True, stage='stage2')
    test_ds_s2 = CombinedHandwashDataset(None, data02_test, is_train=False, stage='stage2')
    
    # 3. Dataset All (Đánh giá tổng hợp 6 classes)
    test_ds_all = CombinedHandwashDataset(None, data02_test, is_train=False, stage='all')
    
    if len(train_ds_s1) == 0:
        print("Không tìm thấy dữ liệu train!")
        return

    print(f"✅ Đã load dữ liệu: Stage1 Train={len(train_ds_s1)} | Stage2 Train={len(train_ds_s2)} | Test={len(test_ds_all)}")

    train_loader_s1 = DataLoader(train_ds_s1, batch_size=128, shuffle=True)
    test_loader_s1 = DataLoader(test_ds_s1, batch_size=128, shuffle=False)
    
    train_loader_s2 = DataLoader(train_ds_s2, batch_size=128, shuffle=True)
    test_loader_s2 = DataLoader(test_ds_s2, batch_size=128, shuffle=False)
    
    test_loader_all = DataLoader(test_ds_all, batch_size=128, shuffle=False)
    
    num_epochs = 35 if not trial_run else 1
    
    # --- TRAINING ---
    model_s1 = train_single_model(train_loader_s1, test_loader_s1, num_classes=5, num_epochs=num_epochs, device=device, trial_run=trial_run, model_name="Stage 1")
    model_s2 = train_single_model(train_loader_s2, test_loader_s2, num_classes=2, num_epochs=num_epochs, device=device, trial_run=trial_run, model_name="Stage 2")
    
    # --- EVALUATION ---
    if not trial_run:
        print(f"📊 Đang tạo biểu đồ đánh giá trên Test Set (Data_02)...")
        os.makedirs("results", exist_ok=True)
        
        model_s1.eval()
        model_s2.eval()
        
        all_preds = []
        all_labels = []
        
        with torch.no_grad():
            for batch in test_loader_all:
                img, skel, lbl = [x.to(device) for x in batch]
                
                out1 = model_s1(img, skel)
                preds1 = torch.argmax(out1, dim=1)
                
                out2 = model_s2(img, skel)
                preds2 = torch.argmax(out2, dim=1)
                
                final_preds = torch.zeros_like(preds1)
                for i in range(len(preds1)):
                    p1 = preds1[i].item()
                    if p1 == 0:
                        # Gọi Stage 2
                        p2 = preds2[i].item()
                        if p2 == 0:
                            final_preds[i] = 0 # B1
                        else:
                            final_preds[i] = 2 # B3
                    elif p1 == 1: final_preds[i] = 1 # B2
                    elif p1 == 2: final_preds[i] = 3 # B4
                    elif p1 == 3: final_preds[i] = 4 # B5
                    elif p1 == 4: final_preds[i] = 5 # B6
                        
                all_preds.extend(final_preds.cpu().numpy())
                all_labels.extend(lbl.cpu().numpy())
                
        all_preds = np.array(all_preds)
        all_labels = np.array(all_labels)
        
        # Áp dụng Median Filter
        all_preds = median_filter(all_preds, size=3) if len(all_preds) > 3 else all_preds
        
        class_names = ["B1", "B2", "B3", "B4", "B5", "B6"]
        
        report = classification_report(all_labels, all_preds, target_names=class_names, zero_division=0)
        print(f"\n--- BÁO CÁO CHI TIẾT TEST SET (Data_02) ---")
        print(report)
        with open("results/accuracy_report_combined.txt", "w") as f:
            f.write(report)
            
        plt.figure(figsize=(10, 8))
        cm = confusion_matrix(all_labels, all_preds)
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=class_names, yticklabels=class_names)
        plt.ylabel('Thực tế')
        plt.xlabel('Dự đoán')
        plt.title('Confusion Matrix - Test Set Data_02')
        plt.tight_layout()
        plt.savefig("results/confusion_matrix_combined.png")
        plt.close()
        
        print("✅ Đã lưu báo cáo tại thư mục 'results/'.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--trial", action="store_true", help="Chạy thử 1 epoch")
    args = parser.parse_args()
    train_combined_model(trial_run=args.trial)
