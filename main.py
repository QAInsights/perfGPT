from flask import Flask, request, render_template
import requests

app = Flask(__name__)


@app.route('/')
def index():
    return render_template("index.html")


@app.route("/upload", methods=['POST'])
def askgpt_upload():
    file = request.files['file']

    url = "https://api.openai.com/v1/files"
    api_key = ""
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'multipart/form-data'
    }

    print(file)
    response = requests.post(url, headers=headers, files={'file': (file.filename, file.stream, file.content_type)})

    return response.json()

    url = f"https://api.openai.com/v1/engines/davinci/jobs"

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    data = {
        "model": "davinci",
        "prompt": f"analyze the contents of file with id {file_id}"
    }
    response = requests.post(url, headers=headers, json=data)

    print(response.json())
    return "Success", 200


if __name__ == '__main__':
    app.run(debug=True)
