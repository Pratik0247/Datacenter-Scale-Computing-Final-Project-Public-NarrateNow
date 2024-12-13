import json
import os
import uuid

import pika
import redis
from epubcheck import EpubCheck
from flask import Flask, jsonify, request, send_file

from constants import (GCS_BUCKET_NAME, MAX_FILE_SIZE, RABBITMQ_HOST,
                       SPLITTER_QUEUE_NAME, UPLOAD_FOLDER, EVENT_TRACKER_QUEUE_NAME, RABBITMQ_PASSWORD, RABBITMQ_USER,
                       REDIS_HOST, REDIS_PORT)
from messages import split_job, add_book
from utils import upload_to_gcs, download_file_from_gcs

# Create a Flask application instance
app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ---- Initialize Redis Client -----
redis_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


# ---- Initialize RabbitMQ client for job creation ----
connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST, credentials=pika.PlainCredentials(username=RABBITMQ_USER, password=RABBITMQ_PASSWORD), heartbeat=3600))
channel = connection.channel()

# ---- Queue to hold split jobs ----
channel.queue_declare(queue=SPLITTER_QUEUE_NAME)
channel.queue_declare(queue=EVENT_TRACKER_QUEUE_NAME)

# ---- API endpoint definitions -----

# Root endpoint for health check
@app.route("/")
def hello_puchki():
  return "Hello Puchki! :)"

@app.route("/health", methods=["GET"])
def health_check():
    return "OK", 200

@app.route("/ready", methods=["GET"])
def readiness_check():
    return "READY", 200


# Upload enpoint receives books from the client and validates it.
@app.route("/upload", methods=["POST"])
def upload():
  if "file" not in request.files:
    return jsonify({"error": "No file part"}), 400

  file = request.files["file"]

  if file.filename == "":
    return jsonify({"error": "No selected file"}), 400

  if file.content_type != "application/epub+zip":
    return jsonify({"error": "File is not an EPUB"}), 400

  is_valid, message = validate_epub(file)

  if is_valid:
    try:
      book_uuid = str(uuid.uuid4())

      # Define GCS path using the single UUID
      gcs_path = f"{book_uuid}/books/{book_uuid}.epub"

      # Save the validated file to GCS
      upload_to_gcs(file, GCS_BUCKET_NAME, gcs_path)

      # Notify event tracker service about the new book.
      notify_new_book(book_uuid)

      # Publish a message to the splitter queue for the splitter to start processing the book.
      enqueue_splitter_job(book_uuid)

      # Return response to client.
      return (
        jsonify(
          {
            "message": "Valid EPUB file uploaded successfully",
            "job_id": book_uuid,  # Return the single UUID
          }
        ),
        200,
      )
    except Exception as e:
      return jsonify({"error": f"Failed to upload to GCS: {e}"}), 500
  else:
    return jsonify({"error": message}), 400

# Endpoint to fetch job status
@app.route("/status/<book_uuid>", methods=["GET"])
def get_job_status(book_uuid):
  try:
    # Get book status
    book_status = redis_client.get(f"status:book:{book_uuid}")
    if not book_status:
      return jsonify({"error": "Job ID not found"}), 404

    # Get total and completed chapters
    total_chapters = redis_client.get(f"book:{book_uuid}:total_chapters") or 0
    completed_chapters = redis_client.get(f"book:{book_uuid}:completed_chapters") or 0

    # Fetch chapters
    chapters_key = f"book:{book_uuid}:chapters"
    chapter_ids = redis_client.smembers(chapters_key)

    chapters = []
    for chapter_id in chapter_ids:
      chapter_status = redis_client.get(f"status:chapter:{chapter_id}")
      chapters.append({"chapter_id": chapter_id, "status": chapter_status})

    return jsonify({
      "job_id": book_uuid,
      "status": book_status,
      "total_chapters": int(total_chapters),
      "completed_chapters": int(completed_chapters),
      "chapters": chapters
    }), 200
  except Exception as e:
    return jsonify({"error": f"Failed to fetch status: {e}"}), 500

