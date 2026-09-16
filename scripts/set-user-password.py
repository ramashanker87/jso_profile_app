import getpass
import json
import os
import subprocess
import sys
import tempfile

password = getpass.getpass("Permanent password (hidden): ")
if not password:
    raise SystemExit("No password supplied; account password was not changed.")
fd, path = tempfile.mkstemp(prefix="profile-library-password-", suffix=".json")
try:
    with os.fdopen(fd, "w") as stream:
        json.dump(
            {
                "UserPoolId": sys.argv[1],
                "Username": sys.argv[2],
                "Password": password,
                "Permanent": True,
            },
            stream,
        )
    password = None
    subprocess.run(
        [
            "aws",
            "cognito-idp",
            "admin-set-user-password",
            "--cli-input-json",
            "file://" + path,
            "--region",
            sys.argv[3],
        ],
        check=True,
    )
    print("Password configured. No invitation email sent.")
finally:
    os.unlink(path)
