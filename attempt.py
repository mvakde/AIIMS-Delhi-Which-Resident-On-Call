import google.generativeai as genai
import os
import csv
from PIL import Image
import io

def extract_resident_schedule(image_path, api_key):
    """
    Extracts resident doctor schedule from an image using Gemini API and saves it to a CSV file.

    Args:
        image_path (str): Path to the PNG image file.
        api_key (str): Your Gemini API key.

    Returns:
        str: Path to the created CSV file, or None if there was an error.
    """

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-exp-1206')

    try:
        image = Image.open(image_path)
        image_bytes = io.BytesIO()
        image.save(image_bytes, format=image.format)
        image_data = image_bytes.getvalue()

        prompt_text = """
        Instructions:
        - Make a table containing all the residents in each shift.
        - The table should have 4 headers: Shift, Block, Resident type, Resident Name
        - Values that can be taken:
              - Shift: Morning or Night,
              - Block:  "Main (Centre), "Main (Periphery)", "Surgical", "Burns & Plastic", "MCH"
              - Resident Type: JR or SR
              - Resident Name: The names you extract
        - Ordering: All the Morning shift names first, then Night shift. Within each shift, order by the block, Within each block, order by type
        - Write the JR resident shifts separately for both morning and night (Meaning the name will be repeated)

        Explanation of the relevant parts of the document:
        - There are 5 types of residents: "Main (Centre), "Main (Periphery)", "Surgical", "Burns & Plastic", "MCH"
        - For "Main (Centre)" and "Main (Periphery)", the names are at the top of the document in the table named "Duty Teams". The names are under the columns SR1, SR2, JR1 and JR2. The SR residents either do the morning(day) shift or the night shift. The JR residents do both shifts. SR1 and JR1 belong to "Main (Centre)" while SR2 and JR2 belong to "Main (Periphery)
        - For "Surgical", "Burns & Plastic" and "MCH", the residents names are written next to Duty SR (M), Duty SR (N) and Duty JR. Similar to the above, there are separate SR residents for Morning (M) shifts and Night (N) shifts, while JR residents do both. The "MCH" block will always have an extra JR resident
        - IGNORE EVERYTHING ELSE IN THE DOCUMENT UPLOADED

        From the document, extract the names of all the residents on duty for the day shift and Night shift separately and create the table as described above.
        """

        response = model.generate_content([prompt_text, {"mime_type": 'image/png', "data": image_data}])
        response.resolve() # waits for response to be available
        extracted_text = response.text

        # Basic parsing of the text response (This might need adjustments based on Gemini's output format)
        # **Important:** This parsing is a placeholder and highly dependent on the format Gemini returns.
        # You will likely need to inspect Gemini's output and refine this part.
        lines = extracted_text.strip().split('\n')
        data_rows = []
        for line in lines:
            if "|" in line and "Shift" not in line and "---" not in line and line.strip(): # Basic row detection, adjust as needed
                parts = [part.strip() for part in line.split('|') if part.strip()]
                if len(parts) == 4:
                    data_rows.append(parts)


        csv_filename = "resident_schedule.csv"
        with open(csv_filename, 'w', newline='') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow(["Shift", "Block", "Resident Type", "Resident Name"]) # Header
            csv_writer.writerows(data_rows)

        return csv_filename

    except Exception as e:
        print(f"Error processing image: {e}")
        return None

if __name__ == "__main__":
    image_file_path = "resident_schedule.png"  # Replace with the path to your image file
    gemini_api_key = "YOUR_API_KEY"  # Replace with your actual Gemini API key

    if not os.path.exists(image_file_path):
        print(f"Error: Image file not found at '{image_file_path}'. Please replace 'your_schedule_image.png' with the correct path.")
    else:
        csv_file = extract_resident_schedule(image_file_path, gemini_api_key)
        if csv_file:
            print(f"Resident schedule saved to '{csv_file}'")
            # You can add code here to automatically download the CSV file in a web application context.
        else:
            print("Failed to extract resident schedule.")