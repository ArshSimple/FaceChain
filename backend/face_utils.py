import face_recognition
import cv2
import numpy as np
import json
import os
import base64

# File to store user data (simulated DB)
EMBEDDINGS_FILE = "known_embeddings.json"

def load_embeddings():
    """
    Loads user data and converts face encodings from JSON Lists back to NumPy Arrays.
    """
    if not os.path.exists(EMBEDDINGS_FILE):
        return {}

    try:
        with open(EMBEDDINGS_FILE, "r") as f:
            data = json.load(f)
            
        # ⚡ CRITICAL FIX: Convert Lists back to Numpy Arrays for the AI ⚡
        for user_id, user_data in data.items():
            if 'encoding' in user_data:
                user_data['encoding'] = np.array(user_data['encoding'])
                
        return data
    except Exception as e:
        print(f"⚠️ Error loading DB: {e}")
        return {}

def save_embedding(user_id, encoding, mfa_secret, role="user", name="Unknown"):
    """
    Saves a new user. auto-converts Numpy Array to List for JSON safety.
    """
    data = load_embeddings()
    
    # ⚡ CRITICAL FIX: Ensure we save as a List, not Numpy ⚡
    if hasattr(encoding, 'tolist'):
        encoding_to_save = encoding.tolist()
    else:
        encoding_to_save = encoding

    data[str(user_id)] = {
        "name": name,
        "role": role,
        "mfa_secret": mfa_secret,
        "mfa_enabled": True,
        "encoding": encoding_to_save  # Saved as clean List
    }

    try:
        # Note: We must convert ALL arrays in 'data' to lists before dumping
        # (Because load_embeddings converts them to arrays, we need to reverse it for dump)
        data_for_json = {}
        for uid, udata in data.items():
            entry = udata.copy()
            if isinstance(entry['encoding'], np.ndarray):
                entry['encoding'] = entry['encoding'].tolist()
            data_for_json[uid] = entry

        with open(EMBEDDINGS_FILE, "w") as f:
            json.dump(data_for_json, f, indent=4)
            
        print(f"✅ User {name} (ID: {user_id}) saved locally.")
    except Exception as e:
        print(f"❌ Failed to save user: {e}")

def decode_image(base64_string):
    """
    Decodes a Base64 string from the frontend into an OpenCV image.
    """
    try:
        if "," in base64_string:
            base64_string = base64_string.split(",")[1]
        
        img_data = base64.b64decode(base64_string)
        np_arr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        
        # Convert BGR (OpenCV) to RGB (Face_Recognition)
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    except Exception as e:
        print(f"Image decode error: {e}")
        return None

def get_face_embedding(image_rgb):
    """
    Detects face and returns the 128-d encoding.
    """
    try:
        # Detect faces
        face_locations = face_recognition.face_locations(image_rgb)
        if not face_locations:
            return None
        
        # Encode the first face found
        encodings = face_recognition.face_encodings(image_rgb, face_locations)
        if encodings:
            return encodings[0] # Returns a Numpy Array
    except Exception as e:
        print(f"Embedding error: {e}")
    return None

def find_match(live_encoding, tolerance=0.45):
    """
    Compares live face with all stored faces.
    Lower tolerance = Stricter match.
    """
    data = load_embeddings()
    
    # Convert live_encoding to numpy if it isn't already
    if isinstance(live_encoding, list):
        live_encoding = np.array(live_encoding)

    for user_id, user_data in data.items():
        stored_encoding = user_data['encoding']
        
        # Calculate Distance (Math happens here)
        # ⚡ Both must be Numpy Arrays for this to work ⚡
        distance = face_recognition.face_distance([stored_encoding], live_encoding)[0]
        
        if distance < tolerance:
            return user_id, user_data
            
    return None, None