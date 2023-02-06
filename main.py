from flask import Flask, request, render_template
import openai
import os
import re
import constants
import pandas as pd

app = Flask(__name__)


@app.route('/')
def index():
    """
    index
    :return:    index html
    """
    return render_template("index.html")


@app.route('/about')
def about():
    return render_template("about.html")


@app.route('/features')
def features():
    return render_template("features.html")


def beautify_response(text):
    """
    :param text: the response from GPT
    :return: beautified response
    """
    pattern = r'(\d+)'
    numbers = re.finditer(pattern, text)
    offset = 0
    for match in numbers:
        num = text[match.start()+offset:match.end()+offset]
        first_half, second_half = text[:match.start()+offset], text[match.end()+offset:]
        text = f'{first_half}<span class="fw-bold">{num}</span>{second_half}'
        offset += 29  # number of chars added by the <span> tags
    
    return text


@app.route('/upload', methods=['POST'])
def askgpt_upload():
    """
    ask GPT
    :return:    analyzed response from GPT
    """
    try:
        openai.api_key = os.environ['OPENAI_API_KEY']
    except KeyError:
        return render_template("analysis_response.html", response="API key not set.")

    if request.method == 'POST':
        if request.files:
            file = request.files['file']
            contents = pd.read_csv(file)
            if len(contents) > constants.FILE_SIZE:
                return render_template('analysis_response.html', response="File size too large.")
            try:
                response = openai.Completion.create(
                    model="text-davinci-003",
                    prompt=f"""
                    Please analyse this performance test results: \n {contents}
                    """,
                    temperature=0,
                    max_tokens=1000,
                    top_p=1.0,
                    frequency_penalty=0.0,
                    presence_penalty=0.0
                )
                response = beautify_response(response['choices'][0]['text'])
                return render_template("analysis_response.html", response=response)
            except Exception as e:
                return e
        else:
            return render_template('analysis_response.html', response="Upload a valid file")


if __name__ == '__main__':
    app.run(debug=True)
