import cv2
import numpy as np
import time
import mediapipe as mp
import threading

# Import the inference wrapper (deleted, will be rewritten later)
# from inference_pipeline import InferenceWrapper

class HandwashStateMachine:
    def __init__(self, t_min=5.0, threshold=0.8):
        self.t_min = t_min
        self.threshold = threshold
        
        self.current_step = 0 # 0 means has not started step 1 (Background)
        self.step_start_time = None
        self.step_durations = [0.0] * 7 # duration for each step 1-6 (0 is bg)
        self.completed_steps = set()
        
        # 1-indexed steps: 1 to 6
        self.total_steps = 6
        
        self.warning_msg = ""
        self.warning_time = 0

    def update(self, pred_class, confidence):
        # pred_class: 0 (bg), 1, 2, 3, 4, 5, 6
        
        if confidence < self.threshold:
            self.step_start_time = None
            return
            
        if pred_class == 0:
            self.step_start_time = None
            return
            
        if pred_class != self.current_step + 1:
            if pred_class in self.completed_steps:
                # Doing an already completed step is fine, or warning? 
                pass
            elif pred_class > self.current_step + 1:
                # Skipped a step
                self.set_warning(f"SKIPPED STEP! Please do step {self.current_step + 1} first.")
            return

        # Doing the correct next step
        if self.step_start_time is None:
            self.step_start_time = time.time()
        else:
            elapsed = time.time() - self.step_start_time
            self.step_durations[pred_class] = elapsed
            
            if elapsed >= self.t_min:
                self.completed_steps.add(pred_class)
                self.current_step = pred_class
                self.step_start_time = None
                self.set_warning(f"Step {pred_class} Completed!", duration=3.0)

    def set_warning(self, msg, duration=2.0):
        self.warning_msg = msg
        self.warning_time = time.time() + duration
        
    def get_warning(self):
        if time.time() < self.warning_time:
            return self.warning_msg
        return ""

class RealTimeApp:
    def __init__(self):
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            max_num_hands=2, min_detection_confidence=0.5, min_tracking_confidence=0.5)
            
        # Try tensorrt backend if on A100, else default mps/cpu for mac
        try:
            self.infer_engine = None # inference_pipeline was deleted
        except Exception as e:
            print("Failed to load models, continuing without them for boilerplate.")
            self.infer_engine = None
            
        self.state_machine = HandwashStateMachine(t_min=5.0)

    def draw_progress_bar(self, frame):
        h, w = frame.shape[:2]
        bar_w = 80
        bar_h = int(h * 0.8)
        start_x = w - bar_w - 20
        start_y = int((h - bar_h) / 2)
        
        step_h = bar_h // 6
        
        for i in range(1, 7):
            y1 = start_y + (6 - i) * step_h
            y2 = y1 + step_h - 5
            
            if i in self.state_machine.completed_steps:
                color = (0, 255, 0) # Green 
            elif self.state_machine.current_step + 1 == i and self.state_machine.step_start_time is not None:
                color = (0, 255, 255) # Yellow
            else:
                color = (100, 100, 100) # Gray
                
            cv2.rectangle(frame, (start_x, y1), (start_x + bar_w, y2), color, -1)
            cv2.putText(frame, f"S{i}", (start_x + 20, y1 + int(step_h/2) + 5), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,0), 2)
                        
            # progress Fill 
            if self.state_machine.current_step + 1 == i and self.state_machine.step_start_time is not None:
                progress = min(1.0, self.state_machine.step_durations[i] / self.state_machine.t_min)
                pv = int((y2 - y1) * progress)
                cv2.rectangle(frame, (start_x, y2 - pv), (start_x + bar_w, y2), (0, 200, 255), -1)

    def draw_warning(self, frame):
        msg = self.state_machine.get_warning()
        if msg:
            cv2.putText(frame, msg, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

    def process(self):
        cap = cv2.VideoCapture(0)
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret: break
            
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.hands.process(frame_rgb)
            
            # Extract dummy features for now 
            dummy_img_feat = np.random.randn(1, 1, 1024).astype(np.float32)
            dummy_skel_feat = np.zeros((1, 1, 126), dtype=np.float32)
            
            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    self.mp_drawing.draw_landmarks(frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
                    
            if self.infer_engine:
                probs = self.infer_engine.process_frame(dummy_img_feat, dummy_skel_feat)
                pred_class = np.argmax(probs)
                confidence = probs[pred_class]
            else:
                # Mock predictions
                pred_class = self.state_machine.current_step + 1
                confidence = 0.9
                
            self.state_machine.update(pred_class, confidence)
            
            self.draw_progress_bar(frame)
            self.draw_warning(frame)
            
            cv2.putText(frame, f"Class: {pred_class} Conf: {confidence:.2f}", (50, 90), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
            
            cv2.imshow('WHO Handwash Monitor', frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    app = RealTimeApp()
    app.process()
