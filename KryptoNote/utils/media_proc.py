import io
import math
import struct
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from mutagen import File as MutagenFile
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
    # Normalized textual tags and technical fields extracted from the source.
    # Binary payloads (for example cover art) are represented by a descriptor;
    # the original bytes remain preserved in the encrypted media file itself.
    embedded_metadata: tuple[dict, ...] = ()


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


_AUDIO_TAG_LABELS = {
    "title": "Title",
    "tit2": "Title",
    "\xa9nam": "Title",
    "artist": "Artist",
    "tpe1": "Artist",
    "\xa9art": "Artist",
    "album": "Album",
    "talb": "Album",
    "\xa9alb": "Album",
    "albumartist": "Album artist",
    "album artist": "Album artist",
    "tpe2": "Album artist",
    "aart": "Album artist",
    "composer": "Composer",
    "tcom": "Composer",
    "\xa9wrt": "Composer",
    "genre": "Genre",
    "tcon": "Genre",
    "\xa9gen": "Genre",
    "gnre": "Genre",
    "date": "Date",
    "year": "Date",
    "tdrc": "Date",
    "tyer": "Date",
    "\xa9day": "Date",
    "tracknumber": "Track",
    "track": "Track",
    "trck": "Track",
    "trkn": "Track",
    "discnumber": "Disc",
    "disc": "Disc",
    "tpos": "Disc",
    "disk": "Disc",
    "bpm": "BPM",
    "tbpm": "BPM",
    "tmpo": "BPM",
    "isrc": "ISRC",
    "tsrc": "ISRC",
    "language": "Language",
    "tlan": "Language",
    "copyright": "Copyright",
    "tcop": "Copyright",
    "cprt": "Copyright",
    "publisher": "Publisher",
    "tpub": "Publisher",
    "organization": "Publisher",
    "encodedby": "Encoded by",
    "encoder": "Encoder",
    "tenc": "Encoded by",
    "\xa9too": "Encoder",
    "comment": "Comment",
    "comments": "Comment",
    "comm": "Comment",
    "\xa9cmt": "Comment",
    "lyrics": "Lyrics",
    "unsyncedlyrics": "Lyrics",
    "unsynced lyrics": "Lyrics",
    "uslt": "Lyrics",
    "\xa9lyr": "Lyrics",
    "sylt": "Synchronized lyrics",
    "apic": "Cover art",
    "covr": "Cover art",
    "picture": "Cover art",
    "compilation": "Compilation",
    "cpil": "Compilation",
}

_AUDIO_INFO_LABELS = {
    "bitrate": "Bitrate",
    "sample_rate": "Sample rate",
    "channels": "Channels",
    "bits_per_sample": "Bits per sample",
    "bitrate_mode": "Bitrate mode",
    "codec": "Codec",
    "codec_description": "Codec",
    "encoder_info": "Encoder",
    "encoder_settings": "Encoder settings",
    "track_gain": "Track gain",
    "track_peak": "Track peak",
    "album_gain": "Album gain",
    "album_peak": "Album peak",
}


def _metadata_label(raw_key, value=None):
    raw = str(raw_key or "Metadata").replace("\x00", "").strip()
    base = raw.split(":", 1)[0]
    label = _AUDIO_TAG_LABELS.get(raw.casefold())
    if label is None:
        label = _AUDIO_TAG_LABELS.get(base.casefold())
    if label is None:
        label = raw.replace(":", " · ").replace("_", " ").strip()
        label = label[:1].upper() + label[1:] if label else "Metadata"

    qualifiers = []
    for attribute in ("desc", "lang"):
        detail = getattr(value, attribute, "")
        detail = str(detail or "").strip()
        if detail and detail.lower() not in {"xxx", "und"}:
            qualifiers.append(detail)
    if qualifiers:
        label += " (" + " · ".join(dict.fromkeys(qualifiers)) + ")"
    return label.replace(":", " · ")


