# ---- Define all the messages that are passed between the services. ----
import redis_ops
# ---- Inter-service messages ----
def split_job(book_uuid):
  return {
    "book_uuid": book_uuid
  }

def chunker_job(book_uuid, chapter_uuid):
  return {
    "book_uuid": book_uuid,
    "chapter_uuid": chapter_uuid,
  }

def tts_job(book_uuid, chapter_uuid, chunk_index):
  return {
    "book_uuid": book_uuid,
    "chapter_uuid": chapter_uuid,
    "chunk_index" : chunk_index
  }

def audio_stitch_job(book_uuid, chapter_uuid):
  return {
    "book_uuid": book_uuid,
    "chapter_uuid": chapter_uuid
  }



# ---- Event tracker service notifications ----
def add_book(book_uuid):
  return {
    "operation" : redis_ops.ADD_BOOK,
    "book_uuid" : book_uuid
  }

def add_chapter(book_uuid, chapter_uuid, chapter_title):
  return {
    "operation" : redis_ops.ADD_CHAPTER,
    "book_uuid" : book_uuid,
    "chapter_uuid" : chapter_uuid,
    "chapter_title" : chapter_title
  }

def add_chunk(book_uuid, chapter_uuid, chunk_index):
  return {
    "operation": redis_ops.REMOVE_CHAPTER,
    "book_uuid": book_uuid,
    "chapter_uuid": chapter_uuid,
    "chunk_index": chunk_index
  }

def update_book_status(book_uuid, status):
  return {
    "operation" : redis_ops.UPDATE_BOOK_STATUS,
    "book_uuid" : book_uuid,
    "status" : status
  }

def update_chapter_status(book_uuid, chapter_uuid, status):
  return {
    "operation" : redis_ops.UPDATE_CHAPTER_STATUS,
    "book_uuid" : book_uuid,
    "chapter_uuid" : chapter_uuid,
    "status" : status
  }

def update_chunk_status(book_uuid, chapter_uuid, chunk_index, status):
  return {
    "operation" : redis_ops.UPDATE_CHAPTER_STATUS,
    "book_uuid" : book_uuid,
    "chapter_uuid" : chapter_uuid,
    "chunk_index" : chunk_index,
    "status" : status
  }

def remove_chapter(book_uuid, chapter_uuid):
  return {
    "operation" : redis_ops.REMOVE_CHAPTER,
    "book_uuid": book_uuid,
    "chapter_uuid": chapter_uuid
  }

def remove_chunk(book_uuid, chapter_uuid, chunk_index):
  return {
    "operation": redis_ops.REMOVE_CHUNK,
    "book_uuid": book_uuid,
    "chapter_uuid": chapter_uuid,
    "chunk_index": chunk_index
  }


