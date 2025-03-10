import google.generativeai as genai
import csv
import os

# Placeholder API key - Replace with your actual Gemini API key if you have one
API_KEY = "ENTER_YOUR_API_KEY"  # Replace with your actual API key if you want to run this with a real API key
genai.configure(api_key=API_KEY)

def extract_resident_schedule_from_image(image_path):
    """
    Extracts resident duty schedule from an image using Gemini API and returns
    structured data.

    Args:
        image_path: Path to the PNG image file.

    Returns:
        A list of dictionaries, where each dictionary represents a resident duty entry.
        Returns None if extraction fails.
    """

    try:
        model = genai.GenerativeModel('gemini-exp-1206')

        with open(image_path, "rb") as image_file:
            image_data = image_file.read()

        image_parts = [
            {"mime_type": "image/png", "data": image_data},
        ]

        prompt_parts = [
            "Extract the resident duty schedule from this image. "
            "Identify residents on duty for 'Day' and 'Night' shifts. "
            "Focus on 'Duty Teams' table for Main (Centre) and Main (Periphery) blocks, and 'SURGICAL BLOCK', 'Burns & Plastic Block', 'MCH BLOCK' sections. "
            "List resident names, their shift (Morning/Night), block (Main (Centre), Main (Periphery), Surgical, Burns & Plastic, MCH), and resident type (SR or JR). "
            "Return the data in a way that is easy to parse, ideally structured with clear labels for each piece of information (Shift, Block, Resident Type, Resident Name)."
        ]

        response = model.generate_content(prompt_parts + image_parts)
        response.resolve()

        if response.text:
            extracted_text = response.text
            print("Extracted Text from Gemini API:\n", extracted_text) # For debugging

            schedule_data = parse_extracted_text(extracted_text)
            return schedule_data
        else:
            print("No text extracted from the image.")
            return None

    except Exception as e:
        print(f"Error during image processing or API call: {e}")
        return None


