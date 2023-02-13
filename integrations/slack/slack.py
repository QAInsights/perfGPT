import requests


def send_slack_notifications(msg):
    headers = {
        'Content-type': 'application/json',
    }

    json_data = {
        'text': msg,
    }

    response = requests.post(
        'https://hooks.slack.com/services/{{test}}',
        headers=headers,
        json=json_data,
    )
    print(response)
