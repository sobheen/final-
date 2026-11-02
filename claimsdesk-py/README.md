# ClaimsDesk WhatsApp Document Tracker (Python / FastAPI)

## Run in PyCharm
1. Open this folder as a project. Settings > Python Interpreter > Add > Virtualenv.
2. Terminal: `pip install -r requirements.txt`
3. Run > Edit Configurations > + Python. Choose "module name", enter `uvicorn`, parameters
   `app.main:app --reload --port 8000`, working directory = project root. Run it.
4. Open http://localhost:8000

## Deploy to Vercel
Push to GitHub, import in Vercel (Python runtime detected from requirements.txt).
Add the Upstash Redis integration so state persists between serverless instances.

## Go live on WhatsApp
Set env vars from `.env.example` (WHATSAPP_TOKEN, WHATSAPP_PHONE_ID, ANTHROPIC_API_KEY).
Meta webhook URL: https://<app>.vercel.app/api/webhook, verify token `claimsdesk-verify`, subscribe to `messages`.
Edit patients in `app/store.py` (`seed`). Phone format: international, no +.
