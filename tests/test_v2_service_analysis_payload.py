from __future__ import annotations

from otomoto_parser.v2._service_analysis_payload import build_listing_payload, build_vehicle_report_payload
from otomoto_parser.v2._service_analysis_payload_support import _flatten_wrapper_values, _merge_wrapper_evidence, _should_skip_report_field
from otomoto_parser.v2._service_analysis_report_findings import _extract_important_findings, _finding_from_scalar
from otomoto_parser.v2._service_analysis_report_normalization import (
    _extract_provider_events,
    _extract_summary_items,
    _normalize_history_event,
)


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
        "title": "Trusted title",
        "url": "https://example.com/listing",
        "location": "Trusted location",
        "createdAt": "2026-03-12T13:08:23Z",
        "price": {"amount": 43000, "currency": "PLN", "marketPriceAssessment": "IN"},
        "seller": {"name": "Dealer", "websiteUrl": "https://dealer.example"},
        "listingContent": {
            "dataVerified": True,
            "badges": ["ASO"],
            "shortDescription": "compact me",
            "description": "Detailed description",
        },
        "vehicle": {
            "identifiers": {"vin": "SEARCH-VIN"},
            "make": "Mercedes-Benz",
            "model": "CLA",
            "version": "250",
            "drive": "4x4",
            "color": "White",
        },
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

    assert payload["vehicle"]["identifiers"] == {
        "registrationNumber": "DLU8613F",
        "firstRegistrationDate": "2014-01-01",
    }


def test_build_listing_payload_truncates_long_description_and_ignores_invalid_timeline_source() -> None:
    payload = build_listing_payload(
        {"id": "4"},
        {"node": {"shortDescription": "abcd", "valueAddedServices": "bad"}},
        {"description": "x" * 3010, "parametersDict": {"model": {"values": ["bad", {"label": "CLA"}]}}},
    )

    assert payload["listingContent"]["shortDescription"] == "abcd"
    assert payload["listingContent"]["description"] == ("x" * 2997) + "..."
    assert payload["vehicle"] == {"model": "CLA"}
    assert "badges" not in payload["listingContent"]


def test_build_listing_payload_collapses_origin_fields_to_single_canonical_key() -> None:
    payload = build_listing_payload(
        {"id": "4"},
        {"node": {"parameters": [{"key": "country_origin", "displayValue": "Poland"}]}},
        {"parameters": [{"key": "origin_country", "displayValue": "Germany"}]},
    )

    assert payload["vehicle"]["countryOfOrigin"] == "Germany"
    assert "originCountry" not in payload["vehicle"]


def test_build_listing_payload_keeps_country_origin_when_origin_country_is_absent() -> None:
    payload = build_listing_payload(
        {"id": "4"},
        {"node": {"parameters": [{"key": "country_origin", "displayValue": "Poland"}]}},
        {"parameters": [{"key": "origin_country", "displayValue": ""}]},
    )

    assert payload["vehicle"]["countryOfOrigin"] == "Poland"
    assert "originCountry" not in payload["vehicle"]


def test_build_listing_payload_keeps_country_origin_from_parameters_dict_when_origin_country_is_absent() -> None:
    payload = build_listing_payload(
        {"id": "4"},
        {"node": {"parameters": []}},
        {"parametersDict": {"country_origin": {"displayValue": "Poland"}, "origin_country": {"displayValue": ""}}},
    )

    assert payload["vehicle"]["countryOfOrigin"] == "Poland"
    assert "originCountry" not in payload["vehicle"]


