import os
import json
import time
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pickle

SCOPES = [
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.announcements.readonly'
]

TOKEN_FILE = 'token.pickle'
CREDENTIALS_FILE = 'credentials.json'
TIMESTAMP_FILE = 'last_timestamp.txt'
POLL_INTERVAL = 300


# ---------------- AUTH ---------------- #

def authenticate():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)

    return build('classroom', 'v1', credentials=creds)


# ---------------- TIMESTAMP ---------------- #

def load_last_timestamp():
    if not os.path.exists(TIMESTAMP_FILE):
        return None
    try:
        with open(TIMESTAMP_FILE, 'r') as f:
            return float(f.read().strip())
    except:
        return None


def save_last_timestamp(ts):
    with open(TIMESTAMP_FILE, 'w') as f:
        f.write(str(ts))


def iso_to_timestamp(iso_string):
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        return dt.timestamp()
    except:
        return 0


# ---------------- ANNOUNCEMENTS ---------------- #

def check_announcements(service, course_id, last_ts):
    try:
        results = service.courses().announcements().list(
            courseId=course_id,
            orderBy='updateTime desc',
            pageSize=10
        ).execute()

        announcements = results.get('announcements', [])
        new_items = []
        latest_ts = last_ts if last_ts else 0

        for ann in announcements:
            ts = iso_to_timestamp(ann.get("updateTime", ""))

            # Track newest timestamp (always)
            latest_ts = max(latest_ts, ts)

            # Only collect if last_ts exists AND announcement is newer
            if last_ts and ts > last_ts:
                new_items.append(ann)

        return new_items, latest_ts

    except HttpError as e:
        print(f"Error fetching announcements: {e}")
        return [], last_ts


# ---------------- MAIN CHECK ---------------- #

def check_classroom_updates():
    service = authenticate()
    last_ts = load_last_timestamp()

    # Detect if this is the very first run
    first_run = last_ts is None

    try:
        results = service.courses().list(pageSize=100).execute()
        courses = results.get('courses', [])

        if not courses:
            print("No courses found.")
            return

        print(f"Checking {len(courses)} courses...\n")

        latest_timestamp_found = last_ts or 0
        updates_found = False

        for course in courses:
            course_id = course['id']
            course_name = course['name']

            new_announcements, course_latest_ts = check_announcements(service, course_id, last_ts)

            latest_timestamp_found = max(latest_timestamp_found, course_latest_ts)

            # If first run → DO NOT print anything
            if first_run:
                continue

            # Print only new announcements
            if new_announcements:
                updates_found = True
                print("=" * 70)
                print(f"NEW ANNOUNCEMENTS IN: {course_name}")
                print("=" * 70)

                for ann in new_announcements:
                    print(f"Time: {ann.get('creationTime', '')}")
                    print(f"Text: {ann.get('text', '')[:200]}")
                    print("-" * 70)

        # Save the newest timestamp ALWAYS
        save_last_timestamp(latest_timestamp_found)

        if first_run:
            print("First run → Timestamp stored. Waiting for new announcements...\n")
        elif not updates_found:
            print("No new announcements.")
        else:
            print("Updates printed above.")

    except Exception as e:
        print(f"Unexpected error: {e}")


# ---------------- LOOP ---------------- #

if __name__ == "__main__":
    print("Google Classroom Announcement Monitor")
    print(f"Checking every {POLL_INTERVAL} seconds...\n")

    while True:
        try:
            check_classroom_updates()
            print(f"Next check in {POLL_INTERVAL}s...\n")
        except KeyboardInterrupt:
            print("\nStopped by user.")
            break
        time.sleep(POLL_INTERVAL)

