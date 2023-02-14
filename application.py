import openai
import pandas as pd
from flask import Flask, request, render_template
from flask import send_from_directory
from flask_dance.contrib.github import make_github_blueprint

import version
from utils import *

logging.basicConfig(level=logging.INFO)


class ReverseProxied(object):
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        # if one of x_forwarded or preferred_url is https, prefer it.
        forwarded_scheme = environ.get("HTTP_X_FORWARDED_PROTO", None)
        preferred_scheme = application.config.get("PREFERRED_URL_SCHEME", None)
        if "https" in [forwarded_scheme, preferred_scheme]:
            environ["wsgi.url_scheme"] = "https"
        return self.app(environ, start_response)


application = Flask(__name__)

application.secret_key = os.environ['FLASK_SECRET_KEY']
application.config["GITHUB_OAUTH_CLIENT_ID"] = os.environ['GITHUB_OAUTH_CLIENT_ID']
application.config["GITHUB_OAUTH_CLIENT_SECRET"] = os.environ['GITHUB_OAUTH_CLIENT_SECRET']
github_bp = make_github_blueprint()

application.config.update(dict(
    PREFERRED_URL_SCHEME='https'
))
application.wsgi_app = ReverseProxied(application.wsgi_app)

application.register_blueprint(github_bp, url_prefix="/login")
# os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Images
IMAGES_FOLDER = os.path.join('static', 'images')
application.config['UPLOAD_FOLDER'] = IMAGES_FOLDER
hero_image = os.path.join(application.config['UPLOAD_FOLDER'], 'perfgpt.png')
invalid_image = os.path.join(application.config['UPLOAD_FOLDER'], 'robot-found-a-invalid-page.png')


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
        return render_template("index.html", image=hero_image, auth=check_authorized_status(),
                               version=version.__version__)

    except Exception as e:
        print(e)
        return render_template("index.html", image=hero_image, auth=check_authorized_status(),
                               version=version.__version__)


@application.errorhandler(404)
def page_not_found(error):
    try:
        auth = check_authorized_status()
        if auth['logged_in']:
            auth['upload_status'] = 1
        else:
            auth['upload_status'] = 0
        response = "We are not there yet 🙁"
        return render_template("invalid.html", image=invalid_image, response=response,
                               auth=check_authorized_status(), version=version.__version__)
    except Exception as e:
        return render_template("invalid.html", image=invalid_image, response=e,
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
        webhook = get_webhook()
    except Exception as e:
        print(e)
    return render_template("account.html",
                           webhook=webhook,
                           settings_saved=None,
                           auth=check_authorized_status(), version=version.__version__)


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
                    return render_template("analysis_response.html", response=responses,
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


@application.route('/saveslack', methods=['POST'])
def save_slack_key():
    if github.authorized:
        settings_saved = save_webhook_url(integration_type="slack", webhook_url=request.form['slack_webhook'])
        if settings_saved == "success":
            return render_template("account.html",
                                   settings_saved="Saved",
                                   auth=check_authorized_status(),
                                   version=version.__version__)
        else:
            return render_template("account.html",
                                   settings_saved="Failed",
                                   auth=check_authorized_status(),
                                   version=version.__version__)


if __name__ == '__main__':
    application.run(host='0.0.0.0', port=80, debug=True)
