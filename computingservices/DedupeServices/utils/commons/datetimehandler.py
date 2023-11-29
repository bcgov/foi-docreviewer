
from datetime import datetime, timedelta
import pytz

def convert_to_pst(datetime_str):
    # Extract date and time parts from the string
    date_str = datetime_str[2:9]
    time_str = datetime_str[10:15]

    # Parse the date and time strings
    parsed_datetime = datetime.strptime(f"{date_str} {time_str}", "%Y%m%d %H%M%S")

    # Extract the timezone offset and convert to timedelta
    offset_str = datetime_str[-6:].replace("'", "")
    offset_hours = int(offset_str[:-2])
    offset_minutes = int(offset_str[-2:])
    offset_delta = timedelta(hours=offset_hours, minutes=offset_minutes)

    # Apply the UTC offset
    pst_timezone = pytz.timezone('America/Los_Angeles')
    utc_datetime = parsed_datetime - offset_delta
    pst_datetime = utc_datetime.astimezone(pst_timezone)

    return pst_datetime
