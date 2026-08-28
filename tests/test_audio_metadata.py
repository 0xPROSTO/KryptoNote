import os
import subprocess
import sys
import time
import zlib
from pathlib import Path
from types import SimpleNamespace

import cv2
from mutagen.id3 import TPE1, USLT
from PIL import Image, PngImagePlugin

import KryptoNote.utils.media_proc as media_proc
import KryptoNote.utils.secure_temp as secure_temp
from KryptoNote.core.crypto import CryptoManager
from KryptoNote.core.database.connection import DatabaseConnection
from KryptoNote.core.database.repository import NodeRepository
from KryptoNote.gui.services.media_metadata_backfill import (
    MediaMetadataBackfillWorker,
)
from KryptoNote.utils.media_proc import (
    AUDIO_WAVEFORM_PEAK_COUNT,
    _StreamingAudioPeakAggregator,
    _metadata_label,
    _metadata_text_values,
    read_media_metadata,
    read_mutagen_metadata,
    read_video_embedded_metadata,
)
from KryptoNote.utils.secure_temp import cleanup_stale_metadata_temp_dirs


def test_artist_and_lyrics_metadata_remain_lossless_in_encrypted_payload():
    artist = TPE1(encoding=3, text=["Massive Attack"])
    lyrics = USLT(
        encoding=3,
        lang="eng",
        desc="Album booklet",
        text="First line\nSecond line",
    )
    entries = [
        {
            "key": "TPE1",
            "label": _metadata_label("TPE1", artist),
            "values": _metadata_text_values(artist),
            "source": "tag",
        },
        {
            "key": "USLT:Album booklet:eng",
            "label": _metadata_label("USLT:Album booklet:eng", lyrics),
            "values": _metadata_text_values(lyrics),
            "source": "tag",
        },
    ]

    database = DatabaseConnection(":memory:")
    crypto = CryptoManager()
    crypto.load_data_key(b"audio-metadata-test-key-32-bytes")
    repository = NodeRepository(database, crypto)
    try:
        item_id = repository.add_item(
            "audio",
            0,
            0,
            360,
            108,
            title="Teardrop.mp3",
            original_filename="Teardrop.mp3",
            media_metadata=entries,
        )
        restored = repository.get_items_by_ids([item_id])[0].media_metadata
    finally:
        repository.close()
        database.close()

    assert restored[0]["label"] == "Artist"
    assert restored[0]["values"] == ["Massive Attack"]
    assert restored[1]["label"] == "Lyrics (Album booklet · eng)"
    assert restored[1]["values"] == ["First line\nSecond line"]


def test_rms_waveform_does_not_spread_one_transient_over_the_track():
    aggregator = _StreamingAudioPeakAggregator()
    frames_per_bin = 100
    for index in range(AUDIO_WAVEFORM_PEAK_COUNT):
        amplitude = 1.0 if index == AUDIO_WAVEFORM_PEAK_COUNT // 2 else 0.1
        aggregator.add(index * frames_per_bin, frames_per_bin, amplitude)

    waveform = aggregator.finalize(
        AUDIO_WAVEFORM_PEAK_COUNT * frames_per_bin
    )

    assert sum(value > 0.9 for value in waveform) <= 2
    assert sum(value < 0.2 for value in waveform) >= 90


def test_image_text_metadata_is_extracted_for_properties(tmp_path):
    path = tmp_path / "evidence.png"
    png_info = PngImagePlugin.PngInfo()
    png_info.add_text("Artist", "ZeroXX")
    png_info.add_text("Description", "One\nTwo\nThree\nFour")
    Image.new("RGB", (8, 6), "black").save(path, pnginfo=png_info)

    metadata = read_media_metadata(path, media_type="image")
    values_by_label = {
        entry["label"]: entry["values"]
        for entry in metadata.embedded_metadata
    }

    assert values_by_label["Artist"] == ["ZeroXX"]
    assert values_by_label["Description"] == ["One\nTwo\nThree\nFour"]


