import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Debugging: Print GOOGLE_CREDENTIALS to check if it is being loaded
print("GOOGLE_CREDENTIALS:", os.getenv("GOOGLE_CREDENTIALS"))

creds_dict = json.loads(os.getenv("GOOGLE_CREDENTIALS"))  # This is failing
