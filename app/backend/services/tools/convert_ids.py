
from __future__ import annotations
import re
from uuid import UUID



# Convert IDs (Steam ID <-> Palworld UID)


# Standalone CityHash64 (CityHash by Google) — replaces palsav._cityhash.
# The exact variant Palworld uses: CityHash64 on the UTF-16-LE encoded digits.
def _cityhash64(data: bytes) -> int:
    const = 0x9DDFEA08EB382D69
    mask = 0xFFFFFFFFFFFFFFFF
    mult = 0x9E3779B97F4A7C15
    len_ = len(data)

    def fetch64(p: int) -> int:
        return int.from_bytes(data[p:p + 8], "little")

    def fetch32(p: int) -> int:
        return int.from_bytes(data[p:p + 4], "little")

    def rotate(val: int, shift: int) -> int:
        return ((val >> shift) | (val << (64 - shift))) & mask

    def shift_mix(val: int) -> int:
        return (val ^ (val >> 47)) & mask

    def hash_len_16(u, v):
        a = (u * mult) & mask
        a = rotate(a, 31)
        a = (a * mult) & mask
        b = (v * mult) & mask
        h = (a ^ b) & mask
        h = (h * mult) & mask
        b = rotate(b, 33)
        b = (b * mult) & mask
        h = (h ^ b) & mask
        return h

    def weak_hash_len_32_with_seeds(w, x, y, z, a, b):
        a = (a + w) & mask
        b = rotate((b + a + z) & mask, 21)
        c = a & mask
        a = (a + x + y) & mask
        b = (b + a) & mask
        return (a, b)

    def weak_hash_len_32_with_seeds_data(s, a, b):
        return weak_hash_len_32_with_seeds(
            fetch32(s), fetch32(s + 4), fetch32(s + 8), fetch32(s + 12), a, b,
        )

    def hash_len_0_to_16():
        if len_ >= 8:
            mul = (mult * (fetch64(0) ^ 0)) & mask
            a = (fetch64(0) + fetch64(len_ - 8)) & mask
            b = rotate(a, 43) & mask
            c = ((a * mul) ^ b) & mask
            d = (rotate(b, 31) + c) & mask
            mul = (mul * const) & mask
            h = ((c * mul) ^ (d * mult)) & mask
            h = (h * mult) ^ d
            return shift_mix(h)
        if len_ >= 4:
            mul = (mult * fetch32(0)) & mask
            return shift_mix((rotate(fetch32(0) * mul & mask, 17) * fetch32(len_ - 4) * mult) & mask)
        if len_ > 0:
            a = data[0]
            b = data[len_ >> 1]
            c = data[len_ - 1]
            y = (a + (b << 8)) & mask
            z = (len_ + (c << 2)) & mask
            return shift_mix((mult * y) ^ (const * z)) & mask
        return mult

    if len_ <= 16:
        return hash_len_0_to_16()

    x = fetch64(len_ - 40)
    y = fetch64(len_ - 16) + fetch64(len_ - 56)
    z = (hash_len_16(fetch64(len_ - 48) + len_, fetch64(len_ - 24)) +
         fetch64(0)) & mask

    while len_ > 64:
        x = (rotate(x + y + fetch64(0) + fetch32(8), 37) * const) & mask
        y = (rotate(y + fetch64(8) + fetch32(16 + 8), 42) * const) & mask
        x ^= fetch64(16 + 24)
        y = (y + fetch64(16 + 32)) & mask
        z = (rotate(z + fetch64(16 + 40), 33) * const) & mask
        v = weak_hash_len_32_with_seeds_data(16, z, y)
        w = weak_hash_len_32_with_seeds_data(16 + 32, (z + fetch64(16 + 16)) & mask, fetch64(16 + 48) + x)
        x = (x + v[0]) & mask
        y = (v[1] + y) & mask
        z = (z + w[0]) & mask
        a = (hash_len_16(v[0] + w[1], y + fetch64(16 + 8)) + z) & mask
        b = (hash_len_16(w[0] + v[1], z + fetch64(16 + 56)) + x) & mask
        data = data[64:]
        len_ -= 64

    a = (hash_len_16(fetch64(0) ^ const, fetch64(8) ^ const) + (fetch64(16) ^ len_)) & mask
    b = (hash_len_16(fetch64(24) + z, fetch64(32) + y) + a) & mask
    c = (hash_len_16(b, fetch64(40) + x) + z) & mask
    d = (hash_len_16(a, fetch64(48) + z) + b) & mask
    e = (hash_len_16(c, fetch64(56) + b) + d) & mask
    if len_ > 56:
        x = (x + fetch64(0)) & mask
        y = (y + fetch64(8)) & mask
        z = (z + fetch64(16)) & mask
        a = (hash_len_16(fetch64(0) ^ const, fetch64(8) ^ const) + (fetch64(16) ^ len_)) & mask
        b = (hash_len_16(fetch64(24) + z, fetch64(32) + y) + a) & mask
        c = (hash_len_16(b, fetch64(40) + x) + z) & mask
    return hash_len_16(c, e)


