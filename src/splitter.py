import html
import json
import os
import re
import tempfile
import uuid

import pika
from bs4 import BeautifulSoup
from ebooklib import ITEM_DOCUMENT, epub

from constants import (CHUNKER_QUEUE_NAME, DOWNLOAD_FOLDER,
                       RABBITMQ_HOST, SPLITTER_QUEUE_NAME, GCS_BUCKET_NAME, EVENT_TRACKER_QUEUE_NAME, RABBITMQ_PASSWORD,
                       RABBITMQ_USER)
from messages import add_chapter, update_book_status, chunker_job
from utils import download_file_from_gcs, upload_to_gcs

# ---- Initialize RabbitMQ client to pick split jobs ----
connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST, credentials=pika.PlainCredentials(username=RABBITMQ_USER, password=RABBITMQ_PASSWORD)))
channel = connection.channel()



# ---- Callback function to process messages ----
def process_split_job(ch, method, properties, body):
  """
  Callback function to process jobs from the RabbitMQ queue.

  :param ch: RabbitMQ channel
  :param method: RabbitMQ delivery method
  :param properties: RabbitMQ message properties
  :param body: The message body (job parameters)
  """

  try:
    # Parse the message
    job = json.loads(body)

    # Extract job parameters
    book_uuid = job.get('book_uuid')
    book_path = f"{book_uuid}/books/{book_uuid}.epub"

    # Log the job parameters
    print(f"Processing Job:")
    print(f"  Job UUID: {book_uuid}")
    print(f"  Bucket Name: {GCS_BUCKET_NAME}")
    print(f"  Book Path: {book_path}")

    # update_book_status(book_uuid, 'processing')

    # Download the file from GCS
    temp_download_dir = f"{DOWNLOAD_FOLDER}_splitter"
    os.makedirs(temp_download_dir, exist_ok = True)
    local_file_path = os.path.join(temp_download_dir, f"{book_uuid}.epub")
    download_file_from_gcs(GCS_BUCKET_NAME, book_path, local_file_path)
    print(f"File downloaded successfully for Job UUID: {book_uuid}")

    # Split the book into chapters and upload them to GCS
    split_book_into_chapters(local_file_path, GCS_BUCKET_NAME, book_uuid)

    # Acknowledge the message after successful processing
    ch.basic_ack(delivery_tag=method.delivery_tag)
  except Exception as e:
    print(f"Error processing job: {e}")
    # Reject the message and requeue it
    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

# ---- Book Splitting Logic ----
def split_book_into_chapters(epub_file, bucket_name, book_uuid):
  """
  Splits an EPUB file into individual chapters and uploads them to GCS.

  :param epub_file: Path to the EPUB file
  :param bucket_name: Name of the GCS bucket
  :param book_uuid: UUID of the job in process
  """
  try:
    # Notify the event tracker that the status of the book is now 'in_progress'
    notify_event_tracker(update_book_status(book_uuid, "in_progress"))

    book = epub.read_epub(epub_file)
    chapter_count = 0

    for item in book.get_items():
      if item.get_type() == ITEM_DOCUMENT:
        soup = BeautifulSoup(item.get_body_content(), 'html.parser')

        # Remove script and style tags
        for tag in soup(['script', 'style', 'span', 'div']):
          tag.decompose()

        # Preserve paragraph breaks and handle drop caps
        paragraphs = []
        for paragraph in soup.find_all('p'):
          # Handle dropcap specifically
          dropcap_span = paragraph.find('span', class_='dropcap')
          if dropcap_span:
            dropcap = dropcap_span.get_text(strip=True)
            dropcap_span.extract()  # Remove dropcap to avoid duplication
            paragraph_text = f"{dropcap}{paragraph.get_text(strip=True)}"
            # Combine dropcap with the rest of the paragraph text
            paragraph_text = dropcap + paragraph.get_text(strip=True)
          else:
            paragraph_text = paragraph.get_text(strip=True)

          paragraphs.append(paragraph_text)

        # Join paragraphs with double newlines
        chapter_text = "\n\n".join(paragraphs)

        # Merge hyphenated words across lines
        chapter_text = re.sub(r'-\n', '', chapter_text)

        # Decode HTML entities and clean up text
        chapter_text = html.unescape(chapter_text).replace('\xa0', ' ')

        # Skip empty chapters
        if not chapter_text:
          continue

        # chapter_title = f"Chapter_{chapter_count:02}"
        raw_title = item.get_name() or f"Chapter_{chapter_count + 1:02}"
        leaf_title = os.path.basename(raw_title)  # Get the file name only
        chapter_title, _ = os.path.splitext(leaf_title)  # Strip extensions like .html
        chapter_title = re.sub(r'[^\w\s-]', '_', chapter_title)  # Replace special characters

        if is_metadata(chapter_title, chapter_text):
          print(f"Skipping metadata chapter: {chapter_title}")
          continue

        chapter_count += 1
        chapter_uuid = str(uuid.uuid4())
        # Destination path in GCS
        destination_blob_name = f"{book_uuid}/chapters/{chapter_uuid}.txt"

        # Create a temporary file for the chapter
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as temp_file:
          temp_file.write(chapter_text.encode('utf-8'))
          temp_file.flush()  # Ensure all data is written to the file
          temp_file_path = temp_file.name

        # Upload the chapter text to GCS
        try:
          # Open the temporary file as a binary file
          with open(temp_file_path, 'rb') as file_obj:
            upload_to_gcs(file_obj, bucket_name, destination_blob_name)
        except Exception as e:
          print(f"Error uploading chapter {chapter_title} (uuid: {chapter_uuid}) to GCS:\nError:\n{e}")
        finally:
          os.remove(temp_file_path)  # Clean up temporary file

        # Notify the event tracker about the chapter we just uploaded to GCS
        notify_event_tracker(add_chapter(book_uuid, chapter_uuid, chapter_title))

        # Add a new job into the chunker queue.
        enqueue_chunker_job(book_uuid, chapter_uuid)

    if chapter_count == 0:
      print("No chapters found in the EPUB file.")
    else:
      print(f"Book split into {chapter_count} chapters and uploaded to GCS.")

  except Exception as e:
    print(f"Error splitting book into chapters: {e}")
    raise

