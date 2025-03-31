from datetime import date, datetime, timedelta

def get_last_sunday() -> date:
    """Returns the datetime.date object corresponding to the last sunday before today.
    Excludes the present day (if it is a sunday).
    """
    today = datetime.today().date()
    days_since_sunday = today.weekday() + 1  # weekday() -> Monday=0, Sunday=6
    previous_sunday = today - timedelta(days=days_since_sunday)
    return previous_sunday
