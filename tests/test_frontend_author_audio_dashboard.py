from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_wires_rapsod_author_audio_upload():
    source = (ROOT / "frontend/src/routes/dashboard.jsx").read_text()
    styles = (ROOT / "frontend/src/index.css").read_text()

    assert "uploadPostAudioRecording" in source
    assert "AUTHOR_AUDIO_ACCEPT" in source
    assert "audio/webm" in source
    assert "AuthorAudioUploadButton" in source
    assert "user?.has_author_audio_access" in source
    assert "author_audio_can_upload" in source
    assert "author_audio_message" in source
    assert ".author-audio-status" in styles


def test_docs_describe_author_audio_dashboard_flow():
    source = (ROOT / "frontend/src/routes/docs.jsx").read_text()

    assert "Rapsod încarcă sau înlocuiește lecturile de autor" in source
    assert "postărilor aprobate din Panou" in source
