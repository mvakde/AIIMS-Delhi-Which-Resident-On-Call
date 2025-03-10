import google.generativeai as genai
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import base64
import re
import time
import datetime
import smtplib
from email.mime.text import MIMEText

# --- Configuration ---
GEMINI_API_KEY = "AIzaSyCIjxuTpS1CoIaU34fiXkcPwkoGwq72e2A"  # Replace with your actual API key later
GOOGLE_SHEET_ID = "1jmGjtVM7LCMuTreNWnfkW1NRkHpiGmRsIabQHL4zbhE"  # Replace with your actual Google Sheet ID
GOOGLE_SHEET_TAB_NAME = "Sheet1"  # Replace with your actual tab name
ERROR_EMAIL = "aryamanmithil@gmail.com"
SCHEDULE_IMAGE_PATH = "./duty_schedule.png"  # Path to the schedule image (ensure this file exists in the same directory, or provide full path)
CREDENTIALS_FILE = 'path/to/your/credentials.json' # Path to your Google Cloud credentials JSON file (if needed for Google Sheets API)

# --- Initialize Gemini API ---
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-exp-1206')

def image_to_text(image_path):
    """
    Extracts text from an image using Gemini Pro Vision API.
    """
    try:
        with open(image_path, "rb") as image_file:
            image_data = image_file.read()

        image_parts = [
            {
                "mime_type": "image/jpeg",  # Assuming JPEG image
                "data": image_data
            },
        ]

        prompt_parts = [
            "Extract all the text from this duty roster image. Return the text as is, without any modifications or formatting. I need the raw text content.",
            image_parts[0],
        ]

        response = model.generate_content(prompt_parts)
        response.resolve() # Ensure response is fully resolved before accessing text
        return response.text if response.text else "No text extracted."

    except Exception as e:
        print(f"Error during image to text conversion: {e}")
        return None

def parse_schedule_text(text):
    """
    Parses the extracted text and structures it into a table format.
    """
    if not text:
        return []

    table_data = []
    blocks = re.split(r'(AB8 ICU|SURGICAL BLOCK|Burns & Plastic Block|MCH BLOCK|RPC-|ORTHO-|CDER/ Dental-|PAC Clinic f/b respective duty-|Pain Clinic-|CT/MRI-|APS-|NCA-|Village-|NCI, Jhajjar-|TC-|LEAVES)', text)
    current_block = "Unknown Block"

    for i in range(1, len(blocks), 2): # Step by 2 to get block name and content
        block_name = blocks[i].strip()
        block_content = blocks[i+1].strip() if i + 1 < len(blocks) else ""

        if block_name:
            current_block = block_name

        day_shift_match = re.search(r'Day\s+(.*?)(?=Night|$)', block_content, re.DOTALL | re.IGNORECASE)
        night_shift_match = re.search(r'Night\s+(.*?)(?=SURGICAL BLOCK|Burns & Plastic Block|MCH BLOCK|RPC-|ORTHO-|CDER/ Dental-|PAC Clinic f/b respective duty-|Pain Clinic-|CT/MRI-|APS-|NCA-|Village-|NCI, Jhajjar-|TC-|LEAVES|$)', block_content, re.DOTALL | re.IGNORECASE) # Added block names as terminators


        day_shift_doctors = []
        night_shift_doctors = []

        if day_shift_match:
            day_shift_text = day_shift_match.group(1).strip()
            day_shift_doctors = [doc.strip() for doc in re.findall(r'([A-Za-z\s\.\*#]+)(?:,|\s|$)', day_shift_text) if doc.strip()] # Improved regex to capture doctor names

        if night_shift_match:
            night_shift_text = night_shift_match.group(1).strip()
            night_shift_doctors = [doc.strip() for doc in re.findall(r'([A-Za-z\s\.\*#]+)(?:,|\s|$)', night_shift_text) if doc.strip()] # Improved regex


        for doctor in day_shift_doctors:
            if doctor: # Check for empty strings
                table_data.append(["Day", doctor, current_block])
        for doctor in night_shift_doctors:
             if doctor: # Check for empty strings
                table_data.append(["Night", doctor, current_block])

    return table_data


