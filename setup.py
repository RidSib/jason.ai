import os
import time
import io
from elevenlabs.client import ElevenLabs
from dotenv import load_dotenv
from pydub import AudioSegment
from pydub.playback import play
 
# Load environment variables first
load_dotenv()

client = ElevenLabs(
  api_key=os.environ.get("ELEVENLABS_API_KEY"),
)

def main():
    print("Starting...")
    
    audio_stream = client.text_to_speech.convert_as_stream(
        text="This is a test",
        voice_id="JBFqnCBsd6RMkjVDRZzb",
        model_id="eleven_multilingual_v2"
    )
    
    # Collect all audio chunks
    audio_data = b''
    for chunk in audio_stream:
        if isinstance(chunk, bytes):
            audio_data += chunk
    
    # Play audio using pydub
    if audio_data:
        audio = AudioSegment.from_file(io.BytesIO(audio_data), format="mp3")
        play(audio)


if __name__ == "__main__":
    main()