def test_build_vehicle_report_payload_normalizes_report_evidence_without_dropping_unique_facts() -> None:
    events = [{"type": "registration", "date": "2014-01-01", "label": "first"}] * 9
    events[1] = {"type": "inspection", "mileage": 120000, "country": "PL", "source": "cepik"}
    events[2] = {"type": "sale", "label": "auction"}
    payload = build_vehicle_report_payload(
        {
            "identity": {"vin": "VIN", "registrationNumber": "DLU8613F", "firstRegistrationDate": "2014-01-01"},
            "summary": {"autodnaAvailable": True},
            "report": {
                "vin_number": "VIN",
                "registration_number": "DLU8613F",
                "first_registration_date": "2014-01-01",
                "api_version": "1.0.20",
                "technical_data": {
                    "technicalData": {
                        "basicData": {"make": "Mercedes-Benz", "color": "White"},
                        "ownershipHistory": {"numberOfOwners": 2},
                    }
                },
                "timeline_data": {"timelineData": {"events": events + ["skip"]}},
                "autodna_data": {
                    "summary": {
                        "events": 3,
                        "damage": "Minor rear damage reported",
                    },
                    "history": [
                        {"type": "damage", "date": "2018-03-01", "country": "DE", "source": "AutoDNA", "description": "Rear bumper repair"},
                    ],
                },
                "carfax_data": {
                    "summary": {"entries": 1},
                    "title": {"salvage": False, "rebuilt": True},
                    "ownership": {"ownerCount": 2},
                    "checks": [{"odometerRollback": True, "date": "2020-01-01", "mileage": 180000, "country": "US"}],
                },
            },
        }
    )

    assert payload == {
        "identity": {"vin": "VIN", "registrationNumber": "DLU8613F", "firstRegistrationDate": "2014-01-01"},
        "trustedIdentifiers": {
            "vin": "VIN",
            "registrationNumber": "DLU8613F",
            "firstRegistrationDate": "2014-01-01",
            "apiVersion": "1.0.20",
        },
        "summary": {"autodnaAvailable": True},
        "sourceStatus": {"apiVersion": "1.0.20", "autodnaAvailable": True},
        "technicalData": {
            "basicData": {"make": "Mercedes-Benz", "color": "White"},
            "ownershipHistory": {"numberOfOwners": 2},
        },
        "historyEvents": [
            {"date": "2014-01-01", "type": "registration", "label": "first", "source": "timeline"},
            {"type": "inspection", "mileage": 120000, "country": "PL", "source": "cepik"},
            {"date": "2018-03-01", "type": "damage", "label": "Rear bumper repair", "country": "DE", "source": "AutoDNA"},
        ],
        "timeline": {
            "eventCount": 9,
            "eventTypes": ["registration", "inspection", "sale"],
            "events": [
                {"date": "2014-01-01", "type": "registration", "label": "first"},
                {"type": "inspection", "mileage": 120000, "country": "PL", "source": "cepik"},
                {"type": "sale", "label": "auction"},
                {"date": "2014-01-01", "type": "registration", "label": "first"},
                {"date": "2014-01-01", "type": "registration", "label": "first"},
                {"date": "2014-01-01", "type": "registration", "label": "first"},
                {"date": "2014-01-01", "type": "registration", "label": "first"},
                {"date": "2014-01-01", "type": "registration", "label": "first"},
            ],
        },
        "autodnaSummary": {"events": 3, "damage": "Minor rear damage reported"},
        "carfaxSummary": {"entries": 1},
        "reportSummaries": [
            {"source": "autodna", "label": "Events", "value": 3},
            {"source": "autodna", "label": "Damage", "category": "damage", "value": "Minor rear damage reported"},
            {"source": "carfax", "label": "Entries", "value": 1},
        ],
        "importantFindings": [
            {"source": "autodna", "label": "Damage", "category": "damage", "value": "Minor rear damage reported"},
            {"source": "autodna", "label": "Damage", "category": "damage", "value": "Rear bumper repair", "date": "2018-03-01", "country": "DE"},
            {"source": "carfax", "label": "Salvage", "category": "title", "value": False},
            {"source": "carfax", "label": "Rebuilt", "category": "title", "value": True},
            {"source": "carfax", "label": "Ownercount", "category": "ownership", "value": 2},
            {"source": "carfax", "label": "Odometerrollback", "category": "mileage", "value": True, "date": "2020-01-01", "mileage": 180000, "country": "US"},
        ],
    }


def test_build_vehicle_report_payload_keeps_raw_timeline_contract_with_provider_history() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "timeline_data": {
                    "timelineData": {
                        "events": [
                            {"type": "registration", "date": "2014-01-01", "label": "first"},
                            {"type": "inspection", "date": "2015-01-01", "label": "check"},
                        ]
                    }
                },
                "autodna_data": {
                    "history": [
                        {"type": "damage", "date": "2018-03-01", "country": "DE", "source": "AutoDNA", "description": "Rear bumper repair"},
                    ]
                },
            }
        }
    )

    assert payload["historyEvents"] == [
        {"date": "2014-01-01", "type": "registration", "label": "first", "source": "timeline"},
        {"date": "2015-01-01", "type": "inspection", "label": "check", "source": "timeline"},
        {"date": "2018-03-01", "type": "damage", "label": "Rear bumper repair", "country": "DE", "source": "AutoDNA"},
    ]
    assert payload["timeline"] == {
        "eventCount": 2,
        "eventTypes": ["registration", "inspection"],
        "events": [
            {"date": "2014-01-01", "type": "registration", "label": "first"},
            {"date": "2015-01-01", "type": "inspection", "label": "check"},
        ],
    }
    assert payload["timeline"]["eventCount"] < len(payload["historyEvents"])
    assert "damage" not in payload["timeline"]["eventTypes"]
    assert payload["importantFindings"] == [
        {"source": "autodna", "label": "Damage", "category": "damage", "value": "Rear bumper repair", "date": "2018-03-01", "country": "DE"},
    ]


