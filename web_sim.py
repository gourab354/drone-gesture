import cv2
import mediapipe as mp
import pydirectinput
import time

# --- CONFIGURATION FOR KEYBOARD CONTROLS ---
# Change these if the web simulator uses different keys!
KEY_THROTTLE_UP = 'w'
KEY_THROTTLE_DOWN = 's'
KEY_PITCH_FORWARD = 'up'
KEY_PITCH_BACKWARD = 'down'
KEY_YAW_LEFT = 'a'
KEY_YAW_RIGHT = 'd'

# Disable failsafe to avoid crashing if mouse hits corner
pydirectinput.FAILSAFE = False

# Threshold for left hand Y-axis (Throttle)
# In OpenCV, y=0 is top of screen, y=1 is bottom. 
# So < 0.4 means "high up" (lift), > 0.6 means "low down" (drop)
LIFT_THRESHOLD_UP = 0.4 
LIFT_THRESHOLD_DOWN = 0.6

# Setup MediaPipe
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
hands = mp_hands.Hands(max_num_hands=2, min_detection_confidence=0.6, min_tracking_confidence=0.6)

TIP_IDS = {"thumb": 4, "index": 8, "middle": 12, "ring": 16, "pinky": 20}
PIP_IDS = {"thumb": 2, "index": 6, "middle": 10, "ring": 14, "pinky": 18}

def get_fingers_up(landmarks, handedness_label):
    up = {}
    if handedness_label == "Right":
        up["thumb"] = landmarks[TIP_IDS["thumb"]].x < landmarks[PIP_IDS["thumb"]].x
    else:
        up["thumb"] = landmarks[TIP_IDS["thumb"]].x > landmarks[PIP_IDS["thumb"]].x

    for f in ["index", "middle", "ring", "pinky"]:
        up[f] = landmarks[TIP_IDS[f]].y < landmarks[PIP_IDS[f]].y
    return up

def press_key(key):
    pydirectinput.keyDown(key)

def release_key(key):
    pydirectinput.keyUp(key)

def main():
    cap = cv2.VideoCapture(0)
    print("Browser Drone Controller started.")
    print("Click on your browser window to make sure it receives keyboard inputs!")

    # Keep track of currently pressed keys to avoid repeating presses and to release them
    active_keys = set()

    def update_keys(keys_to_press):
        nonlocal active_keys
        # Release keys that shouldn't be pressed anymore
        for key in active_keys - keys_to_press:
            release_key(key)
        # Press new keys
        for key in keys_to_press - active_keys:
            press_key(key)
        active_keys = keys_to_press

    while True:
        ok, frame = cap.read()
        if not ok: break

        frame = cv2.flip(frame, 1) # Mirror image
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb)

        keys_this_frame = set()
        left_hand_action = "HOLD"
        right_hand_action = "HOLD"

        if result.multi_hand_landmarks:
            for hand_landmarks, handedness in zip(result.multi_hand_landmarks, result.multi_handedness):
                label = handedness.classification[0].label # "Left" or "Right"
                lm = hand_landmarks.landmark
                up = get_fingers_up(lm, label)
                n_up = sum(up.values())
                fingers_up = {k for k, v in up.items() if v}

                mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

                # ---------------- LEFT HAND LOGIC ----------------
                if label == "Left":
                    # Muthi baniye (Fist) -> all fingers down (n_up == 0 or close to 0)
                    if n_up <= 1: # allowing thumb or 1 finger accident to still be fist
                        # check Y coordinate of the wrist (landmark 0)
                        wrist_y = lm[0].y
                        if wrist_y < LIFT_THRESHOLD_UP:
                            keys_this_frame.add(KEY_THROTTLE_UP)
                            left_hand_action = "LIFT (UP)"
                        elif wrist_y > LIFT_THRESHOLD_DOWN:
                            keys_this_frame.add(KEY_THROTTLE_DOWN)
                            left_hand_action = "DROP (DOWN)"
                        else:
                            left_hand_action = "FIST (CENTER)"

                # ---------------- RIGHT HAND LOGIC ----------------
                elif label == "Right":
                    if fingers_up == {"index"}:
                        keys_this_frame.add(KEY_PITCH_FORWARD)
                        right_hand_action = "FORWARD"
                    elif fingers_up == {"index", "middle"}:
                        keys_this_frame.add(KEY_PITCH_BACKWARD)
                        right_hand_action = "BACKWARD"
                    elif fingers_up == {"thumb"}:
                        keys_this_frame.add(KEY_YAW_LEFT)
                        right_hand_action = "TURN LEFT"
                    elif fingers_up == {"pinky"}:
                        keys_this_frame.add(KEY_YAW_RIGHT)
                        right_hand_action = "TURN RIGHT"

        # Apply keyboard inputs
        update_keys(keys_this_frame)

        # Draw UI
        cv2.putText(frame, f"Left Hand: {left_hand_action}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, f"Right Hand: {right_hand_action}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, f"Keys Pressed: {', '.join(active_keys)}", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        # Draw threshold lines
        h, w = frame.shape[:2]
        cv2.line(frame, (0, int(h * LIFT_THRESHOLD_UP)), (w, int(h * LIFT_THRESHOLD_UP)), (200, 200, 200), 1)
        cv2.line(frame, (0, int(h * LIFT_THRESHOLD_DOWN)), (w, int(h * LIFT_THRESHOLD_DOWN)), (200, 200, 200), 1)
        cv2.putText(frame, "LIFT ZONE", (10, int(h * LIFT_THRESHOLD_UP) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200,200,200), 1)
        cv2.putText(frame, "DROP ZONE", (10, int(h * LIFT_THRESHOLD_DOWN) + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200,200,200), 1)

        cv2.imshow("Browser Controller", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Cleanup
    update_keys(set()) # Release all keys
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
