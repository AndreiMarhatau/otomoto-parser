from __future__ import annotations

from otomoto_parser.v2._service_analysis_payload import build_listing_payload, build_vehicle_report_payload
from otomoto_parser.v2._service_analysis_payload_support import _flatten_wrapper_values, _merge_wrapper_evidence, _should_skip_report_field
from otomoto_parser.v2._service_analysis_report_findings import _extract_important_findings, _finding_from_scalar
from otomoto_parser.v2._service_analysis_report_normalization import (
    _extract_provider_events,
    _extract_summary_items,
    _normalize_history_event,
)


def test_build_listing_payload_maps_new_search_and_listing_schema() -> None:
    payload = build_listing_payload(
        {"id": "6146171299", "url": "https://example.com/listing"},
        {
            "node": {
                "id": "6146171299",
                "title": "Node title",
                "shortDescription": "Raw short description",
                "url": "https://example.com/search-node",
                "cepikVerified": True,
                "price": {"amount": {"value": "43000", "currencyCode": "PLN"}},
                "priceEvaluation": {"indicator": "IN"},
            }
        },
        {
            "id": "6146171299",
            "price": {"labels": [{"label": "Gross"}, {"label": "VAT invoice"}]},
            "mainFeatures": ["First owner", "Service book"],
            "description": "Detailed listing page payload",
            "seller": {
                "type": "dealer",
                "featuresBadges": [{"label": "Company seller"}, {"label": "Top seller"}],
            },
            "equipment": [
                {
                    "label": "Comfort",
                    "values": [{"label": "Air conditioning"}, {"label": "Heated seats"}],
                }
            ],
            "isParts": False,
            "isUsedCar": True,
            "verifiedCar": {"status": "verified"},
            "verifiedCarFields": ["vin", "registration"],
            "details": [
                {"key": "make", "label": "Marka pojazdu", "value": "Mercedes-Benz"},
                {
                    "key": "vin",
                    "label": "VIN",
                    "value": "Wv3K9Zx1k7PjYIaJz62w+Pbg26TSroFd9HO9iVuhxOgs.1.ctzWCzFZf7YcoRbtqWY++A==",
                },
                {
                    "key": "registration",
                    "label": "Numer rejestracyjny",
                    "value": "O42JyEHx385vdx5SNhOZSIPPptMpvJWl.1.KRKEiQLPrCHWJtiYviYD7A==",
                },
                {
                    "key": "date_registration",
                    "label": "Data pierwszej rejestracji",
                    "value": "cH5qTiAf6w1chGVA+eFmkBKi8sphFIb+mzI=.1.oKkuw5QdwFdr/LuW8/+pXg==",
                },
            ],
        },
    )

    assert payload == {
        "search": {
            "price": {"value": "43000", "currencyCode": "PLN"},
            "title": "Node title",
            "shortDescription": "Raw short description",
            "url": "https://example.com/search-node",
            "cepikVerified": True,
            "priceEvaluation": {"indicator": "IN"},
        },
        "listing": {
            "priceLabels": ["Gross", "VAT invoice"],
            "mainFeatures": ["First owner", "Service book"],
            "description": "Detailed listing page payload",
            "seller": {"type": "dealer", "featuresBadges": ["Company seller", "Top seller"]},
            "equipment": [{"label": "Comfort", "values": ["Air conditioning", "Heated seats"]}],
            "isParts": False,
            "isUsedCar": True,
            "verifiedCar": {"status": "verified"},
            "verifiedCarFields": ["vin", "registration"],
            "details": [
                {"label": "Marka pojazdu", "value": "Mercedes-Benz"},
                {"label": "VIN", "value": "WDDSJ4EB2EN056917"},
                {"label": "Numer rejestracyjny", "value": "DLU8613F"},
                {"label": "Data pierwszej rejestracji", "value": "2014-01-01"},
            ],
        },
    }


def test_build_listing_payload_search_price_value_falls_back_to_units_then_price_value() -> None:
    units_payload = build_listing_payload(
        {"id": "6146171299"},
        {
            "node": {
                "price": {"amount": {"units": 43000, "currencyCode": "PLN"}},
            }
        },
        None,
    )
    price_value_payload = build_listing_payload(
        {"id": "6146171299"},
        {
            "node": {
                "price": {"value": "44000", "amount": {"currencyCode": "PLN"}},
            }
        },
        None,
    )

    assert units_payload == {
        "search": {
            "price": {"value": 43000, "currencyCode": "PLN"},
        }
    }
    assert price_value_payload == {
        "search": {
            "price": {"value": "44000", "currencyCode": "PLN"},
        }
    }