def _binary_metadata_descriptor(value):
    raw = bytes(value)
    format_name = getattr(value, "imageformat", None)
    formats = {13: "JPEG", 14: "PNG"}
    try:
        kind = formats.get(int(format_name), "Binary data")
    except (TypeError, ValueError):
        kind = "Binary data"
    return f"{kind} · {len(raw):,} bytes"


def _metadata_text_values(value, *, depth=0):
    if value is None or depth > 5:
        return []
    if isinstance(value, str):
        text = value.replace("\x00", "").strip()
        return [text] if text else []
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value)
        try:
            decoded = raw.decode("utf-8").replace("\x00", "").strip()
        except UnicodeDecodeError:
            decoded = ""
        if decoded and sum(character.isprintable() or character in "\r\n\t" for character in decoded) / len(decoded) > 0.9:
            return [decoded]
        return [_binary_metadata_descriptor(value)]
    if isinstance(value, bool):
        return ["Yes" if value else "No"]
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            return []
        return [str(value)]
    if isinstance(value, dict):
        result = []
        for key in sorted(value, key=lambda item: str(item).casefold()):
            for item in _metadata_text_values(value[key], depth=depth + 1):
                result.append(f"{key}={item}")
        return result
    if isinstance(value, (list, tuple, set, frozenset)):
        if (
            isinstance(value, tuple)
            and len(value) == 2
            and isinstance(value[0], str)
            and isinstance(value[1], (int, float))
        ):
            return [f"{value[0]} @ {value[1]} ms"]
        result = []
        for item in value:
            result.extend(_metadata_text_values(item, depth=depth + 1))
        return result

    text_payload = getattr(value, "text", None)
    if text_payload is not None:
        return _metadata_text_values(text_payload, depth=depth + 1)
    url = getattr(value, "url", None)
    if url:
        return _metadata_text_values(url, depth=depth + 1)
    scalar = getattr(value, "value", None)
    if scalar is not None and scalar is not value:
        return _metadata_text_values(scalar, depth=depth + 1)

    descriptor = []
    for attribute, label in (
        ("mime", "MIME"),
        ("type", "Type"),
        ("desc", "Description"),
        ("filename", "Filename"),
        ("owner", "Owner"),
        ("email", "Email"),
        ("rating", "Rating"),
        ("count", "Count"),
    ):
        detail = getattr(value, attribute, None)
        if detail not in (None, "", b""):
            descriptor.append(f"{label}: {detail}")
    data = getattr(value, "data", None)
    if isinstance(data, (bytes, bytearray, memoryview)):
        descriptor.append(f"Data: {len(data):,} bytes")
    if descriptor:
        return [" · ".join(descriptor)]

    pretty = getattr(value, "pprint", None)
    if callable(pretty):
        try:
            return _metadata_text_values(pretty(), depth=depth + 1)
        except Exception:
            pass
    text = str(value).replace("\x00", "").strip()
    if not text or (text.startswith("<") and text.endswith(">") and " object at " in text):
        return []
    return [text]


def _technical_metadata_values(name, value):
    try:
        if name == "bitrate" and float(value) > 0:
            return [f"{float(value) / 1000:.0f} kbps"]
        if name == "sample_rate" and float(value) > 0:
            rate = float(value) / 1000
            return [f"{rate:g} kHz"]
    except (TypeError, ValueError, OverflowError):
        pass
    return _metadata_text_values(value)


