"""Ingest pipeline: dedupe -> owner check -> blur check -> classify -> merge -> checklist -> auto-reply."""
import os, time
import httpx
from .store import REQUIRED, LABEL, load, save


def _first(s):
    return (s or "").strip().split(" ")[0].lower()


def _pending(c):
    return [(k, l) for k, l in REQUIRED if k not in c["docs"]]


def build_reply(c):
    first = c["name"].split(" ")[0]
    got = [f"✓ {l}" for k, l in REQUIRED if c["docs"].get(k, {}).get("status") == "ok"]
    miss = [f"✗ {l}" + (" (image was blurry, please resend)" if c["docs"].get(k, {}).get("status") == "resend" else "")
            for k, l in _pending(c)]
    if not miss:
        return f"Thank you {first}! All 8 documents received. Your claim file is complete."
    return f"Hi {first}, we received:\n" + ("\n".join(got) or "nothing yet") + "\n\nStill pending:\n" + "\n".join(miss)


async def send_whatsapp(to, body):
    tok, pid = os.getenv("WHATSAPP_TOKEN"), os.getenv("WHATSAPP_PHONE_ID")
    if not (tok and pid):
        return False
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"https://graph.facebook.com/v20.0/{pid}/messages",
                         headers={"Authorization": f"Bearer {tok}"},
                         json={"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": body}})
    return r.is_success


async def ingest(phone, items):
    """items: [{filename, hash, pages:[{type, blurry, name}]}]"""
    db = await load()
    c = db["cases"].get(phone)
    if not c:
        return {"error": "unknown sender"}

    def log(kind, msg):
        c["log"].insert(0, {"t": time.time(), "kind": kind, "msg": msg})

    for it in items:
        if it.get("hash") and it["hash"] in c["seen"]:
            log("dup", f"{it['filename']}: duplicate ignored")
            continue
        if it.get("hash"):
            c["seen"].append(it["hash"])
        multi = len(it["pages"]) > 1
        for i, p in enumerate(it["pages"]):
            src = f"{it['filename']} p{i + 1}" if multi else it["filename"]
            ptype = p.get("type", "unknown")
            if p.get("name") and _first(p["name"]) != _first(c["name"]):
                log("quarantine", f'{src}: belongs to "{p["name"]}", quarantined, agent alerted')
                continue
            if p.get("blurry"):
                log("blurry", f"{src}: too blurry" + (f" ({LABEL[ptype]})" if ptype in LABEL else "") + ", needs resend")
                if ptype in LABEL and ptype not in c["docs"]:
                    c["docs"][ptype] = {"status": "resend", "src": src}
                continue
            if ptype not in LABEL:
                log("unknown", f"{src}: could not classify, agent review")
                continue
            d = c["docs"].get(ptype)
            if d and d["status"] == "ok":
                d["pages"] += 1
                d["src"] += f", {src}"
                log("merge", f"{src}: merged into {LABEL[ptype]}")
            else:
                c["docs"][ptype] = {"status": "ok", "src": src, "pages": 1, "t": time.time()}
                log("ok", f"{src}: {LABEL[ptype]} received")

    c["updated"] = time.time()
    msg = build_reply(c)
    c["chat"].append({"t": time.time(), "text": msg})
    sent = await send_whatsapp(phone, msg)
    log("reply", "Auto-reply sent on WhatsApp" if sent else "Auto-reply (demo mode, not sent)")
    await save(db)
    return {"ok": True}
