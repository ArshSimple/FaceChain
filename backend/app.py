from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
import pyotp
import face_utils
# Using the Ethereum Bridge
from eth_chain import eth_ledger as ledger
import os
import re
import json
import numpy as np  # Added to handle array checks

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

        # ⚡ FIX: Convert Numpy Array to List for JSON Serialization ⚡
        if hasattr(encoding, 'tolist'):
            encoding = encoding.tolist()

        # 3. Check for Duplicates (Local Check)
        # Note: We convert back to array if find_match expects it, but usually lists work fine for comparison checks
        existing_id, _ = face_utils.find_match(np.array(encoding))
        if existing_id: 
            return jsonify({"error": f"Face already registered as {existing_id}"}), 400

        # 4. Generate MFA
        mfa_secret = pyotp.random_base32()
        uri = pyotp.totp.TOTP(mfa_secret).provisioning_uri(name=str(user_id), issuer_name="FaceChain")
        role = "admin" if str(user_id) == "1" else "user"
        
        # 5. Save to Local Database (For Backup/Fast Match)
        # Now passing a LIST, so json.dump won't crash
        face_utils.save_embedding(user_id, encoding, mfa_secret, role, name)
        
        # 6. REGISTER ON BLOCKCHAIN (The New Step)
        success = ledger.register_user(user_id, encoding)
        
        if success:
            ledger.add_log(user_id, f"REGISTER: {name}", "SUCCESS", request.remote_addr)
            return jsonify({"message": "Registered On-Chain", "mfa_uri": uri})
        else:
            return jsonify({"error": "Blockchain Registration Failed"}), 500

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

    # Find match locally first to get the User ID
    # We pass the raw numpy array here because dlib/face_recognition expects it for math
    user_id, user_data = face_utils.find_match(encoding)

    if user_id:
        # OPTIONAL: Perform On-Chain Verification here
        # We convert to list() because Blockchain functions need clean numbers, not numpy objects
        ledger.verify_user(user_id, encoding.tolist())

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

    # Check if MFA is globally enabled for this user
    if user.get('mfa_enabled', True) == False:
         session['user_id'] = user_id
         session['role'] = user['role']
         session['logged_in'] = True
         ledger.add_log(user_id, "LOGIN_NO_MFA", "SUCCESS", request.remote_addr)
         return jsonify({"success": True, "role": user['role']})

    # Verify TOTP Code
    totp = pyotp.TOTP(user['mfa_secret'])
    if totp.verify(code):
        session['user_id'] = user_id
        session['role'] = user['role']
        session['logged_in'] = True
        
        ledger.add_log(user_id, "LOGIN_MFA", "SUCCESS", request.remote_addr)
        return jsonify({"success": True, "role": user['role']})
    
    ledger.add_log(user_id, "LOGIN_MFA", "FAILED", request.remote_addr)
    return jsonify({"success": False, "message": "Invalid Code"})

# --- ROUTE: ADMIN DASHBOARD DATA ---
@app.route('/admin/stats', methods=['GET'])
def admin_stats():
    if not session.get('logged_in') or session.get('role') != 'admin':
         return jsonify({"error": "Unauthorized"}), 401
    
    db = face_utils.load_embeddings()
    
    # FETCH LOGS FROM ETHEREUM SMART CONTRACT
    logs = ledger.get_logs()
    
    # Convert DB to list for frontend
    user_list = []
    for k, v in db.items():
        user_list.append({
            "id": k, 
            "name": v.get("name", "Unknown"),
            "mfa_enabled": v.get("mfa_enabled", True)
        })

    return jsonify({"total_users": len(db), "user_list": user_list, "logs": logs})

# --- ROUTE: DELETE USER ---
@app.route('/admin/delete_user', methods=['POST'])
def delete_user():
    if not session.get('logged_in') or session.get('role') != 'admin': 
        return jsonify({"error": "Unauthorized"}), 401
    
    user_to_delete = request.json.get('user_id')
    
    if str(user_to_delete) == "1":
        return jsonify({"error": "Cannot delete the Super Admin!"}), 403

    db = face_utils.load_embeddings()
    if user_to_delete in db:
        deleted_name = db[user_to_delete].get('name', 'Unknown')
        
        del db[user_to_delete]
        with open(face_utils.EMBEDDINGS_FILE, 'w') as f: 
            json.dump(db, f)
        
        ledger.add_log(session['user_id'], f"DELETE: {deleted_name} (ID: {user_to_delete})", "SUCCESS", request.remote_addr)
        return jsonify({"message": "User deleted"})
    
    return jsonify({"error": "User not found"}), 404

# --- ROUTE: TOGGLE MFA ---
@app.route('/admin/toggle_mfa', methods=['POST'])
def toggle_mfa():
    if not session.get('logged_in') or session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    user_id = data.get('user_id')
    
    db = face_utils.load_embeddings()
    if user_id in db:
        # Toggle Status
        current_status = db[user_id].get('mfa_enabled', True)
        new_status = not current_status
        db[user_id]['mfa_enabled'] = new_status
        
        with open(face_utils.EMBEDDINGS_FILE, 'w') as f:
            json.dump(db, f)
            
        status_text = "ENABLED" if new_status else "DISABLED"
        ledger.add_log(session['user_id'], f"MFA_CHANGE: User {user_id} set to {status_text}", "SUCCESS", request.remote_addr)
        
        return jsonify({"success": True, "new_status": new_status})
    
    return jsonify({"error": "User not found"}), 404

# --- ROUTE: LOGOUT ---
@app.route('/logout')
def logout():
    user_id = session.get('user_id')
    if user_id:
        try:
            ledger.add_log(user_id, "LOGOUT", "SUCCESS", request.remote_addr)
        except Exception as e:
            print(f"⚠️ Failed to log logout: {e}")

    session.clear()
    return jsonify({"message": "Logged out"})

if __name__ == '__main__':
    print(f"🚀 FaceChain Server Running.")
    app.run(debug=True, port=5000)