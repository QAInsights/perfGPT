import logging
import os
import re
import boto3
from botocore.exceptions import ClientError
from flask import redirect, url_for
from flask_dance.contrib.github import github
from boto3.dynamodb.conditions import Key
from integrations.slack.slack import send_slack_notifications
import constants


logging.basicConfig(level=logging.INFO)

dynamodb = boto3.resource('dynamodb',
                          aws_secret_access_key=os.environ['AWS_DYNAMODB_SECRET'],
                          aws_access_key_id=os.environ['AWS_DYNAMODB_KEY'],
                          region_name=constants.AWS_DEFAULT_REGION)

table = dynamodb.Table(os.environ['DYNAMODB_PERFGPT_TABLE'])
settings_table = dynamodb.Table(os.environ['DYNAMODB_SETTINGS_TABLE'])


def log_settings_db(username, slack_webhook=None):
    """

    :param username:
    :param slack_webhook:
    :return:
    """
    try:
        db_response = settings_table.put_item(
            Item={
                "username": username,
                "slack_webhook": slack_webhook
            }
        )
        db_status = "fail"
        if (db_response['ResponseMetadata']['HTTPStatusCode']) == 200:
            db_status = "success"
            return db_status
        else:
            return db_status

    except ClientError as e:
        print(e)


def log_db(username, openai_id=None, openai_prompt_tokens=None, openai_completion_tokens=None, openai_total_tokens=None,
           openai_created=None, slack_webhook=None):
    """

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
    username = None
    try:
        if not github.authorized:
            return redirect(url_for("github.login"))
        resp = github.get("/user")
        username = resp.json()["login"]
        return username
    except Exception as e:
        print(e)
        return username


def get_webhook():
    """

    :return:
    """
    try:
        if not github.authorized:
            return redirect(url_for("github.login"))

        response = settings_table.query(KeyConditionExpression=Key('username').eq(get_username()))
        if response['Items'][0]['slack_webhook']:
            return response['Items'][0]['slack_webhook']
        else:
            return None
        print(response)
    except Exception as e:
        print(e)


def save_webhook_url(integration_type=None, webhook_url=None):
    if not github.authorized:
        return redirect(url_for("github.login"))
    else:
        return log_settings_db(username=get_username(), slack_webhook=webhook_url)