# ---------------------------------------------------------------------------------------------------------------------

def notify_event_tracker(message):
  try:
    # Publish the message to the RabbitMQ queue
    channel.basic_publish(
      exchange="",
      routing_key=EVENT_TRACKER_QUEUE_NAME,
      body=json.dumps(message),
    )
  except Exception as e:
    raise RuntimeError(f"Failed to notify event tracker with message: {message}\nError:\n{e}")

# ---------------------------------------------------------------------------------------------------------------------

def enqueue_chunker_job(book_uuid, chapter_title):
  try:
    message = chunker_job(book_uuid, chapter_title)
    # Publish the message to the RabbitMQ queue
    channel.basic_publish(
      exchange="",
      routing_key=CHUNKER_QUEUE_NAME,
      body=json.dumps(message)
    )
  except Exception as e:
    raise RuntimeError(f"Failed to enqueue job in chunker queue: {e}")


# ---------------------------------------------------------------------------------------------------------------------

def is_metadata(chapter_title, chapter_text):
  """
  Determines whether a chapter is metadata or actual content.

  :param chapter_title: The title of the chapter
  :param chapter_text: The full text of the chapter
  :return: True if the chapter is metadata, False otherwise
  """
  # Normalize title and text for comparison
  title_lower = chapter_title.lower() if chapter_title else ""
  text_lower = chapter_text.lower()

  # Comprehensive list of metadata keywords
  METADATA_KEYWORDS = [
    "table of contents", "toc", "index", "contents", "navigation",
    "list of figures", "list of tables", "catalog", "foreword", "preface",
    "acknowledgments", "introduction", "prologue", "epilogue", "afterword",
    "notes", "appendix", "dedication", "about the author", "about this book",
    "introduction to the author", "copyright", "all rights reserved",
    "terms of use", "disclaimer", "license", "publishing", "publisher",
    "isbn", "edition", "version", "revision history", "errata", "change log",
    "references", "bibliography", "works cited", "citations", "further reading",
    "footnotes", "endnotes", "praise for", "reviews", "excerpt", "sample chapter",
    "advance praise", "preview", "teaser", "coming next", "blank page", "front matter",
    "back matter", "half title", "title page", "colophon", "cover", "spine",
    "glossary", "abbreviations", "acronyms", "key terms", "index of terms",
    "dedication", "in memoriam", "by the same author", "also by", "chapter",
    "part", "section", "contents of chapter", "overview of chapter"
  ]

  # Check if title matches any metadata keywords
  if any(keyword in title_lower for keyword in METADATA_KEYWORDS):
    return True

  # Check if the text is too short to be meaningful
  if len(text_lower.strip()) < 100:  # Adjust threshold as needed
    return True

  # Check for high non-alphanumeric character ratio (common in metadata)
  non_alnum_ratio = sum(1 for char in text_lower if not char.isalnum()) / max(len(text_lower), 1)
  if non_alnum_ratio > 0.3:  # Adjust threshold based on content
    return True

  # Check for excessive hyperlinks (common in tables of contents)
  if text_lower.count("http") > 5 or text_lower.count("www.") > 5:
    return True

  # If none of the conditions are met, it's likely content
  return False

def start_service():
  # ---- Queue to hold split jobs ----
  channel.queue_declare(queue=SPLITTER_QUEUE_NAME)
  channel.queue_declare(queue = CHUNKER_QUEUE_NAME)

  # ---- Start consuming messages from the queue ----
  print(f"Listening for messages on queue '{SPLITTER_QUEUE_NAME}'...")
  channel.basic_consume(
    queue=SPLITTER_QUEUE_NAME,
    on_message_callback=process_split_job
  )

  # ---- Keep the program running ----
  try:
    channel.start_consuming()
  except KeyboardInterrupt:
    print("Stopping the splitter program...")
    channel.stop_consuming()
    connection.close()

if __name__ == "__main__":
  start_service()