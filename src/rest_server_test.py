import unittest
from unittest.mock import patch, MagicMock
import tempfile
import os
from flask import Flask
from werkzeug.datastructures import FileStorage  # Import FileStorage for simulating file uploads
from rest_server import app  # Adjust the import path

MAX_FILE_SIZE = 10 * 1024 * 1024 

class TestEventTracker(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    @patch('rest_server.upload_to_gcs')  # Adjust the import path
    @patch('rest_server.validate_epub')
    @patch('rest_server.enqueue_splitter_job')
    @patch('rest_server.notify_new_book')
    def test_upload_valid_epub(self, mock_notify_new_book, mock_enqueue_splitter_job, mock_validate_epub, mock_upload_to_gcs):
        # Mock the validation to return valid EPUB
        mock_validate_epub.return_value = (True, "Valid EPUB file under 10 MB")
        mock_upload_to_gcs.return_value = None  # Simulate successful upload to GCS

        # Create a temporary EPUB file for testing
        with tempfile.NamedTemporaryFile(suffix='.epub', delete=False) as temp_file:
            temp_file.write(b'<?xml version="1.0" encoding="UTF-8"?>'
                            b'<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="bookid">'
                            b'<metadata><title>Test Book</title><author>Author Name</author></metadata>'
                            b'<manifest><item id="item1" href="text1.html" media-type="text/html"/></manifest>'
                            b'<spine><itemref idref="item1"/></spine></package>')
            temp_file_path = temp_file.name

        # Use Flask's test client to upload the file
        with open(temp_file_path, 'rb') as f:
            file_storage = FileStorage(stream=f, filename='test.epub', content_type='application/epub+zip')
            response = self.app.post('/upload', data={'file': file_storage})

        # Check response status and message
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Valid EPUB file uploaded successfully', response.data)

        # Check if the appropriate functions were called
        mock_upload_to_gcs.assert_called_once()
        mock_notify_new_book.assert_called_once()
        mock_enqueue_splitter_job.assert_called_once()

        # Clean up the temporary file
        os.remove(temp_file_path)

    @patch('rest_server.upload_to_gcs')  # Adjust the import path
    @patch('rest_server.validate_epub')
    def test_upload_invalid_epub(self, mock_validate_epub, mock_upload_to_gcs):
        # Mock the validation to return invalid EPUB
        mock_validate_epub.return_value = (False, "Invalid EPUB file: some error")

        # Create a temporary invalid file for testing
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as temp_file:
            temp_file.write(b'Test text content')
            temp_file_path = temp_file.name

        with open(temp_file_path, 'rb') as f:
            file_storage = FileStorage(stream=f, filename='invalid.epub', content_type='application/epub+zip')
            response = self.app.post('/upload', data={'file': file_storage})  # Pass filename as well

        # Check response status and error message
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Invalid EPUB file: some error', response.data)

        # Clean up the temporary file
        os.remove(temp_file_path)

if __name__ == '__main__':
    unittest.main()
