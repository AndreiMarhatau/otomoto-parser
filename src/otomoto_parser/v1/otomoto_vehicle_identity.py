from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from hashlib import sha256
from typing import Any
from urllib.request import Request, urlopen

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/26.4 Safari/605.1.15"
)
DEFAULT_ACCEPT_LANGUAGE = "en-US,en;q=0.9"
PBKDF2_SALT = b"d2905222-d0c5-4ec5-bfcf-e9c29041de3c"


@dataclass
class OtomotoVehicleIdentity:
    advert_id: str
    encrypted_vin: str | None
    encrypted_first_registration_date: str | None
    encrypted_registration_number: str | None
    vin: str
    first_registration_date: str | None
    registration_number: str | None


@dataclass(frozen=True)
class OtomotoPageRequestOptions:
    cookie_header: str | None = None
    user_agent: str = DEFAULT_USER_AGENT
    accept_language: str = DEFAULT_ACCEPT_LANGUAGE
    timeout_s: float = 45.0


def _extract_next_data(html: str) -> dict[str, Any]:
    match = re.search(
        r'<script\b(?=[^>]*\bid=["\']__NEXT_DATA__["\'])(?=[^>]*\btype=["\']application/json["\'])[^>]*>(?P<body>.*?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        raise RuntimeError("Could not find __NEXT_DATA__ in the Otomoto advert page.")
    return json.loads(match.group("body"))


def _extract_encrypted_value(parameters_dict: dict[str, Any], key: str, *, required: bool = True) -> str | None:
    item = parameters_dict.get(key)
    if not isinstance(item, dict):
        if required:
            raise RuntimeError(f"Missing encrypted Otomoto field: {key}")
        return None
    values = item.get("values")
    if not isinstance(values, list) or not values:
        if required:
            raise RuntimeError(f"Missing encrypted Otomoto values for field: {key}")
        return None
    value = values[0].get("value")
    if not isinstance(value, str) or not value:
        if required:
            raise RuntimeError(f"Invalid encrypted Otomoto value for field: {key}")
        return None
    return value


def _derive_key(advert_id: str, version: str) -> bytes:
    password = sha256(advert_id.encode("utf-8")).digest()[:16].hex().encode("utf-8")
    iterations = 10 if version and version != "0" else 10000
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=PBKDF2_SALT,
        iterations=iterations,
    )
    return kdf.derive(password)


def decrypt_otomoto_secret(encrypted_value: str, advert_id: str) -> str:
    parts = encrypted_value.split(".")
    if len(parts) != 3:
        raise RuntimeError("Unexpected encrypted Otomoto value format.")
    cipher_text, version, iv = parts
    key = _derive_key(advert_id, version)
    plain = AESGCM(key).decrypt(
        base64.b64decode(iv),
        base64.b64decode(cipher_text),
        None,
    )
    return plain.decode("utf-8")


def extract_otomoto_vehicle_identity_from_html(html: str) -> OtomotoVehicleIdentity:
    advert = extract_otomoto_advert_from_html(html)
    advert_id = str(advert["id"])
    parameters_dict = advert["parametersDict"]

    encrypted_vin = _extract_encrypted_value(parameters_dict, "vin")
    encrypted_first_registration_date = _extract_encrypted_value(parameters_dict, "date_registration", required=False)
    encrypted_registration_number = _extract_encrypted_value(parameters_dict, "registration", required=False)

    return OtomotoVehicleIdentity(
        advert_id=advert_id,
        encrypted_vin=encrypted_vin,
        encrypted_first_registration_date=encrypted_first_registration_date,
        encrypted_registration_number=encrypted_registration_number,
        vin=decrypt_otomoto_secret(encrypted_vin, advert_id),
        first_registration_date=decrypt_otomoto_secret(encrypted_first_registration_date, advert_id)
        if encrypted_first_registration_date
        else None,
        registration_number=decrypt_otomoto_secret(encrypted_registration_number, advert_id).upper()
        if encrypted_registration_number
        else None,
    )


def extract_otomoto_advert_from_html(html: str) -> dict[str, Any]:
    next_data = _extract_next_data(html)
    advert = next_data["props"]["pageProps"]["advert"]
    if not isinstance(advert, dict):
        raise RuntimeError("Could not find advert data in the Otomoto advert page.")
    return advert


def fetch_otomoto_vehicle_identity(
    url: str,
    options: OtomotoPageRequestOptions | None = None,
    **legacy_kwargs: object,
) -> OtomotoVehicleIdentity:
    html = _fetch_otomoto_page_html(url, _resolve_page_request_options(options, legacy_kwargs))
    return extract_otomoto_vehicle_identity_from_html(html)


def fetch_otomoto_listing_page_data(
    url: str,
    options: OtomotoPageRequestOptions | None = None,
    **legacy_kwargs: object,
) -> dict[str, Any]:
    html = _fetch_otomoto_page_html(url, _resolve_page_request_options(options, legacy_kwargs))
    return extract_otomoto_advert_from_html(html)


def _resolve_page_request_options(
    options: OtomotoPageRequestOptions | None,
    legacy_kwargs: dict[str, object],
) -> OtomotoPageRequestOptions:
    if options is None:
        return OtomotoPageRequestOptions(**legacy_kwargs)
    if legacy_kwargs:
        raise TypeError("Otomoto fetch helpers accept either options or legacy keyword arguments, not both.")
    return options


def _fetch_otomoto_page_html(url: str, options: OtomotoPageRequestOptions) -> str:
    headers = {
        "Accept-Language": options.accept_language,
        "User-Agent": options.user_agent,
    }
    if options.cookie_header:
        headers["Cookie"] = options.cookie_header
    request = Request(url, headers=headers, method="GET")
    with urlopen(request, timeout=options.timeout_s) as response:
        return response.read().decode("utf-8")
