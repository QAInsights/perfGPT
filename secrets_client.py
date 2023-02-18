import boto3
from botocore.exceptions import ClientError
import json
from sentry_sdk import capture_exception
import datetime


class STSCredentials:
    def __init__(self, role_arn):
        self.role_arn = role_arn
        self.session_name = "my_session"
        self.credentials = None
        self.expiration = None

    def get_credentials(self):
        now_utc = datetime.datetime.utcnow()
        now_utc_str = now_utc.strftime('%Y-%m-%d %H:%M:%S+00:00')
        now_utc = datetime.datetime.strptime(now_utc_str, '%Y-%m-%d %H:%M:%S+00:00')
        if self.expiration:
            expiration_str = self.expiration.strftime('%Y-%m-%d %H:%M:%S+00:00')
            expiration = datetime.datetime.strptime(expiration_str, '%Y-%m-%d %H:%M:%S+00:00')

        if self.credentials is None or now_utc >= expiration:
            sts_client = boto3.client('sts')
            response = sts_client.assume_role(
                RoleArn=self.role_arn,
                RoleSessionName=self.session_name,
                DurationSeconds=900
            )
            self.credentials = response['Credentials']
            expiration_str = str(self.credentials['Expiration'])
            dt = datetime.datetime.fromisoformat(expiration_str)
            self.expiration = dt - datetime.timedelta(minutes=5)

        return self.credentials

    def set_arn(self, role_arn):
        self.role_arn = role_arn


def get_secret(secret_name, region_name, credentials):
    """Get secrets from AWS Secret Manager

    :param str secret_name: secret name
    :param str region_name: region name
    :param Sts credentials: Sts credentials object
    :raises e: ClientError
    :return str: value of the secret
    """
    try:

        secrets_client = boto3.client(
            'secretsmanager',
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken'],
            region_name=region_name)

        get_secret_value_response = secrets_client.get_secret_value(
            SecretId=secret_name
        )

    except ClientError as e:
        capture_exception(e)
        raise e

    secret = json.loads(get_secret_value_response['SecretString'])

    return secret[secret_name]
