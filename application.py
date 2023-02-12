import logging
import os
import re
import json
import boto3
import openai
import pandas as pd
import watchtower
from botocore.exceptions import ClientError
from flask import Flask, request, render_template
from flask import redirect, url_for, send_from_directory
from flask_dance.contrib.github import make_github_blueprint, github
from boto3.dynamodb.conditions import Key, And

import constants
import version

logging.basicConfig(level=logging.INFO)

application = Flask(__name__)
# For CloudWatch
# handler = watchtower.CloudWatchLogHandler(log_group_name="perfgpt", log_stream_name="perfgpt-stream",
#                                           region_name=constants.AWS_DEFAULT_REGION)
# handler.formatter.add_log_record_attrs = ["levelname"]
# logger = logging.getLogger("perfgpt")
# logging.getLogger("perfgpt").addHandler(handler)

application.secret_key = os.environ['FLASK_SECRET_KEY']
application.config["GITHUB_OAUTH_CLIENT_ID"] = os.environ['GITHUB_OAUTH_CLIENT_ID']
application.config["GITHUB_OAUTH_CLIENT_SECRET"] = os.environ['GITHUB_OAUTH_CLIENT_SECRET']
application.config["PREFERRED_URL_SCHEME"] = "https"
github_bp = make_github_blueprint()
application.register_blueprint(github_bp, url_prefix="/login")
# os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

dynamodb = boto3.resource('dynamodb',
                          aws_secret_access_key=os.environ['AWS_DYNAMODB_SECRET'],
                          aws_access_key_id=os.environ['AWS_DYNAMODB_KEY'],
                          region_name=constants.AWS_DEFAULT_REGION)
table = dynamodb.Table(constants.dynamodb_table)

# Images
IMAGES_FOLDER = os.path.join('static', 'images')
application.config['UPLOAD_FOLDER'] = IMAGES_FOLDER
hero_image = os.path.join(application.config['UPLOAD_FOLDER'], 'perfgpt.png')
invalid_image = os.path.join(application.config['UPLOAD_FOLDER'], 'robot-found-a-invalid-page.png')


def log_db(username, openai_id=None, openai_prompt_tokens=None, openai_completion_tokens=None, openai_total_tokens=None,
           openai_created=None):
    """

    :param username:
    :param openai_id:
    :param openai_prompt_tokens:
    :param openai_completion_tokens:
    :param openai_total_tokens:
    :param openai_created:
    :return:
    """
    try:
        db_response = table.put_item(
            Item={
                "username": username,
                "inital_upload_limit": 10,
                "datetime": str(openai_created),
                "open_id": openai_id,
                "openai_prompt_tokens": openai_prompt_tokens,
                "openai_completion_tokens": openai_completion_tokens,
                "openai_total_tokens": openai_total_tokens,
                "premium_user": False
            }
        )

    except ClientError as e:
        print(e)


def get_upload_count(username):
    try:
        response = table.query(KeyConditionExpression=Key('username').eq(username))
        total_count = response['Count']
        return int(total_count)

    except ClientError as e:
        print(e)


def check_authorized_status():
    if github.authorized:
        resp = github.get("/user")
        username = resp.json()["login"]
        return {'logged_in': True, 'username': username, 'upload_status': 1}
    else:
        return {'logged_in': False, 'username': None, 'upload_status': 0}