def test_build_listing_payload_omits_undecryptable_identifier_details() -> None:
    payload = build_listing_payload(
        {"id": "6146171299"},
        {"node": {"id": "6146171299"}},
        {
            "id": "6146171299",
            "details": [
                {"key": "registration", "label": "Numer rejestracyjny", "value": "not-encrypted"},
                {"key": "vin", "label": "VIN", "value": None},
                {"key": "mileage", "label": "Przebieg", "value": "120 000 km"},
            ],
        },
    )

    assert payload == {
        "listing": {
            "details": [
                {"label": "Przebieg", "value": "120 000 km"},
            ]
        },
    }


def test_build_vehicle_report_payload_keeps_full_report_and_summary_only() -> None:
    payload = build_vehicle_report_payload(
        {
            "identity": {"vin": "VIN"},
            "summary": {"autodnaAvailable": True},
            "report": {
                "technical_data": {"technicalData": {"basicData": {"make": "Mercedes-Benz"}}},
                "timeline_data": {"timelineData": {"events": [{"type": "registration"}]}},
            },
        }
    )

    assert payload == {
        "summary": {"autodnaAvailable": True},
        "report": {
            "technical_data": {"technicalData": {"basicData": {"make": "Mercedes-Benz"}}},
            "timeline_data": {"timelineData": {"events": [{"type": "registration"}]}},
        },
    }


def test_build_vehicle_report_payload_returns_none_for_invalid_payload() -> None:
    assert build_vehicle_report_payload(None) is None
    assert build_vehicle_report_payload({"identity": {"vin": "VIN"}}) is None


def test_report_normalization_internal_helpers_cover_non_event_and_recursive_paths() -> None:
    assert _extract_provider_events("bad", "autodna") == []
    assert _normalize_history_event(None, source="autodna") is None
    assert _normalize_history_event({"type": "ownership", "country": "US", "ownerCount": 2}, source="carfax") is None
    assert _normalize_history_event({"type": "sale", "label": "Auction listing", "country": "DE"}, source="autodna") is None
    assert _normalize_history_event({"type": "sale", "label": "Auction listing", "date": "2018-01-01", "country": "DE"}, source="autodna") == {
        "date": "2018-01-01",
        "type": "sale",
        "label": "Auction listing",
        "country": "DE",
        "source": "autodna",
    }

    assert _extract_provider_events(
        [
            {"type": "damage", "label": "Minor hit", "country": "DE"},
            {"records": [{"eventType": "inspection", "description": "Checked", "odometer": 0, "countryCode": "PL"}]},
            7,
        ],
        "autodna",
    ) == [
        {"type": "inspection", "label": "Checked", "mileage": 0, "country": "PL", "source": "autodna"},
    ]

    assert _extract_provider_events(
        {
            "history": [{"date": "2020-01-01", "description": "Loose provider label"}],
            "records": [{"mileage": 120000, "label": "Another loose provider label"}],
            "damage": [{"date": "2021-02-02", "description": "Derived from container"}],
        },
        "carfax",
    ) == [
        {"date": "2021-02-02", "type": "damage", "label": "Derived from container", "source": "carfax"},
    ]

    assert _extract_provider_events(
        {
            "records": {"date": "2022-01-01", "damage": True, "country": "US"},
        },
        "carfax",
    ) == [
        {"date": "2022-01-01", "type": "damage", "country": "US", "source": "carfax", "details": ["Damage: True"]},
    ]
    assert _extract_provider_events(
        {
            "records": {"date": "2022-01-01", "damage": False, "country": "US"},
        },
        "carfax",
    ) == []
    assert _extract_provider_events(
        {
            "damage": {"date": "2022-01-01", "status": "severe", "country": "US"},
        },
        "carfax",
    ) == [
        {"date": "2022-01-01", "type": "damage", "country": "US", "source": "carfax", "details": ["Status: severe"]},
    ]
    assert _extract_provider_events(
        {
            "summary": {
                "records": [{"type": "damage", "date": "2022-08-08", "country": "DE", "description": "Auction damage"}],
            },
        },
        "autodna",
    ) == [
        {"date": "2022-08-08", "type": "damage", "label": "Auction damage", "country": "DE", "source": "autodna"},
    ]
    assert _extract_provider_events(
        {"type": "damage", "description": "Minor damage", "date": "2020-01-01", "country": "US"},
        "carfax",
    ) == [
        {"date": "2020-01-01", "type": "damage", "label": "Minor damage", "country": "US", "source": "carfax"},
    ]
    assert _extract_provider_events(
        {"date": "2022-01-01", "country": "US", "damage": True},
        "carfax",
    ) == [
        {"date": "2022-01-01", "type": "damage", "country": "US", "source": "carfax", "details": ["Damage: True"]},
    ]


