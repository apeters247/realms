"""Unit tests for backfill_integrity_and_sources.py.

Tests cover the pure-logic helper functions that require no database.
"""
from __future__ import annotations

import pytest

# Import the module under test
from scripts.backfill_integrity_and_sources import _is_trusted


pytestmark = pytest.mark.unit


def test_is_trusted_wikipedia():
    result = _is_trusted("https://en.wikipedia.org/wiki/Tlaloc")
    assert result == ("wikipedia", 0.80)


def test_is_trusted_edu():
    result = _is_trusted("https://mythology.fas.harvard.edu/tlaloc")
    assert result == ("journal", 0.70)


def test_is_trusted_untrusted():
    result = _is_trusted("https://randomblog.com/tlaloc")
    assert result is None
