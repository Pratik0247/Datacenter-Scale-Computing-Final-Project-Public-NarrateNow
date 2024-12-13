import json

import pika
import redis

import redis_ops
from constants import REDIS_HOST, REDIS_PORT, STITCH_QUEUE_NAME, EVENT_TRACKER_QUEUE_NAME, RABBITMQ_HOST, \
  RABBITMQ_PASSWORD, RABBITMQ_USER
from messages import audio_stitch_job

ALLOWED_BOOK_STATUS = {
  'uploaded',
  'in_progress',
  'completed',
  'failed'
}

ALLOWED_CHAPTER_STATUS = {
  'uploaded',
  'in_progress',
  'completed',
  'failed'
}

ALLOWED_CHUNK_STATUS = {
  'queued',
  'in_progress',
  'completed',
  'failed'
}

# ---- Initialize Redis Client ----
redis_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# ---- Initialize RabbitMQ Connection ----
connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST, credentials=pika.PlainCredentials(username=RABBITMQ_USER, password=RABBITMQ_PASSWORD), heartbeat=3600))
channel = connection.channel()



# ---- Status Tracking Functions ----
def set_status(entity_type, entity_id, status):
  """
  Set the status of a book, chapter, or chunk.
  :param entity_type: Type of entity ('book', 'chapter', 'chunk').
  :param entity_id: Unique identifier for the entity.
  :param status: Status value (e.g., 'uploaded', 'processing', 'completed').
  """
  key = f"status:{entity_type}:{entity_id}"
  redis_client.set(key, status)
  print(f"Set {entity_type} {entity_id} status to '{status}'.")

def get_status(entity_type, entity_id):
  """
  Get the status of a book, chapter, or chunk.
  :param entity_type: Type of entity ('book', 'chapter', 'chunk').
  :param entity_id: Unique identifier for the entity.
  :return: Status value or None if not found.
  """
  key = f"status:{entity_type}:{entity_id}"
  status = redis_client.get(key)
  if status:
    print(f"Status for {entity_type} {entity_id}: {status}")
    return status
  else:
    print(f"No status found for {entity_type} {entity_id}.")
    return None

# ---- Error Logging ----
def log_error(entity_type, entity_id, error_message):
  """
  Log an error for a book, chapter, or chunk.
  :param entity_type: Type of entity ('book', 'chapter', 'chunk').
  :param entity_id: Unique identifier for the entity.
  :param error_message: Error message to log.
  """
  key = f"errors:{entity_type}:{entity_id}"
  redis_client.rpush(key, error_message)
  print(f"Logged error for {entity_type} {entity_id}: {error_message}")

def get_errors(entity_type, entity_id):
  """
  Get all logged errors for a book, chapter, or chunk.
  :param entity_type: Type of entity ('book', 'chapter', 'chunk').
  :param entity_id: Unique identifier for the entity.
  :return: List of error messages.
  """
  key = f"errors:{entity_type}:{entity_id}"
  errors = redis_client.lrange(key, 0, -1)
  if errors:
    print(f"Errors for {entity_type} {entity_id}: {errors}")
    return errors
  else:
    print(f"No errors found for {entity_type} {entity_id}.")
    return []

# ---- Relationship Tracking ----
def add_relationship(parent_key, *child_ids):
  """
  Track a relationship (e.g., chapter in a book, chunk in a chapter).
  :param parent_key: Redis key for the parent entity.
  :param child_ids: IDs of the child entities to add.
  """
  redis_client.sadd(parent_key, *child_ids)
  print(f"Added {len(child_ids)} entities to {parent_key}.")

def get_relationship(parent_key):
  """
  Get all child entities of a parent.
  :param parent_key: Redis key for the parent entity.
  :return: Set of child IDs.
  """
  return redis_client.smembers(parent_key)


# ---- Implementation for different operations ----
def add_book_impl(job):
  """
  Handles the ADD_BOOK operation by storing the book ID in Redis.

  :param job: Dictionary containing book ID.
  """
  book_uuid = job.get("book_uuid")
  if not book_uuid:
    raise ValueError("Missing required fields: book_id.")

  # Set the initial status of the book
  set_status("book", book_uuid, "uploaded")

  print(f"Book added: {book_uuid}")

# ---------------------------------------------------------------------------------------------------------------------

def add_chapter_impl(job):
  book_uuid = job.get("book_uuid")
  chapter_uuid = job.get("chapter_uuid")
  chapter_title = job.get("chapter_title")

  if not book_uuid or not chapter_uuid or not chapter_title:
    raise ValueError("Missing required fields: book_uuid, chapter_uuid, chapter_title.")

  # Define the Redis key for the chapter title.
  chapter_key = f"chapter:{chapter_uuid}"

  # Store chapter title in a Redis hash set.
  redis_client.hset(chapter_key, mapping={
    "title": chapter_title
  })

  # Set the initial status of the chapter.
  set_status("chapter", chapter_uuid, "uploaded")

  # Add the chapter to the book's chapter set
  chapters_key = f"book:{book_uuid}:chapters"
  add_relationship(chapters_key, chapter_uuid)

  # Increment the total chapters count
  total_key = f"book:{book_uuid}:total_chapters"
  redis_client.incr(total_key)

  print(f"Chapter {chapter_title} (uuid: {chapter_uuid}) added under {book_uuid}")

