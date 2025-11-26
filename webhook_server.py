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
import shift_service

load_dotenv()

app = FastAPI()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
API_TOKEN = os.getenv("API_TOKEN")
FB_MESSAGER_API_URL = "https://graph.facebook.com/v24.0/me/messages"

# Map error codes to user-friendly messages
ERROR_MESSAGES = {
    shift_service.ERROR_INVALID_ACTION: "The action you requested is invalid. Please specify 'add' or 'delete'.",
    shift_service.ERROR_INVALID_NAME: "I couldn't find your name in the system. Please contact an admin.",
    shift_service.ERROR_INVALID_TIME: "The times you provided are invalid. Please use times between 9am and 6pm, and make sure the end time is after the start time.",
    shift_service.ERROR_ENTRY_EXISTS: "You already have a shift scheduled for this day. Please request to update it if needed.",
    shift_service.ERROR_DAY_LIMIT_REACHED: "Sorry, this day is already fully booked. Please choose another day.",
}

# Structure for JSON response from Gemini
class TimeSlot(BaseModel):
    action: str = Field(..., description="Action to be performed (e.g., add, delete)")
    day: str = Field(..., description="Day of the week")
    start_time: str = Field(..., description="Start time in 12-hour format with am/pm (e.g., 9am, 2pm)")
    end_time: str = Field(..., description="End time in 12-hour format with am/pm (e.g., 5pm, 11pm)")

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

            # Get name from sender ID
            name = get_user_name(sender_id)

            # Action tree
            if response_text.get('action') == 'add':
                reply_text = insert_shift(
                    name,
                    response_text.get('day'),
                    response_text.get('start_time'),
                    response_text.get('end_time')
                )
            elif response_text.get('action') == 'delete':
                reply_text = delete_shift(
                    name,
                    response_text.get('day')
                )
            else:
                error_msg = ERROR_MESSAGES.get(shift_service.ERROR_INVALID_ACTION, "Invalid action. Please specify 'add' or 'delete'.")
                reply_text = f"❌ {error_msg}"

            send_message(sender_id, reply_text)

    except KeyError:
        print("No message payload found in the request.")
    except Exception as e:
        print(f"Error processing message: {e}")

# Insert shift
def insert_shift(name, day, start_time, end_time):
    result = shift_service._insert_shift(name, day, start_time, end_time)
    
    # Generate appropriate response based on result
    if result == shift_service.UPDATE_SUCCESS:
        reply_text = (f"✅ All set, {name}! Your shift has been scheduled:\n"
                    f"📅 Day: {day}\n"
                    f"🕐 Start: {start_time}\n"
                    f"🕑 End: {end_time}")
    else:
        # Get user-friendly error message
        error_msg = ERROR_MESSAGES.get(result, "An unknown error occurred. Please try again.")
        reply_text = f"❌ {error_msg}"
    
    return reply_text

# Delete shift
def delete_shift(name, day):
    result = shift_service.delete_shift(name, day)
    
    # Generate appropriate response based on result
    if result == shift_service.DELETE_SUCCESS:
        reply_text = f"✅ Done, {name}! Your shift on {day} has been removed."
    else:
        error_msg = ERROR_MESSAGES.get(result, "An unknown error occurred. Please try again.")
        reply_text = f"❌ {error_msg}"
    
    return reply_text

# Get user's name from Facebook
def get_user_name(sender_id: str):
    url = f"https://graph.facebook.com/v24.0/{sender_id}"
    
    params = {
        "fields": "first_name",
        "access_token": API_TOKEN
    }
    
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        data = response.json()
        return data.get('first_name', 'there')
    else:
        print("Failed to get user info:", response.text)
        return "there"

# Send message to Gemini
def parse_message(user_message: str) -> dict:

    system_instruction = (
            "You are an expert scheduling assistant. Your task is to extract four pieces of "
            "information from the user's message: the 'day', 'start_time', 'end_time', and 'action' of a "
            "requested event. Times must be in 12-hour format with am/pm (e.g., '9am', '2pm', '5pm'). "
            "The action will either be 'add', or 'delete'. "
            "If any piece of information is missing or unclear, use the placeholder 'N/A'. "
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
