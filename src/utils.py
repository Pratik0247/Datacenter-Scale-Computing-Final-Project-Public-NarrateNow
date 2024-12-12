import os

from google.cloud import storage

# ---- Initialize Google Cloud Storage client -----
storage_client = storage.Client()

def upload_to_gcs(file, bucket_name, destination_blob_name):
  """
  Uploads a file to Google Cloud Storage.

  :param file: File-like object
  :param bucket_name: Name of the GCS bucket
  :param destination_blob_name: Path in the bucket where the file will be saved
  """

  try:
    file.seek(0)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_file(file)  # Upload file-like object directly
  except Exception as e:
    raise RuntimeError(f"Error uploading to GCS: {e}")


def download_file_from_gcs(bucket_name, source_blob_name, destination_file_name):
  """
  Downloads a file from Google Cloud Storage.

  :param bucket_name: Name of the GCS bucket
  :param source_blob_name: Path to the file in the bucket
  :param destination_file_name: Local path to save the downloaded file
  """
  try:
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(source_blob_name)
    blob.download_to_filename(destination_file_name)
    print(f"Downloaded {source_blob_name} from bucket {bucket_name} to {destination_file_name}")
  except Exception as e:
    raise RuntimeError(f"Failed to download file from GCS: {e}")


def download_folder_from_gcs(bucket_name, folder_prefix, destination_directory):
  """
  Downloads all files in a GCS folder to a local directory.

  :param bucket_name: Name of the GCS bucket
  :param folder_prefix: Path prefix for the folder in the bucket (e.g., "folder/subfolder/")
  :param destination_directory: Local directory to save the downloaded files
  """
  try:
    # Ensure the local destination directory exists
    os.makedirs(destination_directory, exist_ok=True)

    # Get the bucket object
    bucket = storage_client.bucket(bucket_name)

    # List all blobs in the folder
    blobs = bucket.list_blobs(prefix=folder_prefix)

    # Download each file in the folder
    for blob in blobs:
      if not blob.name.endswith("/"):  # Ignore "directory" entries in GCS
        local_file_path = os.path.join(destination_directory, os.path.basename(blob.name))
        blob.download_to_filename(local_file_path)
        print(f"Downloaded {blob.name} to {local_file_path}")

    print(f"All files from {folder_prefix} in bucket {bucket_name} downloaded to {destination_directory}.")

  except Exception as e:
    raise RuntimeError(f"Failed to download folder from GCS: {e}")
