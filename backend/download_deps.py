import urllib.request
import os
import bz2
import shutil

# URL for the standard Dlib shape predictor
url = "http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2"
file_name = "shape_predictor_68_face_landmarks.dat.bz2"
output_file = "shape_predictor_68_face_landmarks.dat"

print("⏳ Downloading Shape Predictor (approx 60MB)...")

try:
    if not os.path.exists(output_file):
        # Download
        urllib.request.urlretrieve(url, file_name)
        print("✅ Download Complete. Extracting...")
        
        # Extract .bz2
        with bz2.BZ2File(file_name) as fr, open(output_file, "wb") as fw:
            shutil.copyfileobj(fr, fw)
        
        # Cleanup
        os.remove(file_name)
        print("✅ Extraction Complete. File is ready.")
    else:
        print("✅ File already exists.")
        
except Exception as e:
    print(f"❌ Error: {e}")
    print("If this fails, download manually here: https://github.com/italojs/facial-landmarks-recognition/raw/master/shape_predictor_68_face_landmarks.dat")
    print("And save it as 'shape_predictor_68_face_landmarks.dat' in this folder.")