# ---------------------------------------------------------------------------------------------------------------------

def add_chunk_impl(job):
  """
  Handles the ADD_CHUNK operation by adding a chunk to the chapter's tracking set.

  :param job: Dictionary containing book UUID, chapter UUID, and chunk index.
  """
  book_uuid = job.get("book_uuid")
  chapter_uuid = job.get("chapter_uuid")
  chunk_index = job.get("chunk_index")

  if not book_uuid or not chapter_uuid or not chunk_index:
    raise ValueError("Missing required fields: book_uuid, chapter_uuid, chunk_index.")

  # Set the initial status of the chunk using set_status
  set_status("chunk", f"{chapter_uuid}:chunk_{chunk_index}", "queued")

  # Define the Redis key for the chunks of this chapter
  chunks_key = f"chapter:{chapter_uuid}:chunks"
  # Add the chunk index to the chapter's chunk tracking set
  add_relationship(chunks_key, f"chunk_{chunk_index}")

  print(f"Chunk {chunk_index} added to chapter {chapter_uuid} under book {book_uuid}.")


# ---------------------------------------------------------------------------------------------------------------------

def update_book_status_impl(job):
  """
  Handles the UPDATE_BOOK_STATUS operation by updating the book ID in Redis.

  :param job: Dictionary containing book UUID and status.
  """
  book_uuid = job.get("book_uuid")
  status = job.get("status")

  if not book_uuid or not status:
    raise ValueError("Missing required fields: book_uuid, status.")

  if status not in ALLOWED_BOOK_STATUS:
    raise ValueError(f"Encountered a non-permissible value for book status: {status}")

  # Set the status of the book
  set_status("book", book_uuid, status)

  print(f"Book status updated for {book_uuid}: Status --> {status}")

# ---------------------------------------------------------------------------------------------------------------------

def update_chapter_status_impl(job):
  """
  Handles the UPDATE_CHAPTER_STATUS operation by updating the chapter's status.

  :param job: Dictionary containing chapter UUID, status, and book UUID.
  """
  book_uuid = job.get("book_uuid")
  chapter_uuid = job.get("chapter_uuid")
  status = job.get("status")

  if not chapter_uuid or not status or not book_uuid:
    raise ValueError("Missing required fields: chapter_uuid, status, book_uuid.")

  if status not in ALLOWED_CHAPTER_STATUS:
    raise ValueError(f"Encountered a non-permissible value for chapter status: {status}")

  # Update the chapter's status
  set_status("chapter", chapter_uuid, status)
  print(f"Chapter status updated for {chapter_uuid}: Status --> {status}")

  # Increment completed chapter count if status is 'completed'
  if status == "completed":
    completed_key = f"book:{book_uuid}:completed_chapters"
    total_key = f"book:{book_uuid}:total_chapters"

    redis_client.incr(completed_key)
    completed_count = int(redis_client.get(completed_key))
    total_count = int(redis_client.get(total_key))

    # Mark the book as completed if all chapters are done
    if completed_count == total_count:
      set_status("book", book_uuid, "completed")
      print(f"Book {book_uuid} marked as completed.")

# ---------------------------------------------------------------------------------------------------------------------

def update_chunk_status_impl(job):
  """
  Handles the UPDATE_CHUNK_STATUS operation by updating the status of a chunk.

  :param job: Dictionary containing book UUID, chapter UUID, chunk index, and status.
  """
  book_uuid = job.get("book_uuid")
  chapter_uuid = job.get("chapter_uuid")
  chunk_index = job.get("chunk_index")
  status = job.get("status")

  if not book_uuid or not chapter_uuid or not chunk_index or not status:
    raise ValueError("Missing required fields: book_uuid, chapter_uuid, chunk_index, status.")

  if status not in ALLOWED_CHUNK_STATUS:
    raise ValueError(f"Encountered a non-permissible value for chunk status: {status}")

  # Update the chunk's status
  set_status("chunk", f"{chapter_uuid}:chunk_{chunk_index}", status)

  print(f"Chunk {chunk_index} of chapter {chapter_uuid} status updated to {status}.")

# ---------------------------------------------------------------------------------------------------------------------

