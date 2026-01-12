from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
import pyotp
import face_utils
# Using the Ethereum Bridge
from eth_chain import eth_ledger as ledger
import os
import re
import json

# Configuration for finding frontend files
FRONTEND_FOLDER = os.path.abspath("../frontend")
app = Flask(__name__, static_folder=FRONTEND_FOLDER)
app.secret_key = 'super_secret_facechain_key'

# Allow CORS for all domains
CORS(app, resources={r"/*": {"origins": re.compile(r"^.*$")}}, supports_credentials=True)

# --- ROUTE: SERVE FRONTEND ---
@app.route('/')
def serve_index(): 
    return send_from_directory(FRONTEND_FOLDER, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename): 
    return send_from_directory(FRONTEND_FOLDER, filename)

# --- ROUTE: REGISTER ---
@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.json
        user_id = data.get('user_id')
        name = data.get('name') or "Unknown"
        image_b64 = data.get('image')

        if not user_id or not image_b64: 
            return jsonify({"error": "Missing Data"}), 400

        # 1. Decode Image
        img_rgb = face_utils.decode_image(image_b64)
        if img_rgb is None: 
            return jsonify({"error": "Image Decode Failed"}), 400

        # 2. Get Face Embedding
        encoding = face_utils.get_face_embedding(img_rgb)
        if encoding is None: 
            return jsonify({"error": "No face detected"}), 400

        # 3. Check for Duplicates
        existing_id, _ = face_utils.find_match(encoding)
        if existing_id: 
            return jsonify({"error": f"Face already registered as {existing_id}"}), 400

        # 4. Generate MFA
        mfa_secret = pyotp.random_base32()
        uri = pyotp.totp.TOTP(mfa_secret).provisioning_uri(name=str(user_id), issuer_name="FaceChain")
        role = "admin" if str(user_id) == "1" else "user"
        
        # 5. Save to Database
        face_utils.save_embedding(user_id, encoding, mfa_secret, role, name)
        
        # 6. Write to Ethereum Blockchain
        ledger.add_log(user_id, f"REGISTER: {name}", "SUCCESS", request.remote_addr)

        return jsonify({"message": "Registered", "mfa_uri": uri})
    except Exception as e:
        print(f"Server Error: {e}")
        return jsonify({"error": str(e)}), 500

# --- ROUTE: AUTHENTICATE (STEP 1) ---
@app.route('/authenticate', methods=['POST'])
def authenticate():
    data = request.json
    image_b64 = data.get('image')
    img_rgb = face_utils.decode_image(image_b64)
    if img_rgb is None: return jsonify({"match": False}), 400
    
    encoding = face_utils.get_face_embedding(img_rgb)
    if encoding is None: return jsonify({"match": False}), 200

    user_id, user_data = face_utils.find_match(encoding)

    if user_id:
        # DO NOT LOGIN YET. Just confirm face match.
        return jsonify({
            "match": True, 
            "user_id": user_id, 
            "name": user_data.get('name', 'User')
        })
    
    return jsonify({"match": False})

# --- ROUTE: VERIFY MFA (STEP 2 - LOGIN) ---
@app.route('/verify-mfa', methods=['POST'])
def verify_mfa():
    data = request.json
    user_id = data.get('user_id')
    code = data.get('code')

    db = face_utils.load_embeddings()
    user = db.get(user_id)

    if not user: 
        return jsonify({"success": False, "message": "User not found"}), 400

    # Verify TOTP Code
    totp = pyotp.TOTP(user['mfa_secret'])
    if totp.verify(code):
        # Create Session
        session['user_id'] = user_id
        session['role'] = user['role']
        session['logged_in'] = True
        
        # Write Login to Ethereum
        ledger.add_log(user_id, "LOGIN_MFA", "SUCCESS", request.remote_addr)
        return jsonify({"success": True, "role": user['role']})
    
    # Log Failure
    ledger.add_log(user_id, "LOGIN_MFA", "FAILED", request.remote_addr)
    return jsonify({"success": False, "message": "Invalid Code"})

# --- ROUTE: ADMIN DASHBOARD DATA ---
@app.route('/admin/stats', methods=['GET'])
def admin_stats():
    # Security Check
    if not session.get('logged_in') or session.get('role') != 'admin':
         return jsonify({"error": "Unauthorized"}), 401
    
    db = face_utils.load_embeddings()
    
    # FETCH LOGS FROM ETHEREUM SMART CONTRACT
    logs = ledger.get_logs()
    logs.reverse() # Show newest first

    user_list = [{"id": k, "name": v.get("name", "Unknown")} for k, v in db.items()]
    return jsonify({"total_users": len(db), "user_list": user_list, "logs": logs})

# --- ROUTE: DELETE USER ---
@app.route('/admin/delete_user', methods=['POST'])
def delete_user():
    if not session.get('logged_in') or session.get('role') != 'admin': 
        return jsonify({"error": "Unauthorized"}), 401
    
    user_to_delete = request.json.get('user_id')
    
    # 🛑 SECURITY: PROTECT ADMIN
    if str(user_to_delete) == "1":
        return jsonify({"error": "Cannot delete the Super Admin!"}), 403

    db = face_utils.load_embeddings()
    if user_to_delete in db:
        del db[user_to_delete]
        with open(face_utils.EMBEDDINGS_FILE, 'w') as f: 
            json.dump(db, f)
        
        # Log Deletion to Blockchain
        ledger.add_log(session['user_id'], f"DELETE_USER: {user_to_delete}", "SUCCESS", request.remote_addr)
        return jsonify({"message": "User deleted"})
    
    return jsonify({"error": "User not found"}), 404

# --- ROUTE: LOGOUT (FIXED) ---
@app.route('/logout')
def logout():
    # 1. Capture user info BEFORE destroying session
    user_id = session.get('user_id')
    
    # 2. Log to Ethereum Ledger if user was logged in
    if user_id:
        try:
            ledger.add_log(user_id, "LOGOUT", "SUCCESS", request.remote_addr)
            print(f"✅ Logout logged for User {user_id}")
        except Exception as e:
            print(f"⚠️ Failed to log logout: {e}")

    # 3. NOW destroy session
    session.clear()
    return jsonify({"message": "Logged out"})

if __name__ == '__main__':
    print(f"🚀 FaceChain Server Running.")
    app.run(debug=True, port=5000)