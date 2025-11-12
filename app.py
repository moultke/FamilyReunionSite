import base64
import subprocess
from flask import Flask, render_template, request, jsonify, redirect, url_for, g, session, send_from_directory
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import secrets
import os
import uuid
import sqlite3
import stripe
import time
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask_session import Session
from werkzeug.exceptions import RequestEntityTooLarge
import os
import platform
from azure.storage.blob import BlobServiceClient, ContentSettings
from io import BytesIO

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'heic', 'mp4', 'mov', 'avi', 'webm'}

# Load environment variables
load_dotenv()

# Check if running on Linux before executing apt-get
if platform.system() == "Linux":
    os.system("apt-get update && apt-get install -y libgl1")

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size

# Azure Blob Storage configuration
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME", "familyreunion-uploads")
USE_AZURE_STORAGE = bool(AZURE_STORAGE_CONNECTION_STRING)

# Initialize Azure Blob Service Client if connection string is available
blob_service_client = None
if USE_AZURE_STORAGE:
    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        # Ensure container exists
        try:
            blob_service_client.create_container(AZURE_CONTAINER_NAME, public_access='blob')
            logging.info(f"Created Azure container: {AZURE_CONTAINER_NAME}")
        except Exception as e:
            if "ContainerAlreadyExists" not in str(e):
                logging.warning(f"Container creation note: {e}")
            else:
                logging.info(f"Using existing Azure container: {AZURE_CONTAINER_NAME}")
    except Exception as e:
        logging.error(f"Failed to initialize Azure Blob Storage: {e}")
        USE_AZURE_STORAGE = False
else:
    logging.info("Azure Storage not configured - using local file storage")

# Enhanced session configuration
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = os.path.join(os.getcwd(), ".flask_session")
app.config["SESSION_PERMANENT"] = True  # Changed to True for better persistence
app.config["SESSION_USE_SIGNER"] = True
app.config["SESSION_KEY_PREFIX"] = "flask_"
app.secret_key = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(32))

# Initialize Flask-Session
Session(app)

# Configure Logging information
logging.basicConfig(level=logging.DEBUG)

secret_key = secrets.token_hex(32)

if not os.path.exists(UPLOAD_FOLDER):
    try:
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    except OSError as e:
        logging.error(f"Could not create upload directory: {e}")


# ------------------ File Handling & Processing ------------------

