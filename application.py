import os
import re
import time

import boto3
import logging
import openai
import pandas as pd
import watchtower
from flask import Flask, request, render_template
from flask import redirect, url_for
from flask_dance.contrib.github import make_github_blueprint, github
import werkzeug
from werkzeug.exceptions import HTTPException

import constants

logging.basicConfig(level=logging.INFO)

application = Flask(__name__)
# For CloudWatch
handler = watchtower.CloudWatchLogHandler(log_group_name="perfgpt", log_stream_name="perfgpt-stream")
handler.formatter.add_log_record_attrs = ["levelname"]
logger = logging.getLogger("perfgpt")
logging.getLogger("perfgpt").addHandler(handler)

application.secret_key = os.environ['FLASK_SECRET_KEY']
application.config["GITHUB_OAUTH_CLIENT_ID"] = os.environ['GITHUB_OAUTH_CLIENT_ID']
application.config["GITHUB_OAUTH_CLIENT_SECRET"] = os.environ['GITHUB_OAUTH_CLIENT_SECRET']
github_bp = make_github_blueprint()
application.register_blueprint(github_bp, url_prefix="/login")
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

dynamodb = boto3.resource('dynamodb',
                          aws_secret_access_key=os.environ['AWS_DYNAMODB_SECRET'],
                          aws_access_key_id=os.environ['AWS_DYNAMODB_KEY'])
table = dynamodb.Table("perfgpt")

# Images
IMAGES_FOLDER = os.path.join('static', 'images')
application.config['UPLOAD_FOLDER'] = IMAGES_FOLDER
hero_image = os.path.join(application.config['UPLOAD_FOLDER'], 'perfgpt.png')
invalid_image = os.path.join(application.config['UPLOAD_FOLDER'], 'robot-found-a-invalid-page.png')


def check_authorized_status():
    if github.authorized:
        upload_status = "enable"
        resp = github.get("/user")
        username = resp.json()["login"]
        return {'logged_in': True, 'upload_status': upload_status, 'username': username}
    else:
        upload_status = "disable"
        return {'logged_in': False, 'upload_status': upload_status, 'username': None}


@application.route('/')
def index():
    """
    index
    :return:    index page
    """
    try:
        auth = check_authorized_status()
        username = auth['username']
        logger.info({"message_type": "user_signin", "username": auth['username']})

    except Exception as e:
        username = ''
        print(e)

    return render_template("index.html", username=username, image=hero_image, auth=auth)


@application.errorhandler(HTTPException)
def page_not_found():
    try:
        openai.api_key = os.environ['OPENAI_API_KEY']
    except KeyError:
        return render_template("analysis_response.html", response="API key not set.", auth=check_authorized_status())
    try:
        response = openai.Completion.create(
            model=constants.model,
            prompt=f"""
            write a four line haiku about invalid page request
            """,
            temperature=constants.temperature,
            max_tokens=constants.max_tokens,
            top_p=constants.top_p,
            frequency_penalty=constants.frequency_penalty,
            presence_penalty=constants.presence_penalty
        )
        print(response)
        return render_template("invalid.html", image=invalid_image, response=response['choices'][0]['text'], username='', auth=check_authorized_status())
    except Exception as e:
        return render_template("invalid.html", image=invalid_image, response=e, username='', auth=check_authorized_status())



@application.route('/signin')
def github_sign():
    if not github.authorized:
        return redirect(url_for("github.login"))
    return redirect('/')


@application.route('/upload')
def upload():
    if not github.authorized:
        return redirect(url_for("github.login"))
    else:
        return render_template('upload.html', auth=check_authorized_status())


@application.route('/about')
def about():
    """

    :return: about page
    """
    logger.info({"message_type": "user_signin", "username": "test"})
    return render_template("about.html", auth=check_authorized_status())


@application.route('/features')
def features():
    """

    :return: features page
    """
    return render_template("features.html", auth=check_authorized_status())


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


@application.route('/analyze', methods=['POST'])
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
    if not github.authorized:
        return redirect(url_for("github.login"))
    resp = github.get("/user")
    username = resp.json()["login"]

    try:
        openai.api_key = os.environ['OPENAI_API_KEY']
    except KeyError:
        return render_template("analysis_response.html", response="API key not set.", auth=check_authorized_status())

    if request.files['file'].filename == '':
        return render_template('analysis_response.html', response="Please upload a valid file.",
                               auth=check_authorized_status())

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
                                                                          " supported formats.",
                                       auth=check_authorized_status())

            if contents.memory_usage().sum() > constants.FILE_SIZE:
                return render_template('analysis_response.html', response="File size too large.",
                                       auth=check_authorized_status())
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
                    logger.info({"username": f"{username} uploaded data"})
                return render_template("analysis_response.html", response=responses, username=username,
                                       auth=check_authorized_status())
            except Exception as e:
                return render_template("analysis_response.html", response=e, auth=check_authorized_status())
        else:
            return render_template('analysis_response.html', response="Upload a valid file",
                                   auth=check_authorized_status())


if __name__ == '__main__':
    application.run(host='0.0.0.0', port=80, debug=True)
