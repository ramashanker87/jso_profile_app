import getpass
import json
import os
import subprocess
import time
import urllib.request

url = (
    os.getenv("PROFILE_API_URL")
    or subprocess.check_output(
        ["terraform", "-chdir=infrastructure/terraform", "output", "-raw", "api_url"],
        text=True,
    ).strip()
)
token = getpass.getpass("Cognito access token (hidden): ")


def call(path, method="GET"):
    request = urllib.request.Request(
        url + path, headers={"Authorization": "Bearer " + token}, method=method
    )
    with urllib.request.urlopen(request, timeout=40) as response:
        return json.load(response)


job = call("/sync", "POST")
while job["status"] in ("RUNNING", "QUEUED"):
    print("Syncing:", job["processed"], "processed")
    time.sleep(3)
    job = call("/sync/" + job["jobId"])
print(json.dumps(job, indent=2))
