import numpy as np
T = 32
skel_reshaped = np.zeros((T, 42, 3))
R = np.zeros((3, 3))
res = skel_reshaped @ R.T
print(res.shape, res.size)
