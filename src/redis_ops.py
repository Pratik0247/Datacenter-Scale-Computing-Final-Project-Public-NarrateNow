# ---- All the allowed redis operations are stored here. ----
# ---- All these operations go through the event tracker service. ----

# Add operations
ADD_BOOK = 'add_book'
ADD_CHAPTER = 'add_chapter'
ADD_CHUNK = 'add_chunk'
ADD_CHUNKS = 'add_chunks'

# Remove operations
REMOVE_CHUNK = 'remove_chunk'
REMOVE_CHAPTER = 'remove_chapter'
REMOVE_BOOK = 'remove_book'

# Status update operations
UPDATE_BOOK_STATUS = 'update_book_status'
UPDATE_CHAPTER_STATUS = 'update_chapter_status'
UPDATE_CHUNK_STATUS = 'update_chunk_status'

