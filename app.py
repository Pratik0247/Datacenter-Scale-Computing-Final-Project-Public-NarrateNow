import io
import time

import requests
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file

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
                # Fetch the list of chapters
                chapters_response = requests.get(f"{BASE_URL}/chapters/{job_id}")
                if chapters_response.status_code == 200:
                    chapters = chapters_response.json().get("chapters", [])
                    chapters_with_titles = []
                    for chapter in chapters:
                        chapter_id = chapter["chapter_id"]
                        title_response = requests.get(f"{BASE_URL}/chapter/{chapter_id}/title")
                        if title_response.status_code == 200:
                            title = title_response.json().get("title", f"Chapter {chapter_id}")
                        else:
                            title = f"Chapter {chapter_id}"  # Default to generic title if fetching fails

                        # Add chapter info with title
                        chapters_with_titles.append({"chapter_id": chapter_id, "title": title})

                    # Render the download template with chapter titles
                    return render_template("download.html", job_id=job_id, chapters=chapters_with_titles)
                else:
                    error_message = chapters_response.json().get("error", "Unknown error fetching chapters.")
                    return render_template("error.html", message=error_message)
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
    # Fetch the chapter title from the REST server
    title_response = requests.get(f"{BASE_URL}/chapter/{chapter_id}/title")
    if title_response.status_code == 200:
        chapter_title = title_response.json().get("title", f"chapter_{chapter_id}")
    else:
        chapter_title = f"chapter_{chapter_id}"  # Default title if fetching fails

    # Sanitize the title for use as a filename
    sanitized_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in chapter_title)

    # Stream the chapter file from the backend REST server
    response = requests.get(f"{BASE_URL}/download/{job_id}/{chapter_id}", stream=True)
    if response.status_code == 200:
        # Send the file to the browser with the sanitized title as the download name
        return send_file(
            io.BytesIO(response.content),
            as_attachment=True,
            download_name=f"{sanitized_title}.mp3",
            mimetype="audio/mpeg"
        )
    else:
        # Return an error message if the file cannot be downloaded
        return render_template("error.html", message="Failed to download chapter.")


if __name__ == "__main__":
    app.run(debug=True)