def read_audio_embedded_metadata(file_path):
    """Return every displayable audio tag and technical field Mutagen exposes.

    Text is retained verbatim. Binary fields are represented by size/type
    descriptors because the complete original file is already stored encrypted.
    Metadata errors never make an otherwise decodable audio import fail.
    """

    try:
        audio = MutagenFile(file_path, easy=False)
    except Exception:
        return ()
    if audio is None:
        return ()

    entries = []
    tags = getattr(audio, "tags", None)
    if tags is not None and hasattr(tags, "items"):
        try:
            tag_items = sorted(tags.items(), key=lambda item: str(item[0]).casefold())
        except Exception:
            tag_items = []
        for raw_key, raw_value in tag_items:
            values = _metadata_text_values(raw_value)
            if values:
                entries.append(
                    {
                        "key": str(raw_key),
                        "label": _metadata_label(raw_key, raw_value),
                        "values": values,
                        "source": "tag",
                    }
                )
        for attribute, label in (("version", "Tag version"), ("size", "Tag size")):
            detail = getattr(tags, attribute, None)
            values = _metadata_text_values(detail)
            if values:
                entries.append(
                    {
                        "key": f"tag.{attribute}",
                        "label": label,
                        "values": values,
                        "source": "technical",
                    }
                )
        for index, unknown in enumerate(
            getattr(tags, "unknown_frames", ()) or (), start=1
        ):
            entries.append(
                {
                    "key": f"UNKNOWN:{index}",
                    "label": f"Unknown tag frame {index}",
                    "values": [_binary_metadata_descriptor(unknown)],
                    "source": "tag",
                }
            )

    info = getattr(audio, "info", None)
    if info is not None:
        for name in sorted(item for item in dir(info) if not item.startswith("_")):
            if name in {"length", "pprint"}:
                continue
            try:
                raw_value = getattr(info, name)
            except Exception:
                continue
            if callable(raw_value):
                continue
            values = _technical_metadata_values(name, raw_value)
            if not values:
                continue
            label = _AUDIO_INFO_LABELS.get(
                name, name.replace("_", " ").capitalize()
            )
            entries.append(
                {
                    "key": f"info.{name}",
                    "label": label,
                    "values": values,
                    "source": "technical",
                }
            )

    for index, picture in enumerate(getattr(audio, "pictures", ()) or (), start=1):
        parts = []
        for attribute, label in (
            ("mime", "MIME"),
            ("type", "Type"),
            ("desc", "Description"),
            ("width", "Width"),
            ("height", "Height"),
            ("depth", "Depth"),
        ):
            detail = getattr(picture, attribute, None)
            if detail not in (None, ""):
                parts.append(f"{label}: {detail}")
        picture_data = getattr(picture, "data", b"") or b""
        parts.append(f"Data: {len(picture_data):,} bytes")
        entries.append(
            {
                "key": f"PICTURE:{index}",
                "label": "Cover art" if index == 1 else f"Cover art {index}",
                "values": [" · ".join(parts)],
                "source": "tag",
            }
        )
    return tuple(entries)


