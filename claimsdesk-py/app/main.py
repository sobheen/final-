import hashlib, os
from pathlib import Path
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
import httpx

from .classify import classify_media, classify_text
from .pipeline import ingest
from .store import load, reset

app = FastAPI(title="ClaimsDesk WhatsApp Document Tracker")
INDEX = Path(__file__).parent / "static" / "index.html"


@app.get("/", response_class=HTMLResponse)
async def home():
    return INDEX.read_text(encoding="utf-8")


@app.get("/api/state")
async def state():
    return JSONResponse(await load(), headers={"Cache-Control": "no-store"})


@app.delete("/api/state")
async def clear():
    await reset()
    return {"ok": True}


@app.post("/api/simulate")
async def simulate(req: Request):
    """Demo mode: page texts go through the same classifier + pipeline as real media."""
    body = await req.json()
    items = [{"filename": it["filename"], "hash": it.get("hash"),
              "pages": [{**classify_text(p["text"]), "blurry": bool(p.get("blurry"))} for p in it["pages"]]}
             for it in body["items"]]
    return await ingest(body["phone"], items)


@app.get("/api/webhook")
async def verify(request: Request):
    q = request.query_params
    if q.get("hub.verify_token") == os.getenv("WHATSAPP_VERIFY_TOKEN", "claimsdesk-verify"):
        return PlainTextResponse(q.get("hub.challenge", ""))
    return Response(status_code=403)


@app.post("/api/webhook")
async def webhook(req: Request):
    payload = await req.json()
    token = os.getenv("WHATSAPP_TOKEN")
    auth = {"Authorization": f"Bearer {token}"}
    try:
        messages = payload["entry"][0]["changes"][0]["value"].get("messages", [])
    except (KeyError, IndexError):
        messages = []
    async with httpx.AsyncClient(timeout=30) as http:
        for m in messages:
            if m.get("type") not in ("image", "document"):
                continue
            media = m[m["type"]]
            meta = (await http.get(f"https://graph.facebook.com/v20.0/{media['id']}", headers=auth)).json()
            data = (await http.get(meta["url"], headers=auth)).content
            pages = await classify_media(data, media.get("mime_type", "image/jpeg"))
            await ingest(m["from"], [{"filename": media.get("filename") or f"{m['type']}-{media['id'][-5:]}",
                                      "hash": hashlib.sha256(data).hexdigest(), "pages": pages}])
    return {"ok": True}
