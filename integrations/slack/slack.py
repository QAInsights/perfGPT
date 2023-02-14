import requests


def send_slack_notifications(msg, webhook):
    headers = {
        'Content-type': 'application/json',
    }

    json_data = {
        'text': msg,
    }

    response = requests.post(
        f'https://hooks.slack.com/services/{webhook}',
        headers=headers,
        json=json_data,
    )
    print(response)
