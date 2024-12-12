# ---- Redis Helper Functions ----
def get_redis_key(book_id, chapter_id):
    """Generate a Redis key for a given job ID and chapter ID."""
    return f"job:{book_id}:chapter:{chapter_id}:chunks"

def add_book(book_id):
    key = f"book:{book_id}"
    redis_client.hset(key, mapping={"status": "uploaded"})
    redis_client.set

def add_chunks(book_id, chapter_id, chunk_ids):
    """Add a list of chunk IDs to Redis for a specific job and chapter."""
    redis_key = get_redis_key(book_id, chapter_id)
    redis_client.sadd(redis_key, *chunk_ids)
    print(f"Added {len(chunk_ids)} chunks to Redis key: {redis_key}")

def remove_chunk(book_id, chapter_id, chunk_id):
    """Remove a chunk ID from Redis for a specific job and chapter."""
    redis_key = get_redis_key(book_id, chapter_id)
    redis_client.srem(redis_key, chunk_id)
    print(f"Removed chunk {chunk_id} from Redis key: {redis_key}")

def is_complete(book_id, chapter_id):
    """Check if all chunks for a given job and chapter are processed."""
    redis_key = get_redis_key(book_id, chapter_id)
    remaining_chunks = redis_client.scard(redis_key)
    return remaining_chunks == 0

def queue_stitch_job(book_id, chapter_id):
    """Queue the audio stitching job in RabbitMQ."""
    message = audio_stitch_job()
    channel.basic_publish(
        exchange="",
        routing_key=STITCH_QUEUE_NAME,
        body=json.dumps(message)
    )
    print(f"Queued stitch job for book ID: {book_id}, chapter ID: {chapter_id}")