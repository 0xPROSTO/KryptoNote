import io

import cv2
from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = None


def create_thumbnail(file_path, size=(800, 800)):
    try:
        if file_path.lower().endswith((".mp4", ".avi", ".mov", ".mkv", ".webm")):
            cap = cv2.VideoCapture(file_path)
            ret, frame = cap.read()
            cap.release()
            if ret:
                img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            else:
                return None
        else:
            img = Image.open(file_path)
            img = ImageOps.exif_transpose(img)

        if img.mode in ("RGBA", "LA"):
            background = Image.new("RGB", img.size, (45, 45, 45))
            background.paste(img, mask=img.split()[-1])
            img = background

        elif img.mode != "RGB":
            img = img.convert("RGB")

        img.thumbnail(size, Image.Resampling.LANCZOS)

        byte_arr = io.BytesIO()
        img.save(byte_arr, format="JPEG", quality=90)
        return byte_arr.getvalue()
    except Exception as e:
        print(f"Error creating thumbnail: {e}")
        return None
