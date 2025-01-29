from flask import Flask, render_template, request, jsonify, redirect, url_for, g, send_from_directory
import sqlite3
import time
import os
from datetime import datetime
import stripe
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Configure Stripe (replace with your actual keys)
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
app.config['STRIPE_PUBLIC_KEY'] = os.environ.get('STRIPE_PUBLIC_KEY')

# Database initialization
DATABASE = 'reunion.db'


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
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
        # Create the images table if it doesn't exist
        db.execute(
            '''
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filepath TEXT NOT NULL
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
    if age_group == 'adult':
        return 50.00  # Example price - adjust as needed
    else:
        return 25.00  # Example price - adjust as needed


# Configure upload folder
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size


# Function to check allowed file extensions
def allowed_file(filename):
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    )


# Routes
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['POST'])
def register():
    registrations = []
    total_cost = 0

    data = request.get_json()
    if not data or 'registrants' not in data:
        return jsonify({'error': 'Invalid data format'}), 400

    for registrant in data['registrants']:
        name = registrant.get('name')
        tshirt_size = registrant.get('tshirtSize')
        age_group = registrant.get('ageGroup')

        if not all([name, tshirt_size, age_group]):
            return jsonify({'error': 'Missing required fields'}), 400

        price = calculate_price(age_group)
        total_cost += price
        registrations.append(
            {
                'name': name,
                'tshirt_size': tshirt_size,
                'age_group': age_group,
                'price': price,
            }
        )

    # Insert into database
    db = get_db()
    for reg in registrations:
        try:
            db.execute(
                'INSERT INTO registrations (name, tshirt_size, age_group, price) VALUES (?, ?, ?, ?)',
                (reg['name'], reg['tshirt_size'], reg['age_group'], reg['price']),
            )
        except Exception as e:
            db.rollback()
            return jsonify({'error': str(e)}), 500

    db.commit()

    return jsonify(
        {'message': 'Registration successful', 'total_cost': total_cost}
    )


@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    registrations = []
    total_cost = 0

    # Fetch registration data from the database
    db = get_db()
    cursor = db.execute(
        'SELECT name, tshirt_size, age_group, price FROM registrations'
    )
    rows = cursor.fetchall()

    for row in rows:
        registrations.append(
            {
                'name': row[0],
                'tshirt_size': row[1],
                'age_group': row[2],
                'price': row[3],
            }
        )
        total_cost += row[3]

    if not registrations:
        return jsonify({'error': 'No registrations found'}), 404

    # Format for Stripe
    line_items = []
    for reg in registrations:
        line_items.append(
            {
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f"{reg['name']} - {reg['age_group']} ({reg['tshirt_size']})",
                    },
                    'unit_amount': int(reg['price'] * 100),  # Amount in cents
                },
                'quantity': 1,
            }
        )

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=url_for('success', _external=True),
            cancel_url=url_for('index', _external=True),
        )
        # Clear the database after creating a session (optional)
        db.execute('DELETE FROM registrations')
        db.commit()

        return jsonify({'id': checkout_session.id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/success')
def success():
    return render_template('success.html')


@app.route('/volunteer', methods=['POST'])
def volunteer():
    name = request.form.get('name')
    email = request.form.get('email')

    # Basic validation (you should do more robust validation)
    if not name or not email:
        return jsonify({'message': 'Name and email are required!'}), 400

    # Store in database or send an email, etc.
    # ...

    return jsonify({'message': 'Thank you for volunteering!'})


@app.route('/contact', methods=['POST'])
def contact():
    name = request.form.get('name')
    email = request.form.get('email')
    message = request.form.get('message')

    # Basic validation
    if not name or not email or not message:
        return jsonify({'message': 'All fields are required!'}), 400

    # Send email or store in database
    # ...

    return jsonify({'message': 'Message sent successfully!'})


# Route to handle image uploads
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # Ensure directory exists
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

        file.save(filepath)

        # Construct URL for the uploaded file
        file_url = url_for('static', filename=f'uploads/{filename}')

        # Store file path in database ( with the correct path)
        db = get_db()
        try:
            db.execute('INSERT INTO images (filepath) VALUES (?)', (file_url,))
            db.commit()
        except Exception as e:
            db.rollback()
            return jsonify({'error': 'Failed to save image path to database'}), 500

        return jsonify(
            {'message': 'File uploaded successfully', 'url': file_url}
        )
    else:
        return jsonify({'error': 'File type not allowed'}), 400


# Route to delete an image
@app.route('/delete', methods=['DELETE'])
def delete_file():
    data = request.get_json()
    print(f"Request data: {data}")  # Print the received data

    if not data or 'filepath' not in data:
        return jsonify({'error': 'Invalid data format'}), 400

    filepath = data['filepath']

    # Extract filename, file_path and db_path from filepath
    filename = filepath.split('/')[-1]
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    db_path = url_for('static', filename=f'uploads/{filename}')

    print(f"Filename: {filename}")  # Print extracted filename
    print(f"File path: {file_path}")  # Print file path
    print(f"DB path: {db_path}")  # Print db path

    if os.path.exists(file_path):
        # Delete from database
        db = get_db()
        try:
            db.execute("DELETE FROM images WHERE filepath = ?", (db_path,))
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"Error deleting from database: {e}")  # Print the error
            return jsonify({'error': 'Failed to delete image from database'}), 500

        # Delete the file
        os.remove(file_path)
        return jsonify({'message': 'File deleted successfully'})
    else:
        return jsonify({'error': 'File not found'}), 404


# New route for admin page
@app.route('/admin')
def admin():
    db = get_db()
    cursor = db.execute('SELECT * FROM images')
    images = cursor.fetchall()
    return render_template('admin.html', images=images)


if __name__ == '__main__':
    app.run(debug=True)
