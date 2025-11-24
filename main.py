from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import PlainTextResponse
import os
from dotenv import load_dotenv
import uvicorn
import requests
import json
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

load_dotenv()

app = FastAPI()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
API_TOKEN = os.getenv("API_TOKEN")
FB_MESSAGER_API_URL = "https://graph.facebook.com/v24.0/me/messages"

# Structure for JSON response from Gemini
class TimeSlot(BaseModel):
    day: str = Field(..., description="Day of the week")
    start_time: str = Field(..., description="Start time in HH:MM format")
    end_time: str = Field(..., description="End time in HH:MM format")

# Initial verification endpoint (Required)
@app.get("/webhook")
async def verify(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        # MUST return challenge as plain text, not JSON
        return PlainTextResponse(challenge, status_code=200)

    return PlainTextResponse("Verification failed", status_code=403)


# Receive messages endpoint
@app.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    print("Incoming webhook:", data)

    # Process message in background to avoid Facebook retries
    background_tasks.add_task(process_message, data)
    
    # Return 200 immediately so Facebook doesn't retry
    return {"status": "ok"}


# Process the message in the background
def process_message(data: dict):
    try:
        # Extract Sender ID and message text
        message_payload = data["entry"][0]["messaging"][0]
        if "message" in message_payload and "text" in message_payload["message"]:
            sender_id = message_payload["sender"]["id"]
            message_text = message_payload["message"]["text"]

            # Process message with Gemini
            response_text = parse_message(message_text)

            # Build a reply string
            reply_text = f"Got it! You requested:\nDay: {response_text.get('day')}\n" \
                         f"Start: {response_text.get('start_time')}\nEnd: {response_text.get('end_time')}"

            send_message(sender_id, reply_text)

    except KeyError:
        print("No message payload found in the request.")
    except Exception as e:
        print(f"Error processing message: {e}")

# Send message to Gemini
def parse_message(user_message: str) -> dict:

    system_instruction = (
            "You are an expert scheduling assistant. Your task is to extract three pieces of "
            "information from the user's message: the 'day', 'start_time', and 'end_time' of a "
            "requested event. If any piece of information is missing or unclear, use the placeholder 'N/A'."
            "You must return the output in the requested JSON format."
        )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_message,
            config=types.GenerateContentConfig(
                temperature=0,
                system_instruction=system_instruction,
                # Specify the desired structured output format using the Pydantic schema
                response_mime_type="application/json",
                response_schema=TimeSlot,
            )
        )

        # Parse the JSON string from the response and return it as a Python dictionary
        extracted_data = json.loads(response.text)
        return extracted_data

    except Exception as e:
        print(f"Error during Gemini API call: {e}")
        # Return default structure on failure to prevent the main process from crashing
        return {"day": "N/A", "start_time": "N/A", "end_time": "N/A"}

 

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