def test_build_vehicle_report_payload_returns_none_for_invalid_payload() -> None:
    assert build_vehicle_report_payload(None) is None
    assert build_vehicle_report_payload({"report": {"timeline_data": {"timelineData": {"events": "bad"}}}}) == {}


def test_build_vehicle_report_payload_deduplicates_repeated_provider_facts_and_skips_raw_noise() -> None:
    payload = build_vehicle_report_payload(
        {
            "identity": {"vin": "VIN"},
            "report": {
                "vin_number": "VIN",
                "autodna_data": {
                    "summary": {"theft": "Theft record found"},
                    "raw": "x" * 1000,
                    "records": [
                        {"type": "theft", "date": "2017-02-02", "country": "PL", "source": "AutoDNA", "description": "Theft record found"},
                        {"type": "theft", "date": "2017-02-02", "country": "PL", "source": "AutoDNA", "description": "Theft record found"},
                    ],
                },
                "carfax_data": {
                    "summary": {"theft": "Theft record found"},
                    "metadata": {"cached_at": "2026-03-25T00:00:00Z"},
                },
            },
        }
    )

    assert payload == {
        "identity": {"vin": "VIN"},
        "trustedIdentifiers": {"vin": "VIN"},
        "historyEvents": [
            {"date": "2017-02-02", "type": "theft", "label": "Theft record found", "country": "PL", "source": "AutoDNA"},
        ],
        "timeline": {
            "eventCount": 1,
            "eventTypes": ["theft"],
            "events": [{"date": "2017-02-02", "type": "theft", "label": "Theft record found", "country": "PL", "source": "AutoDNA"}],
        },
        "autodnaSummary": {"theft": "Theft record found"},
        "carfaxSummary": {"theft": "Theft record found"},
        "reportSummaries": [
            {"source": "autodna", "label": "Theft", "category": "theft", "value": "Theft record found"},
            {"source": "carfax", "label": "Theft", "category": "theft", "value": "Theft record found"},
        ],
        "importantFindings": [
            {"source": "autodna", "label": "Theft", "category": "theft", "value": "Theft record found"},
            {"source": "autodna", "label": "Theft", "category": "theft", "value": "Theft record found", "date": "2017-02-02", "country": "PL"},
            {"source": "carfax", "label": "Theft", "category": "theft", "value": "Theft record found"},
        ],
    }


def test_build_vehicle_report_payload_filters_underscored_metadata_from_findings() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "autodna_data": {
                    "summary": {"damage": "Front-end damage found"},
                    "records": [
                        {
                            "updated_at": "2026-03-25T00:00:00Z",
                            "request_id": "abc-123",
                            "api_version": "1.0.20",
                            "damage_status": "Severe structural damage",
                        }
                    ],
                }
            }
        }
    )

    assert payload["reportSummaries"] == [
        {"source": "autodna", "label": "Damage", "category": "damage", "value": "Front-end damage found"},
    ]
    assert payload["importantFindings"] == [
        {"source": "autodna", "label": "Damage", "category": "damage", "value": "Front-end damage found"},
        {"source": "autodna", "label": "Damagestatus", "category": "damage", "value": "Severe structural damage"},
    ]
    serialized = str(payload)
    assert "updated_at" not in serialized
    assert "request_id" not in serialized
    assert "api_version" not in serialized


def test_build_vehicle_report_payload_caps_provider_only_timeline_events() -> None:
    provider_events = [
        {"type": "damage", "date": f"2018-03-{index + 1:02d}", "country": "DE", "source": "AutoDNA", "description": f"Event {index + 1}"}
        for index in range(12)
    ]
    payload = build_vehicle_report_payload(
        {
            "report": {
                "autodna_data": {
                    "history": provider_events,
                }
            }
        }
    )

    assert payload["historyEvents"] == [
        {"date": f"2018-03-{index + 1:02d}", "type": "damage", "label": f"Event {index + 1}", "country": "DE", "source": "AutoDNA"}
        for index in range(12)
    ]
    assert payload["timeline"] == {
        "eventCount": 12,
        "eventTypes": ["damage"],
        "events": [
            {"date": f"2018-03-{index + 1:02d}", "type": "damage", "label": f"Event {index + 1}", "country": "DE", "source": "AutoDNA"}
            for index in range(8)
        ],
    }


