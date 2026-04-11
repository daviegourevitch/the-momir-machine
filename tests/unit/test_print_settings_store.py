from pathlib import Path

from print_settings_store import (
    DEFAULT_PRINT_SETTINGS,
    load_print_settings,
    normalize_print_settings,
)


def test_normalize_print_settings_clamps_and_coerces_types() -> None:
    normalized = normalize_print_settings(
        {
            "dither_enabled": False,
            "threshold": 999,
            "contrast": 0.1,
            "unsharp_percent": 123.8,
            "unsharp_threshold": "nope",
            "gamma": 3.2,
        }
    )

    assert normalized["dither_enabled"] is False
    assert normalized["threshold"] == 255
    assert normalized["contrast"] == 0.5
    assert normalized["unsharp_percent"] == 124
    assert normalized["unsharp_threshold"] == DEFAULT_PRINT_SETTINGS["unsharp_threshold"]
    assert normalized["gamma"] == 3.2


def test_load_print_settings_persists_normalized_file(tmp_path: Path) -> None:
    path = tmp_path / "print-settings.json"
    path.write_text('{"threshold": -10, "dither_enabled": true}', encoding="utf-8")

    loaded = load_print_settings(path)

    assert loaded["threshold"] == 0
    assert loaded["dither_enabled"] is True
    assert path.is_file()
    on_disk = path.read_text(encoding="utf-8")
    assert '"threshold": 0' in on_disk