def _audio_buffer_frame_energy(buffer):
    """Return per-frame mean-square energy without retaining decoded PCM."""

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
        return 0, np.empty(0, dtype=np.float32), 0
    try:
        samples = np.frombuffer(buffer.constData(), dtype=dtype, count=byte_count // item_size)
    except (TypeError, ValueError, BufferError) as exc:
        raise AudioAnalysisError("Unable to read decoded audio samples") from exc
    frame_count = min(int(buffer.frameCount() or 0), samples.size // channel_count)
    if frame_count <= 0:
        return 0, np.empty(0, dtype=np.float32), 0
    samples = samples[: frame_count * channel_count].reshape(frame_count, channel_count)
    if sample_format_name == "UInt8":
        values = (samples.astype(np.float32) - 128.0) / 128.0
    elif sample_format_name == "Int16":
        values = samples.astype(np.float32) / 32768.0
    elif sample_format_name == "Int32":
        values = samples.astype(np.float32) / 2147483648.0
    else:
        values = samples.astype(np.float32)
    frame_energy = np.mean(np.square(values, dtype=np.float32), axis=1)
    return frame_count, frame_energy, int(audio_format.sampleRate() or 0)


def _audio_buffer_peaks(buffer):
    """Compatibility helper returning one RMS value for a QAudioBuffer."""

    frame_count, frame_energy, _sample_rate = _audio_buffer_frame_energy(buffer)
    if frame_count <= 0:
        return 0, 0.0
    return frame_count, float(np.sqrt(np.mean(frame_energy)))


def _audio_buffer_envelope(buffer):
    """Return short RMS windows so transients do not flatten a whole buffer."""

    frame_count, frame_energy, sample_rate = _audio_buffer_frame_energy(buffer)
    if frame_count <= 0:
        return 0, ()
    # About 12 ms retains useful rhythmic variation while the streaming
    # accumulator below keeps memory bounded for arbitrarily long tracks.
    window_frames = max(128, int(round((sample_rate or 44_100) * 0.012)))
    summaries = []
    for start in range(0, frame_count, window_frames):
        end = min(frame_count, start + window_frames)
        rms = float(np.sqrt(np.mean(frame_energy[start:end])))
        summaries.append((start, end - start, rms))
    return frame_count, tuple(summaries)


_AUDIO_ANALYSIS_MAX_BINS = AUDIO_WAVEFORM_PEAK_COUNT * 2


class _StreamingAudioPeakAggregator:
    """Bounded RMS envelope for short decoded-audio summaries.

    The final 96-bin mapping depends on the total frame count, which is not
    guaranteed to be known while ``QAudioDecoder`` is emitting buffers.  A
    list of all ``(start, length, peak)`` tuples therefore grows linearly with
    the input duration.  This accumulator keeps a contiguous, frame-aligned
    hierarchy of at most 192 bins.  When the next summary would exceed that
    bound, adjacent energy/count pairs are merged and their width is doubled.

    Energy averaging prevents one transient from forcing an entire visual bin
    to full height. PCM and per-buffer state are released immediately, and the
    retained intervals are projected onto the final 96 bins at the end.
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
            pooled = []
            for index in range(0, len(self._bins), 2):
                pair = self._bins[index : index + 2]
                pooled.append(
                    (
                        sum(bin_energy for bin_energy, _count in pair),
                        sum(count for _bin_energy, count in pair),
                    )
                )
            self._bins = pooled
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
            self._bins.extend([(0.0, 0)] * (required_count - len(self._bins)))
        for index in range(first_bin, last_bin + 1):
            bin_start = index * self._bin_width
            bin_end = bin_start + self._bin_width
            overlap = max(0, min(end, bin_end) - max(start, bin_start))
            if overlap <= 0:
                continue
            energy, covered_frames = self._bins[index]
            self._bins[index] = (
                energy + value * value * overlap,
                covered_frames + overlap,
            )
        self._end_frame = max(self._end_frame, end)

    def finalize(self, total_frames=None):
        """Project retained energy into 96 RMS amplitude bins."""

        try:
            total = int(self._end_frame if total_frames is None else total_frames)
        except (TypeError, ValueError, OverflowError):
            total = self._end_frame
        target_energy = [0.0] * AUDIO_WAVEFORM_PEAK_COUNT
        target_frames = [0.0] * AUDIO_WAVEFORM_PEAK_COUNT
        if total <= 0:
            return target_energy
        for index, (energy, covered_frames) in enumerate(self._bins):
            if energy <= 0.0 or covered_frames <= 0:
                continue
            start_frame = index * self._bin_width
            if start_frame >= total:
                break
            end_frame = min(total, self._end_frame, start_frame + self._bin_width)
            if end_frame <= start_frame:
                continue
            energy_per_frame = energy / covered_frames
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
                target_start = target * total / AUDIO_WAVEFORM_PEAK_COUNT
                target_end = (target + 1) * total / AUDIO_WAVEFORM_PEAK_COUNT
                overlap = max(
                    0.0,
                    min(float(end_frame), target_end)
                    - max(float(start_frame), target_start),
                )
                if overlap <= 0:
                    continue
                target_energy[target] += energy_per_frame * overlap
                target_frames[target] += overlap
        return [
            min(1.0, math.sqrt(energy / frames)) if frames > 0 else 0.0
            for energy, frames in zip(target_energy, target_frames)
        ]


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
                frame_count, summaries = _audio_buffer_envelope(buffer)
                if frame_count <= 0:
                    continue
                for offset, summary_frames, rms in summaries:
                    peak_aggregator.add(
                        total_frames + offset,
                        summary_frames,
                        rms,
                    )
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
        embedded_metadata=read_audio_embedded_metadata(path),
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
