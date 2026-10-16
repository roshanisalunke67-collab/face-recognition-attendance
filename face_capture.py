
import cv2
from pathlib import Path

# Face images are stored inside the project folder.
BASE_DIR = Path(__file__).resolve().parent
FACE_FOLDER = BASE_DIR / "data" / "faces"


def capture_face(student_id, images_to_capture=5):
    """Capture face images for an existing student using their database ID."""

    try:
        student_id = int(student_id)
        if student_id <= 0:
            raise ValueError
    except (ValueError, TypeError):
        print("Invalid student ID.")
        return 0

    student_folder = FACE_FOLDER / str(student_id)
    student_folder.mkdir(parents=True, exist_ok=True)

    # Continue numbering so existing images are not overwritten.
    existing_images = list(student_folder.glob("face_*.jpg"))
    saved_numbers = []

    for image_path in existing_images:
        try:
            saved_numbers.append(int(
                image_path.stem.replace("face_", "")
            ))
        except ValueError:
            continue

    next_number = max(saved_numbers, default=0) + 1

    camera = cv2.VideoCapture(0)

    if not camera.isOpened():
        print("Could not open webcam. Check camera permissions.")
        return 0

    saved = 0

    print("Position the consenting student in the camera.")
    print("Press SPACE to capture an image.")
    print("Press Q to stop.")

    try:
        while saved < images_to_capture:
            success, frame = camera.read()

            if not success:
                print("Could not read from webcam.")
                break

            cv2.imshow("FaceAttend - Student Face Registration", frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord(" "):
                filename = student_folder / (
                    f"face_{next_number + saved}.jpg"
                )

                if cv2.imwrite(str(filename), frame):
                    saved += 1
                    print(f"Saved image {saved}: {filename}")

            elif key == ord("q"):
                break

    finally:
        camera.release()
        cv2.destroyAllWindows()

    print(f"Capture finished. New images saved: {saved}")
    return saved


if __name__ == "__main__":
    student_id = input("Enter the registered student's database ID: ")
    capture_face(student_id)
