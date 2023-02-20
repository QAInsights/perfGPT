import openai
import pandas as pd
from flask import Flask, request, render_template, redirect, url_for
from flask import send_from_directory
from flask_dance.contrib.github import make_github_blueprint

from integrations.slack import slack
import version
from utils import *
from analytics import *
from mixpanel import Mixpanel
from sentry_sdk import capture_exception
import sentry_sdk
from sentry_sdk import start_transaction
from sentry_sdk.integrations.flask import FlaskIntegration

application = Flask(__name__)

# Load all env variables
_vars = load_env_vars(application)

sentry_sdk.init(
    dsn=_vars['SENTRY_KEY'],
    integrations=[
        FlaskIntegration(),
    ],
    traces_sample_rate=1.0
)

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


# Authentication middleware
def login_required(func):
    def wrapper(*args, **kwargs):
        if not github.authorized:
            return redirect(url_for("github.login"))
        return func(*args, **kwargs)

    wrapper.__name__ = func.__name__
    return wrapper


mp = Mixpanel(_vars['MIXPANEL_US'])
github_bp = make_github_blueprint()

application.config.update(dict(PREFERRED_URL_SCHEME='https'))
application.wsgi_app = ReverseProxied(application.wsgi_app)
application.register_blueprint(github_bp, url_prefix="/login")

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
@application.route('/debug-sentry')
def index():
    """
    index
    :return:    index page
    """
    try:
        if github.authorized:
            username = get_username()
            log_db(username=username)
        with start_transaction(op="task", name="Home Page"):
            get_analytics_response = get_analytics_data()
            return render_template("index.html", image=hero_image,
                                   total_tokens=get_analytics_response['total_tokens'],
                                   total_users=get_analytics_response['total_users'],
                                   total_uploads=get_analytics_response['total_uploads'],
                                   auth=check_authorized_status(),
                                   version=version.__version__)

    except Exception as e:
        print(e)
        capture_exception(e)
        return render_template("index.html", image=hero_image, auth=check_authorized_status(),
                               version=version.__version__)


@application.errorhandler(404)
@application.route('/debug-sentry')
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
        capture_exception(e)
        return render_template("invalid.html", image=invalid_image, response=e,
                               auth=check_authorized_status(), version=version.__version__)


@application.route('/signin')
@application.route('/debug-sentry')
@login_required
def github_sign():
    username = get_username()
    log_db(username=username)
    mp.track(username, 'User signed up')

    return redirect('/')


@application.route('/upload')
@application.route('/debug-sentry')
@login_required
def upload():
    try:
        mp.track(get_username(), 'Users in Upload page')
        with start_transaction(op="task", name="Upload Page"):

            upload_count = get_upload_count(get_username()) - 1

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
        capture_exception(e)
        return render_template("invalid.html", image=invalid_image, response=e,
                               auth=check_authorized_status(), version=version.__version__)


@application.route('/about')
@application.route('/debug-sentry')
def about():
    """

    :return: about page
    """
    # logger.info({"message_type": "user_signin", "username": "test"})
    return render_template("about.html", auth=check_authorized_status(), version=version.__version__)


@application.route('/features')
@application.route('/debug-sentry')
def features():
    """

    :return: features page
    """
    return render_template("features.html", auth=check_authorized_status(), version=version.__version__)


@application.route('/help')
@application.route('/debug-sentry')
def help_page():
    """

    :return: help page
    """
    return render_template("help.html", auth=check_authorized_status(), version=version.__version__)


@application.route('/account')
@application.route('/debug-sentry')
@login_required
def account():
    """

    :return:
    """
    try:
        username = get_username()
        get_analysis(username)
        webhook = get_webhook()
        slack_notification_status = get_slack_notification_status()

        mp.track(username, "Users in Settings page")
        return render_template("account.html",
                               webhook=webhook,
                               settings_saved=None,
                               slack_notification_status=slack_notification_status,
                               auth=check_authorized_status(), version=version.__version__)
    except Exception as e:
        print(e)
        capture_exception(e)
        return render_template("invalid.html", image=invalid_image, response=e,
                               auth=check_authorized_status(), version=version.__version__)


