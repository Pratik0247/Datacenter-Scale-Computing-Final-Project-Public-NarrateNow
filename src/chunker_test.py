import unittest
from unittest.mock import patch, MagicMock
import json
import os
from io import BytesIO

from chunker import (
    read_text_from_file,
    split_text_into_chunks,
    notify_event_tracker,
    enqueue_tts_job,
    process_job,
    callback
)

class TestChunker(unittest.TestCase):

    def test_read_text_from_file(self):
        with patch('builtins.open', unittest.mock.mock_open(read_data="Test content")):
            result = read_text_from_file("dummy_path.txt")
            self.assertEqual(result, "Test content")

    def test_read_text_from_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            read_text_from_file("non_existent_file.txt")

    def test_split_text_into_chunks(self):
        text = "This is a test. It has multiple sentences. And even multiple paragraphs.\n\nHere's another paragraph. It's short."
        chunks = split_text_into_chunks(text, max_chunk_size=50)
        self.assertEqual(len(chunks), 3)
        self.assertTrue(all(len(chunk.encode('utf-8')) <= 50 for chunk in chunks))

    @patch('chunker.channel')
    def test_notify_event_tracker(self, mock_channel):
        notify_event_tracker("TEST_OP", {"key": "value"})
        mock_channel.basic_publish.assert_called_once()

    @patch('chunker.channel')
    def test_enqueue_tts_job(self, mock_channel):
        enqueue_tts_job("book123", "chapter456", 1)
        mock_channel.basic_publish.assert_called_once()

    @patch('chunker.download_file_from_gcs')
    @patch('chunker.upload_to_gcs')
    @patch('chunker.read_text_from_file')
    @patch('chunker.notify_event_tracker')
    @patch('chunker.enqueue_tts_job')
    def test_process_job(self, mock_enqueue, mock_notify, mock_read, mock_upload, mock_download):
        mock_read.return_value = "This is a test chapter."
        process_job("book123", "chapter456")
        mock_download.assert_called_once()
        mock_read.assert_called_once()
        self.assertTrue(mock_upload.called)
        self.assertTrue(mock_notify.called)
        self.assertTrue(mock_enqueue.called)

    @patch('chunker.process_job')
    def test_callback_success(self, mock_process):
        ch = MagicMock()
        method = MagicMock()
        properties = MagicMock()
        body = json.dumps({"book_uuid": "book123", "chapter_uuid": "chapter456"})
        
        callback(ch, method, properties, body)
        
        mock_process.assert_called_once_with("book123", "chapter456")
        ch.basic_ack.assert_called_once()

    @patch('chunker.process_job')
    def test_callback_error(self, mock_process):
        ch = MagicMock()
        method = MagicMock()
        properties = MagicMock()
        body = json.dumps({"invalid": "data"})
        
        callback(ch, method, properties, body)
        
        mock_process.assert_not_called()
        ch.basic_nack.assert_called_once()

if __name__ == '__main__':
    unittest.main()
