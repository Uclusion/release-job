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


def get_job_report(short_code, capability, domain):
    report_api_url = 'https://investibles.' + domain + '/cli_report/' + urllib.parse.quote(short_code)
    return send('GET', report_api_url, capability)


def get_enclosing_job_code(report):
    if not report:
        return None
    match = re.search(r'##\s*Job\s+(J-[A-Za-z\s]+-\d+)', report)
    return match.group(1).strip() if match else None


# Open items render as '#### <Type> <code>'; resolved ones render '#### Resolved <Type> ...' (no match).
# Open suggestions, questions, and blockers count like tasks: the deployed label implies the job is
# done, which resolves them, so they must block it too (B-all-478 / Q-all-219).
OPEN_WORK_HEADINGS = ('\n#### Task ', '\n#### Suggestion ', '\n#### Question ', '\n#### Issue ')


def job_has_open_work(report):
    return report is not None and any(heading in report for heading in OPEN_WORK_HEADINGS)


def add_note(short_code, body, capability, domain):
    note_api_url = 'https://investibles.' + domain + '/cli/' + urllib.parse.quote(short_code)
    return send('POST', note_api_url, capability, {'body': body, 'tz': 'UTC'})


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

    code_regex = r'([A-Z]+-[A-Za-z\s]+-\d+)'

    def latest_codes(commit_list):
        # commit_list is newest-first, so the first sha seen for a code is that code's latest commit.
        found = {}
        for a_commit in commit_list:
            match = re.search(code_regex, a_commit.commit.message)
            if match:
                code = match.group(1).strip()
                if code not in found:
                    found[code] = a_commit.sha
        return found

    # Commits reachable from the release ref = what is on this environment.
    on_env_latest = latest_codes(commits)
    # Latest commit per code on the default branch - may include commits not yet on this environment.
    head_latest = latest_codes(repo.get_commits(sha=repo.default_branch,
                                                since=get_date_days_ago(days_visible)))

    def is_current_on_env(code):
        # A code is 'on this environment' only when its newest commit anywhere is also the newest that
        # reached here. So a reopened-and-recommitted task whose OLD commit shipped to another
        # environment is not counted as deployed (C-all-1051).
        return code in head_latest and on_env_latest.get(code) == head_latest[code]

    if on_env_latest:
        # Per-task record: label a task/bug only if its LATEST commit is the one on this environment.
        current_task_codes = [c for c in on_env_latest
                              if not c.startswith('J-') and is_current_on_env(c)]
        if current_task_codes:
            label_jobs(current_task_codes, api_token, api_url, label)

        # Resolve each release code to its enclosing job (one report fetch gives the job + its tasks).
        job_reports = {}
        for code in on_env_latest:
            try:
                report = get_job_report(code, api_token, api_url)
            except Exception as e:
                logger.info('could not fetch report for %s: %s', code, e)
                continue
            job_code = code if code.startswith('J-') else get_enclosing_job_code(report)
            if not job_code:
                logger.info('no enclosing job for %s', code)
                continue
            job_reports.setdefault(job_code, report)

        for job_code, report in job_reports.items():
            try:
                # A job's committed units are the codes in its report that actually have a commit.
                committed = [c for c in set(re.findall(code_regex, report)).union({job_code})
                             if c in head_latest]
                pending = sorted(c for c in committed if not is_current_on_env(c))
                # Fully deployed only if every committed unit's LATEST commit is on this environment
                # AND no open tasks, suggestions, questions, or blockers remain (J-all-329 / B-all-478).
                fully_deployed = committed and not pending and not job_has_open_work(report)
                if fully_deployed:
                    label_jobs([job_code], api_token, api_url, label)
                    summary = label + '. All committed tasks have their latest commit on this environment.'
                elif pending:
                    summary = (label + ' not applied: ' + ', '.join(pending)
                               + ' has a newer commit not on this environment'
                               + (' and open work remains' if job_has_open_work(report) else '') + '.')
                else:
                    summary = label + ' not applied: the job still has open tasks, suggestions, questions, or blockers.'
                add_note(job_code, summary, api_token, api_url)
            except Exception as e:
                logger.info('could not reconcile job %s: %s', job_code, e)
