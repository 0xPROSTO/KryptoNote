from PySide6.QtMultimedia import QMediaPlayer

from KryptoNote.gui.controllers.viewer_controller import ViewerController
from KryptoNote.services.graph_export_service import GraphExportService
from KryptoNote.utils.media_proc import (
    AUDIO_WAVEFORM_PEAK_COUNT,
    _StreamingAudioPeakAggregator,
    decode_audio_waveform,
    encode_audio_waveform,
)


def test_audio_waveform_codec_is_bounded_and_round_trips():
    aggregator = _StreamingAudioPeakAggregator()
    for index in range(50_000):
        aggregator.add(index * 1_024, 1_024, (index % 101) / 100)

    assert aggregator.retained_bin_count <= AUDIO_WAVEFORM_PEAK_COUNT * 2
    peaks = aggregator.finalize(50_000 * 1_024)
    payload = encode_audio_waveform(peaks, duration=123.5)
    decoded = decode_audio_waveform(payload)

    assert decoded is not None
    assert len(decoded.peaks) == AUDIO_WAVEFORM_PEAK_COUNT
    assert decoded.duration == 123.5


def test_audio_signature_distinguishes_adts_from_mpeg_audio():
    detect = GraphExportService._extension_from_signature

    assert detect(b"\xff\xf1\x50\x80" + b"\0" * 60, "audio") == ".aac"
    assert detect(b"\xff\xf9\x50\x80" + b"\0" * 60, "audio") == ".aac"
    assert detect(b"\xff\xfb\x90\x64" + b"\0" * 60, "audio") == ".mp3"
    assert detect(b"\x1aE\xdf\xa3" + b"\0" * 60, "audio") == ".mka"


def test_inline_audio_status_cannot_complete_an_image_preview_load():
    controller = ViewerController.__new__(ViewerController)
    controller._shutting_down = False
    controller._playback_generation = 9
    controller._playback_node_id = 41
    controller._playback_media_type = "audio"
    controller._active = True
    controller._node_id = 42
    controller._media_type = "image"
    controller._loading = True

    controller._on_media_status_changed(
        9,
        QMediaPlayer.MediaStatus.LoadedMedia,
    )

    assert controller._loading is True


def test_viewer_collections_are_exposed_as_qml_value_types():
    expected_types = {
        "tags": "QVariantList",
        "metadata": "QVariantMap",
        "imageState": "QVariantMap",
    }

    meta_object = ViewerController.staticMetaObject
    for property_name, expected_type in expected_types.items():
        property_index = meta_object.indexOfProperty(property_name)
        assert property_index >= 0
        assert meta_object.property(property_index).typeName() == expected_type
