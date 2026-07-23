import numpy as np
data = np.load('data/processed_features/0/HandWash_004_A_11_G_01.npy', allow_pickle=True).item()
print("img_feat shape:", data['img_feat'].shape)
print("skel_feat shape:", data['skel_feat'].shape)
