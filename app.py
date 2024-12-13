from flask import Flask, render_template, request, redirect, url_for, jsonify
import requests
import time
import os

app = Flask(__name__)

BASE_URL = "http://localhost:8000"  # URL of the REST server

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    files = {
        "file": (file.filename, file, "application/epub+zip")
    }

    response = requests.post(f"{BASE_URL}/upload", files=files)

    if response.status_code == 200:
        job_id = response.json().get("job_id")
        return redirect(url_for("status", job_id=job_id))
    else:
        error_message = response.json().get("error", "Unknown error")
        return render_template("error.html", message=error_message)

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
        else:
            return render_template("error.html", message="Failed to fetch status.")
        time.sleep(5)  # Poll every 5 seconds

@app.route("/download/<job_id>")
def download(job_id):
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
