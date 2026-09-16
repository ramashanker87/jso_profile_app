#!/usr/bin/env python3
"""Keep secret values out of Terraform state, shell arguments, and source code."""

import argparse
import getpass
import json
from pathlib import Path
import secrets
import subprocess
import boto3


def output(name):
    return subprocess.check_output(
        ["terraform", "-chdir=infrastructure/terraform", "output", "-raw", name],
        text=True,
    ).strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--initialize-only",
        action="store_true",
        help="Generate webhook secret with an empty API key only if the secret has no version",
    )
    args = parser.parse_args()
    client = boto3.client("secretsmanager", region_name=output("aws_region"))
    arn = output("neeto_secret_arn")
    try:
        existing = json.loads(client.get_secret_value(SecretId=arn)["SecretString"])
    except client.exceptions.ResourceNotFoundException:
        existing = {}
    if args.initialize_only and existing:
        print("Secret already initialized; unchanged.")
        return
    api_key = (
        existing.get("NEETO_API_KEY", "")
        if args.initialize_only
        else getpass.getpass(
            "Neeto API key (hidden; leave blank to preserve existing): "
        ).strip()
        or existing.get("NEETO_API_KEY", "")
    )
    webhook = existing.get("NEETO_WEBHOOK_SECRET") or secrets.token_urlsafe(32)
    client.put_secret_value(
        SecretId=arn,
        SecretString=json.dumps(
            {"NEETO_API_KEY": api_key, "NEETO_WEBHOOK_SECRET": webhook}
        ),
    )
    print(
        "Secret saved. Retrieve NEETO_WEBHOOK_SECRET in the AWS Secrets Manager console to configure NeetoForm. No secret values were printed."
    )


if __name__ == "__main__":
    main()
