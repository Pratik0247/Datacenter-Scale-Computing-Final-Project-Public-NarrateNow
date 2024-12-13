import json
import os
from io import BytesIO

import pika

from constants import CHUNKER_QUEUE_NAME, GCS_BUCKET_NAME, RABBITMQ_HOST, TTS_QUEUE_NAME, EVENT_TRACKER_QUEUE_NAME, \
  RABBITMQ_PASSWORD, RABBITMQ_USER
from messages import tts_job, update_chapter_status, add_chunk
from redis_ops import ADD_CHUNK, UPDATE_CHAPTER_STATUS
from utils import download_file_from_gcs, upload_to_gcs

# ---- Initialize RabbitMQ client to pick split jobs ----
connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST, credentials=pika.PlainCredentials(username=RABBITMQ_USER, password=RABBITMQ_PASSWORD)))
channel = connection.channel()

def read_text_from_file(file_path):
  """Reads text content from the given file."""
  if not os.path.exists(file_path):
    raise FileNotFoundError(f"The file {file_path} does not exist.")
  with open(file_path, 'r', encoding='utf-8') as file:
    return file.read()

def split_text_into_chunks(text, max_chunk_size=5000):
  """
  Splits the input text into chunks of size less than max_chunk_size bytes,
  ensuring the split does not occur mid-sentence or mid-paragraph.
  """
  chunks = []
  current_chunk = ""
  paragraphs = text.split('\n\n')  # Split text into paragraphs

  for paragraph in paragraphs:
    sentences = paragraph.split('. ')  # Split paragraph into sentences
    for sentence in sentences:
      sentence += '. ' if not sentence.endswith('. ') else ''
      if len(current_chunk.encode('utf-8')) + len(sentence.encode('utf-8')) < max_chunk_size:
        current_chunk += sentence
      else:
        chunks.append(current_chunk.strip())
        current_chunk = sentence
    # Append paragraph separator
    current_chunk += '\n\n'

  # Add the last chunk if not empty
  if current_chunk.strip():
    chunks.append(current_chunk.strip())

  return chunks

def notify_event_tracker(operation, message):
  """
  Sends a message to the event tracker queue.
  :param operation: Operation type (e.g., 'UPDATE_CHAPTER_STATUS', 'ADD_CHUNK').
  :param message: Message payload to send.
  """
  message["operation"] = operation
  channel.basic_publish(
    exchange="",
    routing_key=EVENT_TRACKER_QUEUE_NAME,
    body=json.dumps(message)
  )
  print(f"Notified event tracker: {operation} with message: {message}")

def enqueue_tts_job(book_uuid:str, chapter_uuid:str, chunk_index:int):
  try:
    message = tts_job(book_uuid, chapter_uuid, chunk_index)
    # Publish the message to the RabbitMQ queue
    channel.basic_publish(
      exchange="",
      routing_key=TTS_QUEUE_NAME,
      body=json.dumps(message)
    )
    print(f"Added TTS job for book: {book_uuid}, chapter: {chapter_uuid}, chunk {chunk_index}.")
  except Exception as e:
    raise RuntimeError(f"Failed to enqueue job in TTS queue: {e}")

def process_job(book_uuid, chapter_uuid):
  """
  Processes a single job by downloading, chunking, and uploading a chapter file.

  :param book_uuid: Unique identifier for the book under process.
  :param chapter_uuid: Unique identifier of the chapter to process
  """
  # Derive source and temporary file paths
  bucket_name = GCS_BUCKET_NAME

  # TODO: Notify event tracker that a chapter is under process.
  notify_event_tracker(UPDATE_CHAPTER_STATUS, update_chapter_status(book_uuid, chapter_uuid, 'in_progress'))

  source_blob_name = f"{book_uuid}/chapters/{chapter_uuid}.txt"  # e.g., chapter_001.txt
  temp_file_path = "temp_input.txt"  # Temporary file to save the downloaded content

  # Download file from GCS
  download_file_from_gcs(bucket_name, source_blob_name, temp_file_path)

  # Read and process the text file
  text = read_text_from_file(temp_file_path)
  chunks = split_text_into_chunks(text)

  for index, chunk in enumerate(chunks, start=1):
    destination_blob_name = f"{book_uuid}/chunks/{chapter_uuid}/chunk_{index}.txt"
    with BytesIO(chunk.encode('utf-8')) as file_like:
      # Add the chunk to GCS
      upload_to_gcs(file_like, bucket_name, destination_blob_name)
    print(f"Uploaded chunk {index} to {destination_blob_name} on GCS")

    # Notify the event tracker that a new chunk has been under the given chapter.
    notify_event_tracker(ADD_CHUNK, add_chunk(book_uuid, chapter_uuid, index))

    # Add a job for the TTS to process the given chunk.
    enqueue_tts_job(book_uuid, chapter_uuid, index)

  print(f"Chapter {chapter_uuid} has been split into {len(chunks)} chunks and uploaded to GCS.")

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

    print(f"Processing job: UUID={book_uuid}, Chapter={chapter_uuid}")
    process_job(book_uuid, chapter_uuid)  # Process the job

    # Acknowledge the message
    ch.basic_ack(delivery_tag=method.delivery_tag)
  except Exception as e:
    print(f"Error processing job: {e}")
    # Reject the message and requeue for future processing
    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def start_service():
  # Set prefetch count to 1
  channel.basic_qos(prefetch_count=1)

  # ---- Queue to hold split jobs ----
  channel.queue_declare(queue=CHUNKER_QUEUE_NAME)
  channel.queue_declare(queue=TTS_QUEUE_NAME)
  channel.queue_declare(queue=EVENT_TRACKER_QUEUE_NAME)
  # Set up RabbitMQ consumer
  channel.basic_consume(queue=CHUNKER_QUEUE_NAME, on_message_callback=callback)

  print("Waiting for chunker jobs.")
  # ---- Keep the program running ----
  try:
    channel.start_consuming()
  except KeyboardInterrupt:
    print("Stopping the chunker program...")
    channel.stop_consuming()
    connection.close()

if __name__ == "__main__":
  start_service()