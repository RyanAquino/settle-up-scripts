import logging
import logging.handlers
import os
from datetime import datetime, timezone
import requests
import pyrebase
import calendar
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from requests import Session

logger.info(f"Loading envs... : {load_dotenv(verbose=True)}")

NAMESPACE = os.getenv("NAMESPACE")
DOMAIN = os.getenv("DOMAIN")
USER_EMAIL = os.getenv("USER_EMAIL")
USER_PASSWORD = os.getenv("USER_PASSWORD")
SETTLE_UP_API_KEY = os.getenv("SETTLE_UP_API_KEY")
SHEET_ID = os.getenv("SHEET_ID")
RAW_PRIVATE_KEY = os.getenv("PRIVATE_KEY")
PRIVATE_KEY = RAW_PRIVATE_KEY.replace("\\n", "\n")
OFFSET = 2

scopes = ["https://www.googleapis.com/auth/spreadsheets"]

dt = datetime.now(tz=timezone.utc)
curr_year = dt.year
curr_month_num = dt.month
month_name = calendar.month_name[curr_month_num - OFFSET]


def init_gspread():
    credentials = {
        "type": "service_account",
        "project_id": "scripts-interval",
        "private_key_id": "63c81a1a9c37e33774bcb35e2506d49bea8dc66b",
        "private_key": PRIVATE_KEY,
        "client_email": "scripts-interval-sa@scripts-interval.iam.gserviceaccount.com",
        "client_id": "115821091947389819402",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/scripts-interval-sa%40scripts-interval.iam.gserviceaccount.com",
        "universe_domain": "googleapis.com",
    }
    gcreds = Credentials.from_service_account_info(credentials, scopes=scopes)
    client = gspread.authorize(gcreds)
    return client.open_by_key(SHEET_ID).worksheet(str(curr_year))


def get_target_group(request_session: Session):
    groups = request_session.get(
        f"{BASE_URL}/userGroups/{user_id}.json",
    )
    groups = groups.json()

    for group_id, metadata in groups.items():
        group = request_session.get(f"{BASE_URL}/groups/{group_id}.json")
        group = group.json()
        group_name = group.get("name")
        if group_name == f"{CURR_MONTH} 2025":
            return group_id


def post_create_transaction(request_session: Session, group_id: str):
    import time

    ms = time.time_ns() // 1_000_000
    payload = {
        "category": "😃",
        "currencyCode": "PHP",
        "dateTime": ms,
        "exchangeRates": {"PHP": "1"},
        "fixedExchangeRate": False,
        "items": [
            {
                "amount": "500",
                "forWhom": [{"memberId": "-OI-8lqJ49B4yX7lpjCP", "weight": "1"}],
            }
        ],
        "purpose": "TEST API",
        "type": "expense",
        "whoPaid": [{"memberId": "-OI-96V4JWwoxjP2mUzQ", "weight": "1"}],
    }
    response = request_session.post(
        f"{BASE_URL}/transactions/{group_id}.json", json=payload
    )
    response = response.json()

    return response


def compute_transaction_total(request_session: Session, group_id: str):
    if not group_id:
        logger.error("Target group id is not found")
        return

    transactions = request_session.get(f"{BASE_URL}/transactions/{group_id}.json")
    transactions = transactions.json()
    total = 0

    for key, value in transactions.items():
        items = value.get("items", [])

        for item in items:
            total += float(item.get("amount", 0))

    return total


if __name__ == "__main__":
    CURR_MONTH = datetime.now(tz=timezone.utc).strftime("%B")
    config = {
        "apiKey": SETTLE_UP_API_KEY,
        "authDomain": DOMAIN,
        "databaseURL": f"https://{DOMAIN}",
        "storageBucket": f"{NAMESPACE}.appspot.com",
        "projectId": NAMESPACE,
    }

    firebase = pyrebase.initialize_app(config)
    pb_auth = firebase.auth()
    creds = pb_auth.sign_in_with_email_and_password(USER_EMAIL, USER_PASSWORD)
    user_id = creds.get("localId")
    BASE_URL = f"https://{DOMAIN}"

    with requests.Session() as session:
        session.params = {"auth": creds.get("idToken")}
        target_group_id = get_target_group(session)
        total = compute_transaction_total(session, target_group_id)

        if total is not None:
            sheet = init_gspread()
            row_cell = sheet.find("Food")
            col_cell = sheet.find(month_name)
            sheet.update_cell(row_cell.row, col_cell.col, total)
            logger.success(f"Total: {total}")
