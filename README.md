# Family Reunion 2025 Website

This website is designed for the Family Reunion event scheduled for July 17-20, 2025.

## Features

-   Responsive design with a sticky navigation bar.
-   Hero section with a carousel and countdown timer.
-   Registration form with dynamic updates and payment integration via Stripe.
-   Event schedule and hotel information.
-   Photo gallery.
-   FAQ section with accordion-style answers.
-   Volunteer signup modal.
-   Contact form.

## Technologies

-   **Backend:** Flask (Python)
-   **Frontend:** HTML, CSS (Bootstrap 5), JavaScript
-   **Payment:** Stripe
-   **Database:** SQLite

## Setup

1.  **Clone the repository:**

    ```bash
    git clone <repository-url>
    cd family-reunion-2025
    ```

2.  **Create a virtual environment:**

    ```bash
    python3 -m venv venv
    ```

3.# Activate the virtual environment (Linux/macOS)
    source venv/bin/activate

    # Activate the virtual environment (Windows)
    venv\Scripts\activate
    ```

4.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

5.  **Stripe API Keys:**

    *   Obtain your Stripe API keys (secret key and publishable key) from your Stripe Dashboard.
    *   Create a `.env` file in the root directory of the project.
    *   Add your Stripe keys to the `.env` file:

    ```
    STRIPE_SECRET_KEY=your_stripe_secret_key
    STRIPE_PUBLIC_KEY=your_stripe_publishable_key
    ```

6.  **Run the application:**

    ```bash
    flask run
    ```

    The application will be accessible at `http://127.0.0.1:5000/`.

## Deployment (Heroku Example)

1.  **Create a Heroku account** if you don't already have one.
2.  **Install the Heroku CLI** following the instructions on the Heroku website.
3.  **Login to Heroku:**

    ```bash
    heroku login
    ```

4.  **Initialize a Git repository (if not already done):**

    ```bash
    git init
    git add .
    git commit -m "Initial commit"
    ```

5.  **Create a Heroku app:**

    ```bash
    heroku create your-app-name
    ```

    (Replace `your-app-name` with a unique name for your app).

6.  **Set environment variables on Heroku:**

    ```bash
    heroku config:set STRIPE_SECRET_KEY=your_stripe_secret_key
    heroku config:set STRIPE_PUBLIC_KEY=your_stripe_publishable_key
    ```

7.  **Create a `Procfile`:**

    Create a file named `Procfile` (no extension) in the root directory with the following content:

    ```
    web: gunicorn app:app
    ```

8.  **Install `gunicorn`:**

    ```bash
    pip install gunicorn
    ```

9.  **Update `requirements.txt`:**

    Make sure `gunicorn` is included in your `requirements.txt` file.

10. **Deploy to Heroku:**

    ```bash
    git push heroku master
    ```

11. **Open the app in your browser:**

    ```bash
    heroku open
    ```

## Testing

-   Test all forms (registration, volunteer, contact) thoroughly.
-   Verify payment processing with Stripe test cards.
-   Ensure responsiveness on different devices and browsers.
-   Check for JavaScript errors in the browser console.

## Troubleshooting

-   **Database issues:** If you encounter errors related to the database, make sure the `reunion.db` file has the correct permissions.
-   **Stripe errors:** Double-check your Stripe API keys in the `.env` file and Heroku environment variables.
-   **Deployment problems:** Review the Heroku logs for error messages:

    ```bash
    heroku logs --tail
    ```

## Additional Notes

-   Remember to replace placeholder images, hotel links, and pricing with actual content.
-   Consider adding more robust form validation on both the frontend and backend.
-   For production, use a more secure database like PostgreSQL.
-   Implement email functionality for sending registration confirmations and other communications.
-   Add a mechanism for handling photo uploads to the gallery (consider using a cloud storage service like AWS S3).# Trigger fresh deployment
