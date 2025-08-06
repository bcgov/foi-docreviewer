import sys
from datetime import datetime, date, timedelta

def get_date_from_command_line():
    """
    Retrieves a date from the command line if provided, otherwise returns today's date.

    Returns:
        datetime.date: The date to be used.
    """
    if len(sys.argv) > 1:
        date_string = sys.argv[1]
        try:
            # Attempt to parse the date string with a common format (YYYY-MM-DD)
            parsed_date = datetime.strptime(date_string, '%Y-%m-%d').date()
            return parsed_date.strftime('%Y-%m-%d')
        except ValueError:
            print(f"Warning: Could not parse '{date_string}' as a valid date (YYYY-MM-DD). Using today's date.")
            return datetime.now().date().strftime('%Y-%m-%d')
    else:
        # get previous day's date if no date is provided
        return (date.today()-timedelta(days=1)).strftime('%Y-%m-%d')