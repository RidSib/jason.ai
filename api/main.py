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
# Change this import to use psycopg2-binary
import psycopg2.extras

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

def connect_to_db():
    """Connect to the Neon PostgreSQL database and return connection object"""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("WARNING: DATABASE_URL environment variable is not set")
        raise ValueError("DATABASE_URL environment variable is not set")
    
    try:
        print(f"Connecting to database...")
        conn = psycopg2.connect(db_url)
        print("Connection established successfully!")
        return conn
    except Exception as e:
        print(f"Database connection error: {str(e)}")
        raise

@app.get('/tools/events')
async def tool_events(request: Request):
    conn = None
    cursor = None
    try:
        # Connect to the database
        conn = connect_to_db()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Query all events from the events table
        cursor.execute("SELECT * FROM events")
        events = cursor.fetchall()
        
        # Convert to list of dictionaries for JSON response
        result = []
        for event in events:
            result.append(dict(event))
        
        return {"events": result}
    
    except Exception as e:
        print(f"Error in tool_events: {str(e)}")
        traceback.print_exc()
        return {"error": f"Database operation failed: {str(e)}"}
        
    finally:
        # Always close cursor and connection
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if conn:
            try:
                conn.close()
            except:
                pass

@app.post('/tools/bookings')
async def tool_bookings(request: Request):
    conn = None
    cursor = None
    try:
        # Get the booking data from the request
        data = await request.json()
        user_name = data.get('user_name')
        event_id = data.get('event_id')
        
        if not user_name or not event_id:
            return {"error": "Both user_name and event_id are required"}
        
        # Connect to the database
        conn = connect_to_db()
        cursor = conn.cursor()
    
        # Look up user_id from users table based on user_name
        cursor.execute("SELECT person_id FROM users WHERE name = %s", (user_name,))
        user_result = cursor.fetchone()
        
        if not user_result:
            return {"error": f"User with name '{user_name}' not found"}
        
        user_id = user_result[0]
        
        # Insert the new booking into the bookings table
        cursor.execute(
            "INSERT INTO bookings (person_id, event_id) VALUES (%s, %s)",
            (user_id, event_id)
        )
        
        # Commit the transaction
        conn.commit()
        
        return {"success": True, "person_id": user_id, "event_id": event_id}
    
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except:
                pass
        print(f"Error in tool_bookings: {str(e)}")
        traceback.print_exc()
        return {"error": f"Database operation failed: {str(e)}"}
        
    finally:
        # Always close cursor and connection - fixed the double close issue
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if conn:
            try:
                conn.close()
            except:
                pass
        # Remove these lines to avoid double-closing
        # cursor.close()
        # conn.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)