def update_google_sheet(sheet_id, tab_name, data):
    """
    Updates a Google Sheet with the provided data.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', ['https://www.googleapis.com/auth/spreadsheets'])
    # If there are no valid credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # --- Option 1: Using credentials.json file (Service Account or OAuth 2.0) ---
            if CREDENTIALS_FILE and os.path.exists(CREDENTIALS_FILE):
                creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=['https://www.googleapis.com/auth/spreadsheets'])
            else:
                print("Warning: No valid credentials found. Google Sheets update might fail.")
                return False # Or raise an exception

            # --- Option 2:  OAuth 2.0 flow (if you prefer interactive login - uncomment below and comment out Option 1) ---
            # from google_auth_oauthlib.flow import InstalledAppFlow
            # flow = InstalledAppFlow.from_client_secrets_file(
            #     'path/to/your/credentials.json', ['https://www.googleapis.com/auth/spreadsheets']) # Replace with your credentials file
            # creds = flow.run_local_server(port=0)


        # Save the credentials for the next run
        if creds and creds.valid: # Only save if credentials were created and valid
            with open('token.json', 'w') as token:
                token.write(creds.to_json())

    try:
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()

        # Clear existing content in the sheet (optional - if you want to replace the entire sheet)
        clear_body = {}
        clear_request = sheet.values().clear(spreadsheetId=sheet_id, range=tab_name, body=clear_body)
        clear_response = clear_request.execute()


        # Prepare data for writing
        values = [["Shift Timing", "Doctor Name", "Building"]] + data  # Headers + table data
        body = {
            'values': values
        }
        result = sheet.values().update(
            spreadsheetId=sheet_id,
            range=tab_name, # Write to the specified tab (e.g., "Sheet1")
            valueInputOption="USER_ENTERED",
            body=body).execute()
        print(f"{result.get('updatedCells')} cells updated in sheet!")
        return True

    except HttpError as error:
        print(f"An error occurred: {error}")
        return False


def send_error_email(error_message, to_email):
    """
    Sends an error notification email.
    """
    sender_email = "your_email@gmail.com"  # Replace with your email address
    sender_password = "your_password"  # Replace with your email password or app password if using Gmail

    message = MIMEText(f"Subject: Duty Schedule Update Failed\n\nError: {error_message}")
    message['From'] = sender_email
    message['To'] = to_email

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server: # For Gmail SSL
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, message.as_string())
        print("Error email sent successfully!")
    except Exception as e:
        print(f"Failed to send error email: {e}")


def main():
    """
    Main function to orchestrate the schedule extraction and Google Sheet update.
    """
    try:
        extracted_text = image_to_text(SCHEDULE_IMAGE_PATH)
        if not extracted_text or "No text extracted" in extracted_text:
            raise Exception("Failed to extract text from image or no text found.")

        table_data = parse_schedule_text(extracted_text)
        if not table_data:
            raise Exception("Failed to parse schedule data from extracted text.")

        if not update_google_sheet(GOOGLE_SHEET_ID, GOOGLE_SHEET_TAB_NAME, table_data):
            raise Exception("Failed to update Google Sheet.")

        print("Duty schedule updated successfully!")

    except Exception as e:
        error_msg = f"Error processing duty schedule: {e}"
        print(error_msg)
        send_error_email(error_msg, ERROR_EMAIL)


if __name__ == "__main__":
    while True: # Simulate daily run and retries
        now = datetime.datetime.now()
        if now.hour >= 18:  # 6 PM or later
            for attempt in range(2): # Retry twice (initial run + 1 retry)
                print(f"Attempt {attempt+1} to update duty schedule at {now.strftime('%Y-%m-%d %H:%M:%S')}")
                try:
                    main()
                    break  # Success, exit retry loop
                except Exception as e:
                    print(f"Attempt {attempt+1} failed: {e}")
                    if attempt == 0:
                        print("Waiting for 1 hour before retrying...")
                        time.sleep(3600)  # Wait for 1 hour
                    else:
                        print("Max retries reached. Check logs and error email.")
            break # Exit the while loop after attempts are done for the day
        else:
            print(f"Waiting until 6 PM to run. Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
            time.sleep(60 * 60) # Wait for 1 hour and check again