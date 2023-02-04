from flask import Flask, request, render_template
import openai
import os
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
                return render_template("analysis_response.html", response=response['choices'][0]['text'])
            except Exception as e:
                return e
        else:
            return render_template('analysis_response.html', response="Upload a valid file")


if __name__ == '__main__':
    app.run(debug=True)
