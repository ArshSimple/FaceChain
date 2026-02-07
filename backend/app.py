# --- 1. SILENCE WARNINGS (MUST BE FIRST) ---
import warnings
import os
import logging

# Filter specific "pkg_resources" warning
warnings.filterwarnings("ignore", category=UserWarning, message=".*pkg_resources is deprecated.*")
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Silence Flask's startup logs safely
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# --- 2. STANDARD IMPORTS ---
from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
import pyotp
import face_utils
from eth_chain import eth_ledger as ledger
import json
import numpy as np
import webbrowser
from threading import Timer
from datetime import datetime

# --- PATH CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_FOLDER = os.path.join(os.path.dirname(BASE_DIR), "frontend")
DATA_DIR = os.path.join(BASE_DIR, "data")
SCHEDULE_FILE = os.path.join(DATA_DIR, "exam_schedule.json")

app = Flask(__name__, static_folder=FRONTEND_FOLDER)
app.secret_key = 'RESET_SESSION_KEY_999' 
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False 
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# --- GLOBAL CACHE ---
print("🚀 Loading User Database...")
USER_DB_CACHE = face_utils.load_embeddings()
print(f"✅ Database Loaded: {len(USER_DB_CACHE)} users.")

def load_schedule():
    if not os.path.exists(SCHEDULE_FILE): return {}
    with open(SCHEDULE_FILE, 'r') as f: return json.load(f)

def save_schedule(data):
    with open(SCHEDULE_FILE, 'w') as f: json.dump(data, f, indent=4)

def save_all_users():
    with open(face_utils.EMBEDDINGS_FILE, 'w') as f:
        json.dump(USER_DB_CACHE, f, indent=4)

@app.route('/')
def serve_index(): return send_from_directory(FRONTEND_FOLDER, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename): return send_from_directory(FRONTEND_FOLDER, filename)

# --- AUTHENTICATION & REGISTER ---

@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.json
        user_id = data.get('user_id')
        name = data.get('name')
        
        if not user_id or not data.get('image'): return jsonify({"error": "Missing Data"}), 400

        img_rgb = face_utils.decode_image(data.get('image'))
        if img_rgb is None: return jsonify({"error": "Image Decode Failed"}), 400
        
        encoding = face_utils.get_face_embedding(img_rgb)
        if encoding is None: return jsonify({"error": "No face detected"}), 400
        if hasattr(encoding, 'tolist'): encoding = encoding.tolist()

        if user_id in USER_DB_CACHE:
            return jsonify({"error": "User ID already exists"}), 400

        mfa_secret = pyotp.random_base32()
        uri = pyotp.totp.TOTP(mfa_secret).provisioning_uri(name=f"{name} ({user_id})", issuer_name="FaceChain Exam")
        role = "admin" if str(user_id) == "1" else "student"
        
        new_user = {
            "encoding": encoding,
            "mfa_secret": mfa_secret,
            "role": role,
            "name": name,
            "roll_no": data.get('roll_no'),
            "exam_subjects": data.get('exam_subjects') or [],
            "mfa_enabled": True,
            "exams_verified": [] 
        }

        USER_DB_CACHE[user_id] = new_user
        save_all_users()

        ledger.register_user(user_id, encoding)
        ledger.add_log(user_id, f"REGISTER: {name}", "SUCCESS", request.remote_addr)
        
        return jsonify({"message": "Registered", "mfa_uri": uri})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/authenticate', methods=['POST'])
def authenticate():
    data = request.json
    user_id_input = data.get('user_id')
    
    if user_id_input not in USER_DB_CACHE:
        ledger.add_log(user_id_input, "LOGIN_ATTEMPT", "USER_NOT_FOUND", request.remote_addr)
        return jsonify({"match": False, "error": "User not found"}), 200

    img_rgb = face_utils.decode_image(data.get('image'))
    if img_rgb is None: return jsonify({"match": False}), 400
    
    encoding = face_utils.get_face_embedding(img_rgb)
    if encoding is None: 
        ledger.add_log(user_id_input, "LOGIN_ATTEMPT", "NO_FACE", request.remote_addr)
        return jsonify({"match": False}), 200

    matched_id, user_data = face_utils.find_match(encoding)
    
    if matched_id and matched_id == user_id_input:
        ledger.verify_user(matched_id, encoding.tolist())
        return jsonify({
            "match": True, "user_id": matched_id, 
            "name": user_data.get('name'), "mfa_required": user_data.get('mfa_enabled', True) 
        })
    else:
        ledger.add_log(user_id_input, "LOGIN_ATTEMPT", "FACE_MISMATCH", request.remote_addr)
        return jsonify({"match": False})

