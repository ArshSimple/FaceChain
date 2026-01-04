from flask import Flask, request, jsonify, session
from flask_cors import CORS
from face_utils import extract_embedding
import os, json, base64, cv2, numpy as np
from scipy.spatial.distance import cosine
from functools import wraps
import datetime

app = Flask(__name__)
app.secret_key = 'facechain_secret_key_123' 

# CORS & Session Config (Keeping your working setup)
CORS(app, supports_credentials=True, origins=r".*")

app.config.update(
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_HTTPONLY=True,
    PERMANENT_SESSION_LIFETIME=datetime.timedelta(days=1)
)

UPLOAD_FOLDER = 'uploads'
EMBEDDINGS_FILE = 'known_embeddings.json'
AUTH_LOGS_FILE = 'auth_logs.json'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

if not os.path.exists(AUTH_LOGS_FILE):
    with open(AUTH_LOGS_FILE, 'w') as f: json.dump([], f)

def load_known_embeddings():
    if not os.path.exists(EMBEDDINGS_FILE) or os.path.getsize(EMBEDDINGS_FILE) == 0:
        return {}
    with open(EMBEDDINGS_FILE, 'r') as f:
        try: return json.load(f)
        except: return {}

def log_authentication(user_id, status):
    logs = []
    if os.path.exists(AUTH_LOGS_FILE):
        with open(AUTH_LOGS_FILE, 'r') as f:
            try: logs = json.load(f)
            except: logs = []
    logs.insert(0, {
        "timestamp": datetime.datetime.now().isoformat(),
        "user_id": user_id, 
        "status": status,
        "hash_short": f"0x{os.urandom(4).hex()}"
    })
    with open(AUTH_LOGS_FILE, 'w') as f: json.dump(logs[:50], f, indent=4)

def roles_required(*roles):
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'role' not in session: 
                return jsonify({"error": "Login required"}), 401
            if session['role'] not in roles: 
                return jsonify({"error": "Permission denied"}), 403
            return f(*args, **kwargs)
        return decorated_function
    return wrapper

# --- REGISTER ROUTE (Updated) ---
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    try:
        img_data = data['image'].split(',')[1]
        img_bytes = base64.b64decode(img_data)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        
        user_id = str(data['user_id']).strip()
        path = os.path.join(UPLOAD_FOLDER, f"{user_id}_reg.jpg")
        cv2.imwrite(path, img)
        
        embedding = extract_embedding(path)
        
        # --- NEW SECURITY CHECKS ---
        if isinstance(embedding, str) and embedding == "MULTIPLE_FACES":
            os.remove(path) # Cleanup
            return jsonify({"error": "⚠️ SECURITY ALERT: Multiple faces detected! Only one person allowed."}), 400
            
        if embedding is None: 
            os.remove(path) # Cleanup
            return jsonify({"error": "No face detected. Please face the camera clearly."}), 400
        # ---------------------------

        known = load_known_embeddings()
        if user_id in known: 
            known[user_id].append(embedding.tolist())
        else: 
            known[user_id] = [embedding.tolist()]
            
        with open(EMBEDDINGS_FILE, 'w') as f: json.dump(known, f, indent=4)
        return jsonify({"message": "Face registered successfully", "user_id": user_id})
        
    except Exception as e:
        print(f"REGISTER ERROR: {e}")
        return jsonify({"error": str(e)}), 500

# --- AUTHENTICATE ROUTE (Updated) ---
@app.route('/authenticate', methods=['POST'])
def authenticate():
    data = request.get_json()
    try:
        img_data = data['image'].split(',')[1]
        img_bytes = base64.b64decode(img_data)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        
        temp_path = os.path.join(UPLOAD_FOLDER, "auth_temp.jpg")
        cv2.imwrite(temp_path, img)
        
        embedding = extract_embedding(temp_path)
        
        # --- NEW SECURITY CHECKS ---
        if isinstance(embedding, str) and embedding == "MULTIPLE_FACES":
            log_authentication("Security_Alert", "BLOCKED_MULTIPLE_FACES")
            return jsonify({"error": "⚠️ ACCESS DENIED: Multiple faces detected."}), 400
            
        if embedding is None: 
            return jsonify({"error": "No face detected"}), 400
        # ---------------------------
        
        known_embeddings = load_known_embeddings()
        best_match_uid, best_similarity = None, -1
        
        for uid, emb_list in known_embeddings.items():
            for known_emb_list in emb_list:
                similarity = 1 - cosine(embedding, np.array(known_emb_list))
                if similarity > best_similarity: 
                    best_similarity = similarity
                    best_match_uid = uid
        
        if best_similarity > 0.8:
            session.clear()
            session.permanent = True
            session['user_id'] = str(best_match_uid)
            
            uid_lower = str(best_match_uid).lower()
            if uid_lower in ["1", "admin", "arsh", "test"]:
                session['role'] = 'admin'
            else:
                session['role'] = 'user'
                
            log_authentication(best_match_uid, "SUCCESS")
            return jsonify({"match": True, "user_id": best_match_uid, "role": session['role']})
        
        log_authentication("Unknown", "FAILED")
        return jsonify({"match": False})
        
    except Exception as e: 
        print(f"AUTH ERROR: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/admin/stats', methods=['GET'])
@roles_required('admin')
def get_admin_stats():
    try:
        with open(AUTH_LOGS_FILE, 'r') as f: logs = json.load(f)
        return jsonify({
            "total_users": len(load_known_embeddings()), 
            "logs": logs, 
            "blockchain_status": "Connected (Ganache)"
        })
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})

if __name__ == '__main__':
    print("Starting FaceChain Server on http://127.0.0.1:5000")
    app.run(debug=True, port=5000)