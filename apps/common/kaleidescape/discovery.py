from __future__ import annotations

import asyncio
import socket
from dataclasses import dataclass

SDDP_ADDRESS = "239.255.255.250"
SDDP_PORT = 1902
HEARTBEAT_PORT = 1443


@dataclass(frozen=True)
class DeviceCandidate:
    ip_address: str
    headers: dict[str, str]
    source: str


def local_ipv4_addresses() -> list[str]:
    """Return usable IPv4 interfaces, keeping the multicast route as a fallback."""
    addresses: set[str] = set()
    try:
        for result in socket.getaddrinfo(
            socket.gethostname(), None, socket.AF_INET, socket.SOCK_DGRAM
        ):
            address = str(result[4][0])
            if not address.startswith("127.") and address != "0.0.0.0":
                addresses.add(address)
    except OSError:
        pass

    route = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        route.connect((SDDP_ADDRESS, SDDP_PORT))
        address = route.getsockname()[0]
        if not address.startswith("127.") and address != "0.0.0.0":
            addresses.add(address)
    except OSError:
        pass
    finally:
        route.close()
    return sorted(addresses)


def sddp_search_message(local_ip: str, local_port: int) -> bytes:
    # SDDP's Host header is the unicast return address, not the multicast target.
    return (
        "SEARCH * SDDP/1.0\r\n"
        f'Host: "{local_ip}:{local_port}"\r\n\r\n'
    ).encode("ascii")


def parse_sddp(payload: bytes, ip_address: str) -> DeviceCandidate | None:
    text = payload.decode("latin-1", errors="replace").replace("\r\n", "\n")
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if not lines or not (lines[0].startswith("SDDP/") or lines[0].startswith("NOTIFY")):
        return None
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip().strip('"')
    identity = " ".join(headers.get(key, "") for key in ("type", "manufacturer", "model", "driver"))
    if "kaleidescape" not in identity.casefold():
        return None
    return DeviceCandidate(ip_address=ip_address, headers=headers, source="sddp")


async def _discover_sddp_on_interface(
    local_ip: str, timeout: float
) -> list[DeviceCandidate]:
    loop = asyncio.get_running_loop()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setblocking(False)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(local_ip))
    sock.bind((local_ip, 0))
    _, local_port = sock.getsockname()
    candidates: dict[str, DeviceCandidate] = {}
    try:
        await loop.sock_sendto(
            sock, sddp_search_message(local_ip, local_port), (SDDP_ADDRESS, SDDP_PORT)
        )
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            try:
                payload, address = await asyncio.wait_for(
                    loop.sock_recvfrom(sock, 8192), timeout=max(0.01, deadline - loop.time())
                )
            except TimeoutError:
                break
            candidate = parse_sddp(payload, address[0])
            if candidate:
                candidates[candidate.ip_address] = candidate
    finally:
        sock.close()
    return list(candidates.values())


async def discover_sddp(timeout: float = 3.0) -> list[DeviceCandidate]:
    addresses = local_ipv4_addresses()
    if not addresses:
        return []
    results = await asyncio.gather(
        *(_discover_sddp_on_interface(address, timeout) for address in addresses),
        return_exceptions=True,
    )
    candidates: dict[str, DeviceCandidate] = {}
    errors: list[OSError] = []
    for result in results:
        if isinstance(result, OSError):
            errors.append(result)
            continue
        if isinstance(result, BaseException):
            raise result
        for candidate in result:
            candidates[candidate.ip_address] = candidate
    if errors and len(errors) == len(results):
        raise errors[0]
    return list(candidates.values())


class HeartbeatProtocol(asyncio.DatagramProtocol):
    def __init__(self, queue: asyncio.Queue[DeviceCandidate]) -> None:
        self.queue = queue

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        del data
        self.queue.put_nowait(DeviceCandidate(addr[0], {}, "heartbeat"))


async def listen_heartbeats(queue: asyncio.Queue[DeviceCandidate]) -> None:
    loop = asyncio.get_running_loop()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", HEARTBEAT_PORT))
    sock.setblocking(False)
    transport, _ = await loop.create_datagram_endpoint(
        lambda: HeartbeatProtocol(queue),
        sock=sock,
    )
    try:
        await asyncio.Future()
    finally:
        transport.close()


class SddpProtocol(asyncio.DatagramProtocol):
    def __init__(self, queue: asyncio.Queue[DeviceCandidate]) -> None:
        self.queue = queue

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        candidate = parse_sddp(data, addr[0])
        if candidate:
            self.queue.put_nowait(candidate)


async def listen_sddp(queue: asyncio.Queue[DeviceCandidate]) -> None:
    """Receive passive SDDP announcements on the multicast group."""
    loop = asyncio.get_running_loop()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", SDDP_PORT))
    memberships = local_ipv4_addresses() or ["0.0.0.0"]
    joined = 0
    last_error: OSError | None = None
    for address in memberships:
        membership = socket.inet_aton(SDDP_ADDRESS) + socket.inet_aton(address)
        try:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
            joined += 1
        except OSError as error:
            last_error = error
    if not joined and last_error:
        sock.close()
        raise last_error
    sock.setblocking(False)
    transport, _ = await loop.create_datagram_endpoint(lambda: SddpProtocol(queue), sock=sock)
    try:
        await asyncio.Future()
    finally:
        transport.close()
