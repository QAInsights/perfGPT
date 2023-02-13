import requests


def send_slack_notifications(msg):
    headers = {
        'Content-type': 'application/json',
    }

    json_data = {
        'text': msg,
    }

    response = requests.post(
        'https://hooks.slack.com/services/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',
        headers=headers,
        json=json_data,
    )
    print(response)
