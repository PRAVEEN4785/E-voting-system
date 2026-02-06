import cv2
import numpy as np
import base64
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# Eye landmark indices (FaceMesh compatible)
LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]


def decode_image(base64_img):
    header, encoded = base64_img.split(",", 1)
    img = base64.b64decode(encoded)
    npimg = np.frombuffer(img, np.uint8)
    return cv2.imdecode(npimg, cv2.IMREAD_COLOR)


def eye_aspect_ratio(eye):
    A = np.linalg.norm(eye[1] - eye[5])
    B = np.linalg.norm(eye[2] - eye[4])
    C = np.linalg.norm(eye[0] - eye[3])
    return (A + B) / (2.0 * C)


def check_liveness(image_list):
    blink = False
    left = False
    right = False

    EAR_THRESHOLD = 0.23

    base_options = python.BaseOptions(
        model_asset_path="models/face_landmarker.task"
    )

    options = vision.FaceLandmarkerOptions(
        base_options=base_options,
        output_face_blendshapes=False,
        output_facial_transformation_matrixes=False,
        num_faces=1
    )

    detector = vision.FaceLandmarker.create_from_options(options)

    for img_data in image_list:
        image = decode_image(img_data)
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb
        )

        result = detector.detect(mp_image)

        if not result.face_landmarks:
            continue

        landmarks = result.face_landmarks[0]
        h, w, _ = image.shape

        def p(i):
            return np.array([landmarks[i].x * w, landmarks[i].y * h])

        left_eye = np.array([p(i) for i in LEFT_EYE])
        right_eye = np.array([p(i) for i in RIGHT_EYE])

        ear = (eye_aspect_ratio(left_eye) + eye_aspect_ratio(right_eye)) / 2
        if ear < EAR_THRESHOLD:
            blink = True

        nose_x = landmarks[1].x
        if nose_x < 0.48:
            left = True
        elif nose_x > 0.52:
            right = True

        if blink and left and right:
            detector.close()
            return True
        print(
    f"EAR={ear:.3f}, nose_x={nose_x:.3f}, "
    f"blink={blink}, left={left}, right={right}"
)


    detector.close()
    return False
