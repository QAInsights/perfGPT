from flask import Flask, request, render_template
import openai
import os
import re
import constants
import pandas as pd

application = Flask(__name__)


@application.route('/')
def index():
    """
    index
    :return:    index page
    """
    return render_template("index.html")


@application.route('/about')
def about():
    """

    :return: about page
    """
    return render_template("about.html")


@application.route('/features')
def features():
    """

    :return: features page
    """
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
        num = text[match.start() + offset:match.end() + offset]
        first_half, second_half = text[:match.start() + offset], text[match.end() + offset:]
        text = f'{first_half}<span class="fw-bold">{num}</span>{second_half}'
        offset += 29  # number of chars added by the <span> tags

    return text


@application.route('/upload', methods=['POST'])
def askgpt_upload():
    """
    ask GPT
    :return:    analyzed response from GPT
    """
    # Below prompts dict has the results title and the prompt for GPT to process
    prompts = {
        "High level Summary": "Act like a performance engineer. Please analyse this performance test results and give "
                              "me a high level summary.",
        "Detailed Summary": "Act like a performance engineer and write a detailed summary from this raw performance "
                            "results."
    }
    try:
        openai.api_key = os.environ['OPENAI_API_KEY']
    except KeyError:
        return render_template("analysis_response.html", response="API key not set.")

    if request.files['file'].filename == '':
        return render_template('analysis_response.html', response="Please upload a valid file.")

    if request.method == 'POST':
        if request.files:
            file = request.files['file']
            try:
                if file.filename.endswith('.csv'):
                    contents = pd.read_csv(file)
                if file.filename.endswith('.json'):
                    contents = pd.read_json(file)
            except Exception as e:
                return render_template('analysis_response.html', response="Cannot read file data. Please make sure "
                                                                          "the file is not empty and is in one of the"
                                                                          " supported formats.")

            if contents.memory_usage().sum() > constants.FILE_SIZE:
                return render_template('analysis_response.html', response="File size too large.")
            try:
                responses = {}
                for title, prompt in prompts.items():
                    response = openai.Completion.create(
                        model=constants.model,
                        prompt=f"""
                        {prompt}: \n {contents}
                        """,
                        temperature=constants.temperature,
                        max_tokens=constants.max_tokens,
                        top_p=constants.top_p,
                        frequency_penalty=constants.frequency_penalty,
                        presence_penalty=constants.presence_penalty
                    )
                    response = beautify_response(response['choices'][0]['text'])
                    responses[title] = response
                print(responses)
                return render_template("analysis_response.html", response=responses)
            except Exception as e:
                return render_template("analysis_response.html", response=e)
        else:
            return render_template('analysis_response.html', response="Upload a valid file")


if __name__ == '__main__':
    application.run(host='0.0.0.0', port=80, debug=True)
