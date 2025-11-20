from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import os
from dotenv import load_dotenv
import uvicorn
import requests

load_dotenv()

app = FastAPI()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
API_TOKEN = os.getenv("API_TOKEN")
FB_MESSAGER_API_URL = "https://graph.facebook.com/v24.0/me/messages"


# 1️ Verification endpoint (Facebook calls this once)
@app.get("/webhook")
async def verify(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        # MUST return challenge as plain text, not JSON
        return PlainTextResponse(challenge, status_code=200)

    return PlainTextResponse("Verification failed", status_code=403)


# 2️ Messenger sends messages here
@app.post("/webhook")
async def receive_message(request: Request):
    data = await request.json()
    print("Incoming webhook:", data)

    try:
        # Extract Sender ID and message text
        message_payload = data["entry"][0]["messaging"][0]
        if "message" in message_payload and "text" in message_payload["message"]:
            sender_id = message_payload["sender"]["id"]
            message_text = message_payload["message"]["text"]

            send_message(sender_id, f"You said: {message_text}")

    except KeyError:
        print("No message payload found in the request.")

    return {"status": "ok"}  # Always respond 200 to messages

# Send message back to user
def send_message(recipient_id: str, message_text: str):
    headers = {"Content-Type": "application/json"}

    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }

    params = {
        "access_token": API_TOKEN
    }

    response = requests.post(FB_MESSAGER_API_URL, params=params, json=payload, headers=headers)
    if response.status_code != 200:
        print("Failed to send message:", response.text)

if __name__ == "__main__":
    port = 8000
    uvicorn.run(app, host="0.0.0.0", port=port)
