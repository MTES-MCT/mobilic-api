import re
import subprocess


def extract_timestamp_from_log(log):
    return log[:19]


def extract_endpoint_from_log(log):
    endpoint_pattern = r'/graphql "(\w+)"'
    endpoint_match = re.search(endpoint_pattern, log)
    return endpoint_match.group(1) if endpoint_match else ""


def extract_path_from_log(log):
    path_pattern = r'path="([^"]+)"'
    path_match = re.search(path_pattern, log)
    return path_match.group(1) if path_match else ""


def extract_referer_from_log(log):
    referer_pattern = r'referer="([^"]+)"'
    referer_match = re.search(referer_pattern, log)
    return referer_match.group(1) if referer_match else ""


def extract_time_from_log(log):
    time_pattern = r"time=(\d+)ms"
    time_match = re.search(time_pattern, log)
    return int(time_match.group(1)) if time_match else None


def extract_duration_from_log(log):
    time_pattern = r"duration=([\d.]+)s"
    time_match = re.search(time_pattern, log)
    return float(time_match.group(1)) if time_match else None


def extract_user_from_log(log):
    username_pattern = r"user=([\w\s]+) user_id"
    userid_pattern = r"user_id=([\d]+)"

    username_match = re.search(username_pattern, log)
    userid_match = re.search(userid_pattern, log)

    username = username_match.group(1) if username_match else ""
    userid = userid_match.group(1) if userid_match else ""

    return (username, userid)


def extract_status_code_from_log(log):
    status_code_pattern = r"status=(5\d{2})"
    status_code_match = re.search(status_code_pattern, log)
    return status_code_match.group(1) if status_code_match else ""


def extract_request_id_from_log(log):
    request_id_pattern = r"request_id=([^ ]+)"
    request_id_match = re.search(request_id_pattern, log)
    return request_id_match.group(1) if request_id_match else ""


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


def get_status_5xx_requests_all(nb_lines, source_type, file_path=None):
    if source_type == "scalingo":
        cmd = f"scalingo --region osc-fr1 --app mobilic-api logs --lines {nb_lines} | grep 'status=5' || true"
    elif source_type == "file" and file_path:
        cmd = f"cat {file_path} | grep 'status=5'"
    else:
        raise ValueError(
            "source_type must be 'scalingo' or 'file' with a valid file_path."
        )

    lines = [
        l.decode("utf-8")
        for l in subprocess.check_output(cmd, shell=True).splitlines()
    ]

    lines_sorted = sorted(lines, key=lambda x: x[:19])

    for l in lines_sorted:
        ts = extract_timestamp_from_log(l)
        status_code = extract_status_code_from_log(l)
        duration = extract_duration_from_log(l)
        path = extract_path_from_log(l)
        referer = extract_referer_from_log(l)
        request_id = extract_request_id_from_log(l)

        duration_str = f"{duration}s" if duration is not None else "N/A"
        print(
            " - ".join(
                [
                    ts,
                    f"status={status_code}",
                    f"duration={duration_str}",
                    f"path={path}",
                    f"referer={referer}",
                    f"id={request_id}",
                ]
            )
        )
