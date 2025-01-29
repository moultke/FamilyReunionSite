import stripe
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set your Stripe secret key
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

def test_stripe_connection():
    try:
        # Create a test charge (using Stripe's test token)
        charge = stripe.Charge.create(
            amount=1000,  # $10.00 in cents
            currency="usd",
            source="tok_visa",  # Test token for a Visa card
            description="Test charge to verify Stripe connection"
        )

        # If successful, print the charge details
        print("Stripe connection successful!")
        print(f"Charge ID: {charge.id}")
        print(f"Charge Amount: ${charge.amount / 100:.2f}")
        print(f"Charge Status: {charge.status}")

    except stripe.error.StripeError as e:
        # Handle any Stripe-specific errors
        print(f"Stripe error: {e}")
    except Exception as e:
        # Handle any other errors
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    print("Testing Stripe connection...")
    test_stripe_connection()