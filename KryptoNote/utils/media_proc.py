import io
from dataclasses import dataclass

import cv2
from PIL import Image, ImageOps

_MAX_DECODE_BYTES = 256 * 1024 * 1024
_MAX_DECODE_PIXELS = _MAX_DECODE_BYTES // 4
# Pillow raises DecompressionBombError above twice this value, keeping a
# worst-case RGBA decode within the same 256 MiB ceiling as QImageReader.
Image.MAX_IMAGE_PIXELS = _MAX_DECODE_PIXELS // 2
_LARGE_IMAGE_THRESHOLD = Image.MAX_IMAGE_PIXELS


@dataclass
class MediaMetadata:
    width: int = 0
    height: int = 0
    duration: float = 0.0


def read_media_metadata(file_path):
    try:
        if file_path.lower().endswith((".mp4", ".avi", ".mov", ".mkv", ".webm")):
            cap = cv2.VideoCapture(file_path)
            try:
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
                frames = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
            finally:
                cap.release()
            duration = frames / fps if fps > 0 and frames > 0 else 0.0
            return MediaMetadata(width=width, height=height, duration=duration)

        with Image.open(file_path) as img:
            width, height = img.size
            try:
                orientation = img.getexif().get(274, 1)
            except (AttributeError, TypeError, ValueError):
                orientation = 1
            if orientation in (5, 6, 7, 8):
                width, height = height, width
            pixels = width * height
            if pixels > _LARGE_IMAGE_THRESHOLD:
                print(f"Warning: very large image ({width}x{height}, {pixels:,} pixels) — processing may be slow: {file_path}")
            return MediaMetadata(width=width, height=height)
    except Exception as e:
        print(f"Error reading media metadata: {e}")
        return MediaMetadata()


def create_thumbnail(file_path, size=(800, 800)):
    img = None
    try:
        if file_path.lower().endswith((".mp4", ".avi", ".mov", ".mkv", ".webm")):
            cap = cv2.VideoCapture(file_path)
            try:
                ret, frame = cap.read()
            finally:
                cap.release()
            if ret:
                img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                img.thumbnail(size, Image.Resampling.LANCZOS)
            else:
                return None
        else:
            with Image.open(file_path) as source:
                pixels = source.width * source.height
                if pixels > _LARGE_IMAGE_THRESHOLD:
                    print(
                        f"Warning: very large image ({source.width}x{source.height}, "
                        f"{pixels:,} pixels) — thumbnail creation may be slow"
                    )
                # JPEG decoders can reduce during load. thumbnail(reducing_gap)
                # then downsizes before EXIF rotation and colour conversion.
                try:
                    source.draft("RGB", size)
                except (AttributeError, ValueError):
                    pass
                source.thumbnail(
                    size,
                    Image.Resampling.BICUBIC,
                    reducing_gap=3.0,
                )
                img = ImageOps.exif_transpose(source).copy()

        if img.mode in ("RGBA", "LA"):
            background = Image.new("RGB", img.size, (45, 45, 45))
            background.paste(img, mask=img.split()[-1])
            img.close()
            img = background

        elif img.mode != "RGB":
            converted = img.convert("RGB")
            img.close()
            img = converted

        byte_arr = io.BytesIO()
        img.save(byte_arr, format="JPEG", quality=80, optimize=True)
        return byte_arr.getvalue()
    except Exception as e:
        print(f"Error creating thumbnail: {e}")
        return None
    finally:
        if img is not None:
            img.close()
