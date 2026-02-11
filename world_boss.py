import os
import tkinter as tk
from tkinter import ttk, messagebox
import requests
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(SCRIPT_DIR, "credentials.json")
TOKEN_FILE = os.path.join(SCRIPT_DIR, "token.json")
API_KEY_FILE = os.path.join(SCRIPT_DIR, "api_key.txt")


def get_local_timezone():
    try:
        from tzlocal import get_localzone
        return str(get_localzone())
    except ImportError:
        pass
    try:
        link = os.path.realpath("/etc/localtime")
        tz = link.split("zoneinfo/")[-1]
        if "/" in tz:
            return tz
    except Exception:
        pass
    import subprocess
    try:
        result = subprocess.run(
            ["timedatectl", "show", "-p", "Timezone", "--value"],
            capture_output=True, text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except FileNotFoundError:
        pass
    return "UTC"


LOCAL_TZ = get_local_timezone()


def get_calendar_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)


def create_boss_event(service, boss_name, boss_time):
    event = {
        "summary": f"SMMO World Boss: {boss_name}",
        "description": f"{boss_name} is now attackable!",
        "start": {
            "dateTime": boss_time.isoformat(),
            "timeZone": LOCAL_TZ,
        },
        "end": {
            "dateTime": (boss_time + timedelta(hours=1)).isoformat(),
            "timeZone": LOCAL_TZ,
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 5},
            ],
        },
    }
    created = service.events().insert(calendarId="primary", body=event).execute()
    return created.get("htmlLink")


class WorldBossApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SMMO World Boss Tracker")
        self.root.geometry("700x500")
        self.root.minsize(600, 400)

        self.boss_data = []

        self._build_api_key_frame()
        self._build_fetch_button()
        self._build_boss_table()
        self._build_calendar_button()
        self._build_status_bar()

        self._load_api_key()
        self._update_clock()

    def _build_api_key_frame(self):
        frame = ttk.LabelFrame(self.root, text="API Key", padding=8)
        frame.pack(fill="x", padx=10, pady=(10, 5))

        self.api_key_var = tk.StringVar()
        entry = ttk.Entry(frame, textvariable=self.api_key_var, width=50, show="*")
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        save_btn = ttk.Button(frame, text="Save", command=self._save_api_key)
        save_btn.pack(side="left")

    def _build_fetch_button(self):
        self.fetch_btn = ttk.Button(
            self.root, text="Fetch World Bosses", command=self._fetch_bosses
        )
        self.fetch_btn.pack(pady=5)

    def _build_boss_table(self):
        columns = ("name", "status", "enable_time")
        frame = ttk.Frame(self.root)
        frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.tree = ttk.Treeview(frame, columns=columns, show="headings", height=10)
        self.tree.heading("name", text="Boss Name")
        self.tree.heading("status", text="Status")
        self.tree.heading("enable_time", text="Enable Time")

        self.tree.column("name", width=200, anchor="w")
        self.tree.column("status", width=200, anchor="center")
        self.tree.column("enable_time", width=200, anchor="center")

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _build_calendar_button(self):
        self.cal_btn = ttk.Button(
            self.root, text="Add to Google Calendar",
            command=self._add_to_calendar, state="disabled"
        )
        self.cal_btn.pack(pady=5)

    def _build_status_bar(self):
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(
            self.root, textvariable=self.status_var, relief="sunken", anchor="w"
        )
        status_bar.pack(fill="x", side="bottom", padx=10, pady=(0, 10))

    def _load_api_key(self):
        if os.path.exists(API_KEY_FILE):
            with open(API_KEY_FILE, "r") as f:
                key = f.read().strip()
            self.api_key_var.set(key)
            self._set_status("API key loaded from file.")

    def _save_api_key(self):
        key = self.api_key_var.get().strip()
        if not key:
            messagebox.showwarning("Warning", "API key cannot be empty.")
            return
        with open(API_KEY_FILE, "w") as f:
            f.write(key)
        self._set_status("API key saved.")

    def _fetch_bosses(self):
        key = self.api_key_var.get().strip()
        if not key:
            messagebox.showwarning("Warning", "Please enter an API key first.")
            return

        self._set_status("Fetching world bosses...")
        self.root.update_idletasks()

        try:
            url = "https://api.simple-mmo.com/v1/worldboss/all?api_key=" + key
            response = requests.post(url)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            self._set_status(f"Error fetching bosses: {e}")
            return

        self.boss_data = sorted(
            data, key=lambda b: b.get("enable_time") or float("inf")
        )
        now = datetime.now()

        # Clear existing rows
        for item in self.tree.get_children():
            self.tree.delete(item)

        for boss in self.boss_data:
            name = boss.get("name", "Unknown")
            enable_time = boss.get("enable_time")
            if enable_time:
                dt = datetime.fromtimestamp(enable_time)
                diff = dt - now
                if diff.total_seconds() <= 0:
                    status = "ATTACKABLE NOW!"
                else:
                    days = diff.days
                    hours, remainder = divmod(diff.seconds, 3600)
                    minutes = remainder // 60
                    status = f"{days}d {hours}h {minutes}m"
                time_str = dt.strftime("%Y-%m-%d %I:%M:%S %p")
            else:
                status = "N/A"
                time_str = "N/A"

            self.tree.insert("", "end", values=(name, status, time_str))

        self.cal_btn.config(state="normal")
        self._set_status(f"Fetched {len(data)} bosses.")

    def _add_to_calendar(self):
        if not self.boss_data:
            messagebox.showinfo("Info", "No boss data. Fetch bosses first.")
            return

        self._set_status("Authenticating with Google Calendar...")
        self.root.update_idletasks()

        try:
            service = get_calendar_service()
        except Exception as e:
            self._set_status(f"Calendar auth error: {e}")
            return

        self._set_status("Authenticated. Creating events...")
        self.root.update_idletasks()

        now = datetime.now()
        created_count = 0

        for boss in self.boss_data:
            name = boss.get("name", "Unknown")
            enable_time = boss.get("enable_time")
            if not enable_time:
                continue
            dt = datetime.fromtimestamp(enable_time)
            if dt <= now:
                continue
            try:
                create_boss_event(service, name, dt)
                created_count += 1
            except Exception as e:
                self._set_status(f"Error creating event for {name}: {e}")
                return

        self._set_status(f"Events created! ({created_count} upcoming bosses added)")

    def _set_status(self, message):
        now_str = datetime.now().strftime("%I:%M:%S %p")
        self.status_var.set(f"[{now_str}] {message}")

    def _update_clock(self):
        # Only update the status bar clock if the current message is a clock tick
        current = self.status_var.get()
        if current.startswith("Current time:"):
            now_str = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
            self.status_var.set(f"Current time: {now_str}")
        self.root.after(1000, self._update_clock)


if __name__ == "__main__":
    root = tk.Tk()
    app = WorldBossApp(root)
    root.mainloop()
