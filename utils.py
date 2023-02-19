import json
import logging
import os
import re
import traceback
from decimal import Decimal

import boto3
import requests
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from flask_dance.contrib.github import github
from sentry_sdk import capture_exception

import constants
import secrets_client
from secrets_client import STSCredentials

logging.basicConfig(level=logging.INFO)

sts_client = boto3.client('sts',
                          region_name=constants.AWS_DEFAULT_REGION,
                          aws_access_key_id=os.environ['AWS_DYNAMODB_KEY'],
                          aws_secret_access_key=os.environ['AWS_DYNAMODB_SECRET']
                          )
sts_credentials = STSCredentials(os.environ['ARN'])

dynamodb = None
table = None
settings_table = None


def load_env_vars(application):
    global sts_credentials, dynamodb, table, settings_table
    load_dotenv()
    _vars = {}
    _vars['ARN'] = os.environ['ARN']
    sts_credentials.set_arn(_vars['ARN'])
    credentials = sts_credentials.get_credentials(sts_client)

    dynamodb = init_dynamodb()


    if os.getenv('FLASK_ENV') == "development":
        application.secret_key = os.environ['FLASK_SECRET_KEY']
        application.config["GITHUB_OAUTH_CLIENT_ID"] = os.environ['GITHUB_OAUTH_CLIENT_ID']
        application.config["GITHUB_OAUTH_CLIENT_SECRET"] = os.environ['GITHUB_OAUTH_CLIENT_SECRET']
        _vars['MIXPANEL_US'] = os.environ['MIXPANEL_US']
        _vars['OPENAI_API_KEY'] = os.environ['OPENAI_API_KEY']
        _vars['SENTRY_KEY'] = os.environ['SENTRY_KEY']
        _vars['ARN'] = os.environ['ARN']

    elif os.getenv('FLASK_ENV') == "production":

        application.secret_key = os.environ['FLASK_SECRET_KEY']
        application.config["GITHUB_OAUTH_CLIENT_ID"] = secrets_client.get_secret('GITHUB_OAUTH_CLIENT_ID',
                                                                                 constants.AWS_DEFAULT_REGION,
                                                                                 credentials)
        application.config["GITHUB_OAUTH_CLIENT_SECRET"] = secrets_client.get_secret('GITHUB_OAUTH_CLIENT_SECRET',
                                                                                     constants.AWS_DEFAULT_REGION,
                                                                                     credentials)
        _vars['MIXPANEL_US'] = secrets_client.get_secret('MIXPANEL_US',
                                                         constants.AWS_DEFAULT_REGION,
                                                         credentials)
        _vars['OPENAI_API_KEY'] = secrets_client.get_secret('OPENAI_API_KEY',
                                                            constants.AWS_DEFAULT_REGION,
                                                            credentials)

        _vars['ANALYTICS_URL'] = secrets_client.get_secret('ANALYTICS_URL',
                                                           constants.AWS_DEFAULT_REGION,
                                                           credentials)
        _vars['SENTRY_KEY'] = secrets_client.get_secret('SENTRY_KEY',
                                                        constants.AWS_DEFAULT_REGION,
                                                        credentials)

    else:
        print("No environment exists.")
        exit(1)
    sts_credentials = STSCredentials(os.environ['ARN'])
    return _vars


def print_exceptions(e):
    print("Exception occurred on line:", traceback.format_exc().split("\n"))


def init_dynamodb():

    global dynamodb, sts_credentials, table, settings_table
    try:

        credentials = sts_credentials.get_credentials(sts_client)

        session = boto3.Session(
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken']
        )
        dynamodb = session.resource('dynamodb',
                                    region_name=constants.AWS_DEFAULT_REGION)
        table = dynamodb.Table(os.environ['DYNAMODB_PERFGPT_TABLE'])
        settings_table = dynamodb.Table(os.environ['DYNAMODB_SETTINGS_TABLE'])

        return dynamodb
    except Exception as e:
        print_exceptions(e)
        capture_exception(e)
        print(e)


def log_settings_db(username, slack_webhook=None, send_notifications=None, dynamodb=None):
    """

    :param dynamodb:
    :param send_notifications:
    :param username:
    :param slack_webhook:
    :return:
    """
    try:
        init_dynamodb()
        db_response = settings_table.put_item(
            Item={
                "username": username,
                "slack_webhook": slack_webhook,
                "send_notifications": send_notifications
            }
        )
        db_status = "fail"
        if (db_response['ResponseMetadata']['HTTPStatusCode']) == 200:
            db_status = "success"
            return db_status
        else:
            return db_status

    except ClientError as e:
        if e.response['Error']['Code'] == 'ExpiredTokenException':
            print("The security token has expired. Please refresh your token.")
            # re_init()
            capture_exception(e)
            print_exceptions(e)

        else:
            print(f"An error occurred: {e}")


def log_db(username, openai_id=None, openai_prompt_tokens=None, openai_completion_tokens=None, openai_total_tokens=None,
           openai_created=None, slack_webhook=None, dynamodb=None):
    """

    :param dynamodb:
    :param slack_webhook:
    :param username:
    :param openai_id:
    :param openai_prompt_tokens:
    :param openai_completion_tokens:
    :param openai_total_tokens:
    :param openai_created:
    :return:
    """
    try:
        init_dynamodb()
        db_response = table.put_item(
            Item={
                "username": username,
                "inital_upload_limit": 10,
                "datetime": str(openai_created),
                "open_id": openai_id,
                "openai_prompt_tokens": openai_prompt_tokens,
                "openai_completion_tokens": openai_completion_tokens,
                "openai_total_tokens": openai_total_tokens,
                "slack_webhook": slack_webhook,
                "premium_user": False
            }
        )
    except ClientError as e:
        print_exceptions(e)
        if e.response['Error']['Code'] == 'ExpiredTokenException':
            print("The security token has expired. Please refresh your token.")

        else:
            print(f"An error occurred: {e}")
            capture_exception(e)


