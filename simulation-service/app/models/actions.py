DIPLOMATIC_ACTIONS = [
    "issue_statement",
    "propose_negotiation",
    "recall_ambassador",
    "strengthen_alliance",
    "condemn_action",
    "request_mediation",
    "sign_agreement",
]

ECONOMIC_ACTIONS = [
    "impose_sanction",
    "lift_sanction",
    "restrict_trade",
    "offer_aid",
    "currency_intervention",
]

MILITARY_ACTIONS = [
    "deploy_forces",
    "conduct_exercise",
    "mobilize_reserves",
    "withdraw_forces",
    "establish_no_fly_zone",
    "naval_patrol",
    "cyber_operation",
]

INTELLIGENCE_ACTIONS = [
    "increase_surveillance",
    "share_intelligence",
    "conduct_recon",
    "electronic_warfare",
]

META_ACTIONS = [
    "do_nothing",
    "internal_focus",
]

ALL_ACTIONS = (
    DIPLOMATIC_ACTIONS
    + ECONOMIC_ACTIONS
    + MILITARY_ACTIONS
    + INTELLIGENCE_ACTIONS
    + META_ACTIONS
)

ACTION_LIST_TEXT = ", ".join(ALL_ACTIONS)
