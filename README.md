[README.md](https://github.com/user-attachments/files/25240755/README.md)
# SMMO World Boss Tracker

A Python GUI app that tracks world boss timers in [Simple MMO](https://web.simple-mmo.com/) and optionally adds reminders to your Google Calendar.

## Features

- Fetches all world bosses from the SMMO API
- Displays boss name, countdown status, and enable time in a sortable table
- Bosses sorted from soonest to latest
- Adds upcoming bosses to Google Calendar with a 5-minute popup reminder
- API key saved locally for convenience
- Automatic timezone detection

## Requirements

- Python 3.8+
- [SMMO API key](https://web.simple-mmo.com/api)
- Google Cloud project with Calendar API enabled (for calendar features)

### Python packages

```
requests
google-auth
google-auth-oauthlib
google-api-python-client
```

Install with:

```bash
pip install requests google-auth google-auth-oauthlib google-api-python-client
```

## Setup

1. Clone the repo
2. Install the Python packages above
3. **Google Calendar (optional):** Place your `credentials.json` from the Google Cloud Console in the project directory
4. Run the app:

```bash
python world_boss.py
```

## Usage

1. Enter your SMMO API key and click **Save**
2. Click **Fetch World Bosses** to load the boss list
3. Review the boss table — bosses show a countdown or "ATTACKABLE NOW!"
4. Click **Add to Google Calendar** to create calendar events for upcoming bosses
