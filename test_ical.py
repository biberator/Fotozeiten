from icalendar import Calendar, Event, vDate
from datetime import datetime, timedelta
import pytz
import os

tz = pytz.timezone("Europe/Berlin")

def test_simple_event():
    cal = Calendar()
    cal.add("prodid", "-//Test Kalender//")
    cal.add("version", "2.0")

    heute = datetime.now(tz).date()
    event = Event()
    event.add("summary", "Test-Event")
    event.add("dtstart", vDate(heute))
    event.add("dtend", vDate(heute + timedelta(days=1)))
    event.add("dtstamp", datetime.now(pytz.utc))
    cal.add_component(event)

    os.makedirs("docs", exist_ok=True)
    with open("docs/test.ics", "wb") as f:
        f.write(cal.to_ical())
    print("Test-ICS erstellt: docs/test.ics")

if __name__ == "__main__":
    test_simple_event()
