
from pathlib import Path
import shutil

import cv2
import numpy as np
from insightface.app import FaceAnalysis

BASE_DIR = Path(__file__).resolve().parent
FACE_FOLDER = BASE_DIR / "data" / "faces"

# Prototype threshold only. Validate with genuine and unknown faces.
SIMILARITY_THRESHOLD = 0.45


def load_face_model():
    """Load InsightFace, retrying once after a corrupt ONNX cache."""
    model_dir = Path.home() / ".insightface" / "models" / "buffalo_l"

    for attempt in range(2):
        print(f"Loading InsightFace model (attempt {attempt + 1}/2)...")

        try:
            face_model = FaceAnalysis(
                name="buffalo_l",
                providers=["CPUExecutionProvider"]
            )
            face_model.prepare(ctx_id=-1, det_size=(320, 320))
            print("InsightFace model loaded successfully!")
            return face_model

        except Exception as error:
            message = str(error).lower()
            corrupt_model = (
                "invalid_protobuf" in message
                or "protobuf parsing failed" in message
            )

            if not corrupt_model or attempt == 1:
                raise

            print("Corrupt ONNX cache detected.")

            # Remove only the cached buffalo_l model.
            if model_dir.exists():
                shutil.rmtree(model_dir)

            # The next attempt lets InsightFace download the model again.

    raise RuntimeError("Unable to load the InsightFace model.")


model = load_face_model()


def get_largest_face(image):
    """Return the largest detected face, or None."""
    faces = model.get(image)

    if not faces:
        return None

    return max(
        faces,
        key=lambda face: (
            (face.bbox[2] - face.bbox[0])
            * (face.bbox[3] - face.bbox[1])
        )
    )


def load_face_database():
    """
    Load enrolled face images.

    Expected layout:
        data/faces/<student_id>/face_*.jpg

    Returns:
        Dictionary mapping student IDs to representative embeddings.
    """
    face_database = {}

    if not FACE_FOLDER.exists():
        print("Face folder does not exist:", FACE_FOLDER)
        return face_database

    for student_folder in FACE_FOLDER.iterdir():
        if not student_folder.is_dir():
            continue

        try:
            student_id = int(student_folder.name)
        except ValueError:
            print(
                "Skipping folder without numeric student ID:",
                student_folder.name
            )
            continue

        embeddings = []

        for image_path in sorted(student_folder.glob("*.jpg")):
            image = cv2.imread(str(image_path))

            if image is None:
                print("Could not read:", image_path)
                continue

            face = get_largest_face(image)

            if face is None:
                print("No face detected in:", image_path)
                continue

            embedding = face.normed_embedding.astype(np.float32)
            embeddings.append(embedding)

        if embeddings:
            mean_embedding = np.mean(embeddings, axis=0)
            norm = np.linalg.norm(mean_embedding)

            if norm > 0:
                face_database[student_id] = mean_embedding / norm
                print(
                    f"Loaded student ID {student_id}: "
                    f"{len(embeddings)} usable image(s)"
                )

    print(f"Face database ready: {len(face_database)} student(s)")
    return face_database


def recognize_face(
    frame,
    face_database=None,
    threshold=SIMILARITY_THRESHOLD
):
    """
    Match the largest face in a BGR image frame.

    Returns a dictionary with student_id, similarity, and message.
    """
    if face_database is None:
        face_database = load_face_database()

    if not face_database:
        return {
            "student_id": None,
            "similarity": None,
            "message": "No enrolled face images found."
        }

    face = get_largest_face(frame)

    if face is None:
        return {
            "student_id": None,
            "similarity": None,
            "message": "No face detected."
        }

    live_embedding = face.normed_embedding.astype(np.float32)

    best_student_id = None
    best_similarity = -1.0

    for student_id, stored_embedding in face_database.items():
        similarity = float(np.dot(live_embedding, stored_embedding))

        if similarity > best_similarity:
            best_similarity = similarity
            best_student_id = student_id

    if best_similarity < threshold:
        return {
            "student_id": None,
            "similarity": best_similarity,
            "message": "No sufficiently similar enrolled face."
        }

    return {
        "student_id": best_student_id,
        "similarity": best_similarity,
        "message": "Face match found."
    }


if __name__ == "__main__":
    database = load_face_database()

    if not database:
        print("No usable face embeddings found.")
    else:
        print("Recognition module test completed.")
        print("Enrolled student IDs:", sorted(database.keys()))
        print(
            "Next: test recognize_face() with live webcam frames "
            "before recording attendance."
        )
