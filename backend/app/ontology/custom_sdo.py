from stix2 import CustomObject, properties


@CustomObject(
    "x-vessel",
    [
        ("name", properties.StringProperty(required=True)),
        ("mmsi", properties.StringProperty()),
        ("imo", properties.StringProperty()),
        ("vessel_type", properties.StringProperty()),
        ("flag_state", properties.StringProperty()),
        ("hull_number", properties.StringProperty()),
        ("navy", properties.StringProperty()),
        ("call_sign", properties.StringProperty()),
    ],
)
class XVessel:
    pass


@CustomObject(
    "x-aircraft",
    [
        ("name", properties.StringProperty(required=True)),
        ("icao24", properties.StringProperty()),
        ("callsign", properties.StringProperty()),
        ("aircraft_type", properties.StringProperty()),
        ("military_type", properties.StringProperty()),
        ("country", properties.StringProperty()),
        ("force", properties.StringProperty()),
        ("registration", properties.StringProperty()),
        ("is_uav", properties.BooleanProperty(default=lambda: False)),
    ],
)
class XAircraft:
    pass


@CustomObject(
    "x-satellite",
    [
        ("name", properties.StringProperty(required=True)),
        ("norad_id", properties.StringProperty()),
        ("mission_type", properties.StringProperty()),
        ("country", properties.StringProperty()),
        ("orbit_type", properties.StringProperty()),
        ("inclination", properties.FloatProperty()),
        ("period_minutes", properties.FloatProperty()),
    ],
)
class XSatellite:
    pass


@CustomObject(
    "x-facility",
    [
        ("name", properties.StringProperty(required=True)),
        ("facility_type", properties.StringProperty()),
        ("country", properties.StringProperty()),
        ("operator", properties.StringProperty()),
        ("branch", properties.StringProperty()),
    ],
)
class XFacility:
    pass


@CustomObject(
    "x-geopolitical-event",
    [
        ("name", properties.StringProperty(required=True)),
        ("event_type", properties.StringProperty()),
        ("country", properties.StringProperty()),
        ("description", properties.StringProperty()),
        ("source_url", properties.StringProperty()),
        ("goldstein_scale", properties.FloatProperty()),
    ],
)
class XGeopoliticalEvent:
    pass


@CustomObject(
    "x-geopolitical-actor",
    [
        ("name", properties.StringProperty(required=True)),
        ("actor_type", properties.StringProperty()),
        ("country_code", properties.StringProperty()),
        ("ideology", properties.StringProperty()),
        ("military_capability", properties.StringProperty()),
        (
            "alliance_memberships",
            properties.ListProperty(properties.StringProperty()),
        ),
    ],
)
class XGeopoliticalActor:
    pass
