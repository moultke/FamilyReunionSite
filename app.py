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
import platform
from azure.storage.blob import BlobServiceClient, ContentSettings
from io import BytesIO

# PostgreSQL support
try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'heic', 'mp4', 'mov', 'avi', 'webm'}

# Load environment variablesss
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
    try:
        db = get_db()
        hero_slides = db.execute('SELECT * FROM hero_slides WHERE active = 1 ORDER BY display_order').fetchall()
        return render_template('index.html', config=app.config, hero_slides=hero_slides)
    except Exception as e:
        logging.error(f"Index route error: {e}")
        return f"Error loading page: {e}", 500


@app.route('/family-tree')
def family_tree():
    return render_template('family_tree.html')


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
DATABASE_URL = os.getenv('DATABASE_URL')
USE_POSTGRES = bool(DATABASE_URL) and HAS_PSYCOPG2


class DatabaseWrapper:
    """Unified database wrapper that works with both SQLite and PostgreSQL.

    Provides a consistent interface so all route code can use db.execute()
    and db.fetchall() / db.fetchone() regardless of backend.
    SQL uses '?' placeholders which are auto-converted to '%s' for PostgreSQL.
    """

    def __init__(self, connection, is_postgres=False):
        self._conn = connection
        self._cursor = None
        self._is_postgres = is_postgres

    def _convert_query(self, query):
        """Convert SQLite-style '?' placeholders to PostgreSQL '%s'."""
        if self._is_postgres:
            return query.replace('?', '%s')
        return query

    def execute(self, query, params=None):
        """Execute a query. Returns self for chaining."""
        converted = self._convert_query(query)
        if self._is_postgres:
            self._cursor = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            self._cursor.execute(converted, params or ())
        else:
            self._cursor = self._conn.execute(converted, params or ())
        return self

    def fetchall(self):
        """Fetch all results from the last query."""
        if self._cursor is None:
            return []
        rows = self._cursor.fetchall()
        if self._is_postgres:
            # RealDictCursor returns RealDictRow objects which already support ['key'] access
            return rows
        return rows

    def fetchone(self):
        """Fetch one result from the last query."""
        if self._cursor is None:
            return None
        row = self._cursor.fetchone()
        return row

    @property
    def lastrowid(self):
        """Get the last inserted row ID."""
        if self._is_postgres:
            # For PostgreSQL, the INSERT must use RETURNING id
            # This is handled by using RETURNING in the query
            return self._cursor.fetchone()['id'] if self._cursor else None
        return self._cursor.lastrowid if self._cursor else None

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._conn.rollback()
        return False


def get_db():
    """Get a database connection (PostgreSQL if configured, SQLite otherwise).

    Never falls back from PostgreSQL to SQLite to prevent data loss.
    If PostgreSQL is configured but unreachable, raises the error so
    routes can return a proper 503 to the user.
    """
    db = getattr(g, "_database", None)
    if db is None:
        if USE_POSTGRES:
            conn = psycopg2.connect(DATABASE_URL, sslmode='require')
            conn.autocommit = False
            db = g._database = DatabaseWrapper(conn, is_postgres=True)
            logging.debug("Connected to PostgreSQL")
        else:
            conn = sqlite3.connect(DATABASE, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            db = g._database = DatabaseWrapper(conn, is_postgres=False)
            logging.debug("Connected to SQLite")
    return db


def _pg_column_exists(cursor, table, column):
    """Check if a column exists in a PostgreSQL table."""
    cursor.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
        (table, column)
    )
    return cursor.fetchone() is not None


def init_db():
    """Initialize database tables once at startup.

    If PostgreSQL is configured, retries the connection up to 3 times
    before giving up. Never falls back to SQLite in production to
    prevent data loss from split-brain databases.
    """
    if USE_POSTGRES:
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                _init_db_postgres()
                return
            except Exception as e:
                logging.error(f"PostgreSQL init attempt {attempt}/{max_retries} failed: {e}")
                if attempt < max_retries:
                    import time as _time
                    _time.sleep(2 * attempt)  # backoff: 2s, 4s
                else:
                    logging.warning(
                        "All PostgreSQL connection attempts failed. "
                        "The app will start but database operations will retry on each request."
                    )
    else:
        _init_db_sqlite()


