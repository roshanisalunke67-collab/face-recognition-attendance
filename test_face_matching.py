
from pathlib import Path

import cv2
import numpy as np
from insightface.app import FaceAnalysis

FACE_FOLDER = Path("data") / "faces"

model = FaceAnalysis(
    name="buffalo_l",
    providers=["CPUExecutionProvider"]
)
model.prepare(ctx_id=-1, det_size=(640, 640))

def get_largest_face_embedding(image_path):
    image = cv2.imread(str(image_path))

    if image is None:
        return None

    faces = model.get(image)

    if not faces:
        return None

    # Select the largest detected face
    face = max(
        faces,
        key=lambda f: (
            (f.bbox[2] - f.bbox[0]) *
            (f.bbox[3] - f.bbox[1])
        )
    )

    return face.normed_embedding

# Load reference images for registered students
known_embeddings = {}

for student_folder in FACE_FOLDER.iterdir():
    if not student_folder.is_dir():
        continue

    embeddings = []

    for image_path in student_folder.glob("*.jpg"):
        embedding = get_largest_face_embedding(image_path)

        if embedding is not None:
            embeddings.append(embedding)

    if embeddings:
        known_embeddings[student_folder.name] = np.mean(
            embeddings, axis=0
        )
        known_embeddings[student_folder.name] /= np.linalg.norm(
            known_embeddings[student_folder.name]
        )

if not known_embeddings:
    print("No usable reference faces found.")
    raise SystemExit(1)

# Test matching using a saved reference image
test_image = next(FACE_FOLDER.glob("*/*.jpg"))
test_embedding = get_largest_face_embedding(test_image)

if test_embedding is None:
    print("No face found in the test image.")
    raise SystemExit(1)

scores = {
    roll: float(np.dot(test_embedding, reference))
    for roll, reference in known_embeddings.items()
}

best_roll = max(scores, key=scores.get)

print("\nFace matching test")
print("Test image:", test_image)
print("Best matching roll number:", best_roll)
print("Cosine similarity:", round(scores[best_roll], 4))
print("Similarity scores are not calibrated probabilities.")
print("This is a prototype test, not proof of identity.")
