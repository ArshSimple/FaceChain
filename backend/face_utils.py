import face_recognition
import dlib
import numpy as np
import json
import os
import base64
import cv2

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")
DATA_DIR = os.path.join(BASE_DIR, "data")

SHAPE_PREDICTOR_PATH = os.path.join(MODELS_DIR, "shape_predictor_68_face_landmarks.dat")
RECOGNITION_MODEL_PATH = os.path.join(MODELS_DIR, "dlib_face_recognition_resnet_model_v1.dat")
EMBEDDINGS_FILE = os.path.join(DATA_DIR, "known_embeddings.json")

# --- GLOBAL MODEL LOADING (Loads once for speed) ---
print("⏳ Loading AI Models...")
detector = dlib.get_frontal_face_detector()
try:
    predictor = dlib.shape_predictor(SHAPE_PREDICTOR_PATH)
    face_rec_model = dlib.face_recognition_model_v1(RECOGNITION_MODEL_PATH)
    print("✅ AI Models Loaded.")
except RuntimeError:
    print(f"❌ ERROR: Models not found in {MODELS_DIR}")
    print("Please move .dat files to backend/models/")
    exit(1)

def load_embeddings():
    if not os.path.exists(EMBEDDINGS_FILE):
        return {}
    try:
        with open(EMBEDDINGS_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_embedding(user_id, encoding, mfa_secret, role, name, roll_no, exam_subjects):
    data = load_embeddings()
    data[user_id] = {
        "encoding": encoding,
        "mfa_secret": mfa_secret,
        "role": role,
        "name": name,
        "roll_no": roll_no,
        "exam_subjects": exam_subjects,
        "mfa_enabled": True
    }
    with open(EMBEDDINGS_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def decode_image(base64_string):
    try:
        if "base64," in base64_string:
            base64_string = base64_string.split(",")[1]
        img_data = base64.b64decode(base64_string)
        np_arr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    except Exception:
        return None

def get_face_embedding(image):
    # Detect faces
    faces = detector(image, 1)
    if len(faces) != 1:
        return None  # Ensure exactly one face
    
    # Get shape and encoding
    shape = predictor(image, faces[0])
    face_descriptor = face_rec_model.compute_face_descriptor(image, shape)
    return np.array(face_descriptor)

def find_match(encoding, tolerance=0.45): # Stricter tolerance for security
    data = load_embeddings()
    # Compare against all known faces
    known_encodings = [np.array(v['encoding']) for v in data.values()]
    user_ids = list(data.keys())
    
    if not known_encodings:
        return None, None

    # Calculate distances
    distances = np.linalg.norm(known_encodings - encoding, axis=1)
    min_dist_idx = np.argmin(distances)
    
    if distances[min_dist_idx] < tolerance:
        matched_id = user_ids[min_dist_idx]
        return matched_id, data[matched_id]
    
    return None, None