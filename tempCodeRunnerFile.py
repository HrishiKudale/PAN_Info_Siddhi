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