def test_video_technical_metadata_is_extracted_for_properties():
    fourcc = sum(ord(character) << (8 * index) for index, character in enumerate("avc1"))
    values = {
        cv2.CAP_PROP_FOURCC: fourcc,
        cv2.CAP_PROP_BITRATE: 4200,
    }

    class Capture:
        def get(self, property_id):
            return values.get(property_id, 0)

    entries = read_video_embedded_metadata(
        "missing-video.mp4",
        Capture(),
        frames=240,
        fps=24,
    )
    values_by_label = {
        entry["label"]: entry["values"]
        for entry in entries
    }

    assert values_by_label["Frame rate"] == ["24"]
    assert values_by_label["Frame count"] == ["240"]
    assert values_by_label["Video codec"] == ["avc1"]
    assert values_by_label["Video bitrate"] == ["4200 kbps"]


def test_compressed_id3_metadata_has_one_aggregate_output_budget(
    monkeypatch,
    tmp_path,
):
    original_zlib = media_proc._mutagen_id3_frames.zlib
    monkeypatch.setattr(
        media_proc,
        "_MAX_MUTAGEN_ID3_DECOMPRESSED_BYTES",
        64,
    )

    def oversized_frame(_path, *, easy):
        assert easy is False
        media_proc._mutagen_id3_frames.zlib.decompress(
            zlib.compress(b"A" * 65)
        )

    monkeypatch.setattr(media_proc, "MutagenFile", oversized_frame)
    assert read_mutagen_metadata(tmp_path / "oversized.mp3") == ()
    assert media_proc._mutagen_id3_frames.zlib is original_zlib

    def cumulative_frames(_path, *, easy):
        assert easy is False
        bounded_zlib = media_proc._mutagen_id3_frames.zlib
        bounded_zlib.decompress(zlib.compress(b"A" * 40))
        bounded_zlib.decompress(zlib.compress(b"B" * 40))

    monkeypatch.setattr(media_proc, "MutagenFile", cumulative_frames)
    assert read_mutagen_metadata(tmp_path / "cumulative.mp3") == ()
    assert media_proc._mutagen_id3_frames.zlib is original_zlib

    def bounded_frame(_path, *, easy):
        assert easy is False
        decoded = media_proc._mutagen_id3_frames.zlib.decompress(
            zlib.compress(b"safe metadata")
        )
        assert decoded == b"safe metadata"
        return SimpleNamespace(
            tags={"TIT2": "Evidence"},
            info=None,
            pictures=(),
        )

    monkeypatch.setattr(media_proc, "MutagenFile", bounded_frame)
    entries = read_mutagen_metadata(tmp_path / "bounded.mp3")
    assert entries[0]["label"] == "Title"
    assert entries[0]["values"] == ["Evidence"]
    assert media_proc._mutagen_id3_frames.zlib is original_zlib


def test_startup_cleanup_removes_plaintext_from_dead_session(tmp_path):
    session = tmp_path / "kryptonote-meta-424242-0123456789abcdef"
    session.mkdir()
    plaintext = session / "media-evidence.mp3"
    plaintext.write_bytes(b"decrypted evidence")
    active = tmp_path / "kryptonote-meta-434343-fedcba9876543210"
    active.mkdir()
    active_plaintext = active / "media-active.mp3"
    active_plaintext.write_bytes(b"active evidence")
    ready = tmp_path / "active-lock-ready"
    release = tmp_path / "active-lock-release"
    repository_root = Path(__file__).resolve().parents[1]
    holder_script = "\n".join(
        (
            "import sys",
            "import time",
            "from pathlib import Path",
            "import KryptoNote.utils.secure_temp as secure_temp",
            "session, ready, release = map(Path, sys.argv[1:4])",
            "lock = secure_temp._try_lock_session(session, create=True)",
            "if lock is None: raise SystemExit(3)",
            "ready.write_text('ready', encoding='utf-8')",
            "deadline = time.monotonic() + 10.0",
            "while not release.exists() and time.monotonic() < deadline: time.sleep(0.05)",
            "secure_temp._release_session_lock(lock)",
        )
    )
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            holder_script,
            str(active),
            str(ready),
            str(release),
        ],
        cwd=repository_root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 5.0
        while not ready.exists() and time.monotonic() < deadline:
            if holder.poll() is not None:
                break
            time.sleep(0.05)
        assert ready.exists()

        removed = cleanup_stale_metadata_temp_dirs(tmp_path)

        assert removed == 1
        assert not session.exists()
        assert active_plaintext.exists()
    finally:
        release.write_text("release", encoding="utf-8")
        try:
            holder.wait(timeout=5)
        except subprocess.TimeoutExpired:
            holder.kill()
            holder.wait(timeout=5)
            raise
        cleanup_stale_metadata_temp_dirs(tmp_path)

    assert not active.exists()