def test_build_vehicle_report_payload_does_not_promote_non_event_provider_facts_to_history_events() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "carfax_data": {
                    "ownership": {
                        "country": "US",
                        "ownerCount": 2,
                    }
                }
            }
        }
    )

    assert "historyEvents" not in payload
    assert "timeline" not in payload
    assert payload["importantFindings"] == [
        {"source": "carfax", "label": "Ownercount", "category": "ownership", "value": 2, "country": "US"},
    ]


def test_build_vehicle_report_payload_does_not_promote_date_or_mileage_only_provider_facts_to_history_events() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "carfax_data": {
                    "ownership": {
                        "lastTransfer": {"date": "2020-01-01", "ownerCount": 3},
                        "odometerFact": {"mileage": 0, "ownerCount": 3},
                    }
                }
            }
        }
    )

    assert "historyEvents" not in payload
    assert "timeline" not in payload
    assert payload["importantFindings"] == [
        {"source": "carfax", "label": "Ownercount", "category": "ownership", "value": 3, "date": "2020-01-01"},
        {"source": "carfax", "label": "Ownercount", "category": "mileage", "value": 3, "mileage": 0},
    ]


def test_build_vehicle_report_payload_preserves_zero_mileage_event_evidence() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "autodna_data": {
                    "history": [
                        {"type": "inspection", "date": "2014-01-01", "mileage": 0, "country": "PL", "source": "AutoDNA", "description": "Factory delivery"},
                    ]
                }
            }
        }
    )

    assert payload["historyEvents"] == [
        {"date": "2014-01-01", "type": "inspection", "label": "Factory delivery", "mileage": 0, "country": "PL", "source": "AutoDNA"},
    ]
    assert payload["timeline"] == {
        "eventCount": 1,
        "eventTypes": ["inspection"],
        "events": [
            {"date": "2014-01-01", "type": "inspection", "label": "Factory delivery", "mileage": 0, "country": "PL", "source": "AutoDNA"},
        ],
    }


def test_build_vehicle_report_payload_preserves_undated_typed_provider_records_as_findings() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "carfax_data": {
                    "records": [
                        {"type": "damage", "description": "Minor damage"},
                    ]
                }
            }
        }
    )

    assert "historyEvents" not in payload
    assert "timeline" not in payload
    assert payload["importantFindings"] == [
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "Minor damage"},
    ]


def test_build_vehicle_report_payload_typed_provider_findings_inherit_parent_context() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "carfax_data": {
                    "damage": {
                        "date": "2021-05-05",
                        "mileage": 123456,
                        "country": "US",
                        "records": [
                            {"type": "damage", "description": "Minor damage"},
                        ],
                    }
                }
            }
        }
    )

    assert payload["importantFindings"] == [
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "Minor damage", "date": "2021-05-05", "mileage": 123456, "country": "US"},
    ]


def test_build_vehicle_report_payload_sanitizes_wrapper_heavy_provider_summaries() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "autodna_data": {
                    "summary": {
                        "updated_at": "2026-03-25T00:00:00Z",
                        "request_id": "abc-123",
                        "wrapper": {
                            "events": 3,
                            "damage": "Front-end damage found",
                            "items": [
                                {"theft": "Recovered theft record"},
                                {"metadata": {"api_version": "1.0.20"}},
                            ],
                        },
                    }
                }
            }
        }
    )

    assert payload["autodnaSummary"] == {
        "events": 3,
        "damage": "Front-end damage found",
        "items": [{"theft": "Recovered theft record"}],
    }
    serialized = str(payload["autodnaSummary"])
    assert "updated_at" not in serialized
    assert "request_id" not in serialized
    assert "api_version" not in serialized


