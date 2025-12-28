import dlib
import numpy as np
import cv2
import hashlib

# Load models (download from dlib.net and place in this directory)
shape_predictor = dlib.shape_predictor("shape_predictor_68_face_landmarks.dat")
face_rec_model = dlib.face_recognition_model_v1("dlib_face_recognition_resnet_model_v1.dat")
face_detector = dlib.get_frontal_face_detector()

def extract_embedding(image_path):
    image = cv2.imread(image_path)
    if image is None:
        return None
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    detections = face_detector(rgb)
    if not detections:
        return None
    shape = shape_predictor(rgb, detections[0])
    face_descriptor = face_rec_model.compute_face_descriptor(rgb, shape)
    return np.array(face_descriptor)

def compute_sha256(embedding):
    return hashlib.sha256(embedding.tobytes()).hexdigest()
