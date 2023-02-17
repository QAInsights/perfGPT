import boto3
from botocore.exceptions import ClientError
import json


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
            aws_access_key_id=credentials.aws_access_key_id,
            aws_secret_access_key=credentials.aws_secret_access_key,
            aws_session_token=credentials.aws_session_token,
            region_name=region_name)

        get_secret_value_response = secrets_client.get_secret_value(
            SecretId=secret_name
        )

    except ClientError as e:
        raise e

    secret = json.loads(get_secret_value_response['SecretString'])

    return secret[secret_name]
