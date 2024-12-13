import unittest
from unittest.mock import patch, MagicMock
import json
import tempfile
import os

from tts import (
    text_to_speech,
    notify_event_tracker,
    process_job,
    callback,
    start_service
)

class TestTTSService(unittest.TestCase):

    @patch('tts.client.synthesize_speech')
    def test_text_to_speech_mocked(self, mock_synthesize_speech):
        # Create a mock response
        mock_response = MagicMock()
        mock_response.audio_content = b'mock audio content'
        mock_synthesize_speech.return_value = mock_response

        # Create temporary input and output files
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_input, \
             tempfile.NamedTemporaryFile(mode='wb+', delete=False) as temp_output:
            # Write dummy content to the input file
            temp_input.write('Test text')
            temp_input.flush()

            # Call the text_to_speech function
            text_to_speech(temp_input.name, temp_output.name)

            # Validate the output file content
            with open(temp_output.name, 'rb') as f:
                output_content = f.read()
                print(f"Output file content: {output_content}")  # Debugging
                self.assertEqual(output_content, b'mock audio content')

        # Clean up temporary files
        os.unlink(temp_input.name)
        os.unlink(temp_output.name)

    @patch('tts.channel')
    def test_notify_event_tracker(self, mock_channel):
        notify_event_tracker('TEST_OP', {'key': 'value'})
        mock_channel.basic_publish.assert_called_once()

    @patch('tts.download_file_from_gcs')
    @patch('tts.upload_to_gcs')
    @patch('tts.text_to_speech')
    @patch('tts.notify_event_tracker')
    def test_process_job(self, mock_notify, mock_tts, mock_upload, mock_download):
        process_job('book123', 'chapter456', 1)
        mock_download.assert_called_once()
        mock_tts.assert_called_once()
        mock_upload.assert_called_once()
        self.assertEqual(mock_notify.call_count, 2)

    @patch('tts.process_job')
    def test_callback_success(self, mock_process):
        ch = MagicMock()
        method = MagicMock()
        properties = MagicMock()
        body = json.dumps({"book_uuid": "book123", "chapter_uuid": "chapter456", "chunk_index": 1})
        
        callback(ch, method, properties, body)
        
        mock_process.assert_called_once_with("book123", "chapter456", 1)
        ch.basic_ack.assert_called_once()

    @patch('tts.process_job')
    def test_callback_error(self, mock_process):
        ch = MagicMock()
        method = MagicMock()
        properties = MagicMock()
        body = json.dumps({"invalid": "data"})
        
        callback(ch, method, properties, body)
        
        mock_process.assert_not_called()
        ch.basic_nack.assert_called_once()

    @patch('tts.channel')
    @patch('tts.connection')
    def test_start_service(self, mock_connection, mock_channel):
        mock_channel.start_consuming.side_effect = KeyboardInterrupt()
        
        start_service()
        
        mock_channel.basic_qos.assert_called_once_with(prefetch_count=1)
        mock_channel.queue_declare.assert_called()
        mock_channel.basic_consume.assert_called_once()
        mock_channel.start_consuming.assert_called_once()
        mock_channel.stop_consuming.assert_called_once()
        mock_connection.close.assert_called_once()

if __name__ == '__main__':
    unittest.main()
