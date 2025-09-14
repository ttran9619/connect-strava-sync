import garminconnect
import datetime
import yaml
import os
import argparse
from typing import Dict, Any, Optional
import garth


def load_secrets() -> dict:
    """Load secrets from .secrets.yaml file.

    Returns:
        dict: Dictionary containing credentials and tokens

    Raises:
        FileNotFoundError: If .secrets.yaml file is missing
    """
    secrets_path = os.path.join(os.path.dirname(__file__), ".secrets.yaml")
    if not os.path.exists(secrets_path):
        raise FileNotFoundError("Missing .secrets.yaml file")

    with open(secrets_path, "r") as f:
        return yaml.safe_load(f) or {}


def validate_date(date_str: str) -> datetime.date:
    """Validate and parse a date string in ISO format (YYYY-MM-DD).
    Args:
        date_str (str): Date string to validate
    Returns:
        datetime.date: Parsed date object
    Raises:
        argparse.ArgumentTypeError: If the date format is invalid
    """

    try:
        return datetime.date.fromisoformat(date_str)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid date format: {date_str}. Please use ISO format (YYYY-MM-DD)"
        )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Namespace: Parsed command line arguments with optional start_date
    """
    parser = argparse.ArgumentParser(
        description="Fetch Garmin Connect activities starting from a specific date"
    )
    parser.add_argument(
        "--start-date",
        type=validate_date,
        help="Start date in ISO format (YYYY-MM-DD). If not provided, defaults to 7 days ago",
    )
    return parser.parse_args()


def login_to_garmin() -> garminconnect.Garmin:
    """Login to Garmin Connect using stored credentials.

    Returns:
        garminconnect.Garmin: Authenticated Garmin client

    Raises:
        Exception: If authentication fails
    """
    secrets = load_secrets()
    username = secrets.get("garmin-username")
    password = secrets.get("garmin-password")

    if not username or not password:
        raise ValueError("Missing garmin-username or garmin-password in .secrets.yaml")

    client = garminconnect.Garmin(username, password, return_on_mfa=True)
    error_string, client_state = client.login()

    if error_string == "needs_mfa":
        mfa_code = input("Enter your MFA code: ")
        print("Processing MFA...")
        client.resume_login(client_state, mfa_code)

    # After successful login, save garth token
    try:
        g = garth.Client()
        g.login(username, password)
        token_data = g.dumps()
        if token_data:  # Only save if we got valid token data
            secrets["garth-token"] = token_data
            secrets_path = os.path.join(os.path.dirname(__file__), ".secrets.yaml")
            with open(secrets_path, "w") as f:
                yaml.safe_dump(secrets, f)
            print("Saved authentication token for future use")
    except Exception as e:
        print(f"Note: Could not save authentication token: {e}")

    return client


def main() -> None:
    """Main function to fetch and display Garmin Connect activities."""
    args = parse_args()

    # Login to Garmin Connect
    try:
        # Try using stored token first
        secrets = load_secrets()
        client = None

        if "garth-token" in secrets:
            try:
                print("Attempting to authenticate using saved token...")
                client = garminconnect.Garmin()
                client.login(secrets["garth-token"])
            except Exception as e:
                print(f"Token authentication failed: {e}")
                print("Falling back to regular login...")
                client = None

        if client is None:
            client = login_to_garmin()

    except Exception as e:
        print(f"Login to Connect failed: {e}")
        return

    # Get activities from start date until now
    today = datetime.date.today()
    start_date = (
        args.start_date if args.start_date else today - datetime.timedelta(days=7)
    )
    try:
        activities = client.get_activities_by_date(
            start_date.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")
        )
    except Exception as e:
        print(f"Failed to fetch activities: {e}")
        return

    # Print name and description for each activity
    for activity in activities:
        name = activity.get("activityName", "No Name")
        description = activity.get("description", "No Description")
        print(f"Name: {name}\nDescription: {description}\n---")


if __name__ == "__main__":
    main()
