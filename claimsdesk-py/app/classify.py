"""Document type classification: keyword rules for demo text, Claude for real media."""
import base64, json, os, re
import httpx

RULES = [
    ("kyc", r"aadhaar|aadhar|uidai|pan card|income tax dep|permanent account"),
    ("cheque", r"cancel+ed cheque|cheque|ifsc|micr"),
    ("policy", r"policy (copy|no|number|schedule)|health card|e-card|member id|sum insured"),
    ("discharge", r"discharge summary|date of discharge|condition at discharge"),
    ("bill", r"final bill|hospital bill|room rent|inpatient bill|bill summary|net payable"),
    ("pharmacy", r"pharmacy|chemist|medical store|batch no|expiry|tablet"),
    ("reports", r"pathology|radiology|lab report|mri|ct scan|x-ray|haemoglobin|investigation|blood test|ecg"),
    ("consult", r"consultation|opd|prescription|doctor notes|progress notes|rx\b"),
]


def classify_text(text: str) -> dict:
    dtype = next((t for t, rx in RULES if re.search(rx, text or "", re.I)), "unknown")
    m = re.search(r"(?:patient|name)\s*[:\-]\s*([A-Za-z ]{3,40})", text or "", re.I)
    return {"type": dtype, "name": m.group(1).strip() if m else None}


PROMPT = ('Classify every page of this Indian health-insurance claim document. Types: kyc, policy, '
          'discharge, bill, reports, consult, pharmacy, cheque, unknown. Return ONLY a JSON array, one '
          'object per page: {"page":1,"type":"...","blurry":false,"name":"patient name printed on it or null"}. '
          'blurry=true if text is not legible.')


async def classify_media(data: bytes, mime: str) -> list:
    key = os.getenv("ANTHROPIC_API_KEY")
    fallback = [{"type": "unknown", "blurry": False, "name": None}]
    if not key:
        return fallback
    block = {"type": "document" if mime == "application/pdf" else "image",
             "source": {"type": "base64", "media_type": mime,
                        "data": base64.b64encode(data).decode()}}
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post("https://api.anthropic.com/v1/messages",
                         headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                         json={"model": "claude-sonnet-4-5", "max_tokens": 1000,
                               "messages": [{"role": "user",
                                             "content": [block, {"type": "text", "text": PROMPT}]}]})
    try:
        text = r.json()["content"][0]["text"].replace("```json", "").replace("```", "")
        return json.loads(text)
    except Exception:
        return fallback