@app.route('/verify-mfa', methods=['POST'])
def verify_mfa():
    data = request.json
    user_id = data.get('user_id')
    code = data.get('code')
    user = USER_DB_CACHE.get(user_id)
    
    if not user: return jsonify({"success": False}), 400
    if str(user_id) == "1": user['role'] = 'admin'

    if pyotp.TOTP(user['mfa_secret']).verify(code) or user.get('mfa_enabled', True) == False:
        session['user_id'] = user_id
        session['role'] = user['role']
        session['logged_in'] = True
        ledger.add_log(user_id, "LOGIN", "SUCCESS", request.remote_addr)
        return jsonify({
            "success": True, "role": user['role'], 
            "exam_subjects": user.get('exam_subjects', []), 
            "schedule": load_schedule()
        })
    
    ledger.add_log(user_id, "MFA_VERIFY", "FAILED", request.remote_addr)
    return jsonify({"success": False, "message": "Invalid Code"})

@app.route('/mark_exam_verified', methods=['POST'])
def mark_exam_verified():
    if not session.get('logged_in'): return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    user_id = session.get('user_id')
    subject = data.get('subject')
    
    if user_id in USER_DB_CACHE:
        if 'exams_verified' not in USER_DB_CACHE[user_id]:
            USER_DB_CACHE[user_id]['exams_verified'] = []
            
        record_entry = f"{subject}"
        
        if record_entry not in USER_DB_CACHE[user_id]['exams_verified']:
            USER_DB_CACHE[user_id]['exams_verified'].append(record_entry)
            save_all_users()
            ledger.add_log(user_id, f"EXAM_START: {subject}", "VERIFIED", request.remote_addr)
            
        return jsonify({"success": True})
    return jsonify({"error": "User not found"}), 404

# --- ADMIN ROUTES ---

@app.route('/admin/stats', methods=['GET'])
def admin_stats():
    if not session.get('logged_in') or session.get('role') != 'admin': 
        return jsonify({"error": "Unauthorized"}), 401

    user_list = []
    for k, v in USER_DB_CACHE.items():
        user_list.append({
            "id": k, 
            "name": v.get("name"), 
            "roll_no": v.get("roll_no"), 
            "exam_subjects": v.get("exam_subjects", []),
            "exams_verified": v.get("exams_verified", []),
            "mfa_enabled": v.get("mfa_enabled", True)
        })
    
    return jsonify({
        "total_users": len(USER_DB_CACHE), 
        "user_list": user_list, 
        "logs": ledger.get_logs(), 
        "schedule": load_schedule()
    })

@app.route('/admin/set_schedule', methods=['POST'])
def set_schedule():
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    schedule = load_schedule()
    schedule[data.get('subject')] = data.get('date')
    save_schedule(schedule)
    return jsonify({"success": True})

@app.route('/admin/delete_schedule', methods=['POST'])
def delete_schedule():
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    subject = data.get('subject')
    schedule = load_schedule()
    if subject in schedule:
        del schedule[subject]
        save_schedule(schedule)
        return jsonify({"success": True})
    return jsonify({"error": "Subject not found"}), 404

@app.route('/admin/toggle_mfa', methods=['POST'])
def toggle_mfa():
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 401
    user_id = request.json.get('user_id')
    if user_id in USER_DB_CACHE:
        USER_DB_CACHE[user_id]['mfa_enabled'] = not USER_DB_CACHE[user_id].get('mfa_enabled', True)
        save_all_users()
        return jsonify({"success": True})
    return jsonify({"error": "Not Found"}), 404

@app.route('/admin/delete_user', methods=['POST'])
def delete_user():
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 401
    user_id = request.json.get('user_id')
    if user_id == "1": return jsonify({"error": "Cannot delete admin"}), 403
    if user_id in USER_DB_CACHE:
        del USER_DB_CACHE[user_id]
        save_all_users()
        ledger.add_log("ADMIN", f"DELETED_USER: {user_id}", "WARNING", request.remote_addr)
        return jsonify({"success": True})
    return jsonify({"error": "Not Found"}), 404

@app.route('/logout')
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})

def open_browser():
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        webbrowser.open_new('http://127.0.0.1:5000')

if __name__ == '__main__':
    print("🚀 FaceChain Server Running on Port 5000...")
    Timer(1, open_browser).start()
    app.run(debug=True, port=5000)