def test_build_vehicle_report_payload_important_findings_use_child_context_over_parent() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "carfax_data": {
                    "ownership": {
                        "date": "2020-01-01",
                        "country": "US",
                        "events": [
                            {"ownerCount": 2},
                            {"ownerCount": 3, "date": "2021-01-01", "country": "DE"},
                        ],
                    }
                }
            }
        }
    )

    assert payload["importantFindings"] == [
        {"source": "carfax", "label": "Ownercount", "category": "ownership", "value": 2, "date": "2020-01-01", "country": "US"},
        {"source": "carfax", "label": "Ownercount", "category": "ownership", "value": 3, "date": "2021-01-01", "country": "DE"},
    ]


def test_build_vehicle_report_payload_derives_event_type_from_path_for_anchored_facts() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "carfax_data": {
                    "incidents": {
                        "accident": {
                            "date": "2022-04-04",
                            "country": "US",
                            "accident": True,
                        }
                    }
                }
            }
        }
    )

    assert payload["historyEvents"] == [
        {"date": "2022-04-04", "type": "accident", "country": "US", "source": "carfax", "details": ["Accident: True"]},
    ]
    assert payload["timeline"] == {
        "eventCount": 1,
        "eventTypes": ["accident"],
        "events": [{"date": "2022-04-04", "type": "accident", "country": "US", "source": "carfax"}],
    }


def test_build_vehicle_report_payload_promotes_dated_status_containers_to_events() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "carfax_data": {
                    "damage": {
                        "date": "2022-06-06",
                        "country": "US",
                        "status": "severe",
                    }
                }
            }
        }
    )

    assert payload["historyEvents"] == [
        {"date": "2022-06-06", "type": "damage", "country": "US", "source": "carfax", "details": ["Status: severe"]},
    ]
    assert payload["timeline"] == {
        "eventCount": 1,
        "eventTypes": ["damage"],
        "events": [{"date": "2022-06-06", "type": "damage", "country": "US", "source": "carfax"}],
    }
    assert payload["importantFindings"] == [
        {"source": "carfax", "label": "Status", "category": "damage", "value": "severe", "date": "2022-06-06", "country": "US"},
    ]


def test_build_vehicle_report_payload_promotes_root_anchored_fact_records_to_events() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "carfax_data": {
                    "date": "2022-01-01",
                    "country": "US",
                    "damage": True,
                }
            }
        }
    )

    assert payload["historyEvents"] == [
        {"date": "2022-01-01", "type": "damage", "country": "US", "source": "carfax", "details": ["Damage: True"]},
    ]
    assert payload["timeline"] == {
        "eventCount": 1,
        "eventTypes": ["damage"],
        "events": [{"date": "2022-01-01", "type": "damage", "country": "US", "source": "carfax"}],
    }
    assert payload["importantFindings"] == [
        {"source": "carfax", "label": "Damage", "category": "damage", "value": True, "date": "2022-01-01", "country": "US"},
    ]


def test_build_vehicle_report_payload_preserves_status_for_explicit_typed_records() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "carfax_data": {
                    "records": [
                        {"type": "damage", "date": "2022-07-07", "country": "US", "status": "severe"},
                    ]
                }
            }
        }
    )

    assert payload["historyEvents"] == [
        {"date": "2022-07-07", "type": "damage", "country": "US", "source": "carfax", "details": ["Status: severe"]},
    ]
    assert payload["timeline"] == {
        "eventCount": 1,
        "eventTypes": ["damage"],
        "events": [{"date": "2022-07-07", "type": "damage", "country": "US", "source": "carfax"}],
    }
    assert payload["importantFindings"] == [
        {"source": "carfax", "label": "Status", "category": "damage", "value": "severe", "date": "2022-07-07", "country": "US"},
    ]


def test_build_vehicle_report_payload_extracts_summary_nested_provider_events() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "autodna_data": {
                    "summary": {
                        "records": [
                            {"type": "damage", "date": "2022-08-08", "country": "DE", "description": "Auction damage"},
                        ]
                    }
                }
            }
        }
    )

    assert payload["historyEvents"] == [
        {"date": "2022-08-08", "type": "damage", "label": "Auction damage", "country": "DE", "source": "autodna"},
    ]
    assert payload["timeline"] == {
        "eventCount": 1,
        "eventTypes": ["damage"],
        "events": [{"date": "2022-08-08", "type": "damage", "label": "Auction damage", "country": "DE", "source": "autodna"}],
    }
    assert payload["importantFindings"] == [
        {"source": "autodna", "label": "Damage", "category": "damage", "value": "Auction damage", "date": "2022-08-08", "country": "DE"},
    ]
    assert "reportSummaries" not in payload