def test_report_normalization_internal_helpers_cover_summary_and_finding_branches() -> None:
    assert _extract_summary_items(7, "autodna") == []
    assert _extract_summary_items("ok", "autodna") == []
    assert _extract_summary_items(
        {
            "updated_at": "2026-03-25",
            "wrapper": {"damage": "Severe damage", "items": ["bad", {"theft": "Stolen record"}]},
        },
        "autodna",
    ) == [
        {"source": "autodna", "label": "Damage", "category": "damage", "value": "Severe damage"},
        {"source": "autodna", "label": "Items", "value": "bad"},
        {"source": "autodna", "label": "Theft", "category": "theft", "value": "Stolen record"},
    ]
    assert _extract_summary_items(
        {
            "damage": {"date": "2022-01-01", "country": "US", "mileage": 123456, "status": "severe"},
        },
        "carfax",
    ) == []

    assert _extract_important_findings("bad", "carfax") == []
    assert _extract_important_findings(
        {
            "updated_at": "2026-03-25",
            "checks": [
                {"odometerRollback": True, "odometerReading": 0, "countryCode": "US", "eventDate": "2020-01-01"},
                {"type": "skip", "label": "ignore"},
            ],
        },
        "carfax",
    ) == [
        {"source": "carfax", "label": "Odometerrollback", "category": "mileage", "value": True, "date": "2020-01-01", "mileage": 0, "country": "US"},
    ]
    assert _extract_important_findings(
        {
            "records": [
                {"type": "damage", "description": "Minor damage"},
            ]
        },
        "carfax",
    ) == [
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "Minor damage"},
    ]
    assert _extract_important_findings(
        {
            "records": [
                {"type": "damage", "description": "Minor damage", "date": "2022-07-07", "country": "US"},
            ]
        },
        "carfax",
    ) == [
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "Minor damage", "date": "2022-07-07", "country": "US"},
    ]
    assert _extract_important_findings(
        {
            "damage": {
                "date": "2021-05-05",
                "mileage": 123456,
                "country": "US",
                "records": [{"type": "damage", "description": "Minor damage"}],
            }
        },
        "carfax",
    ) == [
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "Minor damage", "date": "2021-05-05", "mileage": 123456, "country": "US"},
    ]
    assert _finding_from_scalar("carfax", ("date",), "2020-01-01", {}) is None
    assert _finding_from_scalar("carfax", ("damage",), "unknown", {}) is None


def test_report_payload_support_helpers_cover_wrapper_merging_and_status_filtering() -> None:
    assert _should_skip_report_field("updated_at", "2026-03-25") is True
    assert _should_skip_report_field("status", "success") is True
    assert _should_skip_report_field("status", "salvage") is False
    assert _should_skip_report_field("status", {"code": "ok"}, path=("title",)) is True
    assert _should_skip_report_field("status", "salvage", path=("title",)) is False
    assert _should_skip_report_field("status", "ok", path=("wrapper",)) is True
    assert _should_skip_report_field("damage", "severe") is False

    assert _flatten_wrapper_values([]) is None
    assert _flatten_wrapper_values([["Accident found"], ["Import record"]]) == ["Accident found", "Import record"]
    assert _flatten_wrapper_values([["Accident found"], "single"]) == [["Accident found"], "single"]

    merged: dict[str, object] = {"entries": 2}
    _merge_wrapper_evidence(merged, {"damage": "severe"})
    _merge_wrapper_evidence(merged, {"damage": "confirmed"})
    _merge_wrapper_evidence(merged, {"damage": ["auction note"]})
    _merge_wrapper_evidence(merged, {"damage": {"severity": "structural", "country": "US"}})
    _merge_wrapper_evidence(merged, {"damage": {"value": "verified", "source": "wrapper"}})
    _merge_wrapper_evidence(merged, {"damage": "ignored", "theft": "present"})
    _merge_wrapper_evidence(merged, {"Damage": ["auction note"]})
    _merge_wrapper_evidence(merged, {"messages": ["Accident found"]})
    _merge_wrapper_evidence(merged, {"messages": ["Import record"]})
    _merge_wrapper_evidence(merged, ["Accident found", "Import record"])
    _merge_wrapper_evidence(merged, "One more message")
    _merge_wrapper_evidence(merged, [True])
    _merge_wrapper_evidence(merged, False)
    assert merged == {
        "entries": 2,
        "damage": {"value": "severe", "messages": ["confirmed", "auction note", "verified", "ignored", "auction note"], "severity": "structural", "country": "US", "source": "wrapper"},
        "theft": "present",
        "messages": ["Accident found", "Import record", "Accident found", "Import record", "One more message"],
        "items": [True, False],
    }
