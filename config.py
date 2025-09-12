from dotenv import load_dotenv
import os

load_dotenv()

TELEGRAM_BOT_TOKEN=os.getenv('TELEGRAM_BOT_TOKEN')
API_KEY=os.getenv('API_KEY')
API_SECRET=os.getenv('API_SECRET')
NGROK_TOKEN=os.getenv('NGROK_TOKEN')