def test_build_vehicle_report_payload_dedupes_provider_events_ignoring_source_casing() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "autodna_data": {
                    "summary": {
                        "records": [
                            {"type": "damage", "date": "2022-08-08", "country": "DE", "source": "AutoDNA", "description": "Auction damage"},
                        ]
                    },
                    "history": [
                        {"type": "damage", "date": "2022-08-08", "country": "DE", "source": "autodna", "description": "Auction damage"},
                    ],
                }
            }
        }
    )

    assert payload["historyEvents"] == [
        {"date": "2022-08-08", "type": "damage", "label": "Auction damage", "country": "DE", "source": "AutoDNA"},
    ]


def test_build_vehicle_report_payload_omits_top_level_wrapper_only_scalar_summary_items() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "carfax_data": {
                    "summary": {
                        "wrapper": {
                            "data": "Single summary line",
                        }
                    }
                }
            }
        }
    )

    assert payload["carfaxSummary"] == "Single summary line"
    assert "reportSummaries" not in payload


def test_build_vehicle_report_payload_skips_context_only_summary_fields() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "carfax_data": {
                    "summary": {
                        "damage": {
                            "date": "2022-01-01",
                            "country": "US",
                            "mileage": 123456,
                            "status": "severe",
                        }
                    }
                }
            }
        }
    )

    assert "reportSummaries" not in payload


def test_build_vehicle_report_payload_filters_negative_anchored_flags_from_events_and_findings() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "carfax_data": {
                    "incidents": {
                        "accident": {
                            "date": "2022-04-04",
                            "country": "US",
                            "accident": False,
                        }
                    }
                }
            }
        }
    )

    assert "historyEvents" not in payload
    assert "timeline" not in payload
    assert "importantFindings" not in payload


def test_build_vehicle_report_payload_keeps_wrapper_contained_summary_scalars_and_lists() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "carfax_data": {
                    "summary": {
                        "wrapper": {
                            "entries": 2,
                            "messages": ["Accident found", "Import record"],
                        }
                    }
                }
            }
        }
    )

    assert payload["carfaxSummary"] == {
        "entries": 2,
        "messages": ["Accident found", "Import record"],
    }


def test_build_vehicle_report_payload_flattens_wrapper_only_summary_scalars_and_lists() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "autodna_data": {
                    "summary": {
                        "response": ["Accident found", "Import record"],
                    }
                },
                "carfax_data": {
                    "summary": {
                        "wrapper": {
                            "data": "Single summary line",
                        }
                    }
                },
            }
        }
    )

    assert payload["autodnaSummary"] == ["Accident found", "Import record"]
    assert payload["carfaxSummary"] == "Single summary line"


def test_build_vehicle_report_payload_preserves_wrapper_messages_alongside_sibling_summary_keys() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "carfax_data": {
                    "summary": {
                        "entries": 2,
                        "wrapper": {
                            "data": ["Accident found", "Import record"],
                        },
                    }
                }
            }
        }
    )

    assert payload["carfaxSummary"] == {
        "entries": 2,
        "messages": ["Accident found", "Import record"],
    }


def test_build_vehicle_report_payload_merges_wrapper_only_nested_facts_into_sibling_summary_containers() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "carfax_data": {
                    "summary": {
                        "title": {"rebuilt": True},
                        "wrapper": {
                            "title": {"salvage": True},
                        },
                    }
                }
            }
        }
    )

    assert payload["carfaxSummary"] == {
        "title": {"rebuilt": True, "salvage": True},
    }
    assert payload["reportSummaries"] == [
        {"source": "carfax", "label": "Rebuilt", "category": "title", "value": True},
        {"source": "carfax", "label": "Salvage", "category": "title", "value": True},
    ]
    assert payload["importantFindings"] == [
        {"source": "carfax", "label": "Rebuilt", "category": "title", "value": True},
        {"source": "carfax", "label": "Salvage", "category": "title", "value": True},
    ]


