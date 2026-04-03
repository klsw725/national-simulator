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


# ---------------------------------------------------------------------------
# v12 — 행위자 (Actors)
# ---------------------------------------------------------------------------


@CustomObject(
    "x-nation-state",
    [
        ("name", properties.StringProperty(required=True)),
        ("country_code", properties.StringProperty(required=True)),
        ("military_power", properties.StringProperty()),
        ("economic_power", properties.StringProperty()),
        ("ideology", properties.StringProperty()),
        (
            "alliance_memberships",
            properties.ListProperty(properties.StringProperty()),
        ),
    ],
)
class XNationState:
    pass


@CustomObject(
    "x-international-org",
    [
        ("name", properties.StringProperty(required=True)),
        ("org_type", properties.StringProperty()),
        (
            "member_states",
            properties.ListProperty(properties.StringProperty()),
        ),
    ],
)
class XInternationalOrg:
    pass


@CustomObject(
    "x-military-force",
    [
        ("name", properties.StringProperty(required=True)),
        ("force_type", properties.StringProperty()),
        ("parent_nation", properties.StringProperty()),
        ("operational_area", properties.StringProperty()),
    ],
)
class XMilitaryForce:
    pass


@CustomObject(
    "x-intelligence-agency",
    [
        ("name", properties.StringProperty(required=True)),
        ("parent_nation", properties.StringProperty()),
        (
            "known_operations",
            properties.ListProperty(properties.StringProperty()),
        ),
    ],
)
class XIntelligenceAgency:
    pass


@CustomObject(
    "x-non-state-actor",
    [
        ("name", properties.StringProperty(required=True)),
        ("actor_subtype", properties.StringProperty()),
        ("operating_region", properties.StringProperty()),
    ],
)
class XNonStateActor:
    pass


@CustomObject(
    "x-key-leader",
    [
        ("name", properties.StringProperty(required=True)),
        ("title", properties.StringProperty()),
        ("parent_org", properties.StringProperty()),
        ("decision_authority", properties.StringProperty()),
    ],
)
class XKeyLeader:
    pass


# ---------------------------------------------------------------------------
# v12 — 자산 (Assets)
# ---------------------------------------------------------------------------


@CustomObject(
    "x-weapon-system",
    [
        ("name", properties.StringProperty(required=True)),
        ("weapon_type", properties.StringProperty()),
        ("range_km", properties.FloatProperty()),
        (
            "platform_compatible",
            properties.ListProperty(properties.StringProperty()),
        ),
    ],
)
class XWeaponSystem:
    pass


# ---------------------------------------------------------------------------
# v12 — 이벤트 (Events)
# ---------------------------------------------------------------------------


@CustomObject(
    "x-military-event",
    [
        ("name", properties.StringProperty(required=True)),
        ("event_subtype", properties.StringProperty()),
        (
            "participants",
            properties.ListProperty(properties.StringProperty()),
        ),
        ("description", properties.StringProperty()),
        ("source_url", properties.StringProperty()),
        ("goldstein_scale", properties.FloatProperty()),
    ],
)
class XMilitaryEvent:
    pass


@CustomObject(
    "x-economic-event",
    [
        ("name", properties.StringProperty(required=True)),
        ("event_subtype", properties.StringProperty()),
        (
            "affected_sectors",
            properties.ListProperty(properties.StringProperty()),
        ),
        ("description", properties.StringProperty()),
        ("source_url", properties.StringProperty()),
        ("goldstein_scale", properties.FloatProperty()),
    ],
)
class XEconomicEvent:
    pass


@CustomObject(
    "x-diplomatic-event",
    [
        ("name", properties.StringProperty(required=True)),
        ("event_subtype", properties.StringProperty()),
        ("formality_level", properties.StringProperty()),
        ("description", properties.StringProperty()),
        ("source_url", properties.StringProperty()),
        ("goldstein_scale", properties.FloatProperty()),
    ],
)
class XDiplomaticEvent:
    pass


# ---------------------------------------------------------------------------
# v12 — 지리 (Geography)
# ---------------------------------------------------------------------------


@CustomObject(
    "x-strategic-region",
    [
        ("name", properties.StringProperty(required=True)),
        ("region_type", properties.StringProperty()),
        (
            "disputed_by",
            properties.ListProperty(properties.StringProperty()),
        ),
        ("strategic_value", properties.FloatProperty()),
    ],
)
class XStrategicRegion:
    pass


@CustomObject(
    "x-chokepoint",
    [
        ("name", properties.StringProperty(required=True)),
        ("chokepoint_type", properties.StringProperty()),
        ("transit_volume", properties.FloatProperty()),
    ],
)
class XChokepoint:
    pass
