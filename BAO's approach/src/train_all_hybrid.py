import os
import sys
import copy
import numpy as np
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

def train_single_model_all(train_loader, num_classes, num_epochs, device, model_name):
    print(f"--- Training {model_name} on ALL DATA ({num_classes} classes) ---")
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
    # Use StepLR since we have no validation loss
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=10, gamma=0.5)
    
    for epoch in range(num_epochs):
        model.train()
        train_loss = 0.0
        correct = 0
        total = 0
        
        for batch in train_loader:
            img, skel, lbl = [x.to(device) for x in batch]
            optimizer.zero_grad()
            out = model(img, skel)
            loss = criterion(out, lbl)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item()
            preds = torch.argmax(out, dim=1)
            correct += (preds == lbl).sum().item()
            total += lbl.size(0)
                
        avg_train_loss = train_loss / max(len(train_loader), 1)
        train_acc = (correct / max(total, 1)) * 100
        
        print(f"Epoch {epoch+1:02d}/{num_epochs} | Train Loss: {avg_train_loss:.4f} | Train Acc: {train_acc:.2f}%")
        
        scheduler.step()
            
    print(f"   => Training completed for {model_name}.")
    return model

def train_all():
    data_dir = "data/processed_features"
    if not os.path.exists(data_dir):
        print(f"Không tìm thấy thư mục {data_dir}. Vui lòng chạy ở thư mục gốc chứa 'data'.")
        return

    print(f"🚀 Khởi động Training Pipeline Hybrid TCN-GRU (All Data - No Validation)...")
    
    device = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
    print(f"💻 Đang sử dụng thiết bị: {device}")
    
    num_epochs = 35 
    
    # Datasets cho Stage 1 (6 classes) - empty exclude_list means include all
    train_ds_stage1 = HandwashNumpyDataset(data_dir, subject_exclude=[], is_train=True, stage='stage1')
    
    # Datasets cho Stage 2 (2 classes: chỉ lọc Class 1 và 3)
    train_ds_stage2 = HandwashNumpyDataset(data_dir, subject_exclude=[], is_train=True, stage='stage2')
        
    train_loader_stage1 = DataLoader(train_ds_stage1, batch_size=128, shuffle=True, num_workers=0, pin_memory=False)
    train_loader_stage2 = DataLoader(train_ds_stage2, batch_size=128, shuffle=True, num_workers=0, pin_memory=False)
    
    # 1. Train Stage 1
    model_stage1 = train_single_model_all(train_loader_stage1, num_classes=6, num_epochs=num_epochs, device=device, model_name="Stage 1")
    
    # 2. Train Stage 2
    model_stage2 = train_single_model_all(train_loader_stage2, num_classes=2, num_epochs=num_epochs, device=device, model_name="Stage 2")
    
    # Save models
    os.makedirs("models", exist_ok=True)
    torch.save(model_stage1.state_dict(), "models/model_stage1_all_data.pth")
    torch.save(model_stage2.state_dict(), "models/model_stage2_all_data.pth")
    
    print("✅ Đã lưu weights của 2 models tại thư mục 'models/'")
    print("Bạn có thể dùng model này để dự đoán trên Data_Rửa tay.")

if __name__ == "__main__":
    train_all()
