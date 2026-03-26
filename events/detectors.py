"""
Regex-based threat detectors for KITT security pipeline.

All detectors are regex-first (no LLM calls) for predictable
latency and reliability. The existing llama3.2 intent gate
handles LLM-based classification separately.

Detectors:
  - PII: SSN, email, phone, credit card
  - Exfiltration: base64, URL-encoded, "send to" patterns
  - Indirect injection: post-response instruction patterns

Known limitation: indirect injection checker will false-positive
on meta-discussion about attacks. Acceptable for demo-grade.
"""

import re
from typing import Optional

# --- PII Patterns ---

_SSN = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
_EMAIL = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')
_PHONE = re.compile(r'\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b')
_CREDIT_CARD = re.compile(r'\b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6(?:011|5\d{2}))[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b')


def detect_pii(text: Optional[str]) -> list[dict]:
    """
    Scan text for PII patterns. Returns list of findings.
    Each finding: {type: "pii", subtype: str, match: str, confidence: float}
    """
    if not text:
        return []
    findings = []
    for match in _SSN.finditer(text):
        findings.append({"type": "pii", "subtype": "ssn", "match": _redact(match.group()), "confidence": 0.95})
    for match in _EMAIL.finditer(text):
        findings.append({"type": "pii", "subtype": "email", "match": _redact(match.group()), "confidence": 0.9})
    for match in _PHONE.finditer(text):
        findings.append({"type": "pii", "subtype": "phone", "match": _redact(match.group()), "confidence": 0.7})
    for match in _CREDIT_CARD.finditer(text):
        findings.append({"type": "pii", "subtype": "credit_card", "match": _redact(match.group()), "confidence": 0.9})
    return findings


# --- Exfiltration Patterns ---

_BASE64_BLOCK = re.compile(r'[A-Za-z0-9+/]{40,}={0,2}')
_URL_ENCODED = re.compile(r'(?:%[0-9A-Fa-f]{2}){5,}')
_SEND_TO = re.compile(r'\b(?:send|email|forward|transmit|exfiltrate|upload)\s+(?:to|it\s+to|this\s+to|data\s+to)\b', re.IGNORECASE)


def detect_exfiltration(text: Optional[str]) -> list[dict]:
    """
    Scan text for data exfiltration patterns.
    Each finding: {type: "exfiltration", subtype: str, confidence: float}
    """
    if not text:
        return []
    findings = []
    if _BASE64_BLOCK.search(text):
        findings.append({"type": "exfiltration", "subtype": "base64_block", "confidence": 0.6})
    if _URL_ENCODED.search(text):
        findings.append({"type": "exfiltration", "subtype": "url_encoded", "confidence": 0.6})
    if _SEND_TO.search(text):
        findings.append({"type": "exfiltration", "subtype": "send_to_pattern", "confidence": 0.5})
    return findings


# --- Indirect Prompt Injection (post-response) ---

_INDIRECT_PATTERNS = [
    (re.compile(r'\bignore\s+(?:all\s+)?(?:previous|prior|above)\b', re.IGNORECASE), "ignore_previous"),
    (re.compile(r'\bsystem\s*:', re.IGNORECASE), "system_prefix"),
    (re.compile(r'\byou\s+are\s+now\b', re.IGNORECASE), "role_override"),
    (re.compile(r'\bforget\s+(?:all\s+)?(?:your|previous|prior)\b', re.IGNORECASE), "memory_wipe"),
    (re.compile(r'\bnew\s+instructions?\s*:', re.IGNORECASE), "instruction_inject"),
    (re.compile(r'\bact\s+as\s+(?:a|an|if)\b', re.IGNORECASE), "persona_switch"),
]


def check_indirect_injection(text: Optional[str]) -> list[dict]:
    """
    Scan model response text for indirect prompt injection patterns.
    Each finding: {type: "indirect_injection", subtype: str, confidence: float}
    """
    if not text:
        return []
    findings = []
    for pattern, subtype in _INDIRECT_PATTERNS:
        if pattern.search(text):
            findings.append({"type": "indirect_injection", "subtype": subtype, "confidence": 0.6})
    return findings


def run_all_detectors(text: Optional[str], is_response: bool = False) -> list[dict]:
    """
    Run appropriate detectors on text.
    For prompts: PII + exfiltration.
    For responses (is_response=True): PII + indirect injection.
    """
    if not text:
        return []
    findings = detect_pii(text)
    if is_response:
        findings.extend(check_indirect_injection(text))
    else:
        findings.extend(detect_exfiltration(text))
    return findings


def _redact(value: str) -> str:
    """Partially redact a matched value for safe logging."""
    if len(value) <= 4:
        return "****"
    return value[:2] + "*" * (len(value) - 4) + value[-2:]
