import dlib
import numpy as np
import json
import os
import cv2
import base64

EMBEDDINGS_FILE = 'known_embeddings.json'
PREDICTOR = "shape_predictor_68_face_landmarks.dat"
REC_MODEL = "dlib_face_recognition_resnet_model_v1.dat"

# Initialize Models
try:
    if os.path.exists(PREDICTOR) and os.path.exists(REC_MODEL):
        detector = dlib.get_frontal_face_detector()
        sp = dlib.shape_predictor(PREDICTOR)
        facerec = dlib.face_recognition_model_v1(REC_MODEL)
    else:
        print("⚠️ AI Models missing. Run 'python setup_models.py' first!")
except Exception as e:
    print(f"Error loading models: {e}")

def load_embeddings():
    if not os.path.exists(EMBEDDINGS_FILE): return {}
    with open(EMBEDDINGS_FILE, 'r') as f:
        data = json.load(f)
        for k, v in data.items(): v['encoding'] = np.array(v['encoding'])
        return data

# UPDATED: Now accepts 'name'
def save_embedding(user_id, encoding, mfa_secret, role, name="Unknown"):
    data = load_embeddings()
    data[user_id] = {
        "name": name,
        "encoding": encoding.tolist(),
        "mfa_secret": mfa_secret,
        "role": role
    }
    with open(EMBEDDINGS_FILE, 'w') as f: json.dump(data, f)

def decode_image(b64):
    try:
        if "," in b64: b64 = b64.split(",")[1]
        arr = np.frombuffer(base64.b64decode(b64), np.uint8)
        return cv2.cvtColor(cv2.imdecode(arr, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    except: return None

def get_face_embedding(img):
    if 'detector' not in globals(): return None
    dets = detector(img, 1)
    if not dets: return None
    shape = sp(img, dets[0])
    return np.array(facerec.compute_face_descriptor(img, shape))

def find_match(target_enc, tolerance=0.5):
    db = load_embeddings()
    best_match = None
    min_dist = 1.0
    for uid, data in db.items():
        dist = np.linalg.norm(target_enc - data['encoding'])
        if dist < tolerance and dist < min_dist:
            min_dist = dist
            best_match = (uid, data)
    return best_match if best_match else (None, None)