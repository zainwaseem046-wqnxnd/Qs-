from __future__ import annotations

REASONS = {
    "client_instruction": "Client / employer instruction",
    "design_change": "Design change",
    "unforeseen_conditions": "Unforeseen / ground conditions",
    "error_omission": "Error or omission in documents",
    "regulatory": "Regulatory / statutory requirement",
    "value_engineering": "Value engineering",
    "provisional_sum": "Expenditure of a provisional sum",
    "acceleration": "Acceleration",
    "other": "Other",
}
STATUSES = {
    "draft": "Draft",
    "submitted": "Submitted",
    "approved": "Approved",
    "rejected": "Rejected",
    "withdrawn": "Withdrawn",
}


def change_label(country: str, contract_form: str | None) -> tuple[str, str]:
    """(label, number prefix) for client-side changes, following the contract's terminology."""
    if contract_form and contract_form.startswith("nec4"):
        return "Compensation event", "CE"
    if country == "GB":
        return "Variation", "VAR"
    return "Change order", "CO"


def commitment_change_label(country: str, contract_form: str | None) -> tuple[str, str]:
    if contract_form and contract_form.startswith("nec4"):
        return "Compensation event", "SCE"
    if country == "GB":
        return "Subcontract variation", "SV"
    return "Subcontract change order", "SCO"
