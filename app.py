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
import cv2
import numpy as np
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask_session import Session
import os
import platform

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'heic'}

# Load environment variables
load_dotenv()

# Check if running on Linux before executing apt-get
if platform.system() == "Linux":
    os.system("apt-get update && apt-get install -y libgl1")

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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
    """Convert HEIC to JPG using ImageMagick or OpenCV fallback."""
    jpg_filepath = filepath.rsplit(".", 1)[0] + ".jpg"

    # Check if ImageMagick is installed
    if subprocess.run(["which", "magick"], capture_output=True).returncode == 0:
        try:
            subprocess.run(["magick", filepath, jpg_filepath], check=True)
            os.remove(filepath)  # Delete the original HEIC file
            return jpg_filepath
        except subprocess.CalledProcessError:
            logging.warning("ImageMagick conversion failed, attempting OpenCV.")

    # OpenCV Fallback
    try:
        img = cv2.imread(filepath, cv2.IMREAD_COLOR)
        if img is None:
            logging.error(f"Error loading HEIC image {filepath}")
            return None  # Avoid corrupt images

        cv2.imwrite(jpg_filepath, img)
        os.remove(filepath)  # Delete original HEIC file
        return jpg_filepath
    except Exception as e:
        logging.error(f"Error converting HEIC to JPG with OpenCV: {e}")
        return None


@app.route("/upload-image", methods=["POST"])
def upload_image():
    """Handles file uploads, ensuring correct processing and preventing overwrites."""
    if 'image' not in request.files:
        logging.warning("No file part in request")
        return jsonify({'error': 'No file part'}), 400

    file = request.files['image']
    if file.filename == '':
        logging.warning("No selected file")
        return jsonify({'error': 'No selected file'}), 400

    # Generate a unique filename to prevent overwriting
    file_ext = file.filename.rsplit(".", 1)[-1].lower()
    filename = f"{uuid.uuid4().hex}.{file_ext}"
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    try:
        file.save(file_path)  # Save the uploaded file before processing

        if file_ext == 'heic':
            converted_path = convert_heic_to_jpg(file_path)
            if converted_path:
                filename = os.path.basename(converted_path)
                file_path = converted_path
            else:
                logging.error("HEIC conversion failed")
                return jsonify({'error': 'HEIC conversion failed'}), 500
        else:
            # OpenCV Processing: Read Image from File Stream Correctly
            file.stream.seek(0)  # Ensure file is read from start
            npimg = np.frombuffer(file.stream.read(), np.uint8)  # Convert file to NumPy array
            img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)  # Decode image data

            if img is None:
                logging.error(f"Invalid image format: {filename}")
                os.remove(file_path)  # ✅ Ensure bad file is deleted
                return jsonify({'error': 'Invalid image format or corrupted file'}), 400

            cv2.imwrite(file_path, img)

        logging.info(f"File successfully uploaded: {filename}")
        return jsonify({'success': True, 'image_url': url_for('uploaded_file', filename=filename)})

    except Exception as e:
        logging.error(f"File Upload Error: {e}")
        return jsonify({'error': f"File upload failed: {str(e)}"}), 500


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


def encode_image_to_base64(image_path):
    """Convert an image to a base64 string using OpenCV."""
    img = cv2.imread(image_path)
    if img is None:
        logging.error(f"Failed to read image for base64 encoding: {image_path}")
        return None

    file_ext = image_path.rsplit(".", 1)[-1].lower()
    valid_extensions = {'png', 'jpg', 'jpeg', 'gif'}

    if file_ext not in valid_extensions:
        logging.error(f"Unsupported image format for base64 encoding: {file_ext}")
        return None

    _, buffer = cv2.imencode(f".{file_ext}", img)
    return base64.b64encode(buffer).decode("utf-8")


@app.route('/images')
def get_images():
    """Retrieve images and return base64 encoded versions for display."""
    limit = int(request.args.get('limit', 10))
    offset = int(request.args.get('offset', 0))

    if not os.path.exists(UPLOAD_FOLDER):
        return jsonify({'images': [], 'total_images': 0})

    images = [
        f for f in os.listdir(UPLOAD_FOLDER)
        if os.path.isfile(os.path.join(UPLOAD_FOLDER, f)) and f.lower().endswith(('png', 'jpg', 'jpeg', 'gif'))
    ]
    total_images = len(images)
    images_page = images[offset:offset + limit]

    image_data = []
    for image in images_page:
        image_path = os.path.join(UPLOAD_FOLDER, image)
        base64_image = encode_image_to_base64(image_path)

        if base64_image:
            image_data.append({
                'filename': image,
                'data': f'data:image/{image_path.rsplit(".", 1)[-1]};base64,{base64_image}'
            })

    return jsonify({'images': image_data, 'total_images': total_images})


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

        # Fetch images
        images = [
            {"filename": f} for f in os.listdir(app.config["UPLOAD_FOLDER"])
            if os.path.isfile(os.path.join(app.config["UPLOAD_FOLDER"], f))
        ]
        print(f"🟢 Images Found: {len(images)}")  # Debugging output

        return render_template('admin.html', registrations=registrations, rsvps=rsvps, images=images)

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

        # Fetch images
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
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(image_path):
            os.remove(image_path)
            return jsonify({'success': True, 'message': 'Image deleted successfully'})
        else:
            return jsonify({'success': False, 'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# Initialize the database at startup
init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
