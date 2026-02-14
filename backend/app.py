# ==========================================
# 1. INITIALIZATION & SECURITY SETUP
# ==========================================
import warnings, os, logging, secrets, json, webbrowser
from threading import Timer
from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import pyotp, face_utils
from eth_chain import eth_ledger as ledger

# Silence specific warnings & logs
warnings.filterwarnings("ignore", category=UserWarning, message=".*pkg_resources.*")
logging.getLogger('werkzeug').setLevel(logging.ERROR)

# Config & Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND = os.path.join(os.path.dirname(BASE_DIR), "frontend")
DATA_FILE = os.path.join(BASE_DIR, "data", "known_embeddings.json")
SCHED_FILE = os.path.join(BASE_DIR, "data", "exam_schedule.json")

app = Flask(__name__, static_folder=FRONTEND)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32)) # Secure Key
app.config.update(SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=False, SESSION_COOKIE_HTTPONLY=True)

# Security: CORS (Localhost Only) & Rate Limiter
CORS(app, resources={r"/*": {"origins": ["http://127.0.0.1:5000", "http://localhost:5000"]}}, supports_credentials=True)
limiter = Limiter(get_remote_address, app=app, default_limits=["200 per day", "50 per hour"], storage_uri="memory://")

# ==========================================
# 2. DATABASE HELPERS (The "RAM Cache")
# ==========================================
print("🚀 Loading Database...")
USER_DB = face_utils.load_embeddings() # Load RAM Cache

def save_db():
    """Saves RAM Cache to JSON file."""
    with open(face_utils.EMBEDDINGS_FILE, 'w') as f: json.dump(USER_DB, f, indent=4)

def load_sched():
    if not os.path.exists(SCHED_FILE): return {}
    with open(SCHED_FILE, 'r') as f: return json.load(f)

def save_sched(data):
    with open(SCHED_FILE, 'w') as f: json.dump(data, f, indent=4)

def json_resp(success=True, data=None, msg="", code=200):
    """Shortcut for JSON responses."""
    payload = {"success": success, "message": msg}
    if data: payload.update(data)
    if not success and not msg: payload["error"] = "Unknown Error"
    return jsonify(payload), code

# ==========================================
# 3. CORE & AUTH ROUTES
# ==========================================
@app.route('/')
def index(): return send_from_directory(FRONTEND, 'index.html')

@app.route('/<path:filename>')
def static_files(filename): return send_from_directory(FRONTEND, filename)

@app.route('/register', methods=['POST'])
@limiter.limit("5 per minute")
def register():
    try:
        d = request.json
        uid, name, img = d.get('user_id'), d.get('name'), d.get('image')
        
        if uid in USER_DB: return json_resp(False, msg="User ID Exists", code=400)
        
        # AI Processing
        encoding = face_utils.get_face_embedding(face_utils.decode_image(img))
        if encoding is None: return json_resp(False, msg="No Face Detected", code=400)

        # Create Profile
        mfa_secret = pyotp.random_base32()
        USER_DB[uid] = {
            "encoding": encoding.tolist(), "mfa_secret": mfa_secret,
            "role": "admin" if str(uid) == "1" else "student", "name": name,
            "roll_no": uid, "exam_subjects": d.get('exam_subjects', []),
            "mfa_enabled": True, "exams_verified": []
        }
        save_db()
        ledger.register_user(uid, encoding.tolist()) # Blockchain Log
        ledger.add_log(uid, f"REGISTER: {name}", "SUCCESS", request.remote_addr)

        uri = pyotp.totp.TOTP(mfa_secret).provisioning_uri(name=f"{name} ({uid})", issuer_name="FaceChain")
        
        # ✅ FIX: Added 'msg' here so frontend doesn't show "undefined"
        return json_resp(True, {"mfa_uri": uri}, msg="✅ Registration Successful! Please scan the QR Code.")
        
    except Exception as e: return json_resp(False, msg=str(e), code=500)

