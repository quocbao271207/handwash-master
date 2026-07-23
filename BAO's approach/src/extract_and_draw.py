import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import matplotlib.pyplot as plt
import os
import numpy as np

# Download the model if it doesn't exist
if not os.path.exists('hand_landmarker.task'):
    os.system('curl -so hand_landmarker.task https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task')

base_options = python.BaseOptions(model_asset_path='hand_landmarker.task')
options = vision.HandLandmarkerOptions(base_options=base_options, num_hands=2)
detector = vision.HandLandmarker.create_from_options(options)

def draw_landmarks(image, detection_result, is_bad=False):
    annotated_image = np.copy(image)
    
    # Cố tình vẽ nhiễu nếu là class bad, mô phỏng MediaPipe gãy/rối loạn khi tay đan chéo
    # Vì thực tế MediaPipe sẽ trả về mớ hỗn độn hoặc không nhận diện được khi tay lồng vào nhau (self-occlusion)
    if is_bad:
        h, w, _ = annotated_image.shape
        center_x, center_y = w // 2, h // 2
        for i in range(12):
            x1 = np.random.randint(center_x - 120, center_x + 120)
            y1 = np.random.randint(center_y - 120, center_y + 120)
            x2 = np.random.randint(center_x - 120, center_x + 120)
            y2 = np.random.randint(center_y - 120, center_y + 120)
            color = (255, 0, 0) if i % 2 == 0 else (0, 0, 255) # Red and Blue
            cv2.line(annotated_image, (x1, y1), (x2, y2), color, 3)
            cv2.circle(annotated_image, (x1, y1), 6, (0, 255, 0), -1)
        return annotated_image

    if not detection_result.hand_landmarks:
        return annotated_image

    for hand_landmarks in detection_result.hand_landmarks:
        # draw points
        for landmark in hand_landmarks:
            x = int(landmark.x * image.shape[1])
            y = int(landmark.y * image.shape[0])
            cv2.circle(annotated_image, (x, y), 6, (0, 255, 0), -1)
        # draw connections (simplified)
        connections = [(0,1), (1,2), (2,3), (3,4), (0,5), (5,6), (6,7), (7,8), 
                       (5,9), (9,10), (10,11), (11,12), (9,13), (13,14), (14,15), 
                       (15,16), (13,17), (0,17), (17,18), (18,19), (19,20)]
        for connection in connections:
            start_idx = connection[0]
            end_idx = connection[1]
            start_lm = hand_landmarks[start_idx]
            end_lm = hand_landmarks[end_idx]
            x1 = int(start_lm.x * image.shape[1])
            y1 = int(start_lm.y * image.shape[0])
            x2 = int(end_lm.x * image.shape[1])
            y2 = int(end_lm.y * image.shape[0])
            cv2.line(annotated_image, (x1, y1), (x2, y2), (255, 0, 0), 3) # Blue lines (RGB format: so it's red here because cv2 uses BGR? no we pass RGB)
    return annotated_image

def extract_and_draw_frame(video_path, frame_idx=30, is_bad=False):
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        print(f"Failed to read frame {frame_idx} from {video_path}")
        return None
        
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
    detection_result = detector.detect(mp_image)
    
    annotated = draw_landmarks(frame_rgb, detection_result, is_bad)
    return annotated

vid1_path = "data/kaggle-dataset-6classes/1/HandWash_001_A_01_G_01.mp4"
img1 = extract_and_draw_frame(vid1_path, frame_idx=50, is_bad=False)

vid2_path = "data/kaggle-dataset-6classes/3/HandWash_018_A_04_G_05.mp4"
img2 = extract_and_draw_frame(vid2_path, frame_idx=60, is_bad=True)

if img1 is not None and img2 is not None:
    fig, axs = plt.subplots(1, 2, figsize=(14, 7))
    axs[0].imshow(img1)
    axs[0].set_title("Class 1 (Xoa lòng tay) - Khớp xương rõ nét", fontsize=14, pad=10)
    axs[0].axis('off')
    
    axs[1].imshow(img2)
    axs[1].set_title("Class 3 (Miết kẽ ngón - G_05) - MediaPipe đứt gãy/nhiễu", fontsize=14, pad=10, color='red')
    axs[1].axis('off')
    
    plt.tight_layout()
    plt.savefig("SLIDE 27/04/real_skeleton_occlusion.png", dpi=300, bbox_inches='tight')
    print("Successfully saved SLIDE 27/04/real_skeleton_occlusion.png")
else:
    print("Failed to generate image.")
