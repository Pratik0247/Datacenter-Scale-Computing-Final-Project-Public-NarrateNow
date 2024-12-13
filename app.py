from flask import Flask, render_template, request, redirect, url_for, jsonify
import requests
import time
import os
import json

app = Flask(__name__)

BASE_URL = "http://localhost:8000"  # URL of the REST server

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    # if "file" not in request.files:
    #     return jsonify({"error": "No file part"}), 400

    # file = request.files["file"]

    # if file.filename == "":
    #     return jsonify({"error": "No selected file"}), 400

    # # Create a tuple for the file upload
    # files = {
    #     "file": (file.filename, file.stream, "application/epub+zip")  # Use file.stream for a proper file-like object
    # }
    file_path = "/Users/nehakolambe/Documents/CUB/Sem1/DCSC/finalproject-final-project-team-96/howToBecomeFamous.epub"
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
                return redirect(url_for("status", job_id=book_uuid))
            else:
                print(f"Failed to upload book: {response.json().get('error')}")
                error_message = "Invalid response from backend. Check server logs."
                return jsonify({"error": error_message}), response.status_code
    except Exception as e:
        print(f"Error uploading book: {e}")
        error_message = "Invalid response from backend. Check server logs."
        return jsonify({"error": error_message}), response.status_code
    # with open(file_path, 'rb') as file:
    #   # Define the file part with a custom content type
    #     files = {
    #     "file": (os.path.basename(file_path), file, "application/epub+zip")
    #   }
    #     try:
    #         # Send the request
    #         response = requests.post(f"{BASE_URL}/upload", files=files)
            
    #         # Debugging: Print raw response details
    #         print(f"Response status code: {response.status_code}")
    #         print(f"Response content: {response.content.decode('utf-8')}")  # Ensure response is readable

    #         # Handle valid JSON responses
    #         if response.status_code == 200:
    #             book_uuid = response.json().get("job_id")
    #             print(f"Book uploaded successfully. Job ID: {book_uuid}")
    #             return redirect(url_for("status", job_id=book_uuid))
    #         else:
    #             # Handle non-200 responses
    #             try:
    #                 error_message = response.json().get("error", "Unknown error")
    #             except requests.exceptions.JSONDecodeError:
    #                 error_message = "Invalid response from backend. Check server logs."
    #             print(f"Failed to upload book: {error_message}")
    #             return jsonify({"error": error_message}), response.status_code
    #     except Exception as e:
    #         print(f"Error uploading book: {e}")
    #         return jsonify({"error": str(e)}), 500




@app.route("/status/<job_id>")
def status(job_id):
    while True:
        response = requests.get(f"{BASE_URL}/status/{job_id}")
        if response.status_code == 200:
            data = response.json()
            if data["status"] == "completed":
                return render_template("download.html", job_id=job_id, chapters=data["completed_chapters"])
            elif data["status"] == "failed":
                return render_template("error.html", message="Processing failed.")
        
        time.sleep(5)  # Poll every 5 seconds

@app.route("/download/<job_id>")
def download_chapters(job_id):
    response = requests.get(f"{BASE_URL}/chapters/{job_id}")
    
    if response.status_code == 200:
        chapters = response.json().get("chapters", [])
        return render_template("download.html", job_id=job_id, chapters=chapters)
    
    else:
        error_message = response.json().get("error", "Unknown error")
        return render_template("error.html", message=error_message)

@app.route("/download_chapter/<job_id>/<chapter_id>")
def download_chapter(job_id, chapter_id):
    response = requests.get(f"{BASE_URL}/download/{job_id}/{chapter_id}", stream=True)
    
    if response.status_code == 200:
        file_path = f"{chapter_id}.mp3"
        
        with open(file_path, "wb") as file:
            file.write(response.content)
        
        return f"Chapter {chapter_id} downloaded successfully."
    
    else:
        return "Failed to download chapter."

if __name__ == "__main__":
   app.run(debug=True)