def allowed_file(filename):
    """Check if the file has an allowed extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    return render_template('index.html', config=app.config)


def convert_heic_to_jpg(filepath):
    """Convert HEIC to JPG using ImageMagick."""
    jpg_filepath = filepath.rsplit(".", 1)[0] + ".jpg"

    # Check if ImageMagick is installed
    if subprocess.run(["which", "magick"], capture_output=True).returncode == 0:
        try:
            subprocess.run(["magick", filepath, jpg_filepath], check=True)
            os.remove(filepath)  # Delete the original HEIC file
            return jpg_filepath
        except subprocess.CalledProcessError as e:
            logging.error(f"ImageMagick conversion failed: {e}")
            return None
    else:
        logging.error("ImageMagick not installed - cannot convert HEIC files")
        return None


@app.route("/upload-image", methods=["POST"])
def upload_image():
    """Handles file uploads to Azure Blob Storage or local filesystem."""
    try:
        if 'image' not in request.files:
            logging.warning("No file part in request")
            return jsonify({'error': 'No file part in request'}), 400

        file = request.files['image']
        if file.filename == '':
            logging.warning("No selected file")
            return jsonify({'error': 'No selected file'}), 400

        # Check if file extension is allowed
        if not allowed_file(file.filename):
            logging.warning(f"File type not allowed: {file.filename}")
            return jsonify({'error': 'File type not allowed. Please upload PNG, JPG, JPEG, GIF, HEIC, MP4, MOV, AVI, or WEBM files.'}), 400
    except Exception as e:
        logging.error(f"Error processing upload request: {e}")
        return jsonify({'error': f'Error processing request: {str(e)}'}), 400

    # Generate a unique filename to prevent overwriting
    file_ext = file.filename.rsplit(".", 1)[-1].lower()
    filename = f"{uuid.uuid4().hex}.{file_ext}"

    try:
        if USE_AZURE_STORAGE and blob_service_client:
            # Upload to Azure Blob Storage
            logging.info(f"Uploading to Azure Blob Storage: {filename}")

            # Get MIME type for the file
            mime_type = get_mime_type(file_ext)

            # Read file data
            file_data = file.read()

            # Handle HEIC conversion if needed
            if file_ext == 'heic':
                # Save temporarily for conversion
                temp_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                with open(temp_path, 'wb') as temp_file:
                    temp_file.write(file_data)

                converted_path = convert_heic_to_jpg(temp_path)
                if converted_path:
                    filename = os.path.basename(converted_path)
                    with open(converted_path, 'rb') as converted_file:
                        file_data = converted_file.read()
                    os.remove(converted_path)
                    mime_type = 'image/jpeg'
                else:
                    logging.error("HEIC conversion failed")
                    return jsonify({'error': 'HEIC conversion failed'}), 500

            # Upload to blob
            blob_client = blob_service_client.get_blob_client(container=AZURE_CONTAINER_NAME, blob=filename)
            content_settings = ContentSettings(content_type=mime_type)
            blob_client.upload_blob(file_data, overwrite=True, content_settings=content_settings)

            # Get blob URL
            blob_url = blob_client.url
            logging.info(f"File successfully uploaded to Azure: {filename}")
            return jsonify({'success': True, 'image_url': url_for('uploaded_file', filename=filename)})

        else:
            # Fallback to local storage
            logging.info(f"Uploading to local storage: {filename}")
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            if file_ext == 'heic':
                converted_path = convert_heic_to_jpg(file_path)
                if converted_path:
                    filename = os.path.basename(converted_path)
                    file_path = converted_path
                else:
                    logging.error("HEIC conversion failed")
                    return jsonify({'error': 'HEIC conversion failed'}), 500

            logging.info(f"File successfully uploaded locally: {filename}")
            return jsonify({'success': True, 'image_url': url_for('uploaded_file', filename=filename)})

    except Exception as e:
        logging.error(f"File Upload Error: {e}")
        return jsonify({'error': f"File upload failed: {str(e)}"}), 500


def get_mime_type(file_ext):
    """Get MIME type for file extension."""
    mime_types = {
        'mov': 'video/quicktime',
        'mp4': 'video/mp4',
        'webm': 'video/webm',
        'avi': 'video/x-msvideo',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'gif': 'image/gif',
        'heic': 'image/heic'
    }
    return mime_types.get(file_ext, 'application/octet-stream')


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    """Serve uploaded files from Azure Blob Storage or local filesystem"""
    file_ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mimetype = get_mime_type(file_ext)

    if USE_AZURE_STORAGE and blob_service_client:
        # Redirect to Azure Blob Storage URL
        try:
            blob_client = blob_service_client.get_blob_client(container=AZURE_CONTAINER_NAME, blob=filename)
            # Return redirect to blob URL (already public)
            return redirect(blob_client.url)
        except Exception as e:
            logging.error(f"Error serving file from Azure: {e}")
            return jsonify({'error': 'File not found'}), 404
    else:
        # Serve from local storage
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, mimetype=mimetype)


def encode_image_to_base64(image_path):
    """Convert an image to a base64 string."""
    try:
        with open(image_path, 'rb') as img_file:
            return base64.b64encode(img_file.read()).decode("utf-8")
    except Exception as e:
        logging.error(f"Failed to read image for base64 encoding: {image_path}, Error: {e}")
        return None


@app.route('/images')
def get_images():
    """Retrieve images and videos for display from Azure Blob Storage or local filesystem."""
    limit = int(request.args.get('limit', 10))
    offset = int(request.args.get('offset', 0))

    files = []

    if USE_AZURE_STORAGE and blob_service_client:
        # List blobs from Azure
        try:
            container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)
            blob_list = container_client.list_blobs()

            for blob in blob_list:
                file_ext = blob.name.rsplit(".", 1)[-1].lower() if "." in blob.name else ""
                if file_ext in ['png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi', 'webm']:
                    files.append({
                        'name': blob.name,
                        'last_modified': blob.last_modified
                    })

            # Sort by last modified (newest first)
            files.sort(key=lambda x: x['last_modified'], reverse=True)

        except Exception as e:
            logging.error(f"Error listing blobs: {e}")
            return jsonify({'images': [], 'total_images': 0})
    else:
        # List from local storage
        if not os.path.exists(UPLOAD_FOLDER):
            return jsonify({'images': [], 'total_images': 0})

        file_names = [
            f for f in os.listdir(UPLOAD_FOLDER)
            if os.path.isfile(os.path.join(UPLOAD_FOLDER, f)) and
            f.lower().endswith(('png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi', 'webm'))
        ]

        for file_name in file_names:
            file_path = os.path.join(UPLOAD_FOLDER, file_name)
            files.append({
                'name': file_name,
                'last_modified': os.path.getmtime(file_path)
            })

        # Sort by modification time (newest first)
        files.sort(key=lambda x: x['last_modified'], reverse=True)

    total_images = len(files)
    files_page = files[offset:offset + limit]

    file_data = []
    for file in files_page:
        file_name = file['name']
        file_ext = file_name.rsplit(".", 1)[-1].lower()
        is_video = file_ext in ['mp4', 'mov', 'avi', 'webm']

        file_data.append({
            'filename': file_name,
            'is_video': is_video,
            'type': file_ext
        })

    return jsonify({'images': file_data, 'total_images': total_images})


stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
if not stripe.api_key:
    raise ValueError("Stripe API key is missing! Set STRIPE_SECRET_KEY in environment variables.")

app.config['STRIPE_PUBLIC_KEY'] = os.environ.get('STRIPE_PUBLIC_KEY')
app.secret_key = secret_key

# Database initialization
DATABASE = 'reunion.db'


def get_db():
    """Get a database connection."""
    try:
        db = getattr(g, "_database", None)
        if db is None:
            db = g._database = sqlite3.connect(DATABASE, check_same_thread=False)
            db.row_factory = sqlite3.Row  # Enables dictionary-style row access
        return db
    except sqlite3.Error as e:
        logging.error(f"Database connection error: {e}")
        return None


def init_db():
    """Initialize database tables once at startup."""
    with sqlite3.connect(DATABASE) as db:
        db.execute(
            '''
            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                tshirt_size TEXT,
                age_group TEXT,
                price REAL,
                session_id TEXT,
                stripe_session_id TEXT
            )
            '''
        )

        # Add stripe_session_id column if missing
        try:
            db.execute("SELECT stripe_session_id FROM registrations LIMIT 1")
        except sqlite3.OperationalError:
            db.execute("ALTER TABLE registrations ADD COLUMN stripe_session_id TEXT")

        db.execute(
            '''
            CREATE TABLE IF NOT EXISTS rsvps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT NOT NULL,
                attending TEXT NOT NULL
            )
            '''
        )

        db.execute(
            '''
            CREATE TABLE IF NOT EXISTS birthdays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                birth_date TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )

        db.execute(
            '''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                event_date TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


# Helper function to calculate price
def calculate_price(age_group):
    return 75.00 if age_group == 'adult' else 25.00


@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        if not data or 'registrants' not in data:
            return jsonify({'error': 'Invalid data format'}), 400

        db = get_db()
        if db is None:
            return jsonify({'error': 'Database connection failed'}), 500

        # Generate a unique session ID
        session_id = str(uuid.uuid4())
        total_cost = 0

        # Start a transaction
        try:
            for registrant in data['registrants']:
                name = registrant.get('name')
                tshirt_size = registrant.get('tshirtSize')
                age_group = registrant.get('ageGroup')

                if not all([name, tshirt_size, age_group]):
                    return jsonify({'error': 'Missing required fields'}), 400

                price = calculate_price(age_group)
                total_cost += price

                db.execute(
                    'INSERT INTO registrations (name, tshirt_size, age_group, price, session_id) VALUES (?,?,?,?,?)',
                    (name, tshirt_size, age_group, price, session_id)
                )

            # Commit the transaction
            db.commit()

            # Store session_id in the Flask session
            session['current_session_id'] = session_id
            logging.info(f"Session ID set in Flask session: {session_id}")

            return jsonify({
                'message': 'Registration successful',
                'total_cost': total_cost,
                'session_id': session_id
            })

        except Exception as e:
            # Roll back the transaction if there's an error
            db.rollback()
            raise e

    except Exception as e:
        logging.error(f"❌ Registration Error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/admin')
def admin():
    try:
        db = get_db()
        if db is None:
            return jsonify({"error": "Database connection failed"}), 500

        # Fetch registrations
        registrations = db.execute('SELECT * FROM registrations').fetchall()
        print(f"🟢 Registrations Found: {len(registrations)}")  # Debugging output

        # Fetch RSVPs
        rsvps = db.execute('SELECT * FROM rsvps').fetchall()
        print(f"🟢 RSVPs Found: {len(rsvps)}")  # Debugging output

        # Fetch birthdays
        birthdays = db.execute('SELECT * FROM birthdays ORDER BY birth_date').fetchall()
        print(f"🟢 Birthdays Found: {len(birthdays)}")  # Debugging output

        # Fetch events
        events = db.execute('SELECT * FROM events ORDER BY event_date DESC').fetchall()
        print(f"🟢 Events Found: {len(events)}")  # Debugging output

        # Fetch images from Azure or local storage
        images = []
        if USE_AZURE_STORAGE and blob_service_client:
            try:
                container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)
                blob_list = container_client.list_blobs()
                images = [{"filename": blob.name} for blob in blob_list]
            except Exception as e:
                logging.error(f"Error listing blobs for admin: {e}")
        else:
            if os.path.exists(app.config["UPLOAD_FOLDER"]):
                images = [
                    {"filename": f} for f in os.listdir(app.config["UPLOAD_FOLDER"])
                    if os.path.isfile(os.path.join(app.config["UPLOAD_FOLDER"], f))
                ]
        print(f"🟢 Images Found: {len(images)}")  # Debugging output

        return render_template('admin.html',
                             registrations=registrations,
                             rsvps=rsvps,
                             birthdays=birthdays,
                             events=events,
                             images=images)

    except Exception as e:
        logging.error(f"❌ Admin Page Error: {e}")
        return jsonify({'error': 'Failed to load admin page'}), 500


@app.route('/view-admin')
def view_admin():
    try:
        db = get_db()
        if db is None:
            return jsonify({"error": "Database connection failed"}), 500

        # Fetch registrations
        registrations = db.execute('SELECT * FROM registrations').fetchall()
        logging.info(f"🟢 Registrations Found: {len(registrations)}")

        # Fetch RSVPs
        rsvps = db.execute('SELECT * FROM rsvps').fetchall()
        logging.info(f"🟢 RSVPs Found: {len(rsvps)}")

        # Fetch images from Azure or local storage
        images = []
        if USE_AZURE_STORAGE and blob_service_client:
            try:
                container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)
                blob_list = container_client.list_blobs()
                images = [{"filename": blob.name} for blob in blob_list]
            except Exception as e:
                logging.error(f"Error listing blobs for view-admin: {e}")
        else:
            if os.path.exists(app.config["UPLOAD_FOLDER"]):
                images = [
                    {"filename": f} for f in os.listdir(app.config["UPLOAD_FOLDER"])
                    if os.path.isfile(os.path.join(app.config["UPLOAD_FOLDER"], f))
        ]
        logging.info(f"🟢 Images Found: {len(images)}")

        return render_template('view_admin.html', registrations=registrations, rsvps=rsvps, images=images)

    except Exception as e:
        logging.error(f"❌ View Admin Page Error: {e}")
        return jsonify({'error': 'Failed to load view-only admin page'}), 500


@app.route("/check-session")
def check_session():
    session_id = session.get("current_session_id")
    logging.info(f"Checking session, current_session_id: {session_id}")

    if session_id:
        return jsonify({"message": "Session ID retrieved successfully", "session_id": session_id})
    else:
        return jsonify({"error": "No active session found"}), 400


@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    try:
        # Get the session ID from Flask session
        session_id = session.get('current_session_id')
        logging.info(f"Creating checkout with session ID: {session_id}")

        if not session_id:
            logging.error("No session ID found in Flask session")
            return jsonify({'error': 'No active session found. Please register again.'}), 400

        db = get_db()
        if db is None:
            return jsonify({'error': 'Database connection failed'}), 500

        # Fetch registrations for this session
        registrants = db.execute(
            'SELECT id, name, tshirt_size, age_group, price FROM registrations WHERE session_id = ?',
            (session_id,)
        ).fetchall()

        if not registrants:
            logging.error(f"No registrations found for session ID: {session_id}")
            return jsonify({'error': 'No valid registrations found for this session'}), 400

        line_items = []
        total_amount = 0

        for registrant in registrants:
            amount = int(registrant['price'] * 100)  # Convert to cents
            total_amount += amount
            line_items.append({
                'price_data': {
                    'currency': 'usd',
                    'unit_amount': amount,
                    'product_data': {'name': f"Family Reunion Registration - {registrant['name']}"},
                },
                'quantity': 1,
            })

        try:
            # Create Stripe checkout session
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=line_items,
                mode='payment',
                success_url=url_for('success', _external=True) + f'?session_id={session_id}',
                cancel_url=url_for('index', _external=True) + '?canceled=true',
            )

            logging.info(f"Stripe checkout session created: {checkout_session.id}")

            # Update database with Stripe session ID
            with db:
                db.execute(
                    'UPDATE registrations SET stripe_session_id = ? WHERE session_id = ?',
                    (checkout_session.id, session_id)
                )
                db.commit()

            return jsonify({'sessionId': checkout_session.id})

        except stripe.error.StripeError as e:
            logging.error(f"Stripe API Error: {e}")
            db.rollback()
            return jsonify({'error': f"Payment processing error: {str(e)}"}), 500

    except Exception as e:
        logging.error(f"❌ Checkout Session Error: {e}")
        if 'db' in locals() and db:
            db.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/rsvp', methods=['POST'])
def rsvp():
    try:
        data = request.get_json()
        name = data.get('name')
        email = data.get('email')
        phone = data.get('phone')  # Ensure phone number is collected
        attending = data.get('attending')

        if not all([name, email, phone, attending]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Save RSVP data to the database
        db = get_db()
        with db:
            db.execute(
                'INSERT INTO rsvps (name, email, phone, attending) VALUES (?, ?, ?, ?)',
                (name, email, phone, attending)
            )
            db.commit()

        print(f"✅ RSVP Saved: {name} | {email} | {phone} | Attending: {attending}")
        return jsonify({'success': True, 'message': 'RSVP successfully recorded'})

    except Exception as e:
        print(f"❌ RSVP Error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/attendees')
def get_attendees():
    try:
        db = get_db()

        # Fetch only attendees who RSVP'd with "Yes"
        attendees = db.execute(
            'SELECT name FROM rsvps WHERE LOWER(attending) = "yes"'
        ).fetchall()

        attendee_list = [attendee['name'] for attendee in attendees]

        if not attendee_list:
            return jsonify([])  # Return empty list if no attendees are found

        return jsonify(attendee_list)

    except Exception as e:
        print(f"Error fetching attendees: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/contact', methods=['POST'])
def contact():
    try:
        data = request.form
        name = data.get('name')
        email = data.get('email')
        message = data.get('message')

        if not all([name, email, message]):
            return jsonify({'error': 'Missing required fields'}), 400

        sender_email = os.getenv('MAIL_USERNAME')
        receiver_email = "milliganaiken@gmail.com"  # Replace with your recipient email
        password = os.getenv('MAIL_PASSWORD')

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = f"New Contact Form Submission from {name}"
        msg.attach(MIMEText(f"Name: {name}\nEmail: {email}\n\nMessage:\n{message}", 'plain'))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, msg.as_string())

        return jsonify({'success': True, 'message': 'Email sent successfully!'})

    except Exception as e:
        print(f"❌ Email Sending Error: {e}")
        return jsonify({'error': 'Failed to send email'}), 500


@app.route('/success')
def success():
    session_id = request.args.get('session_id')
    if not session_id:
        return redirect(url_for('index'))

    try:
        db = get_db()

        # First, get all registrations for this session
        registrations = db.execute(
            'SELECT id, name, tshirt_size, age_group, price FROM registrations WHERE session_id = ?',
            (session_id,)
        ).fetchall()

        if not registrations:
            logging.warning(f"No registrations found for session_id: {session_id}")
            return "No registration found for this session."

        # Get the Stripe session ID from the first registration (they should all have the same one)
        result = db.execute(
            'SELECT stripe_session_id FROM registrations WHERE session_id = ? LIMIT 1',
            (session_id,)
        ).fetchone()

        if not result or not result['stripe_session_id']:
            logging.warning(f"No Stripe session ID found for session_id: {session_id}")
            return "Payment information not found."

        stripe_session_id = result['stripe_session_id']

        try:
            # Retrieve the Stripe checkout session
            checkout_session = stripe.checkout.Session.retrieve(stripe_session_id)

            # Get the charge information if payment is paid
            latest_charge = None
            if checkout_session.payment_status == 'paid' and checkout_session.payment_intent:
                payment_intent = stripe.PaymentIntent.retrieve(checkout_session.payment_intent)
                # Check if latest_charge attribute exists before accessing it
                if hasattr(payment_intent, 'latest_charge') and payment_intent.latest_charge:
                    latest_charge = stripe.Charge.retrieve(payment_intent.latest_charge)

            # Calculate total paid
            total_paid = sum(reg['price'] for reg in registrations)

            logging.info(f"✅ Payment completed for session ID: {session_id}, Status: {checkout_session.payment_status}")

            return render_template(
                'success.html',
                checkout_session=checkout_session,
                total_paid=total_paid,
                registrations=registrations,
                latest_charge=latest_charge
            )

        except stripe.error.StripeError as e:
            logging.error(f"⚠️ Stripe error in success route: {e}")
            return f"An error occurred while retrieving payment information: {str(e)}"

    except Exception as e:
        logging.error(f"⚠️ Error in success route: {str(e)}")
        return "An error occurred while retrieving registration information."


@app.route('/set-session', methods=['GET'])
def set_session():
    """Set a session variable to test Flask-Session"""
    session_id = str(uuid.uuid4())
    session['current_session_id'] = session_id
    return jsonify({"message": "Session ID set", "session_id": session_id})


@app.route('/delete_registration/<int:registration_id>', methods=['DELETE'])
def delete_registration(registration_id):
    try:
        db = get_db()
        db.execute('DELETE FROM registrations WHERE id = ?', (registration_id,))
        db.commit()
        return jsonify({'success': True, 'message': 'Registration deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/delete_rsvp/<int:rsvp_id>', methods=['DELETE'])
def delete_rsvp(rsvp_id):
    try:
        db = get_db()
        db.execute('DELETE FROM rsvps WHERE id = ?', (rsvp_id,))
        db.commit()
        return jsonify({'success': True, 'message': 'RSVP deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/delete_image/<filename>', methods=['DELETE'])
def delete_image(filename):
    try:
        if USE_AZURE_STORAGE and blob_service_client:
            # Delete from Azure Blob Storage
            blob_client = blob_service_client.get_blob_client(container=AZURE_CONTAINER_NAME, blob=filename)
            blob_client.delete_blob()
            logging.info(f"Deleted blob from Azure: {filename}")
            return jsonify({'success': True, 'message': 'Image deleted successfully'})
        else:
            # Delete from local storage
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(image_path):
                os.remove(image_path)
                return jsonify({'success': True, 'message': 'Image deleted successfully'})
            else:
                return jsonify({'success': False, 'error': 'File not found'}), 404
    except Exception as e:
        logging.error(f"Error deleting file: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# Birthday Routes
@app.route('/birthdays', methods=['GET'])
def get_birthdays():
    try:
        db = get_db()
        birthdays = db.execute('SELECT * FROM birthdays ORDER BY birth_date').fetchall()
        birthday_list = [{'id': b['id'], 'name': b['name'], 'birth_date': b['birth_date']} for b in birthdays]
        return jsonify(birthday_list)
    except Exception as e:
        logging.error(f"Error fetching birthdays: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/birthdays', methods=['POST'])
def add_birthday():
    try:
        data = request.get_json()
        name = data.get('name')
        birth_date = data.get('date')

        if not all([name, birth_date]):
            return jsonify({'error': 'Missing required fields'}), 400

        db = get_db()
        with db:
            db.execute(
                'INSERT INTO birthdays (name, birth_date) VALUES (?, ?)',
                (name, birth_date)
            )
            db.commit()

        return jsonify({'success': True, 'message': 'Birthday added successfully'})
    except Exception as e:
        logging.error(f"Error adding birthday: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/delete_birthday/<int:birthday_id>', methods=['DELETE'])
def delete_birthday(birthday_id):
    try:
        db = get_db()
        db.execute('DELETE FROM birthdays WHERE id = ?', (birthday_id,))
        db.commit()
        return jsonify({'success': True, 'message': 'Birthday deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# Event Routes
@app.route('/events', methods=['GET'])
def get_events():
    try:
        db = get_db()
        events = db.execute('SELECT * FROM events ORDER BY event_date DESC').fetchall()
        event_list = [{'id': e['id'], 'title': e['title'], 'event_date': e['event_date'], 'description': e['description']} for e in events]
        return jsonify(event_list)
    except Exception as e:
        logging.error(f"Error fetching events: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/events', methods=['POST'])
def add_event():
    try:
        data = request.get_json()
        title = data.get('title')
        event_date = data.get('date')
        description = data.get('description')

        if not all([title, event_date, description]):
            return jsonify({'error': 'Missing required fields'}), 400

        db = get_db()
        with db:
            db.execute(
                'INSERT INTO events (title, event_date, description) VALUES (?, ?, ?)',
                (title, event_date, description)
            )
            db.commit()

        return jsonify({'success': True, 'message': 'Event added successfully'})
    except Exception as e:
        logging.error(f"Error adding event: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/delete_event/<int:event_id>', methods=['DELETE'])
def delete_event(event_id):
    try:
        db = get_db()
        db.execute('DELETE FROM events WHERE id = ?', (event_id,))
        db.commit()
        return jsonify({'success': True, 'message': 'Event deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# Error handler for file size limit
@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    logging.error("File too large error")
    return jsonify({'error': 'File too large. Maximum size is 100MB.'}), 413

# Temporary diagnostic endpoints - remove after migration
@app.route('/debug/list-local-files')
def list_local_files():
    """Temporary endpoint to list files in local uploads folder on server"""
    try:
        local_files = []
        if os.path.exists(UPLOAD_FOLDER):
            for f in os.listdir(UPLOAD_FOLDER):
                file_path = os.path.join(UPLOAD_FOLDER, f)
                if os.path.isfile(file_path):
                    local_files.append({
                        'name': f,
                        'size': os.path.getsize(file_path)
                    })
        return jsonify({
            'total_local_files': len(local_files),
            'files': local_files,
            'path': os.path.abspath(UPLOAD_FOLDER)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/debug/serve-local/<filename>')
def serve_local_file(filename):
    """Temporary endpoint to serve files directly from local storage (bypass Azure)"""
    try:
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found on local storage'}), 404

        file_ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        mimetype = get_mime_type(file_ext)
        return send_from_directory(UPLOAD_FOLDER, filename, mimetype=mimetype)
    except Exception as e:
        logging.error(f"Error serving local file: {e}")
        return jsonify({'error': str(e)}), 500


# Initialize the database at startup **force**
init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
