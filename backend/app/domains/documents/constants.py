from __future__ import annotations

DOCUMENT_CATEGORIES = {
    "drawing": "Drawing",
    "specification": "Specification",
    "contract": "Contract",
    "rfi": "RFI",
    "submittal": "Submittal",
    "invoice": "Invoice",
    "correspondence": "Correspondence",
    "meeting_minutes": "Meeting Minutes",
    "report": "Report",
    "photo": "Site Photograph",
    "quote": "Quotation",
    "insurance": "Insurance Certificate",
    "other": "Other",
}

DISCIPLINES = {
    "general": "General",
    "civil": "Civil",
    "architectural": "Architectural",
    "structural": "Structural",
    "mechanical": "Mechanical",
    "electrical": "Electrical",
    "plumbing": "Plumbing",
    "fire_protection": "Fire Protection",
    "landscape": "Landscape",
    "other": "Other",
}

# Allow-list: extension -> accepted MIME types. Content is also sniffed by magic bytes where possible.
ALLOWED_FILE_TYPES: dict[str, set[str]] = {
    ".pdf": {"application/pdf"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".heic": {"image/heic", "image/heif"},
    ".tif": {"image/tiff"},
    ".tiff": {"image/tiff"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/zip"},
    ".pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation", "application/zip"},
    ".csv": {"text/csv", "text/plain"},
    ".txt": {"text/plain"},
    ".dwg": {"application/acad", "image/vnd.dwg", "application/octet-stream"},
    ".dxf": {"image/vnd.dxf", "application/dxf", "text/plain", "application/octet-stream"},
    ".ifc": {"application/x-step", "text/plain", "application/octet-stream"},
    ".msg": {"application/vnd.ms-outlook", "application/octet-stream"},
    ".eml": {"message/rfc822", "text/plain"},
}

# Formats where we can verify magic bytes; a mismatch is rejected.
MAGIC_REQUIRED = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".docx", ".xlsx", ".pptx"}
