import garminconnect
import datetime
import yaml
import os
import argparse
import json
from typing import Dict, Any, Optional, List
import garth
import stravalib


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
        help="Start date in ISO format (YYYY-MM-DD). If not provided, defaults to 30 days ago",
    )
    parser.add_argument(
        "--end-date",
        type=validate_date,
        help="End date in ISO format (YYYY-MM-DD). If not provided, defaults to today",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="If set, do not call Strava to update activities; only simulate and write summary",
    )
    parser.add_argument(
        "--tolerance-seconds",
        type=int,
        default=10,
        help="Matching tolerance in seconds when pairing Garmin and Strava activities (default: 10)",
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


def login_to_strava() -> stravalib.Client:
    """Login to Strava using stored credentials.

    Returns:
        stravalib.Client: Authenticated Strava client

    Raises:
        Exception: If authentication fails
    """

    secrets = load_secrets()
    client_id = secrets.get("strava-app-client-id")
    client_secret = secrets.get("strava-app-client-secret")

    if not client_id or not client_secret:
        raise ValueError(
            "Missing strava-app-client-id or strava-app-client-secret in .secrets.yaml"
        )

    # Check for stored tokens (both needed for refresh flow)
    access_token = secrets.get("strava-access-token")
    refresh_token = secrets.get("strava-refresh-token")
    expires_at = secrets.get("strava-token-expires-at")  # epoch timestamp

    # If we have both tokens and expiry info, check if refresh needed
    if access_token and refresh_token and expires_at:
        now = datetime.datetime.now().timestamp()
        expires_in = int(expires_at) - now

        # Refresh if expired or expires in < 1 hour
        if expires_in < 3600:
            try:
                print("Refreshing Strava token...")
                client = stravalib.Client()
                refresh_response = client.refresh_access_token(
                    client_id=client_id,
                    client_secret=client_secret,
                    refresh_token=refresh_token,
                )
                # Update tokens and expiry
                access_token = refresh_response["access_token"]
                refresh_token = refresh_response["refresh_token"]
                expires_at = refresh_response["expires_at"]

                # Save refreshed tokens
                secrets["strava-access-token"] = access_token
                secrets["strava-refresh-token"] = refresh_token
                secrets["strava-token-expires-at"] = expires_at
                with open(".secrets.yaml", "w") as f:
                    yaml.safe_dump(secrets, f, default_flow_style=False)
                print("Saved refreshed tokens")
            except Exception as e:
                print(f"Token refresh failed, falling back to re-auth: {e}")
                access_token = None
                refresh_token = None

        # Token still valid, use it
        if access_token:
            return stravalib.Client(access_token=access_token)

    # No stored token or refresh failed: proceed with authorization flow
    app_access = secrets.get("strava-app-client-access-token")
    client = stravalib.Client(access_token=app_access)

    authorize_url = client.authorization_url(
        client_id=client_id,
        redirect_uri="http://127.0.0.1:5000/authorization",
        scope=["read", "activity:read_all", "activity:write"],
    )

    print("Please visit this URL to authorize the application:")
    print(authorize_url)
    token_code = input(
        "Press Enter after you've authorized the application and paste the code..."
    )

    token_response = client.exchange_code_for_token(
        client_id=client_id,
        client_secret=client_secret,
        code=token_code,
    )
    # The token response contains access_token, refresh_token and expires_at.
    if not isinstance(token_response, dict):
        token_response = dict(token_response)

    access_token = token_response["access_token"]
    refresh_token = token_response["refresh_token"]
    expires_at = token_response["expires_at"]

    # Persist the new tokens into .secrets.yaml while preserving other keys.
    secrets["strava-access-token"] = access_token
    secrets["strava-refresh-token"] = refresh_token
    secrets["strava-token-expires-at"] = expires_at
    with open(".secrets.yaml", "w") as f:
        yaml.safe_dump(secrets, f, default_flow_style=False)

    # Return a client authorized with the newly exchanged access token.
    client = stravalib.Client(access_token=access_token)
    return client


def main() -> None:
    """Main function to fetch and display Garmin Connect activities."""
    args = parse_args()

    # Login to Garmin Connect
    try:
        # Try using stored token first
        secrets = load_secrets()
        garmin_client = None

        if "garth-token" in secrets:
            try:
                print("Attempting to authenticate using saved token...")
                garmin_client = garminconnect.Garmin()
                garmin_client.login(secrets["garth-token"])
            except Exception as e:
                print(f"Token authentication failed: {e}")
                print("Falling back to regular login...")
                garmin_client = None

        if garmin_client is None:
            garmin_client = login_to_garmin()

    except Exception as e:
        print(f"Login to Connect failed: {e}")
        return

    strava_client = login_to_strava()

    # Determine start and end dates from CLI args (defaults: start=30 days ago, end=today)
    today = datetime.date.today()
    start_date = (
        args.start_date if args.start_date else today - datetime.timedelta(days=30)
    )
    end_date = args.end_date if args.end_date else today

    if end_date < start_date:
        print("Error: --end-date must be the same or after --start-date")
        return

    try:
        garmin_activities = garmin_client.get_activities_by_date(
            start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")
        )
    except Exception as e:
        print(f"Failed to fetch Garmin activities: {e}")
        return

    # Build datetimes for Strava query (inclusive range)
    start_datetime = datetime.datetime.combine(start_date, datetime.time.min)
    end_datetime = datetime.datetime.combine(end_date, datetime.time.max)

    # Fetch Strava activities in the window
    try:
        strava_activities = list(
            strava_client.get_activities(after=start_datetime, before=end_datetime)
        )
    except Exception as e:
        print(f"Failed to fetch Strava activities: {e}")
        return

    # Matching tolerance
    tolerance_seconds = args.tolerance_seconds

    for g in garmin_activities:
        garmin_start_time = g.get("startTimeLocal")
        garmin_start_time = datetime.datetime.fromisoformat(garmin_start_time)
        best_strava_activity = None
        best_delta = None
        if garmin_start_time:
            for strava_activity in strava_activities:
                strava_start_time = strava_activity.start_date_local
                strava_start_time = strava_start_time.replace(tzinfo=None)
                garmin_start_time = garmin_start_time.replace(tzinfo=None)

                delta = abs((strava_start_time - garmin_start_time).total_seconds())
                if best_strava_activity is None or delta < best_delta:
                    best_strava_activity = strava_activity
                    best_delta = delta

        if (
            best_strava_activity
            and best_delta is not None
            and best_delta <= tolerance_seconds
        ):
            strava_client.update_activity(
                activity_id=best_strava_activity.id,
                name=g.get("activityName"),
                description=g.get("description", ""),
            )


if __name__ == "__main__":
    main()
