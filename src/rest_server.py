import json
import os
import uuid

import pika
from epubcheck import EpubCheck
from flask import Flask, jsonify, request
from google.cloud import storage

from constants import (GCS_BUCKET_NAME, MAX_FILE_SIZE, RABBITMQ_HOST,
                       SPLITTER_QUEUE_NAME, UPLOAD_FOLDER, EVENT_TRACKER_QUEUE_NAME)
from messages import split_job, add_book
from utils import upload_to_gcs

# Create a Flask application instance
app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ---- Initialize Google Cloud Storage client -----
storage_client = storage.Client()

# ---- Initialize RabbitMQ client for job creation ----
connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
channel = connection.channel()

# ---- Queue to hold split jobs ----
channel.queue_declare(queue=SPLITTER_QUEUE_NAME)



# ---- API endpoint definitions -----

# Root endpoint for health check
@app.route("/")
def hello_puchki():
  return "Hello Puchki! :)"


# Upload enpoint receives books from the client and validates it.
# TODO: Store the book name in redis
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

# ---- Helper methods ----

# TODO: Move this validation logic to the front-end client.
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
  app.run(host="0.0.0.0", port=5000)
