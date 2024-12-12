UPLOAD_FOLDER = "uploads"
DOWNLOAD_FOLDER = "downloads"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
GCS_BUCKET_NAME = "dcsc-project-test"
RABBITMQ_HOST = 'localhost'
SPLITTER_QUEUE_NAME = 'splitter_queue'
CHUNKER_QUEUE_NAME = 'chunker_queue'
TTS_QUEUE_NAME = 'tts_queue'
STITCH_QUEUE_NAME = "stitch_queue"
EVENT_TRACKER_QUEUE_NAME = "event_tracker_queue"
REDIS_HOST = 'localhost'
REDIS_PORT = 6379



# ---- PostgreSQL connection setup ----
DB_CONFIG = {
  "host": "localhost",
  "dbname": "postgres",
  "user": "postgres",
  "password": "abc123",
  "port": 5432,
}