
import cv2
import sqlite3
import numpy as np
from pathlib import Path
from datetime import datetime
from insightface.app import FaceAnalysis

# ---------- Configuration ----------
DB_PATH = "attendance.db"
FACE_DIR = Path("data/faces")

# Prototype threshold only; validate before real use.
SIMILARITY_THRESHOLD = 0.50

# ---------- Load face recognition model ----------
print("Loading face recognition model...")

recognizer = FaceAnalysis(
    name="buffalo_l",
    providers=["CPUExecutionProvider"]
)
recognizer.prepare(ctx_id=0, det_size=(640, 640))

print("Model loaded.")

# ---------- Load enrolled face embeddings ----------
known_faces = {}

for student_folder in FACE_DIR.iterdir():
    if not student_folder.is_dir():
        continue

    roll_number = student_folder.name
    embeddings = []

    for image_path in student_folder.glob("*"):
        if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue

        image = cv2.imread(str(image_path))
        if image is None:
            continue

        faces = recognizer.get(image)
        if not faces:
            continue

        # Use the largest detected face in the enrollment image.
        face = max(
            faces,
            key=lambda item: (
                item.bbox[2] - item.bbox[0]
            ) * (
                item.bbox[3] - item.bbox[1]
            )
        )

        embedding = face.normed_embedding
        embeddings.append(embedding)

    if embeddings:
        average = np.mean(embeddings, axis=0)
        average = average / np.linalg.norm(average)
        known_faces[roll_number] = average

if not known_faces:
    raise RuntimeError(
        "No usable enrolled faces found in data/faces."
    )

print("Loaded enrolled roll numbers:", list(known_faces.keys()))

# ---------- Attendance database ----------
def mark_attendance(roll_number):
    """Record at most one attendance entry per student per date."""
    connection = sqlite3.connect(DB_PATH)

    try:
        student = connection.execute(
            "SELECT name FROM students WHERE roll_number = ?",
            (roll_number,)
        ).fetchone()

        if student is None:
            print(
                f"Roll number {roll_number} is not registered "
                "in the students table."
            )
            return False

        connection.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                attendance_date TEXT NOT NULL,
                attendance_time TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Present',
                UNIQUE(student_id, attendance_date),
                FOREIGN KEY(student_id) REFERENCES students(id)
            )
        """)

        today = datetime.now().strftime("%Y-%m-%d")
        current_time = datetime.now().strftime("%H:%M:%S")

        cursor = connection.execute("""
            INSERT OR IGNORE INTO attendance
            (student_id, attendance_date, attendance_time, status)
            SELECT id, ?, ?, 'Present'
            FROM students
            WHERE roll_number = ?
        """, (today, current_time, roll_number))

        connection.commit()

        if cursor.rowcount == 1:
            print(f"Attendance recorded: {student[0]} ({roll_number})")
        else:
            print(f"Attendance already recorded today: {roll_number}")

        return True

    finally:
        connection.close()

# ---------- Live webcam recognition ----------
camera = cv2.VideoCapture(0)

if not camera.isOpened():
    raise RuntimeError(
        "Could not open webcam. Close other apps using the camera."
    )

print("Webcam started. Press Q to quit.")

# Avoid writing attendance on every video frame.
last_seen = {}

try:
    while True:
        success, frame = camera.read()

        if not success:
            print("Could not read a webcam frame.")
            break

        detected_faces = recognizer.get(frame)
        current_time = datetime.now().timestamp()

        for face in detected_faces:
            embedding = face.normed_embedding
            x1, y1, x2, y2 = map(int, face.bbox)

            best_roll = None
            best_score = -1.0

            for roll_number, known_embedding in known_faces.items():
                score = float(np.dot(embedding, known_embedding))

                if score > best_score:
                    best_score = score
                    best_roll = roll_number

            if best_roll is not None and best_score >= SIMILARITY_THRESHOLD:
                label = f"Roll {best_roll} | Similarity {best_score:.2f}"

                # Try to record once when this person is seen.
                # Database uniqueness prevents duplicate daily entries.
                if current_time - last_seen.get(best_roll, 0) > 5:
                    mark_attendance(best_roll)
                    last_seen[best_roll] = current_time
            else:
                label = "Unknown"

            cv2.rectangle(
                frame, (x1, y1), (x2, y2), (0, 255, 0), 2
            )
            cv2.putText(
                frame,
                label,
                (x1, max(y1 - 10, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2
            )

        cv2.imshow("Live Face Attendance - Press Q to quit", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

finally:
    camera.release()
    cv2.destroyAllWindows()

print("Live attendance stopped.")