@app.route('/authenticate', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    d = request.json
    uid = d.get('user_id')
    
    if uid not in USER_DB:
        ledger.add_log(uid, "LOGIN_ATTEMPT", "USER_NOT_FOUND", request.remote_addr)
        return json_resp(False, msg="User Not Found", code=200)

    # Face Check
    encoding = face_utils.get_face_embedding(face_utils.decode_image(d.get('image')))
    if encoding is None: return json_resp(False, msg="No Face Visible", code=200)
    
    match_id, _ = face_utils.find_match(encoding)
    if match_id == uid:
        ledger.verify_user(match_id, encoding.tolist())
        return json_resp(True, {"match": True, "mfa_required": USER_DB[uid].get('mfa_enabled', True)})
    
    ledger.add_log(uid, "LOGIN_ATTEMPT", "FACE_MISMATCH", request.remote_addr)
    return json_resp(False, {"match": False})

@app.route('/verify-mfa', methods=['POST'])
@limiter.limit("5 per minute")
def verify_mfa():
    d = request.json
    uid, code = d.get('user_id'), d.get('code')
    user = USER_DB.get(uid)

    if not user: return json_resp(False, code=400)
    
    # Check Code OR if MFA is Disabled
    if pyotp.TOTP(user['mfa_secret']).verify(code) or not user.get('mfa_enabled', True):
        session['user_id'] = uid
        session['role'] = user['role']
        session['logged_in'] = True
        ledger.add_log(uid, "LOGIN", "SUCCESS", request.remote_addr)
        return json_resp(True, {"role": user['role'], "exam_subjects": user.get('exam_subjects', []), "schedule": load_sched()})

    ledger.add_log(uid, "MFA_VERIFY", "FAILED", request.remote_addr)
    return json_resp(False, msg="Invalid Code")

# ==========================================
# 4. EXAM & ADMIN ROUTES
# ==========================================
@app.route('/mark_exam_verified', methods=['POST'])
def mark_verified():
    if not session.get('logged_in'): return json_resp(False, code=401)
    uid, sub = session.get('user_id'), request.json.get('subject')
    
    if uid in USER_DB and sub not in USER_DB[uid]['exams_verified']:
        USER_DB[uid]['exams_verified'].append(sub)
        save_db()
        ledger.add_log(uid, f"EXAM_START: {sub}", "VERIFIED", request.remote_addr)
    return json_resp(True)

@app.route('/admin/stats')
def admin_stats():
    if session.get('role') != 'admin': return json_resp(False, code=401)
    
    users = [{"id": k, "name": v["name"], "roll_no": v["roll_no"], 
              "exam_subjects": v["exam_subjects"], "exams_verified": v["exams_verified"],
              "mfa_enabled": v.get("mfa_enabled", True)} for k, v in USER_DB.items()]
    
    return json_resp(True, {"total": len(USER_DB), "user_list": users, "logs": ledger.get_logs(), "schedule": load_sched()})

@app.route('/admin/set_schedule', methods=['POST'])
def set_sched():
    if session.get('role') != 'admin': return json_resp(False, code=401)
    sch = load_sched()
    sch[request.json.get('subject')] = request.json.get('date')
    save_sched(sch)
    return json_resp(True)

@app.route('/admin/delete_schedule', methods=['POST'])
def del_sched():
    if session.get('role') != 'admin': return json_resp(False, code=401)
    sch = load_sched()
    sch.pop(request.json.get('subject'), None)
    save_sched(sch)
    return json_resp(True)

@app.route('/admin/user_ops', methods=['POST'])
def user_ops():
    """Handles Delete User AND Toggle MFA to save lines."""
    if session.get('role') != 'admin': return json_resp(False, code=401)
    d = request.json
    uid, action = d.get('user_id'), d.get('action') # 'delete' or 'toggle_mfa'

    if uid not in USER_DB: return json_resp(False, msg="Not Found", code=404)
    
    if action == 'delete':
        if uid == "1": return json_resp(False, msg="Cannot delete Admin", code=403)
        del USER_DB[uid]
        ledger.add_log("ADMIN", f"DELETED: {uid}", "WARNING", request.remote_addr)
    elif action == 'toggle_mfa':
        USER_DB[uid]['mfa_enabled'] = not USER_DB[uid].get('mfa_enabled', True)
    
    save_db()
    return json_resp(True)

@app.route('/logout')
def logout():
    session.clear()
    return json_resp(True, msg="Logged out")

if __name__ == '__main__':
    print("🚀 FaceChain Server Running (Secure Mode)...")
    if not os.environ.get("WERKZEUG_RUN_MAIN"): webbrowser.open_new('http://127.0.0.1:5000')
    app.run(debug=False, port=5000)