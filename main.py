from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import os
from dotenv import load_dotenv
import uvicorn

load_dotenv()

app = FastAPI()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
API_TOKEN = os.getenv("API_TOKEN")


# 1️⃣ Verification endpoint (Facebook calls this once)
@app.get("/webhook")
async def verify(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        # MUST return challenge as plain text, not JSON
        return PlainTextResponse(challenge, status_code=200)

    return PlainTextResponse("Verification failed", status_code=403)


# 2️⃣ Messenger sends messages here
@app.post("/webhook")
async def receive_message(request: Request):
    data = await request.json()
    print("📩 Incoming webhook:", data)
    return {"status": "ok"}  # Always respond 200 to messages


if __name__ == "__main__":
    port = 8000
    uvicorn.run(app, host="0.0.0.0", port=port)
