# Filename: backend/app.py
# Final Version with Google Sheets & Mock OTP Integration

import os
import uuid
import json
import base64
import random  # For generating the mock OTP
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from deepface import DeepFace
from blockchain import Blockchain
from liveness import check_liveness


# --- Imports for Google Sheets ---
import gspread
from google.oauth2.service_account import Credentials
# --------------------------------------

# 1. App Configuration
app = Flask(__name__)
CORS(app)
blockchain = Blockchain()
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///voting.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


if not os.path.exists('temp_images'):
    os.makedirs('temp_images')

# --- Google Sheets Configuration ---
GSPREAD_SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file"
]
SERVICE_ACCOUNT_FILE = 'service_account.json'
SHEET_NAME = 'Mock Aadhar DB'  # Make sure this name exactly matches your Google Sheet
SHEET_ID = ''
# --- Temporary storage for OTPs ---
# In a real app, this would be a database (like Redis)
otp_storage = {}
# ----------------------------------------

# 2. Database Models
class Voter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # The 'voter_id' is now the verified Aadhaar Number
    aadhaar_number = db.Column(db.String(12), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    image_path = db.Column(db.String(200), nullable=False)
    has_voted = db.Column(db.Boolean, default=False)
"""
class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.String(100), nullable=False)
"""
# 3. Helper Function to Access Google Sheet
def get_sheet():
    """Authenticates with Google and returns the first worksheet."""
    try:
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=GSPREAD_SCOPE)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).sheet1
        return sheet
    except Exception as e:
        print(f"Error accessing Google Sheet: {e}")
        return None

# 4. API Routes
@app.route('/')
def index():
    return "E-Voting Backend with Google Sheets is running!"

# --- NEW: /send-otp Route (replaces /verify-aadhaar) ---
@app.route('/send-otp', methods=['POST'])
def send_otp():
    data = request.json
    aadhaar_number = data.get('aadhaarNumber')

    if not aadhaar_number or len(aadhaar_number) != 12 or not aadhaar_number.isdigit():
        return jsonify({"error": "Please enter a valid 12-digit Aadhaar number."}), 400

    # Check if this Aadhaar is already registered in our *own* voting database
    if Voter.query.filter_by(aadhaar_number=aadhaar_number).first():
        return jsonify({"error": "This Aadhaar number is already registered to vote."}), 409

    # --- Find User in Google Sheet ---
    sheet = get_sheet()
    if sheet is None:
        return jsonify({"error": "Could not connect to the verification service."}), 500

    try:
        # Find the cell that matches the Aadhaar number (searches column 1)
        cell = sheet.find(aadhaar_number, in_column=1)
        # Get all data from that row
        row_data = sheet.row_values(cell.row)
        
        # Map data to a dictionary based on our headers (AadhaarNumber, Name, MobileNumber, Age)
        user_data = {
            'aadhaar': row_data[0],
            'name': row_data[1],
            'phone': row_data[2],
            'age': int(row_data[3])
        }

    except gspread.exceptions.CellNotFound:
        return jsonify({"error": "Aadhaar number not found in the registry."}), 404
    except Exception as e:
        print(f"Error reading sheet data: {e}")
        return jsonify({"error": "An error occurred while fetching user data."}), 500

    # --- Perform Age Check ---
    if user_data['age'] < 18:
        return jsonify({"error": "Voter must be 18 years or older to register."}), 403

    # --- MOCK OTP LOGIC ---
    otp = str(random.randint(100000, 999999))
    
    # Store the OTP with the user's data
    otp_storage[aadhaar_number] = {
        "otp": otp,
        "name": user_data['name']
    }
    
    # This is the "Mock" part: Print to terminal instead of sending SMS
    print("---------------------------------------------------------")
    print(f"==> MOCK OTP for {user_data['name']} ({aadhaar_number}): {otp}")
    print("---------------------------------------------------------")
    
    return jsonify({
        "message": "OTP has been generated.",
        "name": user_data['name'] # Send the name back to the UI
    }), 200

