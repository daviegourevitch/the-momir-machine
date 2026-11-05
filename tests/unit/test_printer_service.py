from __future__ import annotations

from io import BytesIO
from typing import Any

import pytest
import requests
from PIL import Image

import printer_service
from constants import SCRYFALL_USER_AGENT
from print_settings_store import DEFAULT_PRINT_SETTINGS

IMAGE_URL = "https://cards.scryfall.io/large/front/a/b/abc.jpg"


def _png_bytes(width: int = 488, height: int = 680) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), (120, 60, 30)).save(buffer, format="PNG")
    return buffer.getvalue()


class FakeResponse:
    def __init__(self, content: bytes = b"", status_code: int = 200) -> None:
        self.content = content
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Client Error", response=self)  # type: ignore[arg-type]


class FakePrinter:
    def __init__(self) -> None:
        self.images: list[Image.Image] = []
        self.closed = False

    def image(self, image: Image.Image) -> None:
        self.images.append(image)

    def cut(self) -> None:
        return

    def close(self) -> None:
        self.closed = True


def _fetch() -> Image.Image:
    return printer_service.fetch_and_prepare_image(
        IMAGE_URL, print_settings=dict(DEFAULT_PRINT_SETTINGS)  # type: ignore[arg-type]
    )


def test_fetch_sends_scryfall_required_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def _get(url: str, **kwargs: Any) -> FakeResponse:
        calls.append({"url": url, **kwargs})
        return FakeResponse(_png_bytes())

    monkeypatch.setattr(printer_service.requests, "get", _get)

    _fetch()

    assert len(calls) == 1
    headers = calls[0].get("headers") or {}
    assert headers.get("User-Agent") == SCRYFALL_USER_AGENT
    # Scryfall asks for a descriptive agent, not a generic library default.
    assert "python-requests" not in headers["User-Agent"]
    assert headers.get("Accept")
    assert calls[0].get("timeout")


def test_fetch_returns_printer_ready_image(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        printer_service.requests, "get", lambda *_a, **_k: FakeResponse(_png_bytes())
    )

    image = _fetch()

    assert image.mode == "1"
    assert image.width == printer_service.PRINTER_WIDTH_PX


@pytest.mark.parametrize(
    "error",
    [
        requests.ConnectionError("connection refused"),
        requests.Timeout("timed out"),
    ],
)
def test_fetch_wraps_network_errors(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    def _get(*_args: Any, **_kwargs: Any) -> FakeResponse:
        raise error

    monkeypatch.setattr(printer_service.requests, "get", _get)

    with pytest.raises(printer_service.CardImageError):
        _fetch()


@pytest.mark.parametrize("status_code", [400, 403, 429, 500])
def test_fetch_wraps_http_errors(monkeypatch: pytest.MonkeyPatch, status_code: int) -> None:
    monkeypatch.setattr(
        printer_service.requests,
        "get",
        lambda *_a, **_k: FakeResponse(b'{"object":"error"}', status_code=status_code),
    )

    with pytest.raises(printer_service.CardImageError):
        _fetch()


def test_fetch_wraps_non_image_body(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        printer_service.requests,
        "get",
        lambda *_a, **_k: FakeResponse(b"<html>blocked</html>"),
    )

    with pytest.raises(printer_service.CardImageError):
        _fetch()


def test_print_card_image_closes_printer_when_image_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    printer = FakePrinter()
    monkeypatch.setattr(printer_service, "detect_usb_printer", lambda: printer)

    def _get(*_args: Any, **_kwargs: Any) -> FakeResponse:
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(printer_service.requests, "get", _get)

    with pytest.raises(printer_service.CardImageError):
        printer_service.print_card_image(IMAGE_URL)

    assert printer.closed is True
    assert printer.images == []


def test_print_card_image_prints_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    printer = FakePrinter()
    monkeypatch.setattr(printer_service, "detect_usb_printer", lambda: printer)
    monkeypatch.setattr(
        printer_service.requests, "get", lambda *_a, **_k: FakeResponse(_png_bytes())
    )

    assert printer_service.print_card_image(IMAGE_URL) is True
    assert len(printer.images) == 1
    assert printer.closed is True