def get_upload_count(username):
    """

    :param username:    username
    :return:            returns the upload count of the user
    """
    try:
        init_dynamodb()
        total_count = 0
        response = table.query(KeyConditionExpression=Key('username').eq(username))
        if response:
            total_count = response['Count']
        return int(total_count)
    except ClientError as e:
        print_exceptions(e)
        if e.response['Error']['Code'] == 'ExpiredTokenException':
            print("The security token has expired. Please refresh your token.")

        else:
            print(f"An error occurred: {e}")
            capture_exception(e)


def check_authorized_status():
    """

    :return:    checks the authorized status, then returns boolean
    """
    if github.authorized:
        resp = github.get("/user")
        username = resp.json()["login"]
        return {'logged_in': True, 'username': username, 'upload_status': 1}
    else:
        return {'logged_in': False, 'username': None, 'upload_status': 0}


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


def get_username():
    """

    :return:    return the username if logged in
    """
    username = None
    try:
        resp = github.get("/user")
        username = resp.json()["login"]
        return username
    except Exception as e:
        print_exceptions(e)
        capture_exception(e)
        return username


def get_webhook():
    """
    get the saved webhook
    :return:
    """
    try:
        init_dynamodb()
        response = settings_table.query(KeyConditionExpression=Key('username').eq(get_username()))

        if response['Items']:
            if response['Items'][0]['slack_webhook']:
                return response['Items'][0]['slack_webhook']
        return None
    except ClientError as e:
        print_exceptions(e)
        if e.response['Error']['Code'] == 'ExpiredTokenException':
            print("The security token has expired. Please refresh your token.")
            capture_exception(e)
        else:
            print(f"An error occurred: {e}")
            capture_exception(e)


def save_webhook_url(integration_type=None, webhook_url=None):
    """
    saves the slack webhook url
    :param integration_type:
    :param webhook_url:
    :return:
    """
    return log_settings_db(username=get_username(), slack_webhook=webhook_url, send_notifications="no")


def get_total_users_count():
    """

    :return:    total users count
    """
    try:
        init_dynamodb()
        response = table.scan()
        users = set()
        for item in response['Items']:
            users.add(item['username'])
        return len(users)
    except ClientError as e:
        print_exceptions(e)
        if e.response['Error']['Code'] == 'ExpiredTokenException':
            print("The security token has expired. Please refresh your token.")
            capture_exception(e)
        else:
            print(f"An error occurred: {e}")
            capture_exception(e)


def get_upload_counts_all():
    """
    return the total upload count for all the users
    :return:    count of open_id count
    """
    try:
        init_dynamodb()
        response = table.scan()
        unique_openids = set()
        for item in response['Items']:
            unique_openids.add(item['open_id'])

        return len(unique_openids)
    except ClientError as e:
        print_exceptions(e)
        if e.response['Error']['Code'] == 'ExpiredTokenException':
            print("The security token has expired. Please refresh your token.")
            capture_exception(e)
        else:
            print(f"An error occurred: {e}")
            capture_exception(e)


def get_total_tokens_all():
    """

    :return:    count of all the tokens from all the users
    """
    try:
        init_dynamodb()
        response = table.scan()
        openai_total_tokens = set()
        for item in response['Items']:
            openai_total_tokens.add(item['openai_total_tokens'])

        total_tokens = Decimal('0')
        for item in openai_total_tokens:
            if item is not None:
                total_tokens += item

        return total_tokens
    except ClientError as e:
        print_exceptions(e)
        if e.response['Error']['Code'] == 'ExpiredTokenException':
            print("The security token has expired. Please refresh your token.")
            capture_exception(e)
        else:
            print(f"An error occurred: {e}")
            capture_exception(e)


def get_slack_notification_status():
    """

    :return:    the Slack notifications status true or false
    """
    try:
        init_dynamodb()
        response = settings_table.query(KeyConditionExpression=Key('username').eq(get_username()))
        if response['Items']:
            if response['Items'][0]['send_notifications']:
                return response['Items'][0]['send_notifications']
            else:
                return None
    except ClientError as e:
        print_exceptions(e)
        if e.response['Error']['Code'] == 'ExpiredTokenException':
            print("The security token has expired. Please refresh your token.")
            capture_exception(e)
        else:
            print(f"An error occurred: {e}")
            capture_exception(e)


def get_analytics_data():
    """

    :return:    get analytics data from dynamodb
    """
    try:
        init_dynamodb()
        credentials = sts_credentials.get_credentials(sts_client)
        if os.getenv('FLASK_ENV') == "development":
            get_analytics = requests.get(os.environ['AWS_GATEWAY_URL']).text
        elif os.getenv('FLASK_ENV') == "production":
            get_analytics = requests.get(secrets_client.get_secret('ANALYTICS_URL',
                                                                   constants.AWS_DEFAULT_REGION,
                                                                   credentials)).text
        else:
            print("No environment exits")

        return json.loads(get_analytics)
    except ClientError as e:
        print_exceptions(e)
        capture_exception(e)


if __name__ == '__main__':
    print("Test")