def _steam_id_to_palworld_uid(steam_id: int) -> str:
    """Convert a Steam 64-bit ID to a Palworld UUID string (w/ dashes, upper)."""
    h = _cityhash64(str(steam_id).encode("utf-16-le"))
    lo = h & 0xFFFFFFFF
    hi = (((h >> 32) & 0xFFFFFFFF) * 23 + lo) & 0xFFFFFFFF
    raw = hi.to_bytes(4, "little") + b"\x00" * 12
    return str(UUID(bytes=raw)).upper()


def _palworld_uid_to_nosteam(palworld_uid: str) -> str:
    """Palworld UUID -> NoSteam hex string (8-char prefix + suffix)."""
    u = UUID(palworld_uid)
    raw = u.bytes[0:4]
    val = int.from_bytes(raw, "little", signed=True) & 0xFFFFFFFF

    def u32(x: int) -> int:
        return x & 0xFFFFFFFF

    a = u32(u32(val << 8) ^ u32(2654435769 - val))
    b = u32(a >> 13 ^ u32(-(val + a)))
    c = u32(b >> 12 ^ u32(val - a - b))
    d = u32(u32(c << 16) ^ u32(a - c - b))
    e = u32(d >> 5 ^ b - d - c)
    f = u32(e >> 3 ^ c - d - e)
    r = u32(u32(u32(f << 10) ^ u32(d - f - e)) >> 15 ^ e - (u32(f << 10) ^ u32(d - f - e)) - f)
    return f"{r:08X}-0000-0000-0000-000000000000"


def detect_input_type(input_str: str) -> str:
    """Return ``"steam_id"``, ``"palworld_uid"``, ``"nosteam_uid"``, or ``"unknown"``."""
    s = input_str.strip()
    if s.startswith("steam_"):
        s = s[6:]
    if s.isdigit() and len(s) == 17:
        return "steam_id"
    if "steamcommunity.com/profiles/" in s:
        return "steam_id"
    if re.match(r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4,}$", s):
        return "palworld_uid" if s.count("-") == 4 else "nosteam_uid"
    if re.match(r"^[0-9A-Fa-f]{8}-0{4}-0{4}-0{4}-0{12}$", s):
        return "nosteam_uid"
    return "unknown"


def convert_ids(input_str: str) -> dict:
    """Convert between Steam ID, Palworld UID, and NoSteam UID formats."""
    raw = input_str.strip()
    input_type = detect_input_type(raw)
    result: dict = {
        "input": raw, "input_type": input_type,
        "steam_id": None, "palworld_uid": None, "nosteam_uid": None,
    }
    if input_type == "steam_id":
        s = raw
        if "steamcommunity.com/profiles/" in s:
            s = s.split("steamcommunity.com/profiles/")[1].split("/")[0]
        elif s.startswith("steam_"):
            s = s[6:]
        steam_id = int(s)
        puid = _steam_id_to_palworld_uid(steam_id)
        result["steam_id"] = str(steam_id)
        result["palworld_uid"] = puid
        result["nosteam_uid"] = _palworld_uid_to_nosteam(puid)
    elif input_type == "palworld_uid":
        result["palworld_uid"] = raw
        result["nosteam_uid"] = _palworld_uid_to_nosteam(raw)
    elif input_type == "nosteam_uid":
        result["nosteam_uid"] = raw
    return result


