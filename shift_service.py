import gspread
import os
import re
from datetime import datetime

# Global worksheet variable
_worksheet = None

# Errors
ERROR_INVALID_ACTION = "ERROR_INVALID_ACTION"
ERROR_INVALID_NAME = "ERROR_INVALID_NAME"
ERROR_INVALID_TIME = "ERROR_INVALID_TIME"
ERROR_ENTRY_EXISTS = "ERROR_ENTRY_EXISTS"
ERROR_DAY_LIMIT_REACHED = "ERROR_DAY_LIMIT_REACHED"

# Success code
UPDATE_SUCCESS = "UPDATE_SUCCESS"
DELETE_SUCCESS = "DELETE_SUCCESS"

def initialise():
    # Get relative path
    dirname = os.path.dirname(__file__)
    filename = os.path.join(dirname, 'credentials.json')
    gc = gspread.service_account(filename)

    # Open the Google Sheet using its key
    sh = gc.open_by_key(os.getenv('GOOGLE_SHEETS_KEY'))
    global _worksheet
    _worksheet = sh.get_worksheet(0)
    return _worksheet

## CRUD OPERATIONS ##
def _insert_shift(name, day, start_time, end_time):
    global _worksheet
    if _worksheet is None:
        _worksheet = initialise()

    # Check input validity
    if not _is_valid_employee(name):
        return ERROR_INVALID_NAME
    
    if not _is_valid_day(day) or not _is_valid_time(start_time, end_time):
        return ERROR_INVALID_TIME

    # Search for cell input
    cell_name = _worksheet.find(re.compile(name, re.IGNORECASE))
    cell_day = _worksheet.find(re.compile(day, re.IGNORECASE))

    # Check if entry already exists
    if _entry_exists(_worksheet, cell_name.row, cell_day.col):
        return ERROR_ENTRY_EXISTS
    
    # Check if day limit reached
    if _day_limit_reached(_worksheet, cell_day.col):
        return ERROR_DAY_LIMIT_REACHED

    # Update cells
    _worksheet.update_cell(cell_name.row, cell_day.col, f"{start_time}")
    _worksheet.update_cell(cell_name.row, cell_day.col + 1, f"{end_time}")
    return UPDATE_SUCCESS

def delete_shift(name, day):
    global _worksheet
    if _worksheet is None:
        _worksheet = initialise()

    # Check input validity
    if not _is_valid_employee(name):
        return ERROR_INVALID_NAME

    # Search for cell input
    cell_name = _worksheet.find(re.compile(name, re.IGNORECASE))
    cell_day = _worksheet.find(re.compile(day, re.IGNORECASE))

    # Clear cells
    _worksheet.update_cell(cell_name.row, cell_day.col, "")
    _worksheet.update_cell(cell_name.row, cell_day.col + 1, "")
    return DELETE_SUCCESS


def read_shift(name, day, start_time, end_time):
    global _worksheet
    if _worksheet is None:
        _worksheet = initialise()

    # Check input validity
    if not _is_valid_employee(name):
        return ERROR_INVALID_NAME
    
    if not _is_valid_day(day):
        return ERROR_INVALID_TIME
    
    cell_name = _worksheet.find(re.compile(name, re.IGNORECASE))
    cell_day = _worksheet.find(re.compile(day, re.IGNORECASE))
    
    # Check if entry exists
    if _entry_exists(_worksheet, cell_name.row, cell_day.col):
        return {
            "name": name,
            "day": day,
            "start_time": _worksheet.cell(cell_name.row, cell_day.col).value,
            "end_time": _worksheet.cell(cell_name.row, cell_day.col + 1).value
        }
    else:
        return None

### HELPER FUNCTIONS ###
def _is_valid_employee(name):
    global _worksheet
    if _worksheet is None:
        _worksheet = initialise()
    
    try:
        cell = _worksheet.find(re.compile(name, re.IGNORECASE))
        return True
    except gspread.exceptions.CellNotFound:
        return False

# Check if times are valid (within hours and end after start)
def _is_valid_time(start_time, end_time, min_hour=9, max_hour=18):
    start_hour = to_24_hour_format(start_time)
    end_hour = to_24_hour_format(end_time)
    
    # Check if both times are within valid hours
    if start_hour < min_hour or start_hour > max_hour:
        return False
    if end_hour < min_hour or end_hour > max_hour:
        return False
    
    # Check if end time is after start time
    if end_hour <= start_hour:
        return False
    
    return True

# Check if the day is valid
def _is_valid_day(day_str):
    valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    if day_str not in valid_days:
        return False
    return True

# Convert to 24-hour format
def to_24_hour_format(time_str):
    time_hour = int(time_str.replace("am", "").replace("pm", ""))
    if 'pm' in time_str and time_hour != 12:
        time_hour += 12
    return time_hour

# Convert to 12-hour format
def _to_12_hour_format(time_str):
    time_hour = int(time_str)
    if time_hour == 0:
        return "12am"
    elif time_hour < 12:
        return f"{time_hour}am"
    elif time_hour == 12:
        return "12pm"
    else:
        return f"{time_hour - 12}pm"

# Check if entry already exists
def _entry_exists(worksheet, row, col):
    existing_value = worksheet.cell(row, col).value
    if existing_value:
        return True
    return False
    
# Check if the day limit has been reached (3 people per day)
def _day_limit_reached(worksheet, col, limit=3):
    # Get all values in the column (returns list of values)
    col_values = worksheet.col_values(col)
    
    # Skip header (first 2 elements) and count non-empty
    filled_count = sum(1 for value in col_values[2:] if value.strip())
    
    if filled_count >= limit:
        return True
    return False