def test_build_vehicle_report_payload_preserves_meaningful_nested_status_evidence() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "carfax_data": {
                    "status": "success",
                    "response": {"status": "ok"},
                    "summary": {
                        "status": "ready",
                        "title": {"status": "salvage"},
                        "damage": {"status": "severe"},
                    },
                    "title": {"status": "salvage"},
                    "damage": {"status": "severe"},
                }
            }
        }
    )

    assert payload["carfaxSummary"] == {
        "title": {"status": "salvage"},
        "damage": {"status": "severe"},
    }
    assert payload["reportSummaries"] == [
        {"source": "carfax", "label": "Status", "category": "title", "value": "salvage"},
        {"source": "carfax", "label": "Status", "category": "damage", "value": "severe"},
    ]
    assert payload["importantFindings"] == [
        {"source": "carfax", "label": "Status", "category": "title", "value": "salvage"},
        {"source": "carfax", "label": "Status", "category": "damage", "value": "severe"},
    ]
    serialized = str(payload)
    assert "'status': 'success'" not in serialized
    assert "'status': 'ok'" not in serialized
    assert "'status': 'ready'" not in serialized


def test_build_vehicle_report_payload_keeps_root_semantic_status_facts() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "carfax_data": {
                    "summary": {"status": "salvage"},
                    "status": "salvage",
                }
            }
        }
    )

    assert payload["carfaxSummary"] == {"status": "salvage"}
    assert payload["reportSummaries"] == [
        {"source": "carfax", "label": "Status", "value": "salvage"},
    ]
    assert payload["importantFindings"] == [
        {"source": "carfax", "label": "Status", "value": "salvage"},
    ]


def test_build_vehicle_report_payload_prefers_clean_sibling_summary_keys_over_wrapper_dict_conflicts() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "carfax_data": {
                    "summary": {
                        "damage": "Clean sibling fact",
                        "wrapper": {
                            "damage": "Wrapper conflict",
                            "theft": "Wrapper-only fact",
                        },
                    }
                }
            }
        }
    )

    assert payload["carfaxSummary"] == {
        "damage": {"value": "Clean sibling fact", "messages": ["Wrapper conflict"]},
        "theft": "Wrapper-only fact",
    }
    assert payload["reportSummaries"] == [
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "Clean sibling fact"},
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "Wrapper conflict"},
        {"source": "carfax", "label": "Theft", "category": "theft", "value": "Wrapper-only fact"},
    ]
    assert payload["importantFindings"] == [
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "Clean sibling fact"},
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "Wrapper conflict"},
        {"source": "carfax", "label": "Theft", "category": "theft", "value": "Wrapper-only fact"},
    ]


def test_build_vehicle_report_payload_preserves_wrapper_nested_facts_when_same_key_already_has_scalar() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "carfax_data": {
                    "summary": {
                        "damage": "reported",
                        "wrapper": {
                            "damage": {"severity": "severe", "country": "US"},
                        },
                    }
                }
            }
        }
    )

    assert payload["carfaxSummary"] == {
        "damage": {"value": "reported", "severity": "severe", "country": "US"},
    }
    assert payload["reportSummaries"] == [
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "reported"},
        {"source": "carfax", "label": "Severity", "category": "damage", "value": "severe"},
    ]
    assert payload["importantFindings"] == [
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "reported"},
        {"source": "carfax", "label": "Severity", "category": "damage", "value": "severe", "country": "US"},
    ]


def test_build_vehicle_report_payload_preserves_wrapper_dict_value_when_same_key_already_has_scalar() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "carfax_data": {
                    "summary": {
                        "damage": "reported",
                        "wrapper": {
                            "damage": {"value": "confirmed", "severity": "severe", "country": "US"},
                        },
                    }
                }
            }
        }
    )

    assert payload["carfaxSummary"] == {
        "damage": {"value": "reported", "messages": ["confirmed"], "severity": "severe", "country": "US"},
    }
    assert payload["reportSummaries"] == [
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "reported"},
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "confirmed"},
        {"source": "carfax", "label": "Severity", "category": "damage", "value": "severe"},
    ]
    assert payload["importantFindings"] == [
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "reported"},
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "confirmed", "country": "US"},
        {"source": "carfax", "label": "Severity", "category": "damage", "value": "severe", "country": "US"},
    ]


def test_build_vehicle_report_payload_preserves_wrapper_scalar_when_same_key_already_has_nested_facts() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "carfax_data": {
                    "summary": {
                        "damage": {"severity": "severe", "country": "US"},
                        "wrapper": {
                            "damage": "reported",
                        },
                    }
                }
            }
        }
    )

    assert payload["carfaxSummary"] == {
        "damage": {"severity": "severe", "country": "US", "value": "reported"},
    }
    assert payload["reportSummaries"] == [
        {"source": "carfax", "label": "Severity", "category": "damage", "value": "severe"},
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "reported"},
    ]
    assert payload["importantFindings"] == [
        {"source": "carfax", "label": "Severity", "category": "damage", "value": "severe", "country": "US"},
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "reported", "country": "US"},
    ]