def test_metadata_watchdog_removes_plaintext_after_abnormal_exit(tmp_path):
    handoff = tmp_path / "metadata-temp-path.txt"
    repository_root = Path(__file__).resolve().parents[1]
    script = "\n".join(
        (
            "import os",
            "import sys",
            "from pathlib import Path",
            "from KryptoNote.utils.secure_temp import create_guarded_metadata_temp_file",
            "descriptor, temp_path = create_guarded_metadata_temp_file('.mp3')",
            "os.write(descriptor, b'decrypted evidence')",
            "os.close(descriptor)",
            "Path(sys.argv[1]).write_text(temp_path, encoding='utf-8')",
            "os._exit(23)",
        )
    )

    result = subprocess.run(
        [sys.executable, "-c", script, str(handoff)],
        cwd=repository_root,
        timeout=15,
        check=False,
    )

    assert result.returncode == 23
    temp_path = Path(handoff.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 5.0
    while temp_path.exists() and time.monotonic() < deadline:
        time.sleep(0.05)

    try:
        assert not temp_path.exists()
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass
        try:
            temp_path.parent.rmdir()
        except OSError:
            pass


def test_existing_image_metadata_is_backfilled_and_persisted_encrypted(tmp_path):
    source_path = tmp_path / "legacy.png"
    png_info = PngImagePlugin.PngInfo()
    png_info.add_text("Artist", "ZeroXX")
    png_info.add_text("Description", "One\nTwo\nThree\nFour")
    Image.new("RGB", (8, 6), "black").save(source_path, pnginfo=png_info)
    payload = source_path.read_bytes()

    database_path = tmp_path / "metadata-backfill.db"
    database = DatabaseConnection(str(database_path))
    crypto = CryptoManager()
    crypto.load_data_key(b"audio-metadata-test-key-32-bytes")
    repository = NodeRepository(database, crypto)
    try:
        item_id = repository.add_item(
            "image",
            0,
            0,
            320,
            180,
            title="legacy.png",
            data=payload,
            original_filename="legacy.png",
        )
        completed = []
        failures = []
        worker = MediaMetadataBackfillWorker(
            str(database_path),
            crypto.create_clone(),
            item_id,
            "image",
            len(payload),
            "legacy.png",
            False,
        )
        worker.finished.connect(
            lambda restored_id, metadata: completed.append(
                (restored_id, metadata)
            )
        )
        worker.failed.connect(
            lambda restored_id, message: failures.append(
                (restored_id, message)
            )
        )
        worker.run()

        assert failures == []
        assert completed and completed[0][0] == item_id
        repository.update_media_metadata(item_id, completed[0][1])
        encrypted = database.cursor.execute(
            "SELECT media_metadata FROM items WHERE id=?",
            (item_id,),
        ).fetchone()[0]
        restored = repository.get_items_by_ids([item_id])[0].media_metadata
    finally:
        repository.close()
        database.close()

    assert b"ZeroXX" not in encrypted
    values_by_label = {
        entry["label"]: entry["values"]
        for entry in restored
    }
    assert values_by_label["Artist"] == ["ZeroXX"]
    assert values_by_label["Description"] == ["One\nTwo\nThree\nFour"]
