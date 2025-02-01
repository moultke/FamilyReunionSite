from flask import Flask, render_template, request, jsonify, redirect, url_for, g, session, send_from_directory
import sqlite3
import os
import stripe
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

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
app.secret_key = "your_secret_key_here"  # Required for session management

print(f"Stripe Secret Key: {os.environ.get('STRIPE_SECRET_KEY')}")
print(f"Stripe Public Key: {app.config['STRIPE_PUBLIC_KEY']}")

# Database initialization
DATABASE = 'reunion.db'


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db():
    """Get a database connection."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE, check_same_thread=False)
        db.row_factory = sqlite3.Row  # Allow accessing columns by name
        db.execute(
            '''
            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                tshirt_size TEXT,
                age_group TEXT,
                price REAL
            )
            '''
        )
        db.commit()  # Ensure table creation is saved
    return db


@app.teardown_appcontext
def close_connection(exception):
    """Close database connection after request."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


# Helper function to calculate price
def calculate_price(age_group):
    return 125.00 if age_group == 'adult' else 50.00


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return jsonify({'message': 'File uploaded successfully', 'filename': filename}), 200

    return jsonify({'error': 'Invalid file type'}), 400


@app.route('/images')
def get_images():
    images = os.listdir(UPLOAD_FOLDER)
    image_urls = [url_for('uploaded_file', filename=image) for image in images]
    return jsonify({'images': image_urls})


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/register', methods=['POST'])
def register():
    """Handle registration and save to database."""
    try:
        data = request.get_json()
        if not data or 'registrants' not in data:
            return jsonify({'error': 'Invalid data format'}), 400

        db = get_db()
        total_cost = 0
        registrations = []

        print("✅ Received Registration Data:", data)  # Debugging

        for registrant in data['registrants']:
            name = registrant.get('name')
            tshirt_size = registrant.get('tshirtSize')
            age_group = registrant.get('ageGroup')

            if not all([name, tshirt_size, age_group]):
                return jsonify({'error': 'Missing required fields'}), 400

            price = calculate_price(age_group)
            total_cost += price

            db.execute(
                'INSERT INTO registrations (name, tshirt_size, age_group, price) VALUES (?, ?, ?, ?)',
                (name, tshirt_size, age_group, price)
            )

            registrations.append({'name': name, 'tshirt_size': tshirt_size, 'age_group': age_group, 'price': price})

        db.commit()  # Save all changes

        print("✅ Data Successfully Saved to Database")  # Debugging

        # Retrieve and print stored records for verification
        cursor = db.execute('SELECT * FROM registrations')
        stored_data = cursor.fetchall()
        print("✅ Stored Data:", stored_data)  # Debugging

        return jsonify({'message': 'Registration successful', 'total_cost': total_cost, 'registrations': registrations})

    except Exception as e:
        print(f"❌ Registration Error: {e}")  # Debugging
        return jsonify({'error': str(e)}), 500


@app.route('/admin')
def admin():
    """Admin panel to view registrations."""
    try:
        db = get_db()

        # Fetch all registrations
        cursor = db.execute('SELECT id, name, tshirt_size, age_group, price FROM registrations')
        registrations = cursor.fetchall()

        print("✅ Admin Page Registrations:", registrations)  # Debugging

        return render_template('admin.html', registrations=registrations)

    except Exception as e:
        print(f"❌ Admin Page Error: {e}")
        return jsonify({'error': 'Failed to load admin page'}), 500


@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    """Create Stripe checkout session."""
    try:
        db = get_db()
        cursor = db.execute('SELECT name, tshirt_size, age_group, price FROM registrations')
        rows = cursor.fetchall()

        registrations = [{'name': row[0], 'tshirt_size': row[1], 'age_group': row[2], 'price': row[3]} for row in rows]
        total_cost = sum(row[3] for row in rows)

        if not registrations:
            return jsonify({'error': 'No registrations found'}), 404

        print("✅ Stripe Checkout Data:", registrations)

        # Store payment details in session before proceeding to checkout
        session['payment_details'] = {
            'registrations': registrations,
            'total_paid': total_cost
        }

        line_items = [
            {
                'price_data': {
                    'currency': 'usd',
                    'product_data': {'name': f"{reg['name']} - {reg['age_group']} ({reg['tshirt_size']})"},
                    'unit_amount': int(reg['price'] * 100),
                },
                'quantity': 1,
            }
            for reg in registrations
        ]

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=url_for('success', _external=True),
            cancel_url=url_for('index', _external=True),
        )

        print(f"✅ Stripe Session Created: {checkout_session.id}")

        # 🔴 **Remove this line to keep data in the database**
        # db.execute('DELETE FROM registrations')
        # db.commit()

        return jsonify({'id': checkout_session.id})

    except Exception as e:
        print(f"❌ Stripe API Error: {e}")
        return jsonify({'error': str(e)}), 500



@app.route('/success')
def success():
    """Display success page after payment."""
    payment_details = session.get('payment_details', {'registrations': [], 'total_paid': 0})
    return render_template('success.html', payment_details=payment_details)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
