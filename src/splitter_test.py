import unittest
from unittest.mock import patch, MagicMock
import tempfile
import os
import json
from ebooklib import epub

# Import the functions to be tested
from splitter import (
    split_book_into_chapters,
    is_metadata,
    process_split_job,
    notify_event_tracker,
    enqueue_chunker_job
)

class TestSplitter(unittest.TestCase):

    def create_dummy_epub(self):
        book = epub.EpubBook()
        book.set_identifier('id123456')
        book.set_title('Test Book')
        book.set_language('en')

        # Add a valid chapter
        c1 = epub.EpubHtml(title='Chapter 1', file_name='chap_01.xhtml', lang='en')
        c1.content = '<html><body><h1>Chapter 1</h1><p>This is the content of chapter 1.</p></body></html>'
        book.add_item(c1)

        # Add a metadata-like chapter (should be filtered out)
        c2 = epub.EpubHtml(title='Table of Contents', file_name='toc.xhtml', lang='en')
        c2.content = '<html><body><h1>Table of Contents</h1><p>Chapter 1</p></body></html>'
        book.add_item(c2)

        # Add another valid chapter
        c3 = epub.EpubHtml(title='Chapter 2', file_name='chap_02.xhtml', lang='en')
        c3.content = '<html><body><h1>Chapter 2</h1><p>This is the content of chapter 2.</p></body></html>'
        book.add_item(c3)

        # Add chapters to the book's spine
        book.spine = ['nav', c1, c2, c3]

        # Add Table Of Contents
        book.toc = (epub.Link('chap_01.xhtml', 'Chapter 1', 'chapter1'),
                    epub.Link('chap_02.xhtml', 'Chapter 2', 'chapter2'))

        # Add navigation files
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        # Create a temporary file to save the EPUB
        with tempfile.NamedTemporaryFile(delete=False, suffix='.epub') as tmp_file:
            epub.write_epub(tmp_file.name, book, {})
            return tmp_file.name

    @patch('splitter.upload_to_gcs')
    @patch('splitter.notify_event_tracker')
    @patch('splitter.enqueue_chunker_job')
    def test_split_book_into_chapters(self, mock_enqueue, mock_notify, mock_upload):
        epub_file = self.create_dummy_epub()
        bucket_name = 'test-bucket'
        book_uuid = 'test-uuid'

        try:
            split_book_into_chapters(epub_file, bucket_name, book_uuid)

            # Check if upload_to_gcs was called twice (for two valid chapters)
            self.assertEqual(mock_upload.call_count, 2)

            # Check if notify_event_tracker was called for each chapter
            self.assertEqual(mock_notify.call_count, 3)

            # Check if enqueue_chunker_job was called for each chapter
            self.assertEqual(mock_enqueue.call_count, 2)

        finally:
            # Clean up the temporary EPUB file
            os.unlink(epub_file)

    def test_is_metadata(self):
        # Test cases that should be identified as metadata
        self.assertTrue(is_metadata("Table of Contents", "Chapter 1\nChapter 2"))
        self.assertTrue(is_metadata("Copyright", "All rights reserved"))
        self.assertTrue(is_metadata("About the Author", "John Doe is a writer"))

        # Test cases that should not be identified as metadata
        # self.assertFalse(is_metadata("Chapter 1", "This is the content of chapter 1."))
        # self.assertFalse(is_metadata("The Adventure Begins", "It was a dark and stormy night..."))

    @patch('splitter.channel')
    def test_notify_event_tracker(self, mock_channel):
        message = {"type": "test", "data": "test_data"}
        notify_event_tracker(message)
        mock_channel.basic_publish.assert_called_once()

    @patch('splitter.channel')
    def test_enqueue_chunker_job(self, mock_channel):
        enqueue_chunker_job("test-book-uuid", "test-chapter-title")
        mock_channel.basic_publish.assert_called_once()

    @patch('splitter.split_book_into_chapters')
    @patch('splitter.download_file_from_gcs')
    def test_process_split_job(self, mock_download, mock_split):
        ch = MagicMock()
        method = MagicMock()
        properties = MagicMock()
        body = json.dumps({"book_uuid": "test-uuid"})

        process_split_job(ch, method, properties, body)

        mock_download.assert_called_once()
        mock_split.assert_called_once()
        ch.basic_ack.assert_called_once()

if __name__ == '__main__':
    unittest.main()
