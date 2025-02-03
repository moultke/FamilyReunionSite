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

secret_key = secrets.token_hex(32)

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Load environment variables
load_dotenv()

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
app.config['STRIPE_PUBLIC_KEY'] = os.environ.get('STRIPE_PUBLIC_KEY')
app.secret_key = secret_key

# Database initialization
DATABASE = 'reunion.db'


def get_db():
    """Get a database connection."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE, check_same_thread=False)  # Corrected: removed extra space
        db.row_factory = sqlite3.Row

        with db:  # Use a single 'with db:' block for ALL database operations
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

            # Add the stripe_session_id column if it doesn't exist (idempotent)
            try:
                db.execute("SELECT stripe_session_id FROM registrations LIMIT 1")
            except sqlite3.OperationalError:
                db.execute("ALTER TABLE registrations ADD COLUMN stripe_session_id TEXT")

            # Create the RSVPs table (INSIDE the 'with db:' block)
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

    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


# Helper function to calculate price
def calculate_price(age_group):
    return 125.00 if age_group == 'adult' else 50.00


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        if not data or 'registrants' not in data:
            return jsonify({'error': 'Invalid data format'}), 400

        db = get_db()
        session_id = str(uuid.uuid4())
        total_cost = 0

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

        db.commit()
        session['current_session_id'] = session_id
        return jsonify({'message': 'Registration successful', 'total_cost': total_cost, 'session_id': session_id})

    except Exception as e:
        print(f"❌ Registration Error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/admin')
def admin():
    try:
        db = get_db()
        registrations = db.execute('SELECT id, name, tshirt_size, age_group, price FROM registrations').fetchall()
        return render_template('admin.html', registrations=registrations)

    except Exception as e:
        print(f"❌ Admin Page Error: {e}")
        return jsonify({'error': 'Failed to load admin page'}), 500


@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    try:
        db = get_db()
        session_id = session.get('current_session_id')
        if not session_id:
            return jsonify({'error': 'No active session found'}), 400

        registrants = db.execute('SELECT name, tshirt_size, age_group, price FROM registrations WHERE session_id =?', (session_id,)).fetchall()
        if not registrants:
            return jsonify({'error': 'No valid registrations for this session'}), 400

        line_items =  [] # Initialize line_items to an empty list
        total_amount = 0

        for registrant in registrants:
            amount = int(registrant['price'] * 100)
            total_amount += amount
            line_items.append({
                'price_data': {
                    'currency': 'usd',
                    'unit_amount': amount,
                    'product_data': {'name': f'Reunion Registration - {registrant["name"]}'},
                },
                'quantity': 1,
            })

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=url_for('success', _external=True) + f'?session_id={session_id}',
            cancel_url=url_for('index', _external=True) + '?canceled=true',
        )

        print(f"Checkout Session ID (Create): {checkout_session.id}")  # Debug print

        with db:  # Use context manager for the database transaction
            # Original (Incorrect - stores session_id/UUID in stripe_session_id):
            # db.execute('UPDATE registrations SET stripe_session_id =? WHERE session_id =?', (session_id, session_id))

            # Corrected (Stores Stripe Checkout Session ID in stripe_session_id):
            db.execute('UPDATE registrations SET stripe_session_id =? WHERE session_id =?', (checkout_session.id, session_id))  # Corrected line

            db.commit()

        return jsonify({'sessionId': checkout_session.id})

    except Exception as e:
        print(f"❌ Checkout Session Error: {e}")
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


# Example function (replace with your actual database/storage logic)
def get_attendee_names():
    # Replace this with your actual database query or file reading logic.
    # This is just placeholder data.
    return ["John Doe", "Jane Smith", "Peter Jones"]

# Add this route to serve uploaded files
@app.route('/static/uploads/<filename>')  # Correct path for serving images
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename) # Use send_from_directory


@app.route('/images')
def get_images():
    limit = int(request.args.get('limit', 10))  # Default limit to 10
    offset = int(request.args.get('offset', 0))  # Default offset to 0

    # Example using file system (adapt to your needs):
    images = [
        f for f in os.listdir(UPLOAD_FOLDER)
        if os.path.isfile(os.path.join(UPLOAD_FOLDER, f)) and f.lower().endswith(('png', 'jpg', 'jpeg', 'gif'))
    ]
    total_images = len(images)

    images_page = images[offset:offset + limit]  # Get images for the current page
    image_urls = [url_for('uploaded_file', filename=image) for image in images_page]

    return jsonify({'images': image_urls, 'total_images': total_images})


@app.route('/upload-image', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file and file.filename.split('.')[-1].lower() in ALLOWED_EXTENSIONS:
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        return jsonify({'success': True, 'image_url': url_for('uploaded_file', filename=filename)})

    return jsonify({'error': 'Invalid file format'}), 400


@app.route('/success')
def success():
    session_id = request.args.get('session_id')

    if not session_id:
        return redirect(url_for('index'))

    try:
        db = get_db()

        # Retrieve stripe_session_id from DB
        result = db.execute(
            'SELECT stripe_session_id FROM registrations WHERE session_id =?', (session_id,)
        ).fetchone()

        if result is None:
            print(f"⚠️ No registration found for session_id: {session_id}")
            return "No registration found for this session."

        stripe_session_id = result['stripe_session_id']

        # Retrieve checkout session from Stripe
        checkout_session = stripe.checkout.Session.retrieve(stripe_session_id)

        # Retrieve the Payment Intent
        payment_intent_id = checkout_session.payment_intent
        if not payment_intent_id:
            print("⚠️ No Payment Intent found in checkout session")
            return "No payment intent found for this session."

        print(f"✅ Payment Intent ID: {payment_intent_id}")

        # Fetch Payment Intent
        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)

        # Print statement
        print(f"Payment Intent Status: {payment_intent.status}")

        # Ensure payment was successful
        if payment_intent.status != "succeeded":
            print(f"⚠️ Payment Intent Status: {payment_intent.status}")
            return f"Payment is still processing. Current status: {payment_intent.status}"

        # Retrieve the latest charge ID
        charge_id = payment_intent.latest_charge
        if not charge_id:
            print(f"⚠️ No charge found for Payment Intent ID: {payment_intent_id}")
            return "No charge associated with this payment."

        # Retrieve the Charge object
        latest_charge = stripe.Charge.retrieve(charge_id)

        # Debug: Print charge object
        print(f"Full Charge Object: {latest_charge}")

        # Retrieve registrations from database
        registrations = db.execute(
            'SELECT name, tshirt_size, age_group, price FROM registrations WHERE session_id =?',
            (session_id,)
        ).fetchall()

        if not registrations:
            print(f"⚠️ No registrations found for session_id: {session_id}")
            return "No registration found for this session."

        total_paid = sum(r['price'] for r in registrations)

        return render_template(
            'success.html',
            registrations=registrations,
            total_paid=total_paid,
            checkout_session=checkout_session,
            payment_intent=payment_intent,
            latest_charge=latest_charge  # Pass charge object
        )

    except stripe.error.StripeError as e:
        print(f"⚠️ Stripe Error: {e}")
        return f"A Stripe error occurred: {e}"

    except Exception as e:
        print(f"⚠️ Error fetching registration data: {e}")
        return "An error occurred."




if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)