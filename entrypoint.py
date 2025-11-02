#!/usr/bin/env -S python3 -B

import sys
import logging
import re
import urllib.request
import json
import urllib.parse
from datetime import date, timedelta, datetime
from github import Github


DEV_API_URL = "dev.api.uclusion.com/v1"
STAGE_API_URL = "stage.api.uclusion.com/v1"
PRODUCTION_API_URL = "production.api.uclusion.com/v1"
DEV_SECRET_KEY_ID = "942a8a2a-2b72-4def-b4ae-68c020cce326_1a0e71d8-16f9-4984-8cc3-3bbeca8df29a"
STAGE_SECRET_KEY_ID = "24a08ec1-70c0-47d7-9a4f-b7cc3acb3776_8755dc22-ab53-422c-8188-7198d2104d30"


def send(method, my_api_url, auth=None, data=None):
    headers = {'Content-Type': 'application/json'}
    if auth is not None:
        headers['Authorization'] = auth

    if data is not None:
        json_data = json.dumps(data)
        json_data_as_bytes = json_data.encode('utf-8')  # Convert to bytes

        req = urllib.request.Request(
            my_api_url,
            data=json_data_as_bytes,
            headers=headers,
            method=method
        )
    else:
        req = urllib.request.Request(
            my_api_url,
            headers=headers,
            method=method
        )

    with urllib.request.urlopen(req) as response:
        # Check the HTTP status code
        if response.status == 200 or response.status == 201:
            # Read and decode the response body
            response_body = response.read().decode('utf-8')
            # If the response is JSON, you can parse it
            response_json = json.loads(response_body)
            return response_json
        else:
           raise Exception(response.status)


def login(api_url, market_id, secret, secret_id):
    login_api_url = 'https://sso.' + api_url + '/cli'
    data = {
        'market_id': market_id,
        'client_secret': secret,
        'client_id': secret_id
    }
    return send('POST', login_api_url, None, data)


def label_jobs(short_codes, capability, domain, label_to_apply):
    complete_job_api_url = 'https://investibles.' + domain + '/add_labels'
    data = {
        'ticket_codes': short_codes,
        'label': label_to_apply
    }
    return send('PATCH', complete_job_api_url, capability, data)


def get_completed_stage(stages):
    for stage in stages:
        if not stage.get('allows_tasks', True):
            return stage
    raise Exception('No stage found')


def get_date_days_ago(days_in_past):
    today = date.today()
    past_date = today - timedelta(days=days_in_past)
    return datetime.combine(past_date, datetime.min.time())


if __name__ == "__main__" :
    secret_key_id = sys.argv[1]
    secret_key = sys.argv[2]
    workspace_id = sys.argv[3]
    git_token = sys.argv[4]
    git_sha = sys.argv[5]
    git_repository = sys.argv[6]
    label = sys.argv[7]

    logger = logging.getLogger()
    logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(levelname)s: %(message)s')
    git_api_url = f"https://api.github.com/repos/{git_repository}/commits?sha={git_sha}"
    logger.info(f"Git API URL: {git_api_url}")

    api_url = PRODUCTION_API_URL
    if secret_key_id == DEV_SECRET_KEY_ID:
        api_url = DEV_API_URL
    elif secret_key_id == STAGE_SECRET_KEY_ID:
        api_url = STAGE_API_URL
    response = login(api_url, workspace_id, secret_key, secret_key_id)
    if response is None or 'uclusion_token' not in response:
        raise Exception(response)
    api_token = response['uclusion_token']
    stages = response['stages']
    completed_stage = get_completed_stage(stages)
    days_visible = completed_stage['days_visible']

    g = Github(git_token)
    repo = g.get_repo(git_repository)
    commits = repo.get_commits(sha=git_sha, since=get_date_days_ago(days_visible))

    regex = r'([A-Z]+-[A-Za-z]+-\d+)'
    jobs = []
    for commit in commits:
        commit_sha = commit["sha"]
        commit_message = commit["commit"]["message"]

        match = re.search(regex, commit_message)
        if match:
            extracted = match.group(1)
            logger.info('extracted %s', extracted)
            jobs.append(extracted)

    if len(jobs) > 0:
        label_jobs(jobs, api_token, api_url, label)
