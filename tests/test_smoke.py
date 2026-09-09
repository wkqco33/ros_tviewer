from __future__ import annotations

from ros_tviewer.main import build_root


def test_build_root():
    root = build_root()
    assert root is not None
