import os
import json
import traceback
from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse
from twilio.twiml.voice_response import VoiceResponse, Connect
from elevenlabs import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
from .twilio_audio_interface import TwilioAudioInterface
from starlette.websockets import WebSocketDisconnect
import pandas as pd

load_dotenv()

ELEVEN_LABS_AGENT_ID = os.getenv("ELEVENLABS_AGENT_ID")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Twilio-ElevenLabs Integration Server"}


@app.post("/twilio/inbound_call")
async def handle_incoming_call(request: Request):
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "Unknown")
    from_number = form_data.get("From", "Unknown")
    print(f"Incoming call: CallSid={call_sid}, From={from_number}")

    response = VoiceResponse()
    connect = Connect()
    connect.stream(url=f"wss://{request.url.hostname}/media-stream")
    response.append(connect)
    return HTMLResponse(content=str(response), media_type="application/xml")


@app.websocket("/media-stream") 
async def handle_media_stream(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket connection opened")

    audio_interface = TwilioAudioInterface(websocket)
    eleven_labs_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

    try:
        conversation = Conversation(
            client=eleven_labs_client,
            agent_id=ELEVEN_LABS_AGENT_ID,
            requires_auth=True, # Security > Enable authentication
            audio_interface=audio_interface,
            callback_agent_response=lambda text: print(f"Agent: {text}"),
            callback_user_transcript=lambda text: print(f"User: {text}"),
        )

        conversation.start_session()
        print("Conversation started")

        async for message in websocket.iter_text():
            if not message:
                continue
            await audio_interface.handle_twilio_message(json.loads(message))

    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception:
        print("Error occurred in WebSocket handler:")
        traceback.print_exc()
    finally:
        try:
            conversation.end_session()
            conversation.wait_for_session_end()
            print("Conversation ended")
        except Exception:
            print("Error ending conversation session:")
            traceback.print_exc()

# Replace the WebSocket endpoint with a regular HTTP GET endpoint
@app.get('/tools/events')
async def tool_events():
    try:
        with open("events.csv", "r") as file:
            content = file.read()
        return {"requirements": content}
    except FileNotFoundError:
        return {"error": "requirements.txt not found"}

@app.post('/tools/bookings')
async def tool_bookings(request: Request):
    try:
        # Get the booking data from the request
        data = await request.json()
        user_name = data.get('user_name')
        event_id = data.get('event_id')
        
        if not user_name or not event_id:
            return {"error": "Both user_name and event_id are required"}
        
        # Look up user_id from users.csv based on user_name
        if not os.path.exists("users.csv"):
            return {"error": "Users database not found"}
        
        users_df = pd.read_csv("users.csv")
        
        # Find the user by name
        user_match = users_df[users_df['name'] == user_name]
        if user_match.empty:
            return {"error": f"User with name '{user_name}' not found"}
        
        user_id = user_match.iloc[0]['user_id']
        
        # Create the bookings file if it doesn't exist
        if not os.path.exists("bookings.csv"):
            df = pd.DataFrame(columns=["user_id", "event_id"])
            df.to_csv("bookings.csv", index=False)
        
        # Read existing bookings
        df = pd.read_csv("bookings.csv")
        
        # Create new booking entry
        new_booking = {
            "user_id": user_id,
            "event_id": event_id
        }
        
        # Append the new booking
        df = pd.concat([df, pd.DataFrame([new_booking])], ignore_index=True)
        
        # Save the updated bookings
        df.to_csv("bookings.csv", index=False)
        
        return {"success": True, "user_id": user_id, "event_id": event_id}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)