def test_build_vehicle_report_payload_preserves_wrapper_messages_when_sibling_messages_exist() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "carfax_data": {
                    "summary": {
                        "messages": ["a"],
                        "wrapper": {
                            "messages": ["b"],
                        },
                    }
                }
            }
        }
    )

    assert payload["carfaxSummary"] == {
        "messages": ["a", "b"],
    }
    assert payload["reportSummaries"] == [
        {"source": "carfax", "label": "Messages", "value": "a"},
        {"source": "carfax", "label": "Messages", "value": "b"},
    ]


def test_build_vehicle_report_payload_merges_wrapper_keys_by_normalized_name() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "carfax_data": {
                    "summary": {
                        "damage": "reported",
                        "wrapper": {
                            "Damage": ["auction note"],
                            "damage": {"severity": "structural"},
                        },
                    }
                }
            }
        }
    )

    assert payload["carfaxSummary"] == {
        "damage": {"value": "reported", "messages": ["auction note"], "severity": "structural"},
    }
    assert payload["reportSummaries"] == [
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "reported"},
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "auction note"},
        {"source": "carfax", "label": "Severity", "category": "damage", "value": "structural"},
    ]


def test_build_vehicle_report_payload_preserves_wrapper_list_when_same_key_already_has_scalar() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "carfax_data": {
                    "summary": {
                        "damage": "reported",
                        "wrapper": {
                            "damage": ["structural", "auction note"],
                        },
                    }
                }
            }
        }
    )

    assert payload["carfaxSummary"] == {
        "damage": {"value": "reported", "messages": ["structural", "auction note"]},
    }
    assert payload["reportSummaries"] == [
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "reported"},
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "structural"},
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "auction note"},
    ]
    assert payload["importantFindings"] == [
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "reported"},
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "structural"},
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "auction note"},
    ]


def test_build_vehicle_report_payload_preserves_wrapper_scalar_when_same_key_already_has_scalar() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "carfax_data": {
                    "summary": {
                        "damage": "reported",
                        "wrapper": {
                            "damage": "confirmed",
                        },
                    }
                }
            }
        }
    )

    assert payload["carfaxSummary"] == {
        "damage": {"value": "reported", "messages": ["confirmed"]},
    }
    assert payload["reportSummaries"] == [
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "reported"},
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "confirmed"},
    ]
    assert payload["importantFindings"] == [
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "reported"},
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "confirmed"},
    ]


def test_build_vehicle_report_payload_preserves_wrapper_first_scalar_conflict_order_independently() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "carfax_data": {
                    "summary": {
                        "wrapper": {
                            "damage": "confirmed",
                        },
                        "damage": "reported",
                    }
                }
            }
        }
    )

    assert payload["carfaxSummary"] == {
        "damage": {"value": "reported", "messages": ["confirmed"]},
    }
    assert sorted(payload["reportSummaries"], key=lambda item: str(item["value"])) == [
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "confirmed"},
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "reported"},
    ]


def test_build_vehicle_report_payload_preserves_wrapper_first_list_conflict_order_independently() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "carfax_data": {
                    "summary": {
                        "wrapper": {
                            "damage": ["structural", "auction note"],
                        },
                        "damage": "reported",
                    }
                }
            }
        }
    )

    assert payload["carfaxSummary"] == {
        "damage": {"value": "reported", "messages": ["structural", "auction note"]},
    }
    assert payload["reportSummaries"] == [
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "structural"},
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "auction note"},
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "reported"},
    ]


def test_build_vehicle_report_payload_preserves_wrapper_first_dict_conflict_order_independently() -> None:
    payload = build_vehicle_report_payload(
        {
            "report": {
                "carfax_data": {
                    "summary": {
                        "wrapper": {
                            "damage": {"severity": "severe", "country": "US"},
                        },
                        "damage": "reported",
                    }
                }
            }
        }
    )

    assert payload["carfaxSummary"] == {
        "damage": {"value": "reported", "severity": "severe", "country": "US"},
    }
    assert payload["reportSummaries"] == [
        {"source": "carfax", "label": "Severity", "category": "damage", "value": "severe"},
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "reported"},
    ]
    assert payload["importantFindings"] == [
        {"source": "carfax", "label": "Severity", "category": "damage", "value": "severe", "country": "US"},
        {"source": "carfax", "label": "Damage", "category": "damage", "value": "reported"},
    ]


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
