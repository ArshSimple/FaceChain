import urllib.request, bz2, shutil, os

def download_and_extract(url, filename, output_name):
    print(f"⬇️  Downloading {output_name}...")
    try:
        urllib.request.urlretrieve(url, filename)
        print(f"📦 Extracting {filename}...")
        with bz2.BZ2File(filename) as fr, open(output_name, "wb") as fw:
            shutil.copyfileobj(fr, fw)
        os.remove(filename)
        print(f"✅ {output_name} ready.")
    except Exception as e:
        print(f"❌ Error: {e}")

models = [
    ("http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2", 
     "shape_predictor_68_face_landmarks.dat.bz2", "shape_predictor_68_face_landmarks.dat"),
    ("http://dlib.net/files/dlib_face_recognition_resnet_model_v1.dat.bz2", 
     "dlib_face_recognition_resnet_model_v1.dat.bz2", "dlib_face_recognition_resnet_model_v1.dat")
]

if __name__ == "__main__":
    for url, archive, final in models:
        if not os.path.exists(final): download_and_extract(url, archive, final)
        else: print(f"⚡ {final} already exists.")