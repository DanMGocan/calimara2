from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_profile_settings_wires_data_portability_controls():
    source = (ROOT / "frontend" / "src" / "routes" / "profile-settings.jsx").read_text(encoding="utf-8")
    api_source = (ROOT / "frontend" / "src" / "api" / "data-portability.js").read_text(encoding="utf-8")

    assert "fetchDataExport" in source
    assert "importDataExport" in source
    assert "Exportă JSON" in source
    assert "Importă JSON" in source
    assert 'api.get("/api/portabilitate/export")' in api_source
    assert 'api.post("/api/portabilitate/import", data)' in api_source


def test_docs_describe_data_portability_behavior():
    docs = (ROOT / "frontend" / "src" / "routes" / "docs.jsx").read_text(encoding="utf-8")

    assert "/api/portabilitate/export" in docs
    assert "/api/portabilitate/import" in docs
    assert "postările aprobate" in docs
