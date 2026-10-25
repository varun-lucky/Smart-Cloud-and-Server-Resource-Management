"""Small terminal client for the SmartCloud LAN API."""
import os
import sys

import requests


def main():
    base = os.getenv("SMARTCLOUD_SERVER_URL", "http://127.0.0.1:5000").rstrip("/")
    token = os.getenv("SMARTCLOUD_CLIENT_TOKEN", "")
    if not token:
        raise SystemExit("Set SMARTCLOUD_CLIENT_TOKEN before using the client.")
    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {token}"
    session.headers["Content-Type"] = "application/json"
    print(f"SmartCloud server: {base}")
    text = input("Text to analyze (one line): ")
    response = session.post(base + "/api/client/jobs", json={"task_type": "text_analysis", "parameters": {"text": text}}, timeout=15)
    response.raise_for_status()
    job_id = response.json()["job_id"]
    print(f"Accepted job {job_id}. Poll status with: python client.py status {job_id}")


def get_job(job_id, result=False):
    base = os.getenv("SMARTCLOUD_SERVER_URL", "http://127.0.0.1:5000").rstrip("/")
    token = os.getenv("SMARTCLOUD_CLIENT_TOKEN", "")
    if not token:
        raise SystemExit("Set SMARTCLOUD_CLIENT_TOKEN before using the client.")
    suffix = "/result" if result else ""
    response = requests.get(f"{base}/api/client/jobs/{job_id}{suffix}", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    response.raise_for_status()
    print(response.text)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] in ("status", "result"):
        get_job(sys.argv[2], sys.argv[1] == "result")
    else:
        main()