@application.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(application.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')


@application.route('/')
def index():
    """
    index
    :return:    index page
    """
    try:
        if github.authorized:
            resp = github.get("/user")
            username = resp.json()["login"]
            log_db(username=username)
        return render_template("index.html", username=username, image=hero_image, auth=check_authorized_status(),
                               version=version.__version__)

    except Exception as e:
        username = ''
        print(e)
        return render_template("index.html", username=username, image=hero_image, auth=check_authorized_status(),
                               version=version.__version__)


@application.errorhandler(Exception)
def page_not_found(error):
    try:
        openai.api_key = os.environ['OPENAI_API_KEY']
    except KeyError:
        return render_template("analysis_response.html", response="API key not set.", auth=check_authorized_status(),
                               version=version.__version__)
    try:
        auth = check_authorized_status()
        username = auth['username']
        if auth['logged_in']:
            auth['upload_status'] = 1
        else:
            auth['upload_status'] = 0
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
        return render_template("invalid.html", image=invalid_image, response=response['choices'][0]['text'],
                               username='', auth=check_authorized_status(), version=version.__version__)
    except Exception as e:
        return render_template("invalid.html", image=invalid_image, response=e, username='',
                               auth=check_authorized_status(), version=version.__version__)


@application.route('/signin')
def github_sign():
    if not github.authorized:
        return redirect(url_for("github.login"))
    else:
        username = check_authorized_status()['username']
        log_db(username=username)
    return redirect('/')


@application.route('/upload')
def upload():
    try:
        if not github.authorized:
            return redirect(url_for("github.login"))
        else:
            upload_count = get_upload_count(check_authorized_status()['username']) - 1
            if upload_count == 0:
                return render_template('upload.html', auth=check_authorized_status(),
                                       upload_count=0,
                                       version=version.__version__)
            else:
                return render_template('upload.html', auth=check_authorized_status(),
                                       upload_count=upload_count,
                                       version=version.__version__)
    except Exception as e:
        print(e)


@application.route('/about')
def about():
    """

    :return: about page
    """
    # logger.info({"message_type": "user_signin", "username": "test"})
    return render_template("about.html", auth=check_authorized_status(), version=version.__version__)


@application.route('/features')
def features():
    """

    :return: features page
    """
    return render_template("features.html", auth=check_authorized_status(), version=version.__version__)


@application.route('/help')
def help_page():
    """

    :return: help page
    """
    return render_template("help.html", auth=check_authorized_status(), version=version.__version__)


def get_analysis(username):
    # response = table.query(KeyConditionExpression=Key('username').eq(username))
    # total_count = response['Count']
    # print(json.dumps(response['Items']))
    # for i, j in json.dumps(response['Items']).items():
    # print(i, j)
    # pass

    # for k,v in response.items():
    #     print(k, type(k), v, type(v))
    pass


@application.route('/account')
def account():
    """

    :return:
    """
    try:
        username = check_authorized_status()['username']
        get_analysis(username)
    except Exception as e:
        print(e)
    return render_template("account.html", auth=check_authorized_status(), version=version.__version__)


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
    try:
        if not github.authorized:
            return redirect(url_for("github.login"))
        resp = github.get("/user")
        username = resp.json()["login"]
        upload_count = get_upload_count(check_authorized_status()['username']) - 1
        print("Upload count " + str(upload_count))
        try:
            openai.api_key = os.environ['OPENAI_API_KEY']
        except KeyError:
            return render_template("analysis_response.html", response="API key not set.",
                                   auth=check_authorized_status(),
                                   upload_count=upload_count,
                                   version=version.__version__)

        if request.files['file'].filename == '':
            return render_template('analysis_response.html', response="Please upload a valid file.",
                                   auth=check_authorized_status(),
                                   upload_count=upload_count,
                                   version=version.__version__)

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
                                           auth=check_authorized_status(),
                                           upload_count=upload_count,
                                           version=version.__version__)

                if contents.memory_usage().sum() > constants.FILE_SIZE:
                    return render_template('analysis_response.html', response="File size too large.",
                                           auth=check_authorized_status(),
                                           upload_count=upload_count,
                                           version=version.__version__)
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
                        # print(response)
                        # logger.info({"username": f"{username} uploaded data"})

                        log_db(username=username, openai_id=response['id'],
                               openai_prompt_tokens=response['usage']['prompt_tokens'],
                               openai_completion_tokens=response['usage']['completion_tokens'],
                               openai_total_tokens=response['usage']['total_tokens'],
                               openai_created=response['created'])

                        response = beautify_response(response['choices'][0]['text'])

                        responses[title] = response
                    return render_template("analysis_response.html", response=responses, username=username,
                                           auth=check_authorized_status(),
                                           upload_count=upload_count,
                                           version=version.__version__)
                except Exception as e:
                    return render_template("analysis_response.html", response=e, auth=check_authorized_status(),
                                           upload_count=upload_count,
                                           version=version.__version__)
            else:
                return render_template('analysis_response.html', response="Upload a valid file",
                                       auth=check_authorized_status(),
                                       upload_count=upload_count,
                                       version=version.__version__)
    except Exception as e:
        print(e)


if __name__ == '__main__':
    application.run(host='0.0.0.0', port=80, debug=True, url_scheme='https')
