from __future__ import annotations

from pathlib import Path

import pytest

from card_service import CardService


def test_warm_runtime_cache_and_pick_card_from_cache(
    make_cards_db, sample_settings_schema, sample_settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = make_cards_db(
        [
            {
                "name": "Alpha Creature",
                "cmc": 3,
                "card_types": ["Creature"],
                "legalities": {"modern": "legal"},
                "image_uris": {"large": "https://example.test/alpha.png"},
            },
            {
                "name": "Beta Creature",
                "cmc": 3,
                "card_types": ["Creature"],
                "legalities": {"modern": "legal"},
                "image_uris": {"large": "https://example.test/beta.png"},
            },
            {
                "name": "Gamma Instant",
                "cmc": 3,
                "card_types": ["Instant"],
                "legalities": {"modern": "legal"},
                "image_uris": {"large": "https://example.test/gamma.png"},
            },
        ]
    )
    service = CardService(db_path)
    monkeypatch.setattr("card_service.random.choice", lambda values: values[0])

    available = service.warm_runtime_cache(sample_settings_schema, sample_settings)
    picked = service.get_random_card(3, sample_settings_schema, sample_settings)

    assert available == [3]
    assert picked == {
        "name": "Alpha Creature",
        "image_url": "https://example.test/alpha.png",
    }


def test_get_random_card_uses_reservoir_sampling_when_cache_not_warmed(
    make_cards_db, sample_settings_schema, sample_settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = make_cards_db(
        [
            {
                "name": "First Creature",
                "cmc": 4,
                "card_types": ["Creature"],
                "legalities": {"modern": "legal"},
                "image_uris": {"large": "https://example.test/first.png"},
            },
            {
                "name": "Second Creature",
                "cmc": 4,
                "card_types": ["Creature"],
                "legalities": {"modern": "legal"},
                "image_uris": {"large": "https://example.test/second.png"},
            },
        ]
    )
    service = CardService(db_path)
    monkeypatch.setattr("card_service.random.randrange", lambda n: 0)

    picked = service.get_random_card(4, sample_settings_schema, sample_settings)
    assert picked == {
        "name": "Second Creature",
        "image_url": "https://example.test/second.png",
    }


def test_extracts_image_from_card_faces_when_image_uris_missing(
    make_cards_db, sample_settings_schema, sample_settings
) -> None:
    db_path = make_cards_db(
        [
            {
                "name": "Transform Card",
                "cmc": 2,
                "card_types": ["Creature"],
                "legalities": {"modern": "legal"},
                "image_uris": None,
                "card_faces": [
                    {"image_uris": {"small": "https://example.test/face.png"}},
                ],
            }
        ]
    )
    service = CardService(db_path)

    picked = service.get_random_card(2, sample_settings_schema, sample_settings)
    assert picked == {
        "name": "Transform Card",
        "image_url": "https://example.test/face.png",
    }


def test_missing_database_returns_empty_results(tmp_path: Path, sample_settings_schema, sample_settings) -> None:
    service = CardService(tmp_path / "missing.db")

    assert service.get_available_mana_values(sample_settings_schema, sample_settings) == []
    assert service.get_random_card(3, sample_settings_schema, sample_settings) is None
    assert service.get_card_image_url_by_name("Anything") is None