# Endpoint to list chapters for a job
@app.route("/chapters/<book_uuid>", methods=["GET"])
def list_chapters(book_uuid):
  try:
    # Fetch chapters for the book
    chapters_key = f"book:{book_uuid}:chapters"
    chapter_ids = redis_client.smembers(chapters_key)

    if not chapter_ids:
      return jsonify({"error": "No chapters found for this job"}), 404

    chapters = []
    for chapter_id in chapter_ids:
      chapter_status = redis_client.get(f"status:chapter:{chapter_id}")
      chapters.append({"chapter_id": chapter_id, "status": chapter_status})

    return jsonify({"job_id": book_uuid, "chapters": chapters}), 200
  except Exception as e:
    return jsonify({"error": f"Failed to list chapters: {e}"}), 500


# Endpoint to fetch chapter title by chapter UUID
@app.route("/chapter/<chapter_uuid>/title", methods=["GET"])
def get_chapter_title(chapter_uuid):
  """
  Fetch the title of a chapter using its UUID.
  """
  try:
    # Redis key for the chapter's metadata
    chapter_key = f"chapter:{chapter_uuid}"

    # Fetch the chapter title from Redis
    chapter_title = redis_client.hget(chapter_key, "title")

    if not chapter_title:
      return jsonify({"error": "Chapter title not found"}), 404

    return jsonify({
      "chapter_uuid": chapter_uuid,
      "title": chapter_title
    }), 200
  except Exception as e:
    return jsonify({"error": f"Failed to fetch chapter title: {e}"}), 500

@app.route("/download/<book_uuid>/<chapter_id>", methods=["GET"])
def download_chapter(book_uuid, chapter_id):
  """
  Endpoint to download a chapter audio file by its UUID from GCS.
  """
  # Define the GCS path for the chapter audio
  source_blob_name = f"{book_uuid}/audio/{chapter_id}.mp3"
  destination_file_name = f"/tmp/{chapter_id}.mp3"
  try:
    # Download the file from GCS
    download_file_from_gcs(GCS_BUCKET_NAME, source_blob_name, destination_file_name)

    # Check if the file exists locally
    if not os.path.exists(destination_file_name):
      return jsonify({"error": "Audio file not found in GCS"}), 404

    # Serve the file to the client without specifying a filename
    return send_file(destination_file_name, as_attachment=True)

  except Exception as e:
    return jsonify({"error": f"Failed to download chapter: {e}"}), 500
  finally:
    # Clean up the temporary file
    if os.path.exists(destination_file_name):
      os.remove(destination_file_name)

# ---- Helper methods ----
def validate_epub(file):
  # Check file size
  file.seek(0, os.SEEK_END)
  file_size = file.tell()
  file.seek(0)  # Reset file pointer

  if file_size > MAX_FILE_SIZE:
    return (
      False,
      f"File size exceeds 10 MB (actual size: {file_size / (1024 * 1024):.2f} MB)",
    )

  # Save the file temporarily
  os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
  temp_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
  file.save(temp_path)

  # # Validate EPUB
  checker = EpubCheck(temp_path)

  # Remove the temporary file
  os.remove(temp_path)

  if checker.valid:
    return True, "Valid EPUB file under 10 MB"
  else:
    return False, f"Invalid EPUB file: {checker.messages}"


def enqueue_splitter_job(book_uuid):
  """
  Publishes a new message to the RabbitMQ splitter queue.
  :param book_uuid: Unique identifier for the book.
  """
  try:
    message = split_job(book_uuid)
    # Publish the message to the RabbitMQ queue
    channel.basic_publish(
      exchange="",
      routing_key=SPLITTER_QUEUE_NAME,
      body=json.dumps(message),  # Convert message to a string for publishing
    )
  except Exception as e:
    raise RuntimeError(f"Failed to enqueue job in splitter queue: {e}")

def notify_new_book(book_uuid):
  try:
    message = add_book(book_uuid)
    # Publish the message to the RabbitMQ queue
    channel.basic_publish(
      exchange="",
      routing_key=EVENT_TRACKER_QUEUE_NAME,
      body=json.dumps(message),  # Convert message to a string for publishing
    )
  except Exception as e:
    raise RuntimeError(f"Failed to notify event tracker about new book entry.: {e}")


# ---- Main ----
# Run the Flask server
if __name__ == "__main__":
  # Host set to '0.0.0.0' to allow external access
  app.run(host="0.0.0.0", port=8000)
