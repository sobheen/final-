"""Case storage. In-memory by default; Upstash Redis (REST) if configured, so state
survives across Vercel serverless instances."""
import json, os, time
import httpx

REQUIRED = [
    ("kyc", "KYC (Aadhaar / PAN)"), ("policy", "Policy copy / health card"),
    ("discharge", "Discharge summary"), ("bill", "Final hospital bill"),
    ("reports", "Investigation reports"), ("consult", "Consultation papers"),
    ("pharmacy", "Pharmacy bills"), ("cheque", "Cancelled cheque"),
]
LABEL = dict(REQUIRED)

_mem = {}
URL = lambda: os.getenv("UPSTASH_REDIS_REST_URL")
TOK = lambda: os.getenv("UPSTASH_REDIS_REST_TOKEN")


def _case(cid, name, phone):
    return {"id": cid, "name": name, "phone": phone, "docs": {}, "log": [],
            "chat": [], "seen": [], "updated": time.time()}


def seed():
    return {"cases": {
        "919800000345": _case("P-1042", "Ravi Kumar", "919800000345"),
        "919811111222": _case("P-1043", "Meera Nair", "919811111222")}}


async def _redis(cmd):
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(URL(), headers={"Authorization": f"Bearer {TOK()}"}, json=cmd)
        return r.json().get("result")


async def load():
    if URL() and TOK():
        raw = await _redis(["GET", "db"])
        return json.loads(raw) if raw else seed()
    if "db" not in _mem:
        _mem["db"] = seed()
    return _mem["db"]


async def save(db):
    if URL() and TOK():
        await _redis(["SET", "db", json.dumps(db)])
    else:
        _mem["db"] = db


async def reset():
    _mem.clear()
    if URL() and TOK():
        await _redis(["DEL", "db"])
