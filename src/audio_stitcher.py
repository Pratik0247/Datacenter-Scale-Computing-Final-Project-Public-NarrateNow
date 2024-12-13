import json
import os

import pika
from pydub import AudioSegment

from constants import GCS_BUCKET_NAME, RABBITMQ_HOST, EVENT_TRACKER_QUEUE_NAME, STITCH_QUEUE_NAME, RABBITMQ_PASSWORD, \
  RABBITMQ_USER
from messages import remove_chapter
from redis_ops import REMOVE_CHAPTER
from utils import download_folder_from_gcs, upload_to_gcs

# ---- Initialize RabbitMQ client to pick split jobs ----
# connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
# channel = connection.channel()

# Set prefetch count to 1
# channel.basic_qos(prefetch_count=1)

# ---- Queue to hold Stitch jobs ----
# channel.queue_declare(queue=STITCH_QUEUE_NAME)
# channel.queue_declare(queue=EVENT_TRACKER_QUEUE_NAME)

connection = pika.BlockingConnection(
  pika.ConnectionParameters(
    RABBITMQ_HOST,
    credentials=pika.PlainCredentials(
      username=RABBITMQ_USER,
      password=RABBITMQ_PASSWORD)
  )
)
channel = connection.channel()

def notify_event_tracker(operation, message):
  """
  Sends a message to the event tracker queue.
  :param operation: Operation type (e.g., 'UPDATE_CHAPTER_STATUS', 'ADD_CHUNK').
  :param message: Message payload to send.
  """
  channel.basic_publish(
    exchange="",
    routing_key=EVENT_TRACKER_QUEUE_NAME,
    body=json.dumps(message)
  )
  print(f"Notified event tracker: {operation} with message: {message}")

def stitch_chunks(chunk_files):
  print("Stitching audio files...")
  combined_audio = AudioSegment.empty()
  for chunk_file in chunk_files:
    audio_segment = AudioSegment.from_file(chunk_file)
    combined_audio += audio_segment
    print(f"Stitched {chunk_file} into the output.")
  return combined_audio


def cleanup_temp_files(output_local_path, temp_input_dir):
  """Cleans up temporary files and directories."""
  try:
    for file in os.listdir(temp_input_dir):
      path = os.path.join(temp_input_dir, file)
      if os.path.exists(path):
        os.remove(path)
    os.rmdir(temp_input_dir)
    print("Temporary files cleaned up.")

    # Ensure local output file is removed (if it exists)
    if os.path.exists(output_local_path):
      os.remove(output_local_path)
      print(f"Local output file {output_local_path} cleaned up.")
  except Exception as cleanup_error:
    print(f"Error during cleanup: {cleanup_error}")


def stitch_audio_files(bucket_name, input_folder_prefix, output_file_gcs_path):
  """
  Stitches all chunk audio files from a GCS folder into a single audio file and uploads the result back to GCS.

  :param bucket_name: Name of the GCS bucket.
  :param input_folder_prefix: Prefix for the folder in GCS containing the audio chunks (e.g., "book123/chapter1/chunks/").
  :param output_file_gcs_path: Path in GCS to store the stitched audio file (e.g., "book123/chapter1/output.mp3").
  """

  # Temporary local directory for storing downloaded chunk files
  temp_input_dir = "temp_audio_files"
  output_local_path = os.path.join(temp_input_dir, "output.mp3")
  try:
    os.makedirs(temp_input_dir, exist_ok=True)
    # Download all files from the GCS folder to the local temp directory
    print(f"Downloading files from GCS folder: {input_folder_prefix}...")
    download_folder_from_gcs(bucket_name, input_folder_prefix, temp_input_dir)

    # Get all downloaded chunk files in the local temp directory
    chunk_files = sorted(
      [os.path.join(temp_input_dir, f) for f in os.listdir(temp_input_dir) if f.endswith(".mp3")],
      key=lambda x: int(os.path.basename(x).replace("chunk_", "").replace(".mp3", ""))
    )

    if not chunk_files:
      print("No audio chunks found in the GCS folder.")

    # Stitch all audio chunks into a single audio file
    combined_audio = stitch_chunks(chunk_files)

    # Export the combined audio to a temporary local file
    combined_audio.export(output_local_path, format="mp3")
    print(f"Stitched audio saved locally at {output_local_path}")

    # Upload the stitched audio file back to GCS
    print(f"Uploading stitched audio to GCS: {output_file_gcs_path}")
    with open(output_local_path, "rb") as output_file:
      upload_to_gcs(output_file, bucket_name, output_file_gcs_path)

    print(f"Stitched audio successfully uploaded to {output_file_gcs_path}")
  except Exception as e:
    print(f"Error in audio stitching process: {e}")
    raise
  # finally:
  #   # Cleanup temporary files
  #   cleanup_temp_files(output_local_path, temp_input_dir)

def process_job(book_uuid:str, chapter_uuid:str):
  print(f"Processing Audio Stitch job: UUID={book_uuid}, Chapter={chapter_uuid}")

  # Define the address of the source folder containing the chunks.
  source_folder_address = f"{book_uuid}/chunks/{chapter_uuid}/audio"

  # define the output folder where the audio should be stored.
  destination_file_address = f"{book_uuid}/audio/{chapter_uuid}.mp3"

  stitch_audio_files(GCS_BUCKET_NAME, source_folder_address, destination_file_address)

  # Remove the chapter from the book's tracking set
  notify_event_tracker(REMOVE_CHAPTER, remove_chapter(book_uuid, chapter_uuid))

def callback(ch, method, properties, body):
  """
  Callback function for RabbitMQ messages.
  Parses the job and processes it.
  """
  try:
    job = json.loads(body)  # Parse the job as JSON
    book_uuid = job.get("book_uuid")
    chapter_uuid = job.get("chapter_uuid")

    if not book_uuid or not chapter_uuid:
      raise ValueError("Invalid job message: missing 'book_uuid' or 'chapter_uuid'.")

    process_job(book_uuid, chapter_uuid)
    # Acknowledge the message after successful processing
    ch.basic_ack(delivery_tag=method.delivery_tag)
  except Exception as e:
    print(f"Error processing job: {e}")
    # Reject the message and requeue for future processing
    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def start_service():
  """
  Initializes RabbitMQ connections and starts consuming messages.
  """
  channel.queue_declare(queue=STITCH_QUEUE_NAME)
  channel.queue_declare(queue=EVENT_TRACKER_QUEUE_NAME)

  channel.basic_qos(prefetch_count=1)

  channel.basic_consume(queue=STITCH_QUEUE_NAME, on_message_callback=callback)
  print("Starting the audio stitcher service...")
  channel.start_consuming()

if __name__ == "__main__":
  start_service()