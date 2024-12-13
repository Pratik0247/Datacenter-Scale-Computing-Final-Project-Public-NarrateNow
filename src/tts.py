import json
from tempfile import NamedTemporaryFile

import pika
from google.cloud import texttospeech

from constants import GCS_BUCKET_NAME, RABBITMQ_HOST, TTS_QUEUE_NAME, EVENT_TRACKER_QUEUE_NAME, RABBITMQ_PASSWORD, \
  RABBITMQ_USER
from messages import update_chunk_status, remove_chunk
from redis_ops import UPDATE_CHUNK_STATUS, REMOVE_CHUNK
from utils import download_file_from_gcs, upload_to_gcs

# ---- Initialize RabbitMQ client to pick split jobs ----
connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST, credentials=pika.PlainCredentials(username=RABBITMQ_USER, password=RABBITMQ_PASSWORD), heartbeat=3600))
channel = connection.channel()

# ---- Instantiate a client for the Text-to-Speech API ----
client = texttospeech.TextToSpeechClient()

# Function to convert text to speech and save as MP3
def text_to_speech(input_file_path:str, output_file_path:str):
  # Read the text from the local file
  with open(input_file_path, "r") as file:
    text_input = file.read()

  # Set up the text input to the API
  synthesis_input = texttospeech.SynthesisInput(text=text_input)

  # Configure the voice settings
  voice = texttospeech.VoiceSelectionParams(
    language_code="en-US",  # You can change this to any language you prefer
    ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,  # You can choose between MALE, FEMALE, or NEUTRAL
  )

  # Configure the audio output settings
  audio_config = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.MP3
  )

  # Call the Google Text-to-Speech API
  response = client.synthesize_speech(
    request={
      "input": synthesis_input,
      "voice": voice,
      "audio_config": audio_config,
    }
  )

  # Save the audio content to a file
  with open(output_file_path, "wb") as out:
    out.write(response.audio_content)

  print(f"Audio content written to file {output_file_path}")

def notify_event_tracker(operation, message):
  """
  Sends a message to the event tracker queue.
  :param operation: Operation type
  :param message: Message payload to send.
  """
  message["operation"] = operation
  channel.basic_publish(
    exchange="",
    routing_key=EVENT_TRACKER_QUEUE_NAME,
    body=json.dumps(message)
  )
  print(f"Notified event tracker: {operation} with message: {message}")

def process_job(book_uuid:str, chapter_uuid:str, chunk_index:int):
  """Downloads a chunk, converts it into audio and pushes the audio to GCS."""
  # Notify the event tracker service that the chunk is in progress.
  notify_event_tracker(UPDATE_CHUNK_STATUS, update_chunk_status(book_uuid, chapter_uuid, chunk_index, 'in_progress'))

  print(f"Processing TTS job: UUID={book_uuid}, Chapter={chapter_uuid}, Chunk={chunk_index}")

  # Define the address parameters for the chunk.
  source_blob_name = f"{book_uuid}/chunks/{chapter_uuid}/chunk_{chunk_index}.txt"  # e.g., chapter_001.txt

  # Use NamedTemporaryFile for automatic cleanup after processing
  with NamedTemporaryFile(delete=True) as temp_input:
    temp_input_path = temp_input.name
    download_file_from_gcs(GCS_BUCKET_NAME, source_blob_name, temp_input_path)

    with NamedTemporaryFile(delete=True) as temp_output:
      temp_output_path = temp_output.name

      # Convert the text to audio.
      text_to_speech(temp_input_path, temp_output_path)

      # Upload the audio to GCS
      destination_blob_name = f"{book_uuid}/chunks/{chapter_uuid}/audio/chunk_{chunk_index}.mp3"

      with open(temp_output_path, 'rb') as output_audio_file:
        upload_to_gcs(output_audio_file, GCS_BUCKET_NAME, destination_blob_name)

      # Notify the event tracker to remove a chunk from the list of chunks for its associated chapter.
      notify_event_tracker(REMOVE_CHUNK, remove_chunk(book_uuid, chapter_uuid, chunk_index))

      print(f"Finished processing TTS job: UUID={book_uuid}, Chapter={chapter_uuid}, Chunk={chunk_index}")

def callback(ch, method, properties, body):
  """
  Callback function for RabbitMQ messages.
  Parses the job and processes it.
  """
  try:
    job = json.loads(body)  # Parse the job as JSON
    book_uuid = job.get("book_uuid")
    chapter_uuid = job.get("chapter_uuid")
    chunk_index = job.get("chunk_index")

    if not book_uuid or not chapter_uuid or not chunk_index:
      raise ValueError("Invalid job message: missing 'book_uuid' or 'chapter_uuid' or 'chunk_index.")

    # Process the job
    process_job(book_uuid, chapter_uuid, chunk_index)

    # Acknowledge the message after successful processing
    ch.basic_ack(delivery_tag=method.delivery_tag)
  except Exception as e:
    print(f"Error processing job: {e}")
    # Reject the message and requeue for future processing
    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def start_service():
  # Set prefetch count to 1
  channel.basic_qos(prefetch_count=1)

  # ---- Queue to hold TTS jobs ----
  channel.queue_declare(queue=TTS_QUEUE_NAME)
  channel.queue_declare(queue=EVENT_TRACKER_QUEUE_NAME)

  # Set up RabbitMQ consumer
  channel.basic_consume(queue=TTS_QUEUE_NAME, on_message_callback=callback)
  print("Waiting for TTS jobs.")

  # ---- Keep the program running ----
  try:
    channel.start_consuming()
  except KeyboardInterrupt:
    print("Stopping the TTS program...")
    channel.stop_consuming()
    connection.close()

if __name__ == "__main__":
  start_service()
