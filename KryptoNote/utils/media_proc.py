import io
import math
import struct
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from ..core.constants import (
    AUDIO_EXTENSIONS,
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
)

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
    # Audio imports use this field as their thumbnail payload.  Keeping the
    # waveform in the existing encrypted thumbnail column avoids a schema
    # migration while allowing the model/export layers to decode it later.
    waveform: bytes | None = None


@dataclass(frozen=True)
class AudioWaveform:
    """Validated waveform data stored in an audio node thumbnail.

    ``peaks`` always contains 96 values in the inclusive range 0..1.  The
    duration is expressed in seconds, matching ``MediaMetadata.duration``.
    """

    peaks: tuple[float, ...]
    duration: float = 0.0
    version: int = 1


class AudioAnalysisError(ValueError):
    """Raised when Qt cannot decode an audio source."""


class AudioAnalysisCancelled(Exception):
    """Raised when a cooperative audio analysis cancellation is requested."""


AUDIO_WAVEFORM_MAGIC = b"ZRXW"
AUDIO_WAVEFORM_VERSION = 1
AUDIO_WAVEFORM_PEAK_COUNT = 96
_AUDIO_WAVEFORM_HEADER = struct.Struct(">4sBBHIQ")
_AUDIO_WAVEFORM_MAX_BYTES = (
    _AUDIO_WAVEFORM_HEADER.size + AUDIO_WAVEFORM_PEAK_COUNT * 4
)
_AUDIO_ANALYSIS_POLL_MS = 100
_AUDIO_ANALYSIS_WATCHDOG_SECONDS = 30.0


