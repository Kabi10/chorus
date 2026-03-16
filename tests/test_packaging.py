import inspect
import pytest


def test_main_is_importable_and_callable():
    from chorus.main import main
    assert callable(main)
    sig = inspect.signature(main)
    required = [p for p in sig.parameters.values()
                if p.default is inspect.Parameter.empty]
    assert len(required) == 0


def test_check_playwright_exits_when_chromium_missing(monkeypatch):
    """_check_playwright() should print clear message and exit(1) when Chromium binary absent."""
    from unittest.mock import MagicMock, patch

    fake_path = "/nonexistent/chromium"
    mock_chromium = MagicMock()
    mock_chromium.executable_path = fake_path
    mock_pw = MagicMock()
    mock_pw.__enter__ = lambda s: mock_pw
    mock_pw.__exit__ = MagicMock(return_value=False)
    mock_pw.chromium = mock_chromium

    with patch("chorus.main.sync_playwright", return_value=mock_pw):
        with pytest.raises(SystemExit) as exc:
            from chorus.main import _check_playwright
            _check_playwright()
        assert exc.value.code == 1


def test_version_exported():
    import chorus
    assert hasattr(chorus, "__version__")
    assert chorus.__version__ == "1.0.0"


def test_frontend_html_accessible_from_package():
    """index.html must be accessible as package data after install."""
    import importlib.resources
    text = importlib.resources.files("chorus").joinpath("frontend/index.html").read_text(encoding="utf-8")
    assert "<html" in text.lower()
