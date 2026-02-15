import json
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
import requests
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

VERSION = "2.3.0"
GITHUB_REPO = "jgrrgth/smmo-WB-calendar-reminders"
SCOPES = ["https://www.googleapis.com/auth/calendar"]

# When running as a PyInstaller bundle, bundled data files are in sys._MEIPASS.
# User-writable files (token, api key) go next to the executable.
if getattr(sys, 'frozen', False):
    BUNDLE_DIR = sys._MEIPASS
    APP_DIR = os.path.dirname(sys.executable)
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))
    APP_DIR = BUNDLE_DIR

CREDENTIALS_FILE = os.path.join(BUNDLE_DIR, "credentials.json")
TOKEN_FILE = os.path.join(APP_DIR, "token.json")
API_KEY_FILE = os.path.join(APP_DIR, "api_key.txt")
SLEEP_ZONE_FILE = os.path.join(APP_DIR, "sleep_zone.json")


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


def create_boss_event(service, boss_name, boss_time, reminder_minutes=5):
    event = {
        "summary": f"🧟 SMMO World Boss: {boss_name}",
        "description": f"{boss_name} is now attackable!",
        "colorId": "11",
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
                {"method": "popup", "minutes": reminder_minutes},
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
        self._build_sleep_zone_frame()
        self._build_calendar_button()
        self._build_status_bar()

        self._load_api_key()
        self._load_sleep_zone()
        self._update_clock()
        self._check_for_update()

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

    def _build_sleep_zone_frame(self):
        frame = ttk.LabelFrame(self.root, text="Do not disturb", padding=8)
        frame.pack(fill="x", padx=10, pady=(0, 5))

        self.sleep_enabled = tk.BooleanVar()
        ttk.Checkbutton(
            frame, text="Enable", variable=self.sleep_enabled
        ).pack(side="left", padx=(0, 12))

        ttk.Label(frame, text="Start:").pack(side="left")
        self.sleep_start_hour = ttk.Combobox(
            frame, state="readonly", width=3,
            values=[str(h) for h in range(1, 13)]
        )
        self.sleep_start_hour.set("10")
        self.sleep_start_hour.pack(side="left", padx=(4, 2))

        self.sleep_start_ampm = ttk.Combobox(
            frame, state="readonly", width=4, values=["AM", "PM"]
        )
        self.sleep_start_ampm.set("PM")
        self.sleep_start_ampm.pack(side="left", padx=(0, 12))

        ttk.Label(frame, text="End:").pack(side="left")
        self.sleep_end_hour = ttk.Combobox(
            frame, state="readonly", width=3,
            values=[str(h) for h in range(1, 13)]
        )
        self.sleep_end_hour.set("8")
        self.sleep_end_hour.pack(side="left", padx=(4, 2))

        self.sleep_end_ampm = ttk.Combobox(
            frame, state="readonly", width=4, values=["AM", "PM"]
        )
        self.sleep_end_ampm.set("AM")
        self.sleep_end_ampm.pack(side="left", padx=(0, 12))

        ttk.Button(
            frame, text="Save", command=self._save_sleep_zone
        ).pack(side="left")

    def _load_sleep_zone(self):
        if os.path.exists(SLEEP_ZONE_FILE):
            try:
                with open(SLEEP_ZONE_FILE, "r") as f:
                    data = json.load(f)
                self.sleep_enabled.set(data.get("enabled", False))
                self.sleep_start_hour.set(str(data.get("start_hour", 10)))
                self.sleep_start_ampm.set(data.get("start_ampm", "PM"))
                self.sleep_end_hour.set(str(data.get("end_hour", 8)))
                self.sleep_end_ampm.set(data.get("end_ampm", "AM"))
            except (json.JSONDecodeError, KeyError):
                pass

    def _save_sleep_zone(self):
        data = {
            "enabled": self.sleep_enabled.get(),
            "start_hour": int(self.sleep_start_hour.get()),
            "start_ampm": self.sleep_start_ampm.get(),
            "end_hour": int(self.sleep_end_hour.get()),
            "end_ampm": self.sleep_end_ampm.get(),
        }
        with open(SLEEP_ZONE_FILE, "w") as f:
            json.dump(data, f, indent=2)
        self._set_status("Sleep zone settings saved.")

    def _in_sleep_zone(self, dt):
        start_h = int(self.sleep_start_hour.get())
        start_ampm = self.sleep_start_ampm.get()
        end_h = int(self.sleep_end_hour.get())
        end_ampm = self.sleep_end_ampm.get()

        # Convert 12-hour to 24-hour
        if start_ampm == "AM":
            start_24 = 0 if start_h == 12 else start_h
        else:
            start_24 = 12 if start_h == 12 else start_h + 12

        if end_ampm == "AM":
            end_24 = 0 if end_h == 12 else end_h
        else:
            end_24 = 12 if end_h == 12 else end_h + 12

        hour = dt.hour

        if start_24 <= end_24:
            # Same-day range (e.g. 1 AM → 6 AM)
            return start_24 <= hour < end_24
        else:
            # Cross-midnight range (e.g. 10 PM → 8 AM)
            return hour >= start_24 or hour < end_24

    def _build_calendar_button(self):
        frame = ttk.Frame(self.root)
        frame.pack(pady=5)

        self.cal_btn = ttk.Button(
            frame, text="Add to Google Calendar",
            command=self._add_to_calendar, state="disabled"
        )
        self.cal_btn.pack(side="left", padx=(0, 8))

        ttk.Label(frame, text="Reminder:").pack(side="left")
        self.reminder_var = tk.StringVar(value="5 minutes")
        reminder_combo = ttk.Combobox(
            frame, textvariable=self.reminder_var, state="readonly", width=12,
            values=["1 minute", "5 minutes", "10 minutes"]
        )
        reminder_combo.pack(side="left", padx=(4, 0))

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
        skipped_count = 0

        for boss in self.boss_data:
            name = boss.get("name", "Unknown")
            enable_time = boss.get("enable_time")
            if not enable_time:
                continue
            dt = datetime.fromtimestamp(enable_time)
            if dt <= now:
                continue
            if self.sleep_enabled.get() and self._in_sleep_zone(dt):
                skipped_count += 1
                continue
            try:
                minutes = int(self.reminder_var.get().split()[0])
                create_boss_event(service, name, dt, minutes)
                created_count += 1
            except Exception as e:
                self._set_status(f"Error creating event for {name}: {e}")
                return

        msg = f"Events created! ({created_count} added"
        if skipped_count:
            msg += f", {skipped_count} skipped — sleep zone"
        msg += ")"
        self._set_status(msg)

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

    def _check_for_update(self):
        def check():
            try:
                url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
                resp = requests.get(url, timeout=5)
                if resp.status_code != 200:
                    return
                data = resp.json()
                tag = data.get("tag_name", "")
                latest = tag.lstrip("vV")
                if latest and tuple(int(x) for x in latest.split(".")) > tuple(int(x) for x in VERSION.split(".")):
                    html_url = data.get("html_url", "")
                    self.root.after(0, self._show_update_bar, latest, html_url)
            except Exception:
                pass

        threading.Thread(target=check, daemon=True).start()

    def _show_update_bar(self, latest_version, release_url):
        frame = ttk.Frame(self.root)
        frame.pack(fill="x", side="bottom", padx=10, pady=(0, 2))

        ttk.Label(
            frame, text=f"Update available: v{latest_version}"
        ).pack(side="left")

        link = ttk.Label(
            frame, text="Download", foreground="blue", cursor="hand2"
        )
        link.pack(side="left", padx=(6, 0))
        link.bind("<Button-1>", lambda e: webbrowser.open(release_url))


if __name__ == "__main__":
    root = tk.Tk()
    app = WorldBossApp(root)
    root.mainloop()
