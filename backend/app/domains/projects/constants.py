"""Controlled vocabularies for projects (US construction terminology)."""

from __future__ import annotations

PROJECT_STATUSES = {
    "pursuit": "Pursuit / Bidding",
    "preconstruction": "Preconstruction",
    "active": "Active / In Construction",
    "on_hold": "On Hold",
    "closeout": "Closeout",
    "complete": "Complete",
    "lost": "Lost Bid",
    "cancelled": "Cancelled",
}
# Statuses counted as "live" backlog in portfolio totals.
LIVE_STATUSES = ("preconstruction", "active", "on_hold", "closeout")

SECTORS = {
    "commercial": "Commercial",
    "residential": "Residential",
    "multifamily": "Multifamily",
    "industrial": "Industrial",
    "institutional": "Institutional (education, healthcare, government)",
    "civil_infrastructure": "Civil & Infrastructure",
    "heavy_civil": "Heavy Civil",
    "energy_utilities": "Energy & Utilities",
    "mixed_use": "Mixed Use",
    "specialty_trade": "Specialty Trade",
}

DELIVERY_METHODS = {
    "design_bid_build": "Design-Bid-Build",
    "design_build": "Design-Build",
    "cm_at_risk": "Construction Manager at Risk",
    "cm_agency": "Construction Manager (Agency)",
    "ipd": "Integrated Project Delivery",
    "job_order_contracting": "Job Order Contracting",
    "public_private_partnership": "Public-Private Partnership (P3)",
    "other": "Other",
}

CONTRACT_TYPES = {
    "lump_sum": "Lump Sum / Stipulated Sum",
    "gmp": "Guaranteed Maximum Price (Cost Plus Fee with GMP)",
    "cost_plus": "Cost Plus Fee",
    "unit_price": "Unit Price",
    "time_and_materials": "Time & Materials",
    "other": "Other",
}

OUR_ROLES = {
    "general_contractor": "General Contractor",
    "construction_manager": "Construction Manager",
    "design_builder": "Design-Builder",
    "subcontractor": "Subcontractor",
    "specialty_contractor": "Specialty Trade Contractor",
    "owner": "Owner / Developer",
    "owners_representative": "Owner's Representative",
}

PROJECT_MEMBER_ROLES = {
    "project_executive": "Project Executive",
    "project_manager": "Project Manager",
    "assistant_project_manager": "Assistant Project Manager",
    "superintendent": "Superintendent",
    "project_engineer": "Project Engineer",
    "estimator": "Estimator",
    "commercial_manager": "Commercial Manager / QS",
    "project_accountant": "Project Accountant",
    "field_engineer": "Field Engineer",
    "viewer": "Viewer",
}

PARTY_ROLES = {
    "owner": "Owner",
    "client": "Client",
    "developer": "Developer",
    "architect": "Architect",
    "structural_engineer": "Structural Engineer",
    "mep_engineer": "MEP Engineer",
    "civil_engineer": "Civil Engineer",
    "consultant": "Consultant",
    "general_contractor": "General Contractor",
    "construction_manager": "Construction Manager",
    "subcontractor": "Subcontractor",
    "supplier": "Supplier",
    "lender": "Lender",
    "surety": "Surety",
    "inspector": "Inspector",
    "other": "Other",
}

PHASE_STATUSES = {"planned": "Planned", "in_progress": "In Progress", "complete": "Complete"}

US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana",
    "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
    "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "PR": "Puerto Rico", "GU": "Guam", "VI": "U.S. Virgin Islands", "AS": "American Samoa",
    "MP": "Northern Mariana Islands",
}

COMPANY_TYPES = {
    "owner": "Owner / Developer",
    "general_contractor": "General Contractor",
    "construction_manager": "Construction Manager",
    "subcontractor": "Subcontractor",
    "supplier": "Supplier / Vendor",
    "architect": "Architect",
    "engineer": "Engineer",
    "consultant": "Consultant",
    "public_agency": "Public Agency",
    "lender": "Lender",
    "surety": "Surety / Insurance",
    "other": "Other",
}