def _normalise_peaks(peaks):
    values = []
    for value in peaks:
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = 0.0
        if not math.isfinite(number):
            number = 0.0
        values.append(max(0.0, min(1.0, number)))
    if not values:
        raise ValueError("Audio waveform must contain at least one peak")
    if len(values) == AUDIO_WAVEFORM_PEAK_COUNT:
        return tuple(values)

    # Keep the payload contract fixed at 96 points while allowing callers to
    # provide a different resolution.  Max-pooling is stable for transients.
    pooled = []
    for index in range(AUDIO_WAVEFORM_PEAK_COUNT):
        start = (index * len(values)) // AUDIO_WAVEFORM_PEAK_COUNT
        end = max(start + 1, ((index + 1) * len(values)) // AUDIO_WAVEFORM_PEAK_COUNT)
        pooled.append(max(values[start:end]))
    return tuple(pooled)


def encode_audio_waveform(peaks, duration=0.0, *, version=AUDIO_WAVEFORM_VERSION):
    """Encode 96 normalised peaks into a bounded, versioned binary payload."""

    if int(version) != AUDIO_WAVEFORM_VERSION:
        raise ValueError(f"Unsupported audio waveform version: {version}")
    normalised = _normalise_peaks(peaks)
    try:
        duration_seconds = float(duration)
    except (TypeError, ValueError):
        duration_seconds = 0.0
    if not math.isfinite(duration_seconds) or duration_seconds < 0:
        duration_seconds = 0.0
    duration_us = min(int(round(duration_seconds * 1_000_000)), (1 << 64) - 1)
    body = struct.pack(f">{AUDIO_WAVEFORM_PEAK_COUNT}f", *normalised)
    header = _AUDIO_WAVEFORM_HEADER.pack(
        AUDIO_WAVEFORM_MAGIC,
        AUDIO_WAVEFORM_VERSION,
        0,
        AUDIO_WAVEFORM_PEAK_COUNT,
        len(body),
        duration_us,
    )
    payload = header + body
    if len(payload) > _AUDIO_WAVEFORM_MAX_BYTES:
        raise ValueError("Audio waveform payload is too large")
    return payload


def decode_audio_waveform(payload):
    """Decode a waveform payload, returning ``None`` for malformed data.

    Thumbnail bytes are user-controlled encrypted data after decryption, so
    callers must be able to treat a legacy image thumbnail or a truncated
    payload as an ordinary "no waveform" case.
    """

    if not isinstance(payload, (bytes, bytearray, memoryview)):
        return None
    raw = bytes(payload)
    if len(raw) < _AUDIO_WAVEFORM_HEADER.size or len(raw) > _AUDIO_WAVEFORM_MAX_BYTES:
        return None
    try:
        magic, version, reserved, count, body_len, duration_us = (
            _AUDIO_WAVEFORM_HEADER.unpack_from(raw)
        )
    except struct.error:
        return None
    if (
        magic != AUDIO_WAVEFORM_MAGIC
        or version != AUDIO_WAVEFORM_VERSION
        or reserved != 0
        or count != AUDIO_WAVEFORM_PEAK_COUNT
        or body_len != count * 4
        or len(raw) != _AUDIO_WAVEFORM_HEADER.size + body_len
    ):
        return None
    try:
        peaks = struct.unpack(
            f">{AUDIO_WAVEFORM_PEAK_COUNT}f",
            raw[_AUDIO_WAVEFORM_HEADER.size :],
        )
    except struct.error:
        return None
    if any(not math.isfinite(value) or value < 0.0 or value > 1.0 for value in peaks):
        return None
    duration = float(duration_us) / 1_000_000.0
    if not math.isfinite(duration) or duration < 0:
        return None
    return AudioWaveform(tuple(float(value) for value in peaks), duration, version)


def is_audio_waveform_payload(payload):
    """Return ``True`` only for a fully validated waveform payload."""

    return decode_audio_waveform(payload) is not None


_RUNTIME_AUDIO_SUFFIXES = {
    "Matroska": {".mka", ".mkv"},
    "Ogg": {".ogg", ".oga", ".opus"},
    "QuickTime": {".mov"},
    "Mpeg4Audio": {".m4a"},
    "AAC": {".aac"},
    "WMA": {".wma"},
    "MP3": {".mp3"},
    "FLAC": {".flac"},
    "Wave": {".wav"},
    # Qt reports MPEG-4 as a container format.  It can carry audio-only
    # tracks on platforms whose backend advertises it, so include .mp4 only
    # when that backend reports MPEG4 decoding support.
    "MPEG4": {".mp4"},
}


def supported_audio_extensions():
    """Return guaranteed audio suffixes plus formats advertised by Qt.

    Importing Qt Multimedia is intentionally lazy: command-line maintenance
    and image-only operations should still work when the multimedia plugin is
    unavailable on a headless system.
    """

    extensions = set(AUDIO_EXTENSIONS)
    try:
        from PySide6.QtMultimedia import QMediaFormat

        media_format = QMediaFormat()
        mode = QMediaFormat.ConversionMode.Decode
        for file_format in media_format.supportedFileFormats(mode):
            format_name = getattr(file_format, "name", str(file_format))
            extensions.update(_RUNTIME_AUDIO_SUFFIXES.get(format_name, ()))
    except Exception:
        # The guaranteed list remains usable if Qt is not installed or the
        # platform multimedia backend cannot enumerate codecs.
        pass
    return frozenset(extensions)


def _audio_buffer_peaks(buffer):
    """Reduce one QAudioBuffer to its frame count and maximum peak."""

    audio_format = buffer.format()
    channel_count = int(audio_format.channelCount() or 0)
    sample_format = audio_format.sampleFormat()
    sample_format_name = getattr(sample_format, "name", str(sample_format))
    dtype_by_format = {
        "UInt8": np.uint8,
        "Int16": np.int16,
        "Int32": np.int32,
        "Float": np.float32,
    }
    dtype = dtype_by_format.get(sample_format_name)
    if channel_count <= 0 or dtype is None:
        raise AudioAnalysisError("Unsupported decoded audio sample format")
    item_size = np.dtype(dtype).itemsize
    byte_count = int(buffer.byteCount() or 0)
    if byte_count <= 0:
        return 0, []
    try:
        samples = np.frombuffer(buffer.constData(), dtype=dtype, count=byte_count // item_size)
    except (TypeError, ValueError, BufferError) as exc:
        raise AudioAnalysisError("Unable to read decoded audio samples") from exc
    frame_count = min(int(buffer.frameCount() or 0), samples.size // channel_count)
    if frame_count <= 0:
        return 0, []
    samples = samples[: frame_count * channel_count].reshape(frame_count, channel_count)
    if sample_format_name == "UInt8":
        values = (samples.astype(np.float32) - 128.0) / 128.0
    elif sample_format_name == "Int16":
        values = samples.astype(np.float32) / 32768.0
    elif sample_format_name == "Int32":
        values = samples.astype(np.float32) / 2147483648.0
    else:
        values = samples.astype(np.float32)
    frame_peaks = np.max(np.abs(values), axis=1)
    # Retain one scalar per decoder buffer.  This discards PCM immediately;
    # ``_StreamingAudioPeakAggregator`` below folds those scalars into a
    # bounded hierarchy instead of retaining one tuple per decoder buffer.
    return frame_count, float(np.max(frame_peaks))


_AUDIO_ANALYSIS_MAX_BINS = AUDIO_WAVEFORM_PEAK_COUNT * 2


class _StreamingAudioPeakAggregator:
    """Bounded max-pool for decoder-buffer peak summaries.

    The final 96-bin mapping depends on the total frame count, which is not
    guaranteed to be known while ``QAudioDecoder`` is emitting buffers.  A
    list of all ``(start, length, peak)`` tuples therefore grows linearly with
    the input duration.  This accumulator keeps a contiguous, frame-aligned
    hierarchy of at most 192 bins.  When the next summary would exceed that
    bound, adjacent bins are max-pooled and their frame width is doubled.

    Max-pooling is monotonic: every input peak remains represented in the
    covered interval, while PCM and per-buffer state are released immediately.
    At the end, the retained intervals are projected onto the 96 output bins.
    The extra level halves the amount of temporal smearing compared with
    pooling directly into the final 96 bins.
    """

    __slots__ = ("_bins", "_bin_width", "_max_bins", "_end_frame")

    def __init__(self, *, max_bins=_AUDIO_ANALYSIS_MAX_BINS):
        max_bins = int(max_bins)
        if max_bins < AUDIO_WAVEFORM_PEAK_COUNT:
            raise ValueError("Audio peak aggregator requires at least 96 bins")
        self._bins = []
        self._bin_width = 1
        self._max_bins = max_bins
        self._end_frame = 0

    @property
    def retained_bin_count(self):
        """Number of retained bins, exposed for bounded-state tests."""

        return len(self._bins)

    @property
    def retained_bin_width(self):
        """Frame width represented by one retained bin."""

        return self._bin_width

    def _pool_once(self):
        if len(self._bins) <= 1:
            self._bins = list(self._bins)
        else:
            self._bins = [
                max(self._bins[index : index + 2])
                for index in range(0, len(self._bins), 2)
            ]
        self._bin_width *= 2

    def _ensure_capacity(self, end_frame):
        # A single decoder buffer can cover more than the current hierarchy;
        # increase the frame width before materialising any bins so memory is
        # bounded even for unusually large backend buffers.
        while (max(0, int(end_frame) - 1) // self._bin_width) + 1 > self._max_bins:
            self._pool_once()

    def add(self, start_frame, frame_count, peak):
        """Merge one decoded-buffer summary into the bounded hierarchy."""

        try:
            start = max(0, int(start_frame))
            count = int(frame_count)
            value = float(peak)
        except (TypeError, ValueError, OverflowError):
            return
        if count <= 0:
            return
        if not math.isfinite(value):
            value = 0.0
        value = max(0.0, min(1.0, value))
        end = start + count
        if end <= start:
            return

        self._ensure_capacity(end)
        first_bin = start // self._bin_width
        last_bin = (end - 1) // self._bin_width
        required_count = last_bin + 1
        if required_count > len(self._bins):
            self._bins.extend([0.0] * (required_count - len(self._bins)))
        for index in range(first_bin, last_bin + 1):
            self._bins[index] = max(self._bins[index], value)
        self._end_frame = max(self._end_frame, end)

    def finalize(self, total_frames=None):
        """Project the retained intervals into 96 normalized max-pool bins."""

        try:
            total = int(self._end_frame if total_frames is None else total_frames)
        except (TypeError, ValueError, OverflowError):
            total = self._end_frame
        peaks = [0.0] * AUDIO_WAVEFORM_PEAK_COUNT
        if total <= 0:
            return peaks
        for index, peak in enumerate(self._bins):
            if peak <= 0.0:
                continue
            start_frame = index * self._bin_width
            if start_frame >= total:
                break
            end_frame = min(total, start_frame + self._bin_width)
            first_bin = min(
                AUDIO_WAVEFORM_PEAK_COUNT - 1,
                int(start_frame * AUDIO_WAVEFORM_PEAK_COUNT / total),
            )
            last_bin = min(
                AUDIO_WAVEFORM_PEAK_COUNT - 1,
                max(
                    first_bin,
                    int(max(0, end_frame - 1) * AUDIO_WAVEFORM_PEAK_COUNT / total),
                ),
            )
            for target in range(first_bin, last_bin + 1):
                peaks[target] = max(peaks[target], float(peak))
        return peaks


def _combine_audio_peak_summaries(summaries, total_frames):
    """Compatibility helper that combines an iterable without extra storage."""

    accumulator = _StreamingAudioPeakAggregator()
    for start_frame, frame_count, peak in summaries:
        accumulator.add(start_frame, frame_count, peak)
    return accumulator.finalize(total_frames)


def analyze_audio_file(
    file_path,
    *,
    cancel_check=None,
    progress_callback=None,
):
    """Decode *file_path* with QAudioDecoder and return ``MediaMetadata``.

    The decoder is driven by a local ``QEventLoop`` so this function works in
    both the synchronous importer and a ``QThread`` worker.  Only bounded peak
    summaries are retained; decoded PCM is never written to a temporary file
    or accumulated in memory.
    """

    path = Path(file_path)
    if not path.is_file():
        raise AudioAnalysisError(f"Audio file does not exist: {path.name}")
    if cancel_check and cancel_check():
        raise AudioAnalysisCancelled("Audio analysis cancelled")
    try:
        from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer, QUrl
        from PySide6.QtMultimedia import QAudioDecoder
    except Exception as exc:
        raise AudioAnalysisError("Qt Multimedia audio decoder is unavailable") from exc
    if QCoreApplication.instance() is None:
        raise AudioAnalysisError("Qt event loop is required to analyze audio")

    decoder = QAudioDecoder()
    loop = QEventLoop()
    peak_aggregator = _StreamingAudioPeakAggregator()
    total_frames = 0
    sample_rate = 0
    decoder_duration = 0
    error_text = []
    finished = False
    cancelled = False
    last_activity = time.monotonic()
    watchdog = QTimer()
    watchdog.setInterval(_AUDIO_ANALYSIS_POLL_MS)

    def _quit():
        if loop.isRunning():
            loop.quit()

    def _on_error(error_code=None, *args):
        nonlocal last_activity
        last_activity = time.monotonic()
        message = decoder.errorString() or "Unable to decode audio"
        if error_code is not None and getattr(error_code, "name", "") not in ("NoError", ""):
            message = f"{message} ({getattr(error_code, 'name', error_code)})"
        error_text.append(message)
        _quit()

    def _on_finished(*args):
        nonlocal finished, last_activity
        finished = True
        last_activity = time.monotonic()
        _quit()

    def _on_buffer_ready(*args):
        nonlocal total_frames, sample_rate, cancelled, last_activity
        try:
            while decoder.bufferAvailable():
                if cancel_check and cancel_check():
                    cancelled = True
                    decoder.stop()
                    _quit()
                    return
                buffer = decoder.read()
                if not buffer or not buffer.isValid():
                    continue
                last_activity = time.monotonic()
                audio_format = buffer.format()
                sample_rate = sample_rate or int(audio_format.sampleRate() or 0)
                frame_count, peak = _audio_buffer_peaks(buffer)
                if frame_count <= 0:
                    continue
                peak_aggregator.add(total_frames, frame_count, peak)
                total_frames += frame_count
                if progress_callback:
                    duration_value = int(decoder.duration() or 0)
                    position_value = int(decoder.position() or 0)
                    progress_callback(position_value, duration_value)
        except AudioAnalysisCancelled:
            cancelled = True
            decoder.stop()
            _quit()
        except Exception as exc:
            error_text.append(str(exc))
            decoder.stop()
            _quit()

    def _poll_decoder():
        nonlocal cancelled, last_activity
        if cancel_check and cancel_check():
            cancelled = True
            decoder.stop()
            _quit()
            return
        if time.monotonic() - last_activity > _AUDIO_ANALYSIS_WATCHDOG_SECONDS:
            error_text.append("Audio decoder timed out")
            decoder.stop()
            _quit()

    decoder.bufferReady.connect(_on_buffer_ready)
    decoder.error.connect(_on_error)
    decoder.finished.connect(_on_finished)
    watchdog.timeout.connect(_poll_decoder)
    try:
        decoder.setSource(QUrl.fromLocalFile(str(path.resolve())))
        if not decoder.isSupported():
            raise AudioAnalysisError(
                f"Unsupported audio format: {path.suffix.lower() or path.name}"
            )
        decoder.start()
        # A backend may report a format error synchronously from ``start``.
        # Do not enter an event loop that has already been asked to quit.
        if not error_text and not finished:
            watchdog.start()
            loop.exec()
        decoder_duration = int(decoder.duration() or 0)
    finally:
        watchdog.stop()
        watchdog.deleteLater()
        try:
            decoder.stop()
        except Exception:
            pass
        decoder.deleteLater()

    if cancel_check and cancel_check():
        cancelled = True
    if cancelled:
        raise AudioAnalysisCancelled("Audio analysis cancelled")
    if error_text:
        raise AudioAnalysisError(f"Unable to decode '{path.name}': {error_text[-1]}")
    if not finished:
        raise AudioAnalysisError(f"Unable to decode '{path.name}'")
    if total_frames <= 0:
        raise AudioAnalysisError(f"Audio file contains no decodable samples: {path.name}")
    duration = (
        total_frames / sample_rate
        if sample_rate > 0
        else max(0.0, float(decoder_duration) / 1000.0)
    )
    peaks = peak_aggregator.finalize(total_frames)
    return MediaMetadata(
        duration=duration,
        waveform=encode_audio_waveform(peaks, duration),
    )


def read_media_metadata(
    file_path,
    *,
    media_type=None,
    cancel_check=None,
    progress_callback=None,
):
    suffix = Path(file_path).suffix.lower()
    # Keep suffix-only auto-detection conservative so a legacy caller that
    # asks about ``.mkv`` or ``.mp4`` still gets video metadata.  The importer
    # passes ``media_type='audio'`` explicitly for runtime-advertised
    # containers such as .mka/.m4a.
    if media_type == "audio" or (
        media_type is None and suffix in AUDIO_EXTENSIONS
    ):
        return analyze_audio_file(
            file_path,
            cancel_check=cancel_check,
            progress_callback=progress_callback,
        )
    try:
        if media_type == "video" or suffix in VIDEO_EXTENSIONS:
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
        if Path(file_path).suffix.lower() in VIDEO_EXTENSIONS:
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