# --- MODIFIED: /register Route ---
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    aadhaar_number = data.get('aadhaarNumber')
    otp = data.get('otp')
    image_data_uri = data.get('imageData')

    # --- Verify the Mock OTP ---
    if aadhaar_number not in otp_storage or otp_storage[aadhaar_number]['otp'] != otp:
        return jsonify({"error": "Invalid or expired OTP."}), 401
    
    # OTP is valid, get the name we stored
    name = otp_storage[aadhaar_number]['name']
    
    # --- Process and Save Face Image ---
    try:
        header, encoded = image_data_uri.split(",", 1)
        binary_data = base64.b64decode(encoded)
        temp_filename = f"temp_images/{uuid.uuid4()}.jpg"
        with open(temp_filename, 'wb') as f:
            f.write(binary_data)
        
        DeepFace.detectFace(img_path=temp_filename)

    except Exception as e:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
        return jsonify({"error": "No face detected or image is invalid."}), 400

    # --- Create the voter record ---
    new_voter = Voter(
        aadhaar_number=aadhaar_number,
        name=name,
        image_path=temp_filename
    )
    db.session.add(new_voter)
    db.session.commit()
    
    # Clean up the used OTP
    del otp_storage[aadhaar_number]

    return jsonify({"message": f"Voter '{name}' registered successfully!"}), 201

# --- /login Route (Unchanged Logic) ---
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    image_list = data.get('images')

    if not image_list or len(image_list) < 5:
        return jsonify({"error": "Insufficient frames for liveness detection."}), 400

    # 🔐 LIVENESS CHECK
    if not check_liveness(image_list):
        return jsonify({"error": "Liveness detection failed. Please blink and turn head."}), 403

    # ✅ Continue face verification
    for voter in Voter.query.all():
        for img_data in image_list:
            temp_path = f"temp_images/live.jpg"
            header, encoded = img_data.split(",", 1)
            with open(temp_path, "wb") as f:
                f.write(base64.b64decode(encoded))

            try:
                result = DeepFace.verify(
                    img1_path=voter.image_path,
                    img2_path=temp_path,
                    model_name="Facenet",
                    enforce_detection=False
                )
                if result['verified']:
                    if voter.has_voted:
                        return jsonify({"error": "Already voted"}), 403

                    return jsonify({
                        "message": f"Welcome {voter.name}",
                        "voterName": voter.name,
                        "voterId": voter.aadhaar_number
                    }), 200
            except:
                continue

    return jsonify({"error": "Face not recognized"}), 401


# --- /vote Route (Updated to use aadhaar_number) ---
@app.route('/vote', methods=['POST'])
def vote():
    data = request.json
    voter_id = data.get('voterId') # This is the Aadhaar Number
    candidate_id = data.get('candidateId')

    if not voter_id or not candidate_id:
        return jsonify({"error": "Voter ID and Candidate ID are required."}), 400

    # --- IDENTITY CHECK (using SQL) ---
    # Find the voter in our SQL database
    voter = Voter.query.filter_by(aadhaar_number=voter_id).first()

    if not voter:
        return jsonify({"error": "Voter not found."}), 404

    if voter.has_voted:
        return jsonify({"error": "This voter has already cast their vote."}), 403

    # --- CAST THE VOTE (using Blockchain) ---

    # 1. First, mark the voter as 'has_voted' in the SQL DB to prevent double login
    voter.has_voted = True
    db.session.add(voter)
    db.session.commit()

    # 2. Now, add the vote to the blockchain's "pending" list
    block_index = blockchain.add_vote(
        voter_aadhaar=voter.aadhaar_number,
        candidate_id=candidate_id
    )

    # --- MINE THE BLOCK (For a project, we can do this instantly) ---
    # In a real system, mining is separate. Here, we'll auto-mine
    # to instantly seal the vote into the chain.
    last_block = blockchain.last_block
    last_hash = blockchain.hash(last_block)
    blockchain.create_block(proof=123, previous_hash=last_hash) # Using a dummy proof

    return jsonify({"message": f"Your vote has been securely recorded in block {block_index}."}), 200
# --- NEW ADMIN/RESULTS ROUTES ---

@app.route('/admin/results', methods=['GET'])
def get_results():
    # This function will read the *entire* blockchain and tally the votes
    votes = {}

    # Iterate over every block in the chain (skip the first "Genesis Block")
    for block in blockchain.chain[1:]:
        for vote in block['votes']:
            candidate = vote['candidate']
            if candidate not in votes:
                votes[candidate] = 0
            votes[candidate] += 1

    return jsonify({
        "message": "Vote tally complete.",
        "results": votes
    }), 200

@app.route('/admin/chain', methods=['GET'])
def get_chain():
    # This lets an admin view the entire, raw blockchain
    return jsonify({
        "chain": blockchain.chain,
        "length": len(blockchain.chain)
    }), 200
# 5. Main execution block
if __name__ == '__main__':
    with app.app_context():
        # This creates the database and tables if they don't exist
        db.create_all()
    app.run(host='127.0.0.1', port=5000, debug=True)
