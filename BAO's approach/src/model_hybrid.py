import torch
import torch.nn as nn

class CausalConv1d(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size, dilation=1):
        super(CausalConv1d, self).__init__()
        self.padding = (kernel_size - 1) * dilation
        self.conv = nn.Conv1d(in_channels, out_channels, kernel_size, 
                              padding=self.padding, dilation=dilation)

    def forward(self, x):
        out = self.conv(x)
        # Remove future padding
        return out[:, :, :-self.padding] if self.padding > 0 else out

class HybridTCNGRU(nn.Module):
    def __init__(self, img_dim=576, skel_dim=126, hidden_dim=64, num_classes=7):
        super().__init__()
        self.img_proj = nn.Sequential(
            nn.Linear(img_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.5)
        )
        self.skel_proj = nn.Sequential(
            nn.Linear(skel_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.5)
        )
        
        # --- Gated Modality Fusion ---
        # Mạng học cách đánh giá độ tin cậy của Image và Skeleton tại mỗi frame
        self.fusion_gate = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 2),
            nn.Sigmoid()
        )
        
        # Causal TCN
        self.tcn = nn.Sequential(
            CausalConv1d(hidden_dim * 2, hidden_dim * 2, 3, dilation=1),
            nn.ReLU(),
            nn.BatchNorm1d(hidden_dim * 2),
            CausalConv1d(hidden_dim * 2, hidden_dim * 2, 3, dilation=2),
            nn.ReLU(),
            nn.BatchNorm1d(hidden_dim * 2),
            CausalConv1d(hidden_dim * 2, hidden_dim * 2, 3, dilation=4),
            nn.ReLU(),
            nn.BatchNorm1d(hidden_dim * 2),
            CausalConv1d(hidden_dim * 2, hidden_dim * 2, 3, dilation=8),
            nn.ReLU(),
            nn.BatchNorm1d(hidden_dim * 2)
        )
        
        self.gru = nn.GRU(hidden_dim * 2, hidden_dim, num_layers=1, batch_first=True)
        
        # --- Temporal Attention ---
        # Thay vì lấy trung bình (mean), mạng sẽ học cách tập trung vào các frame quan trọng nhất
        self.attention = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.Tanh(),
            nn.Linear(hidden_dim // 2, 1)
        )
        
        self.fc = nn.Linear(hidden_dim, num_classes)
        
    def forward(self, img_x, skel_x):
        h_skel = self.skel_proj(skel_x) # [B, T, hidden]
        h_img = self.img_proj(img_x)    # [B, T, hidden]
        
        # Khôi phục Modality Dropout (Tắt Ảnh hoàn toàn 75% thời gian)
        # Vì Feature Dropout (80%) vừa chạy thử khiến AI Overfit trầm trọng (Val Loss lên tới 1.9)
        # Tắt 75% Ảnh là BẮT BUỘC để ngăn AI học vẹt phông nền.
        if self.training:
            mask = (torch.rand(h_img.size(0), 1, 1, device=h_img.device) > 0.75).float()
            h_img = h_img * mask
        else:
            h_img = h_img * 0.25 
            
        # Gated Fusion: Tự động cân bằng tỷ trọng của Ảnh và Khung xương
        cat_feat = torch.cat([h_img, h_skel], dim=-1) # [B, T, 2*hidden]
        gates = self.fusion_gate(cat_feat) # [B, T, 2]
        
        h_img_gated = h_img * gates[:, :, 0:1]
        h_skel_gated = h_skel * gates[:, :, 1:2]
        x = torch.cat([h_img_gated, h_skel_gated], dim=-1) # [B, T, 2*hidden]
        
        # TCN
        x = x.transpose(1, 2)
        x = self.tcn(x)
        x = x.transpose(1, 2) # [B, T, 2*hidden]
        
        # GRU
        out, _ = self.gru(x) # [B, T, hidden_dim]
        out = torch.nn.functional.dropout(out, p=0.5, training=self.training)
        
        # Temporal Attention Pooling
        attn_weights = torch.softmax(self.attention(out), dim=1) # [B, T, 1]
        context = torch.sum(attn_weights * out, dim=1) # [B, hidden_dim]
        
        logits = self.fc(context) 
        return logits
