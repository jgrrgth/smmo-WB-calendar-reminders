# Changelog

## v2.0.0
- Replaced terminal interface with a tkinter GUI
- API key entry with masked input and Save button (auto-loads from file)
- "Fetch World Bosses" button to pull boss data from the API
- Boss list displayed in a sortable Treeview table (Boss Name, Status, Enable Time)
- Bosses sorted from soonest to latest enable time
- "Add to Google Calendar" button that only adds upcoming (future) bosses
- Status bar with timestamped feedback messages

## v1.6.0
- Timezone is now automatically detected from the device instead of being hardcoded to America/New_York

## v1.5.0
- API key is saved to file on first entry and auto-loaded on subsequent runs

## v1.4.0
- Changed Google Calendar reminder to 5 minutes before boss enable time

## v1.3.0
- Added Google Calendar integration with popup reminders for upcoming world bosses

## v1.2.0
- Added countdown showing days, hours, and minutes until each boss is attackable
- Bosses already available display "ATTACKABLE NOW!"

## v1.1.0
- Converted enable_time from Unix timestamp to readable date and time format

## v1.0.0
- Initial script
- POST request to SMMO world boss API
- User inputs API key
- Prints JSON response
- Pauses so user can view output
