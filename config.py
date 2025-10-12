from dotenv import load_dotenv
import os

load_dotenv()

TELEGRAM_BOT_TOKEN=os.getenv('TELEGRAM_BOT_TOKEN')
API_KEY=os.getenv('API_KEY')
API_SECRET=os.getenv('API_SECRET')
NGROK_TOKEN=os.getenv('NGROK_TOKEN')

# Demo account credentials (for testing)
DEMO_API_KEY=os.getenv('DEMO_API_KEY', API_KEY)  # Fallback to real API key if not set
DEMO_API_SECRET=os.getenv('DEMO_API_SECRET', API_SECRET)  # Fallback to real API secret if not set