def remove_chapter_impl(job):
  """
  Handles the REMOVE_CHAPTER operation by marking the chapter as completed,
  removing it from the book's chapter set, and checking if the book is complete.

  :param job: Dictionary containing book UUID and chapter UUID.
  """

  book_uuid = job.get("book_uuid")
  chapter_uuid = job.get("chapter_uuid")

  if not book_uuid or not chapter_uuid:
    raise ValueError("Missing required fields: book_uuid, chapter_uuid.")

  # Mark the chapter as completed
  set_status("chapter", chapter_uuid, "completed")
  print(f"Chapter {chapter_uuid} marked as 'completed'.")

  # Remove the chapter from the book's set
  chapters_key = f"book:{book_uuid}:chapters"
  redis_client.srem(chapters_key, chapter_uuid)
  print(f"Chapter {chapter_uuid} removed from book {book_uuid}'s tracking set.")

  # Remove the chapter from the book's set
  chapters_key = f"book:{book_uuid}:chapters"
  redis_client.srem(chapters_key, chapter_uuid)
  print(f"Chapter {chapter_uuid} removed from book {book_uuid}'s tracking set.")

  # Check if all chapters are completed
  remaining_chapters = redis_client.scard(chapters_key)
  if remaining_chapters == 0:
    print(f"All chapters for book {book_uuid} have been processed. Book processing is complete.")
    set_status("book", book_uuid, "completed")


# ---------------------------------------------------------------------------------------------------------------------

def remove_chunk_impl(job):
  """
  Handles the REMOVE_CHUNK operation by marking the chunk as completed,
  removing it from the chapter's chunk set, and checking if the set is empty.

  :param job: Dictionary containing book UUID, chapter UUID, and chunk index.
  """
  book_uuid = job.get("book_uuid")
  chapter_uuid = job.get("chapter_uuid")
  chunk_index = job.get("chunk_index")

  if not book_uuid or not chapter_uuid or not chunk_index:
    raise ValueError("Missing required fields: book_uuid, chapter_uuid, chunk_index.")

  # Mark the chunk as completed
  set_status("chunk", f"{chapter_uuid}:chunk_{chunk_index}", "completed")
  print(f"Chunk {chunk_index} of chapter {chapter_uuid} marked as 'completed'.")

  # Remove the chunk from the chapter's set
  chunks_key = f"chapter:{chapter_uuid}:chunks"
  redis_client.srem(chunks_key, f"chunk_{chunk_index}")
  print(f"Chunk {chunk_index} removed from chapter {chapter_uuid}'s tracking set.")

  # Check if the set is empty
  remaining_chunks = redis_client.scard(chunks_key)
  if remaining_chunks == 0:
    # Placeholder for adding an audio stitch job
    print(f"All chunks for chapter {chapter_uuid} have been processed. Queueing audio stitch job.")
    try:
      message = audio_stitch_job(book_uuid, chapter_uuid)
      # Publish the message to the RabbitMQ queue
      channel.basic_publish(
        exchange="",
        routing_key=STITCH_QUEUE_NAME,
        body=json.dumps(message)
      )
      print(f"Added audio stitch job for chapter: {chapter_uuid} of book: {book_uuid}")
    except Exception as e:
      raise RuntimeError(f"Failed to enqueue job in Audio stitch queue: {e}")

# ---------------------------------------------------------------------------------------------------------------------


# ---- RabbitMQ Callback ----
def process_message(ch, method, properties, body):
  """
  Callback function for RabbitMQ messages.
  Processes a tracker job: Adds/removes chunks and queues stitch jobs if complete.
  """
  pass
  try:
    job = json.loads(body)
    operation = job.get("operation")

    match operation:
      case redis_ops.ADD_BOOK:
        add_book_impl(job)
      case redis_ops.ADD_CHAPTER:
        add_chapter_impl(job)
      case redis_ops.ADD_CHUNK:
        add_chunk_impl(job)
      case redis_ops.UPDATE_BOOK_STATUS:
        update_book_status_impl(job)
      case redis_ops.UPDATE_CHAPTER_STATUS:
        update_chapter_status_impl(job)
      case redis_ops.UPDATE_CHUNK_STATUS:
        update_chunk_status_impl(job)
      case redis_ops.REMOVE_CHAPTER:
        remove_chapter_impl(job)
      case redis_ops.REMOVE_CHUNK:
        remove_chunk_impl(job)

      case _:
        print("Undefined operation: " + operation)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    # Acknowledge the message if processing is successful
    ch.basic_ack(delivery_tag=method.delivery_tag)
  except Exception as e:
    print(f"Error processing message: {e}")
    # Reject and requeue the message for future processing
    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def start_service():
  # Declare queues
  channel.queue_declare(queue=EVENT_TRACKER_QUEUE_NAME)
  channel.queue_declare(queue=STITCH_QUEUE_NAME)
  # ---- RabbitMQ Consumer ----
  channel.basic_consume(queue=EVENT_TRACKER_QUEUE_NAME, on_message_callback=process_message)

  print("Event tracker service is listening for jobs...")
  try:
    channel.start_consuming()
  except KeyboardInterrupt:
    print("Stopping the event tracker service...")
    channel.stop_consuming()
    connection.close()

if __name__ == "__main__":
  start_service()