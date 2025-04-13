import os
from datetime import datetime, timezone
import requests
import pyrebase
import calendar
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from loguru import logger

logger.info("Loading envs... ", load_dotenv(verbose=True))

NAMESPACE = os.getenv("NAMESPACE")
DOMAIN = os.getenv("DOMAIN")
USER_EMAIL = os.getenv("USER_EMAIL")
USER_PASSWORD = os.getenv("USER_PASSWORD")
SETTLE_UP_API_KEY = os.getenv("SETTLE_UP_API_KEY")
SHEET_ID = os.getenv("SHEET_ID")
OFFSET = 2

scopes = [
    "https://www.googleapis.com/auth/spreadsheets"
]

dt = datetime.now(tz=timezone.utc)
curr_year = dt.year
curr_month_num = dt.month
month_name = calendar.month_name[curr_month_num - OFFSET]

def init_gspread():
    gcreds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
    client = gspread.authorize(gcreds)
    return client.open_by_key(SHEET_ID).worksheet(str(curr_year))

if __name__ == "__main__":


    CURR_MONTH = datetime.now(tz=timezone.utc).strftime("%B")

    config = {
        "apiKey": SETTLE_UP_API_KEY,
        "authDomain": DOMAIN,
        "databaseURL": f"https://{DOMAIN}",
        "storageBucket": f"{NAMESPACE}.appspot.com",
        "projectId": NAMESPACE
    }

    firebase = pyrebase.initialize_app(config)
    pb_auth = firebase.auth()
    creds = pb_auth.sign_in_with_email_and_password(USER_EMAIL, USER_PASSWORD)
    user_id = creds.get("localId")
    BASE_URL = f"https://{DOMAIN}"

    with requests.Session() as session:
        session.params = {
            "auth": creds.get("idToken")
        }
        groups = session.get(
            f"{BASE_URL}/userGroups/{user_id}.json",
        )
        groups = groups.json()

        target_group_id = None
        for group_id, metadata in groups.items():
            group = session.get(f"{BASE_URL}/groups/{group_id}.json")
            group = group.json()
            group_name = group.get("name")
            if group_name == f"{CURR_MONTH} 2025":
                target_group_id = group_id
                break

        if target_group_id:
            transactions = session.get(f"{BASE_URL}/transactions/{target_group_id}.json")
            transactions = transactions.json()
            total = 0

            for key, value in transactions.items():
                items = value.get("items", [])

                for item in items:
                    total += float(item.get("amount", 0))

            sheet = init_gspread()
            row_cell = sheet.find("Food")
            col_cell = sheet.find(month_name)
            sheet.update_cell(row_cell.row, col_cell.col, total)
            logger.success(f"Total: {total}")
