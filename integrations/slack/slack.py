import requests
import json
import datetime

def send_slack_notifications(msg, webhook, title, filename):
    emoji = False

    blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"PerfGPT analysis for {filename} at {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
                    "emoji": emoji
                }
            },
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
