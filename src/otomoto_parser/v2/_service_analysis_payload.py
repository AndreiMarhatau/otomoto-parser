from __future__ import annotations

from typing import Any

from ..otomoto_vehicle_identity import decrypt_otomoto_secret

from ._service_analysis_payload_common import _compact_dict


def build_listing_payload(listing: dict[str, Any], record: dict[str, Any], listing_page: dict[str, Any] | None) -> dict[str, Any]:
    node = record.get("node") if isinstance(record.get("node"), dict) else {}
    page = listing_page if isinstance(listing_page, dict) else {}
    return _compact_dict(
        {
            "search": _search_payload(node),
            "listing": _listing_payload(listing, record, page),
        }
    )


def build_vehicle_report_payload(report_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(report_payload, dict):
        return None
    payload = _compact_dict(
        {
            "report": report_payload.get("report") if isinstance(report_payload.get("report"), dict) else None,
            "summary": report_payload.get("summary") if isinstance(report_payload.get("summary"), dict) else None,
        }
    )
    return payload or None


def _search_payload(node: dict[str, Any]) -> dict[str, Any] | None:
    price = node.get("price") if isinstance(node.get("price"), dict) else {}
    amount = price.get("amount") if isinstance(price.get("amount"), dict) else {}
    price_evaluation = node.get("priceEvaluation") if isinstance(node.get("priceEvaluation"), dict) else {}
    return _compact_dict(
        {
            "price": _compact_dict(
                {
                    "value": _search_price_value(price, amount),
                    "currencyCode": amount.get("currencyCode"),
                }
            ),
            "title": node.get("title"),
            "shortDescription": node.get("shortDescription"),
            "url": node.get("url"),
            "cepikVerified": node.get("cepikVerified"),
            "priceEvaluation": _compact_dict({"indicator": price_evaluation.get("indicator")}),
        }
    )


def _search_price_value(price: dict[str, Any], amount: dict[str, Any]) -> Any:
    return amount.get("value") if amount.get("value") not in (None, "") else amount.get("units") if amount.get("units") not in (None, "") else price.get("value")


def _listing_payload(listing: dict[str, Any], record: dict[str, Any], page: dict[str, Any]) -> dict[str, Any] | None:
    page_price = page.get("price") if isinstance(page.get("price"), dict) else {}
    raw_seller = page.get("seller") if isinstance(page.get("seller"), dict) else {}
    return _compact_dict(
        {
            "priceLabels": _price_labels(page_price),
            "mainFeatures": _plain_list(page.get("mainFeatures")),
            "description": page.get("description"),
            "seller": _compact_dict(
                {
                    "type": raw_seller.get("type"),
                    "featuresBadges": _seller_features_badges(raw_seller.get("featuresBadges")),
                }
            ),
            "equipment": _equipment_payload(page.get("equipment")),
            "isParts": page.get("isParts"),
            "isUsedCar": page.get("isUsedCar"),
            "verifiedCar": page.get("verifiedCar"),
            "verifiedCarFields": page.get("verifiedCarFields"),
            "details": _details_payload(listing, record, page),
        }
    )


def _price_labels(price: Any) -> list[str] | None:
    if not isinstance(price, dict):
        return None
    return _plain_label_list(price.get("labels"))


def _plain_list(value: Any) -> list[Any] | None:
    if not isinstance(value, list):
        return None
    return list(value)


def _plain_label_list(items: Any) -> list[str] | None:
    if not isinstance(items, list):
        return None
    labels = [str(item.get("label")) for item in items if isinstance(item, dict) and isinstance(item.get("label"), str)]
    return labels or None


def _seller_features_badges(items: Any) -> list[str] | None:
    return _plain_label_list(items)


def _equipment_payload(items: Any) -> list[dict[str, Any]] | None:
    if not isinstance(items, list):
        return None
    equipment = []
    for item in items:
        if not isinstance(item, dict):
            continue
        payload = _compact_dict(
            {
                "label": item.get("label"),
                "values": _plain_label_list(item.get("values")),
            }
        )
        if payload:
            equipment.append(payload)
    return equipment or None


def _details_payload(listing: dict[str, Any], record: dict[str, Any], page: dict[str, Any]) -> list[dict[str, Any]] | None:
    details = page.get("details")
    if not isinstance(details, list):
        return None
    advert_id = _advert_id(listing, record, page)
    payload = []
    for detail in details:
        if not isinstance(detail, dict):
            continue
        label = detail.get("label")
        value = _detail_value(detail, advert_id)
        if not isinstance(label, str) or label == "" or value in (None, ""):
            continue
        payload.append({"label": label, "value": value})
    return payload or None


def _advert_id(listing: dict[str, Any], record: dict[str, Any], page: dict[str, Any]) -> str | None:
    for candidate in (page.get("id"), listing.get("id"), (record.get("node") or {}).get("id")):
        if candidate not in (None, ""):
            return str(candidate)
    return None


def _detail_value(detail: dict[str, Any], advert_id: str | None) -> Any:
    detail_key = detail.get("key")
    value = detail.get("value")
    if detail_key not in {"registration", "vin", "date_registration"}:
        return value
    if not isinstance(value, str) or not advert_id:
        return None
    try:
        decrypted = decrypt_otomoto_secret(value, advert_id)
    except Exception:
        return None
    return decrypted.upper() if detail_key == "registration" else decrypted
