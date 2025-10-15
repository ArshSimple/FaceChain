from flask import Flask, request, jsonify
from flask_cors import CORS
from face_utils import extract_embedding
import os, json, base64, cv2, numpy as np
from scipy.spatial.distance import cosine

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
EMBEDDINGS_FILE = 'known_embeddings.json'

# ---------------- Load known embeddings ----------------
def load_known_embeddings():
    if not os.path.exists(EMBEDDINGS_FILE) or os.path.getsize(EMBEDDINGS_FILE) == 0:
        return {}
    with open(EMBEDDINGS_FILE, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

# ---------------- Save embedding ----------------
def save_known_embedding(user_id, embedding):
    data = load_known_embeddings()
    # Ensure each user has a list of embeddings
    if user_id in data:
        data[user_id].append(embedding.tolist())
    else:
        data[user_id] = [embedding.tolist()]
    with open(EMBEDDINGS_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# ---------------- REGISTER FACE ----------------
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data or 'image' not in data or 'user_id' not in data:
        return jsonify({"error": "No image or user_id provided"}), 400

    img_data = data['image'].split(',')[1]
    img_bytes = base64.b64decode(img_data)
    np_arr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    path = os.path.join(UPLOAD_FOLDER, f"{data['user_id']}_{len(load_known_embeddings().get(data['user_id'], []))}.jpg")
    cv2.imwrite(path, img)

    embedding = extract_embedding(path)
    if embedding is None:
        return jsonify({"error": "No face detected"}), 400

    save_known_embedding(data['user_id'], embedding)

    return jsonify({"message": "Face registered", "user_id": data['user_id']})

# ---------------- AUTHENTICATE FACE ----------------
@app.route('/authenticate', methods=['POST'])
def authenticate():
    data = request.get_json()
    if not data or 'image' not in data:
        return jsonify({"error": "No image provided"}), 400

    img_data = data['image'].split(',')[1]
    img_bytes = base64.b64decode(img_data)
    np_arr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    temp_path = os.path.join(UPLOAD_FOLDER, "auth_temp.jpg")
    cv2.imwrite(temp_path, img)

    embedding = extract_embedding(temp_path)
    if embedding is None:
        return jsonify({"error": "No face detected"}), 400

    known_embeddings = load_known_embeddings()
    best_match_uid = None
    best_similarity = -1

    # Check all users and all their embeddings
    for uid, emb_list in known_embeddings.items():
        for known_emb_list in emb_list:
            known_emb = np.array(known_emb_list)
            similarity = 1 - cosine(embedding, known_emb)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match_uid = uid

    if best_similarity > 0.6:  # Threshold
        return jsonify({"match": True, "user_id": best_match_uid, "similarity": best_similarity})
    else:
        return jsonify({"match": False})

if __name__ == '__main__':
    app.run(debug=True)
