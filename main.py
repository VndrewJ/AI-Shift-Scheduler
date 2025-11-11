import gspread
import os
from google.oauth2.service_account import Credentials

# Get relative path
dirname = os.path.dirname(__file__)
filename = os.path.join(dirname, 'credentials.json')
gc = gspread.service_account(filename)

# Open the Google Sheet using its key
sh = gc.open_by_key('134mf9hF5xPVwbH7OwvEquPu5zebDaX_SNuleEt5M8B8')
worksheet = sh.get_worksheet(0)

print("Whats your name?")
name = input()
print("What day do you want to work?")
day = input()
print("What time do you want to start?")
start_time = input()
print("What time do you want to end?")
end_time = input()

# Search for cell input
cell_name = worksheet.find(name)
cell_day_range = worksheet.find(day)
cell_day = cell_day_range.split(':')[0]  # Get the first cell in the range

worksheet.update_cell(cell_name.row, cell_day.col, f"{start_time}")
worksheet.update_cell(cell_name.row, cell_day.col, f"{end_time}")



