import asyncio

from apps.common.kaleidescape.discovery import (
    HeartbeatProtocol,
    SddpProtocol,
    parse_sddp,
    sddp_search_message,
)


def test_parses_kaleidescape_sddp_reply():
    payload = (
        b'SDDP/1.0 200 OK\r\nTYPE: "kaleidescape:cinemaone"\r\n'
        b'MANUFACTURER: "Kaleidescape"\r\nMODEL: "Strato"\r\n\r\n'
    )
    candidate = parse_sddp(payload, "192.0.2.12")
    assert candidate is not None
    assert candidate.ip_address == "192.0.2.12"
    assert candidate.headers["model"] == "Strato"


def test_rejects_unrelated_or_malformed_sddp():
    assert parse_sddp(b"HTTP/1.1 200 OK\r\n", "192.0.2.1") is None
    assert parse_sddp(b"SDDP/1.0 200 OK\r\nTYPE: other:device\r\n", "192.0.2.1") is None


def test_legacy_heartbeat_records_source_address():
    queue: asyncio.Queue = asyncio.Queue()
    HeartbeatProtocol(queue).datagram_received(b"opaque", ("192.0.2.18", 1443))
    candidate = queue.get_nowait()
    assert candidate.ip_address == "192.0.2.18"
    assert candidate.source == "heartbeat"


def test_passive_sddp_announcement_is_queued():
    queue: asyncio.Queue = asyncio.Queue()
    SddpProtocol(queue).datagram_received(
        b'NOTIFY * SDDP/1.0\r\nTYPE: "kaleidescape:player"\r\n',
        ("192.0.2.20", 1902),
    )
    assert queue.get_nowait().source == "sddp"


def test_sddp_search_advertises_its_unicast_return_address():
    payload = sddp_search_message("192.0.2.44", 43123)

    assert payload == (
        b'SEARCH * SDDP/1.0\r\nHost: "192.0.2.44:43123"\r\n\r\n'
    )
    assert b"239.255.255.250" not in payload
