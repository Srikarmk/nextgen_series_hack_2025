"""
Configuration with environment variables
"""
import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Series API Configuration
SERIES_API_KEY = os.getenv("SERIES_API_KEY")
SERIES_BASE_URL = os.getenv("SERIES_BASE_URL", "https://series-hackathon-service-202642739529.us-east1.run.app")
SENDER_NUMBER = os.getenv("SENDER_NUMBER")
RECIPIENT_NUMBER = os.getenv("RECIPIENT_NUMBER")
# Optional: Comma-separated list of phone numbers to prioritize (still processes all messages)
ALLOWED_RECIPIENTS = os.getenv("ALLOWED_RECIPIENTS", "").split(",") if os.getenv("ALLOWED_RECIPIENTS") else []
ALLOWED_RECIPIENTS = [r.strip() for r in ALLOWED_RECIPIENTS if r.strip()]  # Clean up and filter empty

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC")
KAFKA_API_KEY = os.getenv("KAFKA_API_KEY")
KAFKA_API_SECRET = os.getenv("KAFKA_API_SECRET")
KAFKA_CONSUMER_GROUP = os.getenv("KAFKA_CONSUMER_GROUP")

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Redis Configuration (optional, for distributed locking)
REDIS_URL = os.getenv("REDIS_URL")

# Application Settings
LOCK_TIMEOUT = int(os.getenv("LOCK_TIMEOUT", "10"))

# Validate required environment variables
required_vars = [
    "SERIES_API_KEY",
    "SENDER_NUMBER",
    "KAFKA_BOOTSTRAP_SERVERS",
    "KAFKA_TOPIC",
    "KAFKA_API_KEY",
    "KAFKA_API_SECRET",
    "KAFKA_CONSUMER_GROUP",
    "OPENAI_API_KEY"
]

missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# RECIPIENT_NUMBER is optional - bot will respond to anyone who texts first
if not RECIPIENT_NUMBER:
    logger = logging.getLogger(__name__)
    logger.info("RECIPIENT_NUMBER not set - bot will respond to anyone who texts first")
