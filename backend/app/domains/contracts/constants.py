"""Contract form vocabularies. Names are factual references to published standard forms; no contract text is
included. Prime contract forms reuse the project contract types for the organization's country."""

from __future__ import annotations

from app.domains.projects.constants import vocab_for

US_SUBCONTRACT_FORMS = {
    "aia_a401": "AIA A401 Contractor-Subcontractor Agreement",
    "consensusdocs_750": "ConsensusDocs 750 Subcontract",
    "company_subcontract": "Company standard subcontract",
    "purchase_order": "Purchase order terms",
    "other": "Other",
}
UK_SUBCONTRACT_FORMS = {
    "jct_sbcsub": "JCT Standard Building Sub-Contract (SBCSub)",
    "jct_dbsub": "JCT Design and Build Sub-Contract (DBSub)",
    "jct_icsub": "JCT Intermediate Sub-Contract (ICSub)",
    "jct_shortsub": "JCT Short Form of Sub-Contract (ShortSub)",
    "nec4_ecs": "NEC4 Engineering and Construction Subcontract (ECS)",
    "nec4_ecss": "NEC4 Engineering and Construction Short Subcontract (ECSS)",
    "company_subcontract": "Company standard subcontract",
    "purchase_order": "Purchase order terms",
    "other": "Other",
}
SUBCONTRACT_FORMS = {"US": US_SUBCONTRACT_FORMS, "GB": UK_SUBCONTRACT_FORMS}
COMMITMENT_TYPES = {"subcontract": "Subcontract", "purchase_order": "Purchase order"}
STATUSES = {"draft": "Draft", "executed": "Executed", "closed": "Closed", "void": "Void"}


def prime_forms(country: str) -> dict[str, str]:
    return vocab_for(country)["contract_types"]


def subcontract_forms(country: str) -> dict[str, str]:
    return SUBCONTRACT_FORMS.get(country, US_SUBCONTRACT_FORMS)
