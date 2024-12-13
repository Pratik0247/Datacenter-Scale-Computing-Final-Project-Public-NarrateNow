import unittest
from unittest.mock import patch, MagicMock
import json
from event_tracker import (
    add_book_impl, add_chapter_impl, add_chunk_impl,
    update_book_status_impl, update_chapter_status_impl, update_chunk_status_impl,
    remove_chapter_impl, remove_chunk_impl, process_message
)

class TestEventTracker(unittest.TestCase):

    @patch('event_tracker.set_status')
    def test_add_book_impl(self, mock_set_status):
        job = {"book_uuid": "test_book_uuid"}
        add_book_impl(job)
        mock_set_status.assert_called_once_with("book", "test_book_uuid", "uploaded")

    @patch('event_tracker.redis_client')
    @patch('event_tracker.set_status')
    @patch('event_tracker.add_relationship')
    def test_add_chapter_impl(self, mock_add_relationship, mock_set_status, mock_redis):
        job = {"book_uuid": "test_book_uuid", "chapter_uuid": "test_chapter_uuid", "chapter_title": "Test Chapter"}
        add_chapter_impl(job)
        mock_redis.hset.assert_called_once()
        mock_set_status.assert_called_once_with("chapter", "test_chapter_uuid", "uploaded")
        mock_add_relationship.assert_called_once()

    @patch('event_tracker.set_status')
    @patch('event_tracker.add_relationship')
    def test_add_chunk_impl(self, mock_add_relationship, mock_set_status):
        job = {"book_uuid": "test_book_uuid", "chapter_uuid": "test_chapter_uuid", "chunk_index": 1}
        add_chunk_impl(job)
        mock_set_status.assert_called_once_with("chunk", "test_chapter_uuid:chunk_1", "queued")
        mock_add_relationship.assert_called_once()

    @patch('event_tracker.set_status')
    def test_update_book_status_impl(self, mock_set_status):
        job = {"book_uuid": "test_book_uuid", "status": "in_progress"}
        update_book_status_impl(job)
        mock_set_status.assert_called_once_with("book", "test_book_uuid", "in_progress")

    @patch('event_tracker.set_status')
    def test_update_chapter_status_impl(self, mock_set_status):
        job = {"book_uuid": "test_book_uuid", "chapter_uuid": "test_chapter_uuid", "status": "in_progress"}
        update_chapter_status_impl(job)
        mock_set_status.assert_called_once_with("chapter", "test_chapter_uuid", "in_progress")

    @patch('event_tracker.set_status')
    def test_update_chunk_status_impl(self, mock_set_status):
        job = {"book_uuid": "test_book_uuid", "chapter_uuid": "test_chapter_uuid", "chunk_index": 1, "status": "in_progress"}
        update_chunk_status_impl(job)
        mock_set_status.assert_called_once_with("chunk", "test_chapter_uuid:chunk_1", "in_progress")

    @patch('event_tracker.redis_client')
    @patch('event_tracker.set_status')
    @patch('event_tracker.channel')
    def test_remove_chapter_impl(self, mock_channel, mock_set_status, mock_redis):
        job = {"book_uuid": "test_book_uuid", "chapter_uuid": "test_chapter_uuid"}
        mock_redis.scard.return_value = 0
        remove_chapter_impl(job)
        mock_set_status.assert_called_with("book", "test_book_uuid", "completed")

    @patch('event_tracker.redis_client')
    @patch('event_tracker.set_status')
    @patch('event_tracker.channel')
    def test_remove_chunk_impl(self, mock_channel, mock_set_status, mock_redis):
        job = {"book_uuid": "test_book_uuid", "chapter_uuid": "test_chapter_uuid", "chunk_index": 1}
        mock_redis.scard.return_value = 0
        remove_chunk_impl(job)
        mock_set_status.assert_called_with("chunk", "test_chapter_uuid:chunk_1", "completed")
        mock_channel.basic_publish.assert_called_once()

    @patch('event_tracker.add_book_impl')
    @patch('event_tracker.add_chapter_impl')
    @patch('event_tracker.add_chunk_impl')
    @patch('event_tracker.update_book_status_impl')
    @patch('event_tracker.update_chapter_status_impl')
    @patch('event_tracker.update_chunk_status_impl')
    @patch('event_tracker.remove_chapter_impl')
    @patch('event_tracker.remove_chunk_impl')
    def test_process_message(self,
                              mock_remove_chunk,
                              mock_remove_chapter,
                              mock_update_chunk,
                              mock_update_chapter,
                              mock_update_book,
                              mock_add_chunk,
                              mock_add_chapter,
                              mock_add_book):
        
        ch = MagicMock()
        method = MagicMock()
        properties = MagicMock()

        # Test ADD_BOOK operation
        body = json.dumps({"operation": 'ADD_BOOK', 'book_uuid': 'test_book_uuid'})
        
        process_message(ch, method, properties, body)
        

        # Test invalid operation
        body = json.dumps({"operation": 'INVALID_OP'})
        
        process_message(ch, method, properties, body)
        

if __name__ == '__main__':
    unittest.main()
