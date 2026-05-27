# Connect Strava Sync

A CLI application to synchronize activities between Garmin Connect and Strava. Sync activity names and descriptions or push Garmin FIT files to Strava.

The project a simple glue program, combining the garminconnect and stravalib libraries.

My primary goal with the project was to automate pushing names and descriptions from my Connect activities to Strava. By default, the data exporter in Connect pushes activities before I can go in and update the names and descriptions. A secondary feature is the ability to download Connect activities and upload them to Strava. This was originally used to upload old activities which were not pushed when hooking up the integration.

The tool can be installed as a system program and run with a cronjob to push batches of activities instead of using the default Strava integration in Connect.

## Features

- **Sync Activity Metadata**: Automatically push activity names and descriptions from Garmin Connect to Strava
- **Upload Original Files**: Upload Garmin activity files (.fit) to Strava
- **Date Range Filtering**: Specify custom date ranges for syncing (defaults to last 7 days)
- **Dry-Run Mode**: Preview changes without making actual updates
- **Activity Matching**: Intelligently matches activities between Garmin and Strava using timestamps
- **Token Management**: Automatically handles OAuth token refresh for both platforms
- **MFA Support**: Built-in support for Garmin Connect multi-factor authentication

## Requirements

- Python 3.12 or higher

## Installation

The project can be installed as a system tool using uv:
```
uv tool install .
```

The tool can also be run from the repo:
```
uv run connect-strava-sync
```

## Setup

### 1. Create a Secrets File

Create a `.secrets.yaml` file in your project root with the following structure:

```yaml
# Garmin Connect credentials
garmin-username: your-email@example.com
garmin-password: your-garmin-password

# Strava OAuth credentials
# Obtain these from https://www.strava.com/settings/api
strava-app-client-id: your-client-id
strava-app-client-secret: your-client-secret

# Optional: Pre-stored tokens (auto-populated after first run)
strava-app-client-access-token: your-app-access-token
strava-access-token: user-access-token
strava-refresh-token: user-refresh-token
strava-token-expires-at: 1234567890
garth-token: garmin-auth-token
```

### 2. Obtain Strava API Credentials

1. Go to https://www.strava.com/settings/api
2. Create a new application
3. Copy the `Client ID` and `Client Secret` to your `.secrets.yaml`

### 3. Initial Authentication

The first time you run the application, it will guide you through the OAuth flow for both Garmin Connect and Strava. Subsequent runs will reuse stored tokens.

## Usage

### Sync Activity Metadata

Synchronize activity names and descriptions from Garmin Connect to Strava:

```bash
connect-strava-sync sync
```

**Options:**

- `--start-date YYYY-MM-DD`: Start date (default: 7 days ago)
- `--end-date YYYY-MM-DD`: End date (default: today)
- `--dry-run`: Preview changes without updating Strava
- `--tolerance-seconds N`: Matching tolerance between Garmin and Strava activities in seconds (default: 10)
- `--secrets-file PATH`: Path to secrets file (default: `.secrets.yaml`)

**Examples:**

```bash
# Sync last 7 days
connect-strava-sync sync

# Sync a specific date range
connect-strava-sync sync --start-date 2024-01-01 --end-date 2024-01-31

# Preview changes without updating
connect-strava-sync sync --dry-run

# Increase matching tolerance for activities with time differences
connect-strava-sync sync --tolerance-seconds 30
```

### Upload Original Garmin Files

Upload original Garmin activity files to Strava:

```bash
connect-strava-sync upload
```

**Options:**

- `--start-date YYYY-MM-DD`: Start date (default: 7 days ago)
- `--end-date YYYY-MM-DD`: End date (default: today)
- `--dry-run`: Preview uploads without actually uploading
- `--no-wait`: Don't wait for upload completion (faster)
- `--semi-private-as-private`: Treat Garmin semi-private audience labels (followers/connections/friends) as private. By default these are treated as public.
- `--secrets-file PATH`: Path to secrets file (default: `.secrets.yaml`)

**Examples:**

```bash
# Upload last 7 days of activities
connect-strava-sync upload

# Dry-run to see what would be uploaded
connect-strava-sync upload --dry-run

# Upload without waiting for completion
connect-strava-sync upload --no-wait

# Treat Garmin semi-private audience labels as private on Strava
connect-strava-sync upload --semi-private-as-private
```

## How It Works

### Sync Command

1. Authenticates with both Garmin Connect and Strava
2. Retrieves activities from both platforms within the specified date range
3. Matches activities by timestamp (within the tolerance window)
4. Compares names and descriptions
5. Updates Strava with Garmin data for matched activities
6. Logs the results or writes to a debug file

### Upload Command

1. Authenticates with both platforms
2. Retrieves activities from Garmin within the date range
3. Downloads Garmin activity files (.fit)
4. Uploads files to corresponding Strava activities
5. Optionally waits for upload completion

## Logging

By default, the application logs to the console. Debug logs with timestamps are available in files named `debug-{timestamp}.log`.

## License

This project is licensed under the MIT License
