from flask import Flask, request, jsonify, session
from flask_cors import CORS
from face_utils import extract_embedding
import os, json, base64, cv2, numpy as np
from scipy.spatial.distance import cosine
from functools import wraps
import datetime

app = Flask(__name__)
app.secret_key = 'facechain_secret_key_123' 

# ---------------------------------------------------------------------------
# 1. THE "NUCLEAR" CORS FIX
# 'origins=r".*"' tells Flask to accept requests from ANYWHERE (VS Code, 
# local file, different ports) while still allowing cookies.
# ---------------------------------------------------------------------------
CORS(app, supports_credentials=True, origins=r".*")

# ---------------------------------------------------------------------------
# 2. SESSION CONFIGURATION (Crucial for Localhost)
# ---------------------------------------------------------------------------
app.config.update(
    SESSION_COOKIE_SAMESITE="Lax",  # "Lax" is required for http://localhost
    SESSION_COOKIE_SECURE=False,    # Must be False because you don't have https
    SESSION_COOKIE_HTTPONLY=True,
    PERMANENT_SESSION_LIFETIME=datetime.timedelta(days=1)
)

UPLOAD_FOLDER = 'uploads'
EMBEDDINGS_FILE = 'known_embeddings.json'
AUTH_LOGS_FILE = 'auth_logs.json'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize logs file if missing
if not os.path.exists(AUTH_LOGS_FILE):
    with open(AUTH_LOGS_FILE, 'w') as f: json.dump([], f)

# --- HELPER FUNCTIONS ---

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
    
    # Prepend new log
    logs.insert(0, {
        "timestamp": datetime.datetime.now().isoformat(),
        "user_id": user_id, 
        "status": status,
        "hash_short": f"0x{os.urandom(4).hex()}" # Simulated Blockchain Hash
    })
    
    # Keep only last 50 logs
    with open(AUTH_LOGS_FILE, 'w') as f: json.dump(logs[:50], f, indent=4)

def roles_required(*roles):
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Debug: Print what the server sees in the session
            print(f"DEBUG: Checking Role. Session User: {session.get('user_id')}, Role: {session.get('role')}")
            
            if 'role' not in session: 
                return jsonify({"error": "Login required"}), 401
            if session['role'] not in roles: 
                return jsonify({"error": f"Permission denied. You are {session['role']}"}), 403
            return f(*args, **kwargs)
        return decorated_function
    return wrapper

# --- ROUTES ---

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    try:
        # 1. Decode Image
        img_data = data['image'].split(',')[1]
        img_bytes = base64.b64decode(img_data)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        
        user_id = str(data['user_id']).strip()
        
        # 2. Save Image
        path = os.path.join(UPLOAD_FOLDER, f"{user_id}_reg.jpg")
        cv2.imwrite(path, img)
        
        # 3. Extract Embedding
        embedding = extract_embedding(path)
        if embedding is None: 
            return jsonify({"error": "No face detected in the image"}), 400
        
        # 4. Save to JSON
        known = load_known_embeddings()
        if user_id in known: 
            known[user_id].append(embedding.tolist())
        else: 
            known[user_id] = [embedding.tolist()]
            
        with open(EMBEDDINGS_FILE, 'w') as f: json.dump(known, f, indent=4)
        
        print(f"REGISTER: Success for {user_id}")
        return jsonify({"message": "Face registered successfully", "user_id": user_id})
        
    except Exception as e:
        print(f"REGISTER ERROR: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/authenticate', methods=['POST'])
def authenticate():
    data = request.get_json()
    try:
        # 1. Decode Image
        img_data = data['image'].split(',')[1]
        img_bytes = base64.b64decode(img_data)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        
        temp_path = os.path.join(UPLOAD_FOLDER, "auth_temp.jpg")
        cv2.imwrite(temp_path, img)
        
        # 2. Extract Embedding
        embedding = extract_embedding(temp_path)
        if embedding is None: 
            return jsonify({"error": "No face detected"}), 400
        
        # 3. Compare with Known Faces
        known_embeddings = load_known_embeddings()
        best_match_uid, best_similarity = None, -1
        
        for uid, emb_list in known_embeddings.items():
            for known_emb_list in emb_list:
                similarity = 1 - cosine(embedding, np.array(known_emb_list))
                if similarity > best_similarity: 
                    best_similarity = similarity
                    best_match_uid = uid
        
        # 4. Verify Threshold (0.8 is a safe bet for dlib)
        print(f"AUTH DEBUG: Best match {best_match_uid} with score {best_similarity}")
        
        if best_similarity > 0.8:
            session.clear()
            session.permanent = True
            session['user_id'] = str(best_match_uid)
            
            # Grant Admin to specific names or ID "1"
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
    # Run on port 5000
    print("Starting FaceChain Server on http://127.0.0.1:5000")
    app.run(debug=True, port=5000)