def fetch_performance_results(contents, filename, username):
    """Fetch the performance results from OpenAI
    :param contents: contents of uploaded file
    :param file: uploaded filename
    :param username: logged in username
    :return: response from OpenAI
    """
    # Below prompts dict has the results title and the prompt for GPT to process
    prompts = {
        "High level Summary": "Act like a performance engineer. Please analyse this performance test results and give "
                              "me a high level summary.",
        "Detailed Summary": "Act like a performance engineer and write a detailed summary from this raw performance "
                            "results."
    }

    results = {}
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
        log_db(username=username, openai_id=response['id'],
                openai_prompt_tokens=response['usage']['prompt_tokens'],
                openai_completion_tokens=response['usage']['completion_tokens'],
                openai_total_tokens=response['usage']['total_tokens'],
                openai_created=response['created'])

        # Send Slack Notifications if enabled
        if get_slack_notification_status() == 'true':
            try:
                slack.send_slack_notifications(msg=response['choices'][0]['text'],
                                                filename=filename,
                                                title=title,
                                                webhook=get_webhook())
            except Exception as e:
                capture_exception(e)
                pass

        response = beautify_response(response['choices'][0]['text'])

        results[title] = response

    return results


@application.route('/analyze', methods=['POST'])
@application.route('/debug-sentry')
@login_required
def askgpt_upload():
    """
    ask GPT
    :return:    analyzed response from GPT
    """
    try:
        username = get_username()
        upload_count = get_upload_count(username) - 1
        try:
            openai.api_key = _vars['OPENAI_API_KEY']
        except KeyError:

            return render_template("analysis_response.html", response="API key not set.",
                                   auth=check_authorized_status(),
                                   upload_count=upload_count,
                                   version=version.__version__)

        if request.files:
            if request.files['file'].filename == '':
                return render_template('analysis_response.html', response="Please upload a valid file.",
                                       auth=check_authorized_status(),
                                       upload_count=upload_count,
                                       version=version.__version__)
            file = request.files['file']
            try:
                if file.filename.endswith('.csv') or file.filename.endswith('.jtl'):
                    contents = pd.read_csv(file)
                if file.filename.endswith('.json'):
                    contents = pd.read_json(file)
            except Exception as e:
                capture_exception(e)
                return render_template('invalid.html', response="Cannot read file data. Please make sure "
                                                                          "the file is not empty and is in one of "
                                                                          "the"
                                                                          " supported formats.",
                                       auth=check_authorized_status(),
                                       upload_count=upload_count,
                                       version=version.__version__)

            if contents.memory_usage().sum() > constants.FILE_SIZE:
                return render_template('invalid.html', response="File size too large.",
                                       auth=check_authorized_status(),
                                       upload_count=upload_count,
                                       version=version.__version__)
            try:
                results = fetch_performance_results(contents, file.filename, username)
                return render_template("analysis_response.html", response=results,
                                        auth=check_authorized_status(),
                                        upload_count=upload_count,
                                        version=version.__version__)
            except Exception as e:
                return render_template("invalid.html", response=e, auth=check_authorized_status(),
                                       upload_count=upload_count,
                                       version=version.__version__)
        else:
            return render_template('invalid.html', response="Upload a valid file",
                                   auth=check_authorized_status(),
                                   upload_count=upload_count,
                                   version=version.__version__)
    except Exception as e:
        print(e)
        capture_exception(e)
        return render_template("invalid.html", image=invalid_image, response=e,
                               auth=check_authorized_status(), version=version.__version__)


@application.route('/saveslack', methods=['POST'])
@application.route('/debug-sentry')
@login_required
def save_slack_key():
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


@application.route('/sendslacknotifications', methods=['POST'])
@application.route('/debug-sentry')
@login_required
def save_slack_notifications():
    try:
        status = request.form['status']
        log_settings_db(username=get_username(), slack_webhook=get_webhook(), send_notifications=status)
        return "Done"
    except Exception as e:
        capture_exception(e)


if __name__ == '__main__':
    application.run(host='0.0.0.0', port=80, debug=True)
