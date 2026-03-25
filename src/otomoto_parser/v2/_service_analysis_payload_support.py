from __future__ import annotations

from typing import Any

_LISTING_PARAMETER_FIELDS = (
    ("make", "make"),
    ("model", "model"),
    ("version", "version"),
    ("generation", "generation"),
    ("year", "year"),
    ("mileage", "mileage"),
    ("fuel_type", "fuelType"),
    ("gearbox", "gearbox"),
    ("body_type", "bodyType"),
    ("engine_capacity", "engineCapacity"),
    ("engine_power", "enginePower"),
    ("drive", "drive"),
    ("doors_no", "doors"),
    ("seats_no", "seats"),
    ("color", "color"),
    ("registered", "registered"),
    ("country_origin", "countryOfOrigin"),
    ("condition", "condition"),
    ("origin_country", "countryOfOrigin"),
)
_IDENTIFIER_PARAMETER_ALIASES = {"vin": "vin", "registration": "registrationNumber", "date_registration": "firstRegistrationDate"}
_MAX_SHORT_DESCRIPTION_LENGTH = 600
_MAX_DESCRIPTION_LENGTH = 3000
_MAX_TIMELINE_EVENTS = 8
_MAX_TIMELINE_EVENT_FIELDS = ("date", "type", "label", "mileage", "country", "source")


def _technical_data_root(report: dict[str, Any]) -> dict[str, Any]:
    technical_data = report.get("technical_data")
    if not isinstance(technical_data, dict):
        return {}
    return technical_data.get("technicalData") if isinstance(technical_data.get("technicalData"), dict) else {}


def _source_status_payload(report_payload: dict[str, Any], report: dict[str, Any], compact_dict: Any) -> dict[str, Any]:
    summary = report_payload.get("summary") if isinstance(report_payload.get("summary"), dict) else {}
    return compact_dict(
        {
            "apiVersion": report.get("api_version"),
            "autodnaAvailable": summary.get("autodnaAvailable"),
            "carfaxAvailable": summary.get("carfaxAvailable"),
            "autodnaUnavailable": summary.get("autodnaUnavailable"),
            "carfaxUnavailable": summary.get("carfaxUnavailable"),
        }
    )


def _technical_summary_payload(basic_data: dict[str, Any], ownership_history: dict[str, Any], compact_dict: Any) -> dict[str, Any]:
    return compact_dict(
        {
            "basicData": compact_dict({"make": basic_data.get("make"), "model": basic_data.get("model"), "type": basic_data.get("type"), "modelYear": basic_data.get("modelYear"), "fuel": basic_data.get("fuel"), "engineCapacity": basic_data.get("engineCapacity"), "enginePower": basic_data.get("enginePower"), "bodyType": basic_data.get("bodyType"), "color": basic_data.get("color")}),
            "ownershipHistory": compact_dict({"numberOfOwners": ownership_history.get("numberOfOwners"), "numberOfCoowners": ownership_history.get("numberOfCoowners"), "dateOfLastOwnershipChange": ownership_history.get("dateOfLastOwnershipChange")}),
        }
    )
