import json

with open('Handwash_Train_Colab.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

train_func = """# ============================================================
# CELL 10: HÀM HUẤN LUYỆN VÀ 3 EXPERIMENTS
# ============================================================
from sklearn.metrics import classification_report
import pandas as pd
import time
import torch
import torch.nn as nn
import torch.optim as optim

def train_single_model(train_loader, val_loader, num_classes, num_epochs, device, fold_name):
    model = HybridTCNGRU(num_classes=num_classes).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=5, verbose=True)
    
    best_val_acc = 0.0
    best_val_loss = float('inf')
    best_model_state = None
    patience_counter = 0
    patience_limit = 10
    
    print(f"  ▶ Training {fold_name}...")
    for epoch in range(num_epochs):
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0
        for img, skel, lbl in train_loader:
            img, skel, lbl = img.to(device), skel.to(device), lbl.to(device)
            optimizer.zero_grad()
            out = model(img, skel)
            loss = criterion(out, lbl)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            
            train_loss += loss.item() * img.size(0)
            preds = torch.argmax(out, 1)
            train_correct += (preds == lbl).sum().item()
            train_total += img.size(0)
            
        train_loss /= max(train_total, 1)
        
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        with torch.no_grad():
            for img, skel, lbl in val_loader:
                img, skel, lbl = img.to(device), skel.to(device), lbl.to(device)
                out = model(img, skel)
                loss = criterion(out, lbl)
                val_loss += loss.item() * img.size(0)
                preds = torch.argmax(out, 1)
                val_correct += (preds == lbl).sum().item()
                val_total += img.size(0)
                
        val_loss /= max(val_total, 1)
        val_acc = val_correct / max(val_total, 1) * 100
        
        scheduler.step(val_loss)
        
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_val_loss = val_loss
            best_model_state = model.state_dict()
            patience_counter = 0
            star = "⭐"
        else:
            patience_counter += 1
            star = f"(patience {patience_counter}/{patience_limit})"
            
        print(f"    Epoch {epoch+1:02d}/{num_epochs} | Loss {train_loss:.4f}/{val_loss:.4f} | Acc {val_acc:.2f}% {star}")
        
        if patience_counter >= patience_limit:
            print(f"    🛑 Early stop at epoch {epoch+1}")
            break
            
    if best_model_state is not None:
        model.load_state_dict(best_model_state)
    return model, best_val_loss, best_val_acc

"""

# find cell 10 string to append
for cell in nb.get('cells', []):
    if cell.get('cell_type') == 'code' and 'id' in cell.get('metadata', {}):
        if cell['metadata']['id'] == 'cell_09_training':
            old_code = "".join(cell['source'])
            # Remove the first 3 lines of old code (the # CELL 10 comment)
            old_code = old_code.split('\n', 3)[3]
            new_code = train_func + old_code
            cell['source'] = [line + '\n' for line in new_code.split('\n')]
            cell['source'][-1] = cell['source'][-1].rstrip('\n')

with open('Handwash_Train_Colab.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)
