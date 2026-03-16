import inspect
import pytest


@pytest.mark.skip(reason="main() added in Task 3")
def test_main_is_importable_and_callable():
    from chorus.main import main
    assert callable(main)
    sig = inspect.signature(main)
    required = [p for p in sig.parameters.values()
                if p.default is inspect.Parameter.empty]
    assert len(required) == 0


def test_version_exported():
    import chorus
    assert hasattr(chorus, "__version__")
    assert chorus.__version__ == "1.0.0"


def test_frontend_html_accessible_from_package():
    """index.html must be accessible as package data after install."""
    import importlib.resources
    text = importlib.resources.files("chorus").joinpath("frontend/index.html").read_text(encoding="utf-8")
    assert "<html" in text.lower()
