import boto3
from botocore.exceptions import ClientError
import json
import os

import constants


class Sts:
    def __init__(self) -> None:
        self._aws_access_key_id = None
        self._aws_secret_access_key = None
        self._aws_session_token = None

    def set_credentials(self, aws_access_key_id, aws_secret_access_key, aws_session_token):
        self._aws_access_key_id = aws_access_key_id
        self._aws_secret_access_key = aws_secret_access_key
        self._aws_session_token = aws_session_token

    def get_credentials(self):
        return self._aws_access_key_id, self._aws_secret_access_key, self._aws_session_token

    @property
    def aws_access_key_id(self):
        return self._aws_access_key_id

    @property
    def aws_secret_access_key(self):
        return self._aws_secret_access_key

    @property
    def aws_session_token(self):
        return self._aws_session_token


def get_secret(secret_name, region_name):
    sts_client = boto3.client('sts',
                              region_name=region_name,
                              aws_access_key_id=os.environ['AWS_DYNAMODB_KEY'],
                              aws_secret_access_key=os.environ['AWS_DYNAMODB_SECRET']
                              )

    credentials = Sts()

    response = sts_client.assume_role(RoleArn=os.environ['ARN'],
                                      RoleSessionName='my_session')
    access_key_id = response['Credentials']['AccessKeyId']
    secret_access_key = response['Credentials']['SecretAccessKey']
    session_token = response['Credentials']['SessionToken']
    # credentials.set_credentials(access_key_id, secret_access_key, session_token)

    try:
        secrets_client = boto3.client(
            'secretsmanager',
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            aws_session_token=session_token)

        get_secret_value_response = secrets_client.get_secret_value(
            SecretId=secret_name
        )

    except ClientError as e:
        raise e

    secret = json.loads(get_secret_value_response['SecretString'])

    return secret[secret_name]
