import requests
import json


def send_slack_notifications(msg, webhook, title):
    emoji = False

    blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{title}",
                    "emoji": emoji
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "plain_text",
                    "text": f"{msg}",
                    "emoji": emoji
                }
            }
        ]

    data = {
        'blocks': json.dumps(blocks)
    }

    requests.post(f'https://hooks.slack.com/services/{webhook}', json=data)
