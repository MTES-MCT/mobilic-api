import re
import subprocess


def extract_timestamp_from_log(log):
    return log[:19]


def extract_endpoint_from_log(log):
    endpoint_pattern = r'/graphql "(\w+)"'
    endpoint_match = re.search(endpoint_pattern, log)
    return endpoint_match.group(1) if endpoint_match else ""


def extract_time_from_log(log):
    time_pattern = r"time=(\d+)ms"
    time_match = re.search(time_pattern, log)
    return int(time_match.group(1)) if time_match else None


def extract_user_from_log(log):
    username_pattern = r"user=([\w\s]+) user_id"
    userid_pattern = r"user_id=([\d]+)"

    username_match = re.search(username_pattern, log)
    userid_match = re.search(userid_pattern, log)

    username = username_match.group(1) if username_match else ""
    userid = userid_match.group(1) if userid_match else ""

    return (username, userid)


def get_long_requests(nb_results=20, nb_lines=10000):
    cmd = f"scalingo --region osc-fr1 --app mobilic-api logs --lines {nb_lines} | grep '\[web-' | awk 'NF'"

    lines = [
        l.decode("utf-8")
        for l in subprocess.check_output(cmd, shell=True).splitlines()
    ]

    data = []
    for line in lines:
        time = extract_time_from_log(line)
        if time is None:
            continue
        data.append((time, line))
    data.sort(key=lambda l: l[0], reverse=True)
    for d in data[:nb_results]:
        (ms, text) = d
        (username, userid) = extract_user_from_log(text)
        ts = extract_timestamp_from_log(text)
        endpoint = extract_endpoint_from_log(text)
        print(
            " - ".join(
                [f"{ms} ms", ts, endpoint, f"id={userid}", f"name={username}"]
            )
        )


def get_user_requests(user_id, nb_results=20, nb_lines=10000):
    cmd = f"scalingo --region osc-fr1 --app mobilic-api logs --lines {nb_lines} | grep 'user_id={user_id}'"

    lines = [
        l.decode("utf-8")
        for l in subprocess.check_output(cmd, shell=True).splitlines()
    ]

    for l in lines[:nb_results]:
        print(l)
