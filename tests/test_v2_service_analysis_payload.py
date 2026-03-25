from __future__ import annotations

from otomoto_parser.v2._service_analysis_payload import build_listing_payload, build_vehicle_report_payload


def test_build_listing_payload_prefers_listing_values_and_compacts_fields() -> None:
    payload = build_listing_payload(
        {"id": "4", "url": "https://example.com/listing", "title": "Trusted title", "location": "Trusted location"},
        {
            "node": {
                "title": "Node title",
                "createdAt": "2026-03-12T13:08:23Z",
                "cepikVerified": True,
                "shortDescription": "  compact   me  ",
                "parameters": [
                    {"key": "make", "displayValue": "Mercedes-Benz"},
                    {"key": "model", "displayValue": "CLA"},
                    {"key": "version", "displayValue": "200"},
                    {"key": "vin", "displayValue": "SEARCH-VIN"},
                ],
                "price": {"amount": {"units": 43000, "currencyCode": "PLN"}},
                "priceEvaluation": {"indicator": "IN"},
                "sellerLink": {"id": "dealer-1", "name": "Dealer", "websiteUrl": "https://dealer.example"},
                "valueAddedServices": [{"name": " ASO "}, {"name": ""}, {"wrong": "skip"}],
            }
        },
        {
            "title": "Page title",
            "location": {"city": {"name": "Warsaw"}, "region": {"name": "Mazowieckie"}},
            "description": "Detailed description",
            "sellerLink": "https://seller.example",
            "parameters": [
                {"key": "version", "displayValue": "250"},
                {"key": "drive", "displayValue": "4x4"},
            ],
            "parametersDict": {
                "color": {"displayValue": "White"},
                "vin": {"values": [{"value": "ENCRYPTED-VIN"}]},
            },
        },
    )

    assert payload == {
        "id": "4",
        "url": "https://example.com/listing",
        "title": "Trusted title",
        "location": "Trusted location",
        "createdAt": "2026-03-12T13:08:23Z",
        "price": {"amount": 43000, "currency": "PLN", "evaluation": "IN"},
        "seller": {"id": "dealer-1", "name": "Dealer", "websiteUrl": "https://dealer.example"},
        "dataVerified": True,
        "shortDescription": "compact me",
        "description": "Detailed description",
        "identifiers": {"vin": "SEARCH-VIN"},
        "parameters": {
            "make": "Mercedes-Benz",
            "model": "CLA",
            "version": "250",
            "drive": "4x4",
            "color": "White",
        },
        "badges": ["ASO"],
    }


def test_build_listing_payload_uses_detail_identifier_only_when_not_encrypted_listing_data() -> None:
    payload = build_listing_payload(
        {"id": "4", "url": "https://example.com/listing"},
        {"node": {"parameters": []}},
        {
            "parameters": [
                {"key": "registration", "displayValue": "DLU8613F"},
                {"key": "date_registration", "displayValue": "2014-01-01"},
            ],
            "parametersDict": {
                "registration": {"values": [{"value": "encrypted-reg"}]},
                "date_registration": {"values": [{"value": "encrypted-date"}]},
            },
        },
    )

    assert payload["identifiers"] == {
        "registrationNumber": "DLU8613F",
        "firstRegistrationDate": "2014-01-01",
    }


def test_build_listing_payload_truncates_long_description_and_ignores_invalid_timeline_source() -> None:
    payload = build_listing_payload(
        {"id": "4"},
        {"node": {"shortDescription": "abcd", "valueAddedServices": "bad"}},
        {"description": "x" * 3010, "parametersDict": {"model": {"values": ["bad", {"label": "CLA"}]}}},
    )

    assert payload["shortDescription"] == "abcd"
    assert payload["description"] == ("x" * 2997) + "..."
    assert payload["parameters"] == {"model": "CLA"}
    assert "badges" not in payload


def test_build_vehicle_report_payload_compacts_report_and_limits_timeline() -> None:
    events = [{"type": "registration", "date": "2014-01-01", "label": "first"}] * 9
    events[1] = {"type": "inspection", "mileage": 120000, "country": "PL", "source": "cepik"}
    events[2] = {"type": "sale", "label": "auction"}
    payload = build_vehicle_report_payload(
        {
            "identity": {"vin": "VIN"},
            "summary": {"autodnaAvailable": True},
            "report": {
                "api_version": "1.0.20",
                "technical_data": {
                    "technicalData": {
                        "basicData": {"make": "Mercedes-Benz", "color": "White"},
                        "ownershipHistory": {"numberOfOwners": 2},
                    }
                },
                "timeline_data": {"timelineData": {"events": events + ["skip"]}},
                "autodna_data": {"summary": {"events": 3}},
                "carfax_data": {"summary": {"entries": 1}},
            },
        }
    )

    assert payload == {
        "identity": {"vin": "VIN"},
        "summary": {"autodnaAvailable": True},
        "sourceStatus": {"apiVersion": "1.0.20", "autodnaAvailable": True},
        "technicalData": {
            "basicData": {"make": "Mercedes-Benz", "color": "White"},
            "ownershipHistory": {"numberOfOwners": 2},
        },
        "timeline": {
            "eventCount": 10,
            "eventTypes": ["registration", "inspection", "sale"],
            "events": events[:3] + events[3:8],
        },
        "autodnaSummary": {"events": 3},
        "carfaxSummary": {"entries": 1},
    }


def test_build_vehicle_report_payload_returns_none_for_invalid_payload() -> None:
    assert build_vehicle_report_payload(None) is None
    assert build_vehicle_report_payload({"report": {"timeline_data": {"timelineData": {"events": "bad"}}}}) == {}
