from flask import Flask, render_template, request, redirect, flash, send_from_directory
from werkzeug.utils import secure_filename
import pytesseract
import cv2
import os
from PIL import Image
import ftfy
import io
import pandas as pd
from difflib import SequenceMatcher
import re
from fuzzywuzzy import fuzz

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.secret_key = 'your_secret_key'  # Change this to a secure secret key
app.static_folder = 'static'

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def pan_read_data(text):
    name = None
    fname = None
    dob = None
    pan = None
    nameline = []
    dobline = []
    panline = []
    text0 = []
    text1 = []
    text2 = []
    lines = text.split('\n')
    for lin in lines:
        s = lin.strip()
        s = lin.replace('\n', '')
        s = s.rstrip()
        s = s.lstrip()
        text1.append(s)
    text1 = list(filter(None, text1))
    lineno = 0
    for wordline in text1:
        xx = wordline.split('\n')
        if ([w for w in xx if re.search('(INCOMETAXDEPARWENT|INCOME|TAX|GOW|GOVT|GOVERNMENT|OVERNMENT|VERNMENT|DEPARTMENT|EPARTMENT|PARTMENT|ARTMENT|INDIA|NDIA)$', w)]):
            text1 = list(text1)
            lineno = text1.index(wordline)
            break
    text0 = text1[lineno+1:]
    try:
        # Skip if the line contains "Pormanam"
        if "Pormanam" in text0[0]:
            text0 = text0[1:]

        # Extract DOB using regular expression
        dob_pattern = re.compile(r'(\d{2}[-/]\d{2}[-/]\d{4})')
        dob_match = dob_pattern.search(text)
        if dob_match:
            dob = dob_match.group(1)

        # Simplify name and father's name extraction
        name = re.sub('[^a-zA-Z]+', ' ', text0[0].strip())
        fname = re.sub('[^a-zA-Z]+', ' ', text0[1].strip())

        # Cleaning PAN Card details
        text0 = findword(text1, '(Pormanam|Number|umber|Account|ccount|count|Permanent|ermanent|manent|wumm)$')
        panline = text0[0]
        pan = panline.rstrip()
        pan = pan.lstrip()
        pan = pan.replace(" ", "")
        pan = pan.replace("\"", "")
        pan = pan.replace(";", "")
        pan = pan.replace("%", "L")
    except:
        pass
    data = {}
    data['Name'] = name
    data['Father Name'] = fname
    data['Date of Birth'] = dob
    data['PAN'] = pan
    data['ID Type'] = "PAN"
    return data


def findword(textlist, wordstring):
    lineno = -1
    for wordline in textlist:
        xx = wordline.split()
        if ([w for w in xx if re.search(wordstring, w)]):
            lineno = textlist.index(wordline)
            textlist = textlist[lineno+1:]
            return textlist
    return textlist

def process_image(image_path):
    img = cv2.imread(image_path)

    # Convert the image to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Calculate the Laplacian variance as a measure of blurriness
    var = cv2.Laplacian(gray, cv2.CV_64F).var()

    # Adjust the blurriness threshold based on your images
    blurriness_threshold = 100

    if var < blurriness_threshold:
        print(f"Image {image_path} is Too Blurry. Skipping...")
        return None, None

    pytesseract.pytesseract.tesseract_cmd = 'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'
    filename = image_path
    text = pytesseract.image_to_string(Image.open(filename), lang='eng')

    text_output = open('output.txt', 'w', encoding='utf-8')
    text_output.write(text)
    text_output.close()

    file = open('output.txt', 'r', encoding='utf-8')
    extracted_text = file.read()

    extracted_text = ftfy.fix_text(extracted_text)
    extracted_text = ftfy.fix_encoding(extracted_text)

    print(f"Extracted Text: {extracted_text}")  # Add this line for debugging

    data = pan_read_data(extracted_text)

    try:
        # Confidence score calculation based on Name and Father's Name similarity
        name_similarity = fuzz.partial_ratio(data['Name'], data['Father Name'])
        confidence_name = min(name_similarity / 100.0, 1.0)  # Normalize to a value between 0 and 1

        # Confidence score based on Date of Birth presence
        confidence_dob = 1.0 if data['Date of Birth'] and re.match(r'\d{2}[-/]\d{2}[-/]\d{4}', data['Date of Birth']) else 0.0

        # Confidence score based on PAN presence and correct format
        confidence_pan = 1.0 if data['PAN'] and re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', data['PAN']) else 0.0

        # Confidence score based on correctness of names
        confidence_names = 0
        if data['Name'] and data['Father Name']:
            confidence_names += 30

        # Overall confidence score based on individual scores
        overall_confidence = (confidence_name + confidence_dob + confidence_pan + confidence_names) / 4.0

        # Normalize the overall confidence to a percentage
        confidence_score = min(overall_confidence * 100.0, 100.0)

    except:
        pass

    data['Confidence Score'] = confidence_score  # Add the confidence score to the data dictionary

    return data, confidence_score

# Function to read existing data from Excel file
def read_existing_data(output_excel_path):
    try:
        # Try reading the existing data from the Excel file
        existing_data = pd.read_excel(output_excel_path)
        return existing_data
    except FileNotFoundError:
        # If the file doesn't exist yet, return an empty DataFrame
        return pd.DataFrame()

def save_to_excel(data, output_excel_path="C:\\Users\\hrishikesh kudale\\OneDrive\\Desktop\\PAN_card_OCR-main\\output.xlsx"):
    existing_data = read_existing_data(output_excel_path)

    # Concatenate existing data and new data
    combined_data = pd.concat([existing_data, pd.DataFrame([data])], ignore_index=True)

    # Reorder columns to match the desired order
    column_order = ["Name", "Father Name", "Date of Birth", "PAN","Confidence Score"]
    combined_data = combined_data.reindex(columns=column_order)

    # Save the combined data to the Excel file
    combined_data.to_excel(output_excel_path, index=False)



@app.route('/')
def index():
    return render_template('index.html')


@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            # Process the uploaded image
            extracted_data, accuracy = process_image(file_path)
            
            # Save the data to Excel
            save_to_excel(extracted_data)

            # Render the template with extracted data
            return render_template('index.html', filename=filename, data=extracted_data, accuracy=accuracy)


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)