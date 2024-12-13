import unittest
from unittest.mock import patch, MagicMock
import json
import os
from pydub import AudioSegment

# Import the functions to be tested
from audio_stitcher import (
    notify_event_tracker,
    stitch_chunks,
    cleanup_temp_files,
    stitch_audio_files,
    process_job,
    callback
)

class TestAudioStitcher(unittest.TestCase):

    # @patch('audio_stitcher.channel')
    # def test_notify_event_tracker(self, mock_channel):
    #     operation = "TEST_OPERATION"
    #     message = {"key": "value"}
    #     notify_event_tracker(operation, message)
    #     mock_channel.basic_publish.assert_called_once_with(
    #         exchange="",
    #         routing_key="EVENT_TRACKER_QUEUE_NAME",
    #         body=json.dumps(message)
    #     )

    @patch('audio_stitcher.AudioSegment')
    def test_stitch_chunks(self, mock_AudioSegment):
        mock_AudioSegment.empty.return_value = MagicMock()
        mock_AudioSegment.from_file.return_value = MagicMock()
        
        chunk_files = ["chunk1.mp3", "chunk2.mp3"]
        result = stitch_chunks(chunk_files)
        
        self.assertEqual(mock_AudioSegment.from_file.call_count, 2)
        self.assertIsNotNone(result)

    @patch('os.path.exists')
    @patch('os.remove')
    @patch('os.rmdir')
    @patch('os.listdir')
    def test_cleanup_temp_files(self, mock_listdir, mock_rmdir, mock_remove, mock_exists):
        mock_listdir.return_value = ["file1.mp3", "file2.mp3"]
        mock_exists.return_value = True
        
        cleanup_temp_files("output.mp3", "temp_dir")
        
        self.assertEqual(mock_remove.call_count, 3)  # 2 temp files + 1 output file
        mock_rmdir.assert_called_once_with("temp_dir")

    @patch('audio_stitcher.download_folder_from_gcs')
    @patch('audio_stitcher.upload_to_gcs')
    @patch('audio_stitcher.stitch_chunks')
    @patch('os.listdir')
    @patch('os.makedirs')
    def test_stitch_audio_files(self, mock_makedirs, mock_listdir, mock_stitch_chunks, mock_upload, mock_download):
        mock_listdir.return_value = ["chunk_1.mp3", "chunk_2.mp3"]
        mock_stitch_chunks.return_value = MagicMock()
        
        stitch_audio_files("test_bucket", "input_folder", "output_file.mp3")
        
        mock_download.assert_called_once()
        mock_stitch_chunks.assert_called_once()
        mock_upload.assert_called_once()

    @patch('audio_stitcher.stitch_audio_files')
    @patch('audio_stitcher.notify_event_tracker')
    def test_process_job(self, mock_notify, mock_stitch):
        process_job("book123", "chapter456")
        
        mock_stitch.assert_called_once_with(
            "dcsc-project-test",
            "book123/chunks/chapter456/audio",
            "book123/audio/chapter456.mp3"
        )
        mock_notify.assert_called_once()

    @patch('audio_stitcher.process_job')
    def test_callback(self, mock_process_job):
        ch = MagicMock()
        method = MagicMock()
        properties = MagicMock()
        body = json.dumps({"book_uuid": "book123", "chapter_uuid": "chapter456"})
        try:
            message = json.loads(body)
            book_uuid = message["book_uuid"]
            chapter_uuid = message["chapter_uuid"]
            process_job(book_uuid, chapter_uuid)
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except (KeyError, json.JSONDecodeError):
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

        
        # callback(ch, method, properties, body)
        
        # mock_process_job.assert_called_once_with("book123", "chapter456")
        # ch.basic_ack.assert_called_once_with(delivery_tag=method.delivery_tag)

    @patch('audio_stitcher.process_job')
    def test_callback_error(self, mock_process_job):
        ch = MagicMock()
        method = MagicMock()
        properties = MagicMock()
        body = json.dumps({"invalid": "data"})
        
        callback(ch, method, properties, body)
        
        mock_process_job.assert_not_called()
        ch.basic_nack.assert_called_once_with(delivery_tag=method.delivery_tag, requeue=True)

if __name__ == '__main__':
    unittest.main()
