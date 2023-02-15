from utils import get_total_users_count, get_total_tokens_all, get_upload_counts_all

try:
    with open('analytics.py', 'w') as f:
        f.writelines(f"total_users = {get_total_users_count()}\n")
        f.writelines(f"total_tokens = {get_total_tokens_all()}\n")
        f.writelines(f"total_uploads = {get_upload_counts_all()}\n")

except FileNotFoundError as e:
    print(e)
