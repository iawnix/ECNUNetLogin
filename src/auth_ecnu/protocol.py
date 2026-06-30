"""Pure SRun/SRBX1 request construction helpers."""

from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
from typing import Dict, Iterable, Mapping

from .constants import (
    CALLBACK,
    CUSTOM_B64_ALPHABET,
    ENC_VER,
    INFO_PREFIX,
    PASSWORD_PREFIX,
    UINT32_MASK,
)
from .errors import PortalError
from .models import AuthParams, OnlineStatus


def sha1sum(data: str) -> str:
    return hashlib.sha1(data.encode()).hexdigest()


def quirk_base64_encode(data: bytes) -> str:
    out_len = ((len(data) + 2) // 3) * 4
    out = ["="] * out_len
    pos = 0

    for i in range(0, len(data), 3):
        b0 = data[i]
        b1 = data[i + 1] if i + 1 < len(data) else 0
        b2 = data[i + 2] if i + 2 < len(data) else 0
        value = (b0 << 16) | (b1 << 8) | b2

        for j in range(4):
            if i * 8 + j * 6 <= len(data) * 8:
                out[pos] = CUSTOM_B64_ALPHABET[(value >> (6 * (3 - j))) & 0x3F]
            else:
                out[pos] = "="
            pos += 1

    return "".join(out)


def _to_uint32_words(text: str, include_length: bool) -> list[int]:
    raw = text.encode()
    words = [0] * ((len(raw) + 3) // 4)

    for i, byte in enumerate(raw):
        words[i >> 2] |= byte << ((i & 3) << 3)

    if include_length:
        words.append(len(raw))

    return words


def _from_uint32_words(words: Iterable[int], include_length: bool) -> bytes | None:
    words = list(words)
    if include_length:
        if not words:
            return b""
        size = words[-1]
        max_size = (len(words) - 1) * 4
        if size < max_size - 3 or size > max_size:
            return None
        words = words[:-1]
    else:
        size = len(words) * 4

    out = bytearray()
    for word in words:
        out.extend(
            (
                word & 0xFF,
                (word >> 8) & 0xFF,
                (word >> 16) & 0xFF,
                (word >> 24) & 0xFF,
            )
        )
    return bytes(out[:size])


def xencode(data: str, key: str) -> bytes:
    if not data:
        return b""

    v = _to_uint32_words(data, include_length=True)
    k = _to_uint32_words(key, include_length=False)
    if len(k) < 4:
        raise ValueError("token key is too short for XEncode")

    n = len(v) - 1
    rounds = 6 + 52 // len(v)
    sum_value = 0
    z = v[n]

    while rounds > 0:
        rounds -= 1
        sum_value = (sum_value + 0x9E3779B9) & UINT32_MASK
        e = (sum_value >> 2) & 3

        for p in range(n + 1):
            y = v[0] if p == n else v[p + 1]
            idx = (p & 3) ^ e
            mx = (
                ((z >> 5) ^ ((y << 2) & UINT32_MASK))
                + (((y >> 3) ^ ((z << 4) & UINT32_MASK)) ^ (sum_value ^ y))
                + (k[idx] ^ z)
            ) & UINT32_MASK
            z = v[p] = (v[p] + mx) & UINT32_MASK

    encoded = _from_uint32_words(v, include_length=False)
    if encoded is None:
        raise ValueError("XEncode failed")
    return encoded


def build_request_params(params: AuthParams) -> Dict[str, str]:
    acid = str(params.acid)
    auth_info: Dict[str, str] = {
        "enc_ver": ENC_VER,
        "username": params.username,
        "ip": params.ip,
        "acid": acid,
    }
    if params.action == "login":
        auth_info["password"] = params.password

    info_json = json.dumps(auth_info, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    info = INFO_PREFIX + quirk_base64_encode(xencode(info_json, params.token))

    request: Dict[str, str] = {
        "action": params.action,
        "ac_id": acid,
        "n": "200",
        "type": "1",
        "double_stack": "1",
        "ip": params.ip,
        "username": params.username,
        "info": info,
    }

    if params.action == "login":
        md5_hex = hashlib.md5(params.password.encode()).hexdigest()
        request["password"] = PASSWORD_PREFIX + md5_hex
        checksum_parts = [
            params.token,
            params.username,
            params.token,
            md5_hex,
            params.token,
            acid,
            params.token,
            params.ip,
            params.token,
            request["n"],
            params.token,
            request["type"],
            params.token,
            info,
        ]
    else:
        checksum_parts = [
            params.token,
            params.username,
            params.token,
            acid,
            params.token,
            params.ip,
            params.token,
            request["n"],
            params.token,
            request["type"],
            params.token,
            info,
        ]

    request["chksum"] = sha1sum("".join(checksum_parts))
    return request


def build_challenge_params(username: str, ip: str) -> Dict[str, str]:
    return {
        "ip": ip,
        "username": username,
        "double_stack": "1",
        "callback": CALLBACK,
    }


def add_auth_callback(params: Mapping[str, str]) -> Dict[str, str]:
    out = dict(params)
    out["callback"] = CALLBACK
    return out


def find_acid(html: str) -> int:
    match = re.search(r"/index_([0-9]+)\.html", html)
    if not match:
        raise PortalError("acid not found in portal index page")
    return int(match.group(1), 10)


def find_json(jsonp: str) -> str:
    match = re.search(r"C_a_l_l_b_a_c_k\((.+)\)", jsonp)
    if not match:
        raise ValueError("JSONP payload not found")
    return match.group(1)


def query_string(params: Mapping[str, str]) -> str:
    return urllib.parse.urlencode(params)


def online_status_to_dict(status: OnlineStatus) -> Dict[str, object]:
    payload: Dict[str, object] = {
        "online": status.online,
        "username": status.username,
        "raw": status.raw,
    }
    fields = status.raw.split(",") if status.raw else []
    if len(fields) > 8 and fields[8]:
        payload["ip"] = fields[8]
    return payload