def parse_extracted_text(text):
    """
    Parses the text extracted from Gemini API to structure the resident schedule data.

    Args:
        text: The text extracted from the image.

    Returns:
        A list of dictionaries representing the structured resident schedule data.
    """
    schedule_entries = []

    # --- Main (Centre) and Main (Periphery) ---
    if "Duty Teams" in text:
        duty_teams_start = text.find("Duty Teams")
        duty_teams_end = text.find("SURGICAL BLOCK", duty_teams_start) # Assuming Surgical Block comes after

        if duty_teams_end == -1: # In case Surgical block is not found, try Burns & Plastic block
            duty_teams_end = text.find("Burns & Plastic Block", duty_teams_start)
        if duty_teams_end == -1: # If still not found, try MCH Block
            duty_teams_end = text.find("MCH BLOCK", duty_teams_start)
        if duty_teams_end == -1: # If still not found, take rest of the text as duty teams (might be risky)
            duty_teams_end = len(text)


        duty_teams_text = text[duty_teams_start:duty_teams_end]

        day_shift_line_start = duty_teams_text.find("Day")
        night_shift_line_start = duty_teams_text.find("Night")

        if day_shift_line_start != -1 and night_shift_line_start != -1:
            day_shift_line = duty_teams_text[day_shift_line_start:night_shift_line_start]
            night_shift_line = duty_teams_text[night_shift_line_start:duty_teams_end]

            day_names = day_shift_line.split()[1:] # Skip "Day" and take names
            night_names = night_shift_line.split()[1:] # Skip "Night" and take names


            if len(day_names) >= 4: # Expecting SR1, SR2, JR1, JR2 names in order
                schedule_entries.append({"Shift": "Morning", "Block": "Main (Centre)", "Resident Type": "SR", "Resident Name": day_names[0]})
                schedule_entries.append({"Shift": "Morning", "Block": "Main (Periphery)", "Resident Type": "SR", "Resident Name": day_names[1]})
                schedule_entries.append({"Shift": "Morning", "Block": "Main (Centre)", "Resident Type": "JR", "Resident Name": day_names[2]})
                schedule_entries.append({"Shift": "Morning", "Block": "Main (Periphery)", "Resident Type": "JR", "Resident Name": day_names[3]})
                schedule_entries.append({"Shift": "Night", "Block": "Main (Centre)", "Resident Type": "JR", "Resident Name": day_names[2]}) # JR does both shifts
                schedule_entries.append({"Shift": "Night", "Block": "Main (Periphery)", "Resident Type": "JR", "Resident Name": day_names[3]}) # JR does both shifts

            if len(night_names) >= 4: # Expecting SR1, SR2, JR1, JR2 names in order
                schedule_entries.append({"Shift": "Night", "Block": "Main (Centre)", "Resident Type": "SR", "Resident Name": night_names[0]})
                schedule_entries.append({"Shift": "Night", "Block": "Main (Periphery)", "Resident Type": "SR", "Resident Name": night_names[1]})


    # --- Surgical Block ---
    if "SURGICAL BLOCK" in text:
        surgical_block_start = text.find("SURGICAL BLOCK")
        surgical_block_end = text.find("Burns & Plastic Block", surgical_block_start) # Assuming Burns & Plastic comes after

        if surgical_block_end == -1: # In case Burns & Plastic block is not found, try MCH block
            surgical_block_end = text.find("MCH BLOCK", surgical_block_start)
        if surgical_block_end == -1: # If still not found, take rest of the text as surgical block (might be risky)
            surgical_block_end = len(text)


        surgical_block_text = text[surgical_block_start:surgical_block_end]

        if "Duty SR (M)" in surgical_block_text:
            start_index = surgical_block_text.find("Duty SR (M)") + len("Duty SR (M)")
            end_index = surgical_block_text.find("\n", start_index) # Find newline for name end
            sr_morning_name = surgical_block_text[start_index:end_index].strip().split('-')[-1].strip() # Take name after dash if exists
            if sr_morning_name:
                schedule_entries.append({"Shift": "Morning", "Block": "Surgical", "Resident Type": "SR", "Resident Name": sr_morning_name})

        if "Duty SR (N)" in surgical_block_text:
            start_index = surgical_block_text.find("Duty SR (N)") + len("Duty SR (N)")
            end_index = surgical_block_text.find("\n", start_index)
            sr_night_name = surgical_block_text[start_index:end_index].strip().split('-')[-1].strip()
            if sr_night_name:
                schedule_entries.append({"Shift": "Night", "Block": "Surgical", "Resident Type": "SR", "Resident Name": sr_night_name})

        if "Duty JR" in surgical_block_text:
            start_index = surgical_block_text.find("Duty JR") + len("Duty JR")
            end_index = surgical_block_text.find("\n", start_index)
            jr_name = surgical_block_text[start_index:end_index].strip().split('-')[-1].strip()
            if jr_name:
                schedule_entries.append({"Shift": "Morning", "Block": "Surgical", "Resident Type": "JR", "Resident Name": jr_name})
                schedule_entries.append({"Shift": "Night", "Block": "Surgical", "Resident Type": "JR", "Resident Name": jr_name}) # JR does both


    # --- Burns & Plastic Block ---
    if "Burns & Plastic Block" in text:
        burns_block_start = text.find("Burns & Plastic Block")
        burns_block_end = text.find("MCH BLOCK", burns_block_start) # Assuming MCH block comes after

        if burns_block_end == -1: # If MCH block not found, take rest of the text
            burns_block_end = len(text)

        burns_block_text = text[burns_block_start:burns_block_end]

        if "Duty SR (M)" in burns_block_text:
            start_index = burns_block_text.find("Duty SR (M)") + len("Duty SR (M)")
            end_index = burns_block_text.find("\n", start_index)
            sr_morning_name = burns_block_text[start_index:end_index].strip().split('-')[-1].strip()
            if sr_morning_name:
                schedule_entries.append({"Shift": "Morning", "Block": "Burns & Plastic", "Resident Type": "SR", "Resident Name": sr_morning_name})

        if "Duty SR (N)" in burns_block_text:
            start_index = burns_block_text.find("Duty SR (N)") + len("Duty SR (N)")
            end_index = burns_block_text.find("\n", start_index)
            sr_night_name = burns_block_text[start_index:end_index].strip().split('-')[-1].strip()
            if sr_night_name:
                schedule_entries.append({"Shift": "Night", "Block": "Burns & Plastic", "Resident Type": "SR", "Resident Name": sr_night_name})

        if "Duty JR" in burns_block_text:
            start_index = burns_block_text.find("Duty JR") + len("Duty JR")
            end_index = burns_block_text.find("\n", start_index)
            jr_name = burns_block_text[start_index:end_index].strip().split('-')[-1].strip()
            if jr_name:
                schedule_entries.append({"Shift": "Morning", "Block": "Burns & Plastic", "Resident Type": "JR", "Resident Name": jr_name})
                schedule_entries.append({"Shift": "Night", "Block": "Burns & Plastic", "Resident Type": "JR", "Resident Name": jr_name}) # JR does both


    # --- MCH BLOCK ---
    if "MCH BLOCK" in text:
        mch_block_start = text.find("MCH BLOCK")
        mch_block_end = len(text) # MCH block is usually the last one

        mch_block_text = text[mch_block_start:mch_block_end]

        if "Duty SR (M)" in mch_block_text:
            start_index = mch_block_text.find("Duty SR (M)") + len("Duty SR (M)")
            end_index = mch_block_text.find("\n", start_index)
            sr_morning_name = mch_block_text[start_index:end_index].strip().split('-')[-1].strip()
            if sr_morning_name:
                schedule_entries.append({"Shift": "Morning", "Block": "MCH", "Resident Type": "SR", "Resident Name": sr_morning_name})

        if "Duty SR (N)" in mch_block_text:
            start_index = mch_block_text.find("Duty SR (N)") + len("Duty SR (N)")
            end_index = mch_block_text.find("\n", start_index)
            sr_night_name = mch_block_text[start_index:end_index].strip().split('-')[-1].strip()
            if sr_night_name:
                schedule_entries.append({"Shift": "Night", "Block": "MCH", "Resident Type": "SR", "Resident Name": sr_night_name})

        jr_names = []
        if "Duty JR" in mch_block_text:
            start_index = mch_block_text.find("Duty JR") + len("Duty JR")
            end_index = mch_block_text.find("\n", start_index) # Find newline after first JR name, might be multiple JRs
            jr_names_str = mch_block_text[start_index:end_index].strip().split('-')[-1].strip() # Get names string after 'Duty JR - '

            if jr_names_str:
                jr_names = [name.strip() for name in jr_names_str.split(',')] # Split by comma if multiple names

        for jr_name in jr_names:
            if jr_name:
                schedule_entries.append({"Shift": "Morning", "Block": "MCH", "Resident Type": "JR", "Resident Name": jr_name})
                schedule_entries.append({"Shift": "Night", "Block": "MCH", "Resident Type": "JR", "Resident Name": jr_name}) # JR does both


    return schedule_entries


def create_csv_file(schedule_data, csv_filename="resident_schedule.csv"):
    """
    Creates a CSV file from the resident schedule data.

    Args:
        schedule_data: List of dictionaries containing schedule data.
        csv_filename: Name of the CSV file to create.
    """
    if not schedule_data:
        print("No schedule data to write to CSV.")
        return

    csv_headers = ["Shift", "Block", "Resident Type", "Resident Name"]

    with open(csv_filename, mode='w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=csv_headers)
        writer.writeheader()
        writer.writerows(schedule_data)

    print(f"CSV file '{csv_filename}' created successfully.")
    # For web applications, you would typically return the CSV data or file path
    # to be handled for download by the web framework.


if __name__ == "__main__":
    image_file_path = "resident_schedule.png"  # Replace with the actual path to your image file

    if not os.path.exists(image_file_path):
        print(f"Error: Image file not found at '{image_file_path}'")
    else:
        resident_schedule = extract_resident_schedule_from_image(image_file_path)

        if resident_schedule:
            create_csv_file(resident_schedule)
            print("\nResident Schedule Data:") # Print to console as well for verification
            for entry in resident_schedule:
                print(entry)
        else:
            print("Failed to extract resident schedule.")