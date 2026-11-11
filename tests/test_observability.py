import pytest

from apps.common.observability import event, sanitize


def test_recursive_redaction_hides_secrets_and_urls():
    value = sanitize({"token": "abc", "nested": {"cover_url": "http://private/cover.jpg"}})
    assert value == {"token": "[redacted]", "nested": {"cover_url": "[redacted]"}}


def test_event_names_are_stable_domain_names():
    with pytest.raises(ValueError):
        event("Human readable message")
