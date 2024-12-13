import requests
import time
import os

BASE_URL = "http://34.45.125.238:8000"


def upload_book(file_path):
  """
  Upload a book to the REST server.
  """
  try:
    with open(file_path, 'rb') as file:
      # Define the file part with a custom content type
      files = {
        "file": (os.path.basename(file_path), file, "application/epub+zip")
      }
      # Send the request
      response = requests.post(f"{BASE_URL}/upload", files=files)
    if response.status_code == 200:
      book_uuid = response.json().get("job_id")
      print(f"Book uploaded successfully. Job ID: {book_uuid}")
      return book_uuid
    else:
      print(f"Failed to upload book: {response.json().get('error')}")
      return None
  except Exception as e:
    print(f"Error uploading book: {e}")
    return None


def poll_status(book_uuid):
  """
  Poll the REST server for the status of a job.
  """
  print(f"Polling status for book ID: {book_uuid}")
  while True:
    try:
      response = requests.get(f"{BASE_URL}/status/{book_uuid}")
      if response.status_code == 200:
        data = response.json()
        print(f"Current status: {data['status']} ({data['completed_chapters']} of {data['total_chapters']} chapters completed)")
        if data["status"] == "completed":
          return True
        elif data["status"] == "failed":
          print("Processing failed.")
          return False
      else:
        print(f"Failed to fetch status: {response.json().get('error')}")
        return False
    except Exception as e:
      print(f"Error fetching status: {e}")
      return False
    time.sleep(5)  # Poll every 5 seconds


def download_chapters(book_uuid, output_dir):
  """
  Download all chapters of a completed book using their titles as file names.
  """
  os.makedirs(output_dir, exist_ok=True)
  try:
    response = requests.get(f"{BASE_URL}/chapters/{book_uuid}")
    if response.status_code == 200:
      chapters = response.json().get("chapters", [])
      for chapter in chapters:
        chapter_id = chapter["chapter_id"]

        # Fetch the chapter title
        title_response = requests.get(f"{BASE_URL}/chapter/{chapter_id}/title")
        if title_response.status_code == 200:
          chapter_title = title_response.json().get("title")
        else:
          print(f"Failed to fetch title for Chapter {chapter_id}: {title_response.json().get('error')}")
          chapter_title = f"chapter_{chapter_id}"

        # Replace invalid characters in the file name
        sanitized_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in chapter_title)

        # Download the chapter audio
        download_url = f"{BASE_URL}/download/{book_uuid}/{chapter_id}"
        chapter_response = requests.get(download_url)
        if chapter_response.status_code == 200:
          file_path = os.path.join(output_dir, f"{sanitized_title}.mp3")
          with open(file_path, "wb") as file:
            file.write(chapter_response.content)
          print(f"Downloaded Chapter {chapter_id} as {file_path}")
        else:
          print(f"Failed to download Chapter {chapter_id}: {chapter_response.json().get('error')}")
    else:
      print(f"Failed to fetch chapters: {response.json().get('error')}")
  except Exception as e:
    print(f"Error downloading chapters: {e}")


def main():
  """
  Main function to upload a book, poll for status, and download chapters.
  """
  file_path = input("Enter the path to the EPUB file: ")
  output_dir = input("Enter the output directory for downloaded chapters: ")

  book_uuid = upload_book(file_path)
  if not book_uuid:
    print("Book upload failed. Exiting.")
    return

  if poll_status(book_uuid):
    print("Book processing complete. Downloading chapters...")
    download_chapters(book_uuid, output_dir)
  else:
    print("Book processing failed. Exiting.")


if __name__ == "__main__":
  main()