def _init_db_postgres():
    """Initialize PostgreSQL database tables."""
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    try:
        with conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS registrations (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    tshirt_size TEXT,
                    age_group TEXT,
                    price REAL,
                    session_id TEXT,
                    stripe_session_id TEXT
                )
            ''')

            if not _pg_column_exists(cur, 'registrations', 'stripe_session_id'):
                cur.execute("ALTER TABLE registrations ADD COLUMN stripe_session_id TEXT")

            cur.execute('''
                CREATE TABLE IF NOT EXISTS rsvps (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    attending TEXT NOT NULL
                )
            ''')

            cur.execute('''
                CREATE TABLE IF NOT EXISTS birthdays (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    birth_date TEXT NOT NULL,
                    birth_year INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            if not _pg_column_exists(cur, 'birthdays', 'birth_year'):
                cur.execute("ALTER TABLE birthdays ADD COLUMN birth_year INTEGER")

            cur.execute('''
                CREATE TABLE IF NOT EXISTS events (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    event_date TEXT NOT NULL,
                    description TEXT,
                    image_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            if not _pg_column_exists(cur, 'events', 'image_url'):
                cur.execute("ALTER TABLE events ADD COLUMN image_url TEXT")

            cur.execute('''
                CREATE TABLE IF NOT EXISTS comments (
                    id SERIAL PRIMARY KEY,
                    item_type TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    commenter_name TEXT NOT NULL,
                    comment_text TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cur.execute('''
                CREATE TABLE IF NOT EXISTS reactions (
                    id SERIAL PRIMARY KEY,
                    item_type TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    reactor_name TEXT NOT NULL,
                    reaction_type TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(item_type, item_id, reactor_name, reaction_type)
                )
            ''')

            cur.execute('''
                CREATE TABLE IF NOT EXISTS hero_slides (
                    id SERIAL PRIMARY KEY,
                    image_url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    caption TEXT,
                    display_order INTEGER NOT NULL DEFAULT 0,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cur.execute('''
                CREATE TABLE IF NOT EXISTS contacts (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Insert default hero slides if table is empty
            cur.execute('SELECT COUNT(*) FROM hero_slides')
            count = cur.fetchone()[0]
            if count == 0:
                default_slides = [
                    ('static/images/family1.jpg', 'Staying Connected', 'Share your moments with family!', 1),
                    ('static/images/family2.jpg', 'Celebrate Together', 'Every milestone matters.', 2),
                    ('static/images/family3.jpg', 'Family First', 'Always and forever.', 3),
                    ('static/images/family4.jpg', 'Making Memories', 'One moment at a time.', 4)
                ]
                for image_url, title, caption, order in default_slides:
                    cur.execute(
                        'INSERT INTO hero_slides (image_url, title, caption, display_order) VALUES (%s, %s, %s, %s)',
                        (image_url, title, caption, order)
                    )

        conn.commit()
        logging.info("PostgreSQL database initialized successfully")
    except Exception as e:
        conn.rollback()
        logging.error(f"PostgreSQL initialization error: {e}")
        raise
    finally:
        conn.close()


def _init_db_sqlite():
    """Initialize SQLite database tables (local development)."""
    with sqlite3.connect(DATABASE) as db:
        db.execute('''
            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                tshirt_size TEXT,
                age_group TEXT,
                price REAL,
                session_id TEXT,
                stripe_session_id TEXT
            )
        ''')

        try:
            db.execute("SELECT stripe_session_id FROM registrations LIMIT 1")
        except sqlite3.OperationalError:
            db.execute("ALTER TABLE registrations ADD COLUMN stripe_session_id TEXT")

        db.execute('''
            CREATE TABLE IF NOT EXISTS rsvps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT NOT NULL,
                attending TEXT NOT NULL
            )
        ''')

        db.execute('''
            CREATE TABLE IF NOT EXISTS birthdays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                birth_date TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        try:
            db.execute("SELECT birth_year FROM birthdays LIMIT 1")
        except sqlite3.OperationalError:
            db.execute("ALTER TABLE birthdays ADD COLUMN birth_year INTEGER")

        db.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                event_date TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        try:
            db.execute("SELECT image_url FROM events LIMIT 1")
        except sqlite3.OperationalError:
            db.execute("ALTER TABLE events ADD COLUMN image_url TEXT")

        db.execute('''
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_type TEXT NOT NULL,
                item_id TEXT NOT NULL,
                commenter_name TEXT NOT NULL,
                comment_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        db.execute('''
            CREATE TABLE IF NOT EXISTS reactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_type TEXT NOT NULL,
                item_id TEXT NOT NULL,
                reactor_name TEXT NOT NULL,
                reaction_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(item_type, item_id, reactor_name, reaction_type)
            )
        ''')

        db.execute('''
            CREATE TABLE IF NOT EXISTS hero_slides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_url TEXT NOT NULL,
                title TEXT NOT NULL,
                caption TEXT,
                display_order INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        db.execute('''
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        count = db.execute('SELECT COUNT(*) FROM hero_slides').fetchone()[0]
        if count == 0:
            default_slides = [
                ('static/images/family1.jpg', 'Staying Connected', 'Share your moments with family!', 1),
                ('static/images/family2.jpg', 'Celebrate Together', 'Every milestone matters.', 2),
                ('static/images/family3.jpg', 'Family First', 'Always and forever.', 3),
                ('static/images/family4.jpg', 'Making Memories', 'One moment at a time.', 4)
            ]
            for image_url, title, caption, order in default_slides:
                db.execute(
                    'INSERT INTO hero_slides (image_url, title, caption, display_order) VALUES (?, ?, ?, ?)',
                    (image_url, title, caption, order)
                )
            db.commit()

    logging.info("SQLite database initialized successfully")


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

        # Fetch hero slides
        hero_slides = db.execute('SELECT * FROM hero_slides ORDER BY display_order').fetchall()
        print(f"🟢 Hero Slides Found: {len(hero_slides)}")  # Debugging output

        # Fetch contacts
        contacts = db.execute('SELECT * FROM contacts ORDER BY created_at DESC').fetchall()
        print(f"🟢 Contacts Found: {len(contacts)}")  # Debugging output

        # Fetch all comments
        comments = db.execute('SELECT * FROM comments ORDER BY created_at DESC').fetchall()
        print(f"🟢 Comments Found: {len(comments)}")  # Debugging output

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
                             hero_slides=hero_slides,
                             contacts=contacts,
                             comments=comments,
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
            "SELECT name FROM rsvps WHERE LOWER(attending) = 'yes'"
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

        # Save contact form submission to database
        db = get_db()
        with db:
            db.execute(
                'INSERT INTO contacts (name, email, message) VALUES (?, ?, ?)',
                (name, email, message)
            )
            db.commit()

        logging.info(f"Contact form submitted: {name} | {email}")
        return jsonify({'success': True, 'message': 'Message sent successfully!'})

    except Exception as e:
        logging.error(f"❌ Contact Form Error: {e}")
        return jsonify({'error': 'Failed to send message'}), 500


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
        birthday_list = [{
            'id': b['id'],
            'name': b['name'],
            'birth_date': b['birth_date'],
            'birth_year': b.get('birth_year') if hasattr(b, 'get') else (b['birth_year'] if 'birth_year' in b.keys() else None)
        } for b in birthdays]
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
        birth_year = data.get('birth_year')  # Optional

        if not all([name, birth_date]):
            return jsonify({'error': 'Missing required fields'}), 400

        db = get_db()
        with db:
            if birth_year:
                db.execute(
                    'INSERT INTO birthdays (name, birth_date, birth_year) VALUES (?, ?, ?)',
                    (name, birth_date, int(birth_year))
                )
            else:
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
        event_list = [{
            'id': e['id'],
            'title': e['title'],
            'event_date': e['event_date'],
            'description': e['description'],
            'image_url': e.get('image_url') if hasattr(e, 'get') else (e['image_url'] if 'image_url' in e.keys() else None)
        } for e in events]
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
        image_url = data.get('image_url')  # Optional

        if not all([title, event_date, description]):
            return jsonify({'error': 'Missing required fields'}), 400

        db = get_db()
        with db:
            if image_url:
                db.execute(
                    'INSERT INTO events (title, event_date, description, image_url) VALUES (?, ?, ?, ?)',
                    (title, event_date, description, image_url)
                )
            else:
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


@app.route('/delete_contact/<int:contact_id>', methods=['DELETE'])
def delete_contact(contact_id):
    try:
        db = get_db()
        db.execute('DELETE FROM contacts WHERE id = ?', (contact_id,))
        db.commit()
        return jsonify({'success': True, 'message': 'Contact deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# Hero Slides Routes
@app.route('/hero-slides', methods=['GET'])
def get_hero_slides():
    try:
        db = get_db()
        slides = db.execute('SELECT * FROM hero_slides WHERE active = 1 ORDER BY display_order').fetchall()
        slide_list = [{
            'id': s['id'],
            'image_url': s['image_url'],
            'title': s['title'],
            'caption': s['caption'],
            'display_order': s['display_order']
        } for s in slides]
        return jsonify(slide_list)
    except Exception as e:
        logging.error(f"Error fetching hero slides: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/hero-slides', methods=['POST'])
def add_hero_slide():
    try:
        data = request.get_json()
        image_url = data.get('image_url')
        title = data.get('title')
        caption = data.get('caption', '')

        if not image_url or not title:
            return jsonify({'error': 'Image URL and title are required'}), 400

        db = get_db()
        # Get the next display order
        result = db.execute('SELECT MAX(display_order) as max_order FROM hero_slides').fetchone()
        max_order = result['max_order'] if result else 0
        next_order = (max_order or 0) + 1

        db.execute(
            'INSERT INTO hero_slides (image_url, title, caption, display_order) VALUES (?, ?, ?, ?)',
            (image_url, title, caption, next_order)
        )
        db.commit()
        return jsonify({'success': True, 'message': 'Hero slide added successfully'})
    except Exception as e:
        logging.error(f"Error adding hero slide: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/hero-slides/<int:slide_id>', methods=['PUT'])
def update_hero_slide(slide_id):
    try:
        data = request.get_json()
        title = data.get('title')
        caption = data.get('caption')
        image_url = data.get('image_url')

        if not title:
            return jsonify({'error': 'Title is required'}), 400

        db = get_db()
        db.execute(
            'UPDATE hero_slides SET title = ?, caption = ?, image_url = ? WHERE id = ?',
            (title, caption, image_url, slide_id)
        )
        db.commit()
        return jsonify({'success': True, 'message': 'Hero slide updated successfully'})
    except Exception as e:
        logging.error(f"Error updating hero slide: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/hero-slides/<int:slide_id>/reorder', methods=['PUT'])
def reorder_hero_slide(slide_id):
    try:
        data = request.get_json()
        new_order = data.get('display_order')

        if new_order is None:
            return jsonify({'error': 'Display order is required'}), 400

        db = get_db()
        # Get current order
        current = db.execute('SELECT display_order FROM hero_slides WHERE id = ?', (slide_id,)).fetchone()
        if not current:
            return jsonify({'error': 'Slide not found'}), 404

        current_order = current['display_order']

        # Update orders of other slides
        if new_order > current_order:
            # Moving down: shift slides up
            db.execute(
                'UPDATE hero_slides SET display_order = display_order - 1 WHERE display_order > ? AND display_order <= ?',
                (current_order, new_order)
            )
        else:
            # Moving up: shift slides down
            db.execute(
                'UPDATE hero_slides SET display_order = display_order + 1 WHERE display_order >= ? AND display_order < ?',
                (new_order, current_order)
            )

        # Update the slide being moved
        db.execute('UPDATE hero_slides SET display_order = ? WHERE id = ?', (new_order, slide_id))
        db.commit()

        return jsonify({'success': True, 'message': 'Slide reordered successfully'})
    except Exception as e:
        logging.error(f"Error reordering hero slide: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/delete_hero_slide/<int:slide_id>', methods=['DELETE'])
def delete_hero_slide(slide_id):
    try:
        db = get_db()
        # Get the order of the slide being deleted
        slide = db.execute('SELECT display_order FROM hero_slides WHERE id = ?', (slide_id,)).fetchone()
        if slide:
            order = slide['display_order']
            # Delete the slide
            db.execute('DELETE FROM hero_slides WHERE id = ?', (slide_id,))
            # Shift remaining slides up
            db.execute('UPDATE hero_slides SET display_order = display_order - 1 WHERE display_order > ?', (order,))
            db.commit()
        return jsonify({'success': True, 'message': 'Hero slide deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# Comments Routes
@app.route('/comments/<item_type>/<item_id>', methods=['GET'])
def get_comments(item_type, item_id):
    try:
        db = get_db()
        comments = db.execute(
            'SELECT * FROM comments WHERE item_type = ? AND item_id = ? ORDER BY created_at DESC',
            (item_type, item_id)
        ).fetchall()

        comment_list = [{
            'id': c['id'],
            'commenter_name': c['commenter_name'],
            'comment_text': c['comment_text'],
            'created_at': c['created_at']
        } for c in comments]

        return jsonify(comment_list)
    except Exception as e:
        logging.error(f"Error fetching comments: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/comments', methods=['POST'])
def add_comment():
    try:
        data = request.get_json()
        item_type = data.get('item_type')
        item_id = data.get('item_id')
        commenter_name = data.get('commenter_name')
        comment_text = data.get('comment_text')

        if not all([item_type, item_id, commenter_name, comment_text]):
            return jsonify({'error': 'Missing required fields'}), 400

        db = get_db()
        with db:
            if USE_POSTGRES:
                result = db.execute(
                    'INSERT INTO comments (item_type, item_id, commenter_name, comment_text) VALUES (?, ?, ?, ?) RETURNING id',
                    (item_type, item_id, commenter_name, comment_text)
                ).fetchone()
                comment_id = result['id']
            else:
                cursor = db.execute(
                    'INSERT INTO comments (item_type, item_id, commenter_name, comment_text) VALUES (?, ?, ?, ?)',
                    (item_type, item_id, commenter_name, comment_text)
                )
                comment_id = cursor.lastrowid
            db.commit()

        return jsonify({'success': True, 'comment_id': comment_id})
    except Exception as e:
        logging.error(f"Error adding comment: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/comments/<int:comment_id>', methods=['DELETE'])
def delete_comment(comment_id):
    try:
        db = get_db()
        db.execute('DELETE FROM comments WHERE id = ?', (comment_id,))
        db.commit()
        return jsonify({'success': True, 'message': 'Comment deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# Reactions Routes
@app.route('/reactions/<item_type>/<item_id>', methods=['GET'])
def get_reactions(item_type, item_id):
    try:
        db = get_db()
        reactions = db.execute(
            'SELECT reaction_type, COUNT(*) as count FROM reactions WHERE item_type = ? AND item_id = ? GROUP BY reaction_type',
            (item_type, item_id)
        ).fetchall()

        reaction_dict = {r['reaction_type']: r['count'] for r in reactions}

        return jsonify(reaction_dict)
    except Exception as e:
        logging.error(f"Error fetching reactions: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/reactions', methods=['POST'])
def add_reaction():
    try:
        data = request.get_json()
        item_type = data.get('item_type')
        item_id = data.get('item_id')
        reactor_name = data.get('reactor_name')
        reaction_type = data.get('reaction_type')

        if not all([item_type, item_id, reactor_name, reaction_type]):
            return jsonify({'error': 'Missing required fields'}), 400

        db = get_db()
        with db:
            try:
                db.execute(
                    'INSERT INTO reactions (item_type, item_id, reactor_name, reaction_type) VALUES (?, ?, ?, ?)',
                    (item_type, item_id, reactor_name, reaction_type)
                )
                db.commit()
                return jsonify({'success': True, 'action': 'added'})
            except (sqlite3.IntegrityError, Exception) as integrity_err:
                if 'unique' not in str(integrity_err).lower() and 'integrity' not in str(type(integrity_err).__name__).lower():
                    raise
                # User already reacted with this type, remove it (toggle)
                db.rollback()
                db.execute(
                    'DELETE FROM reactions WHERE item_type = ? AND item_id = ? AND reactor_name = ? AND reaction_type = ?',
                    (item_type, item_id, reactor_name, reaction_type)
                )
                db.commit()
                return jsonify({'success': True, 'action': 'removed'})
    except Exception as e:
        logging.error(f"Error adding reaction: {e}")
        return jsonify({'error': str(e)}), 500


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


def seed_birthdays():
    """Seed birthdays from birthday.txt if they don't already exist in the database.

    Parses lines in the format: 'Name M/D/YY' or 'Name M/D' (year optional).
    Two-digit years are interpreted as 1900s (00-99 -> 1900-1999).
    """
    birthday_file = os.path.join(os.path.dirname(__file__), 'birthday.txt')
    if not os.path.exists(birthday_file):
        logging.info("No birthday.txt found, skipping seed")
        return

    entries = []
    with open(birthday_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Split from the right to get the date portion (last token)
            parts = line.rsplit(' ', 1)
            if len(parts) != 2:
                continue
            name = parts[0].strip()
            date_str = parts[1].strip()

            date_parts = date_str.split('/')
            if len(date_parts) == 2:
                # Month/Day only, no year
                month, day = int(date_parts[0]), int(date_parts[1])
                birth_date = f"{month:02d}-{day:02d}"
                entries.append((name, birth_date, None))
            elif len(date_parts) == 3:
                month, day = int(date_parts[0]), int(date_parts[1])
                year_str = date_parts[2]
                year = int(year_str)
                # Two-digit year: interpret as 1900s since these are birth years
                if year < 100:
                    year += 1900
                birth_date = f"{month:02d}-{day:02d}"
                entries.append((name, birth_date, year))

    if not entries:
        return

    try:
        if USE_POSTGRES:
            conn = psycopg2.connect(DATABASE_URL, sslmode='require')
            try:
                with conn.cursor() as cur:
                    for name, birth_date, birth_year in entries:
                        # Check if already exists (by name and birth_date)
                        cur.execute(
                            "SELECT 1 FROM birthdays WHERE name = %s AND birth_date = %s",
                            (name, birth_date)
                        )
                        if cur.fetchone() is None:
                            cur.execute(
                                "INSERT INTO birthdays (name, birth_date, birth_year) VALUES (%s, %s, %s)",
                                (name, birth_date, birth_year)
                            )
                            logging.info(f"Seeded birthday: {name} ({birth_date})")
                conn.commit()
            finally:
                conn.close()
        else:
            conn = sqlite3.connect(DATABASE)
            try:
                for name, birth_date, birth_year in entries:
                    existing = conn.execute(
                        "SELECT 1 FROM birthdays WHERE name = ? AND birth_date = ?",
                        (name, birth_date)
                    ).fetchone()
                    if existing is None:
                        conn.execute(
                            "INSERT INTO birthdays (name, birth_date, birth_year) VALUES (?, ?, ?)",
                            (name, birth_date, birth_year)
                        )
                        logging.info(f"Seeded birthday: {name} ({birth_date})")
                conn.commit()
            finally:
                conn.close()
        logging.info(f"Birthday seeding complete ({len(entries)} entries processed)")
    except Exception as e:
        logging.error(f"Error seeding birthdays: {e}")


# Initialize the database at startup
init_db()
seed_birthdays()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
