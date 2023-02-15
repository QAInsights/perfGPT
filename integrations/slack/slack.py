import requests
import json


def send_slack_notifications(msg, webhook):
    message = {
        "text": f"{msg}",
        "mrkdwn": True
    }

    requests.post(f'https://hooks.slack.com/services/{webhook}',
                  data=json.dumps(message),
                  headers={"Content-Type": "application/json"})
