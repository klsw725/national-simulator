from __future__ import annotations

from typing import Any

from stix2.exceptions import ExtraPropertiesError, InvalidValueError, MissingPropertiesError

from app.ontology.custom_sdo import (
    XAircraft,
    XFacility,
    XGeopoliticalActor,
    XGeopoliticalEvent,
    XSatellite,
    XVessel,
)

SDO_MAP = {
    "x-vessel": XVessel,
    "x-aircraft": XAircraft,
    "x-satellite": XSatellite,
    "x-facility": XFacility,
    "x-geopolitical-event": XGeopoliticalEvent,
    "x-geopolitical-actor": XGeopoliticalActor,
}

SUPPORTED_TYPES = set(SDO_MAP.keys())


class StixValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"STIX validation failed: {'; '.join(errors)}")


class StixValidator:
    def validate(self, object_type: str, properties: dict[str, Any]) -> Any:
        if object_type not in SDO_MAP:
            raise StixValidationError(
                [
                    "Unknown object type: "
                    f"{object_type}. Supported: {', '.join(sorted(SUPPORTED_TYPES))}"
                ]
            )

        cls = SDO_MAP[object_type]
        errors: list[str] = []
        try:
            obj = cls(**properties)
            return obj
        except MissingPropertiesError as exc:
            errors.append(f"Missing required properties: {exc}")
        except InvalidValueError as exc:
            errors.append(f"Invalid value: {exc}")
        except ExtraPropertiesError as exc:
            errors.append(f"Extra properties not allowed: {exc}")
        except Exception as exc:
            errors.append(f"Validation error: {exc}")

        raise StixValidationError(errors)

    def serialize(self, stix_obj: Any) -> str:
        return stix_obj.serialize()
