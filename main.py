#!/usr/bin/env python3
"""
iMessage Auto-Reply Bot with Distributed Locking and Gen Z Messages
Prevents duplicate responses when running multiple instances
"""

import json
import logging
import signal
import sys
import time
import hashlib
from threading import Lock
from typing import Optional, Dict, Any
from kafka import KafkaConsumer
from kafka.errors import KafkaError

from config import (
    SENDER_NUMBER,
    RECIPIENT_NUMBER,
    ALLOWED_RECIPIENTS,
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_TOPIC,
    KAFKA_API_KEY,
    KAFKA_API_SECRET,
    KAFKA_CONSUMER_GROUP,
    REDIS_URL,
    LOCK_TIMEOUT
)
from agent import generate_catchy_message
from api_client import api_client
from message_processor import process_message, handle_message_and_reply

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Reduce verbosity of third-party libraries
logging.getLogger('kafka').setLevel(logging.WARNING)
logging.getLogger('kafka.conn').setLevel(logging.WARNING)
logging.getLogger('kafka.consumer').setLevel(logging.WARNING)
logging.getLogger('kafka.coordinator').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)

# Global shutdown flag for graceful termination
shutdown_flag = False

# Try to import Redis, fall back to in-memory locking if not available
USE_REDIS = False
redis_client = None

try:
    import redis
    USE_REDIS = bool(REDIS_URL)
    if USE_REDIS:
        redis_client = redis.from_url(REDIS_URL)
        # Test connection
        redis_client.ping()
        logger.info("Using Redis for distributed locking")
except (ImportError, Exception) as e:
    USE_REDIS = False
    logger.warning(f"Using in-memory locking (single instance only): {e}")

# In-memory lock for single instance mode
local_lock = Lock()
processed_messages = set()


class MessageLock:
    """Distributed lock to prevent duplicate message processing"""

    def __init__(self, message_id: str, timeout: int = LOCK_TIMEOUT):
        self.message_id = message_id
        self.lock_key = f"msg_lock:{message_id}"
        self.processed_key = f"msg_processed:{message_id}"
        self.timeout = timeout

    def __enter__(self):
        """Acquire lock"""
        if USE_REDIS:
            # Try to acquire distributed lock with Redis
            acquired = redis_client.set(
                self.lock_key,
                "locked",
                nx=True,  # Only set if doesn't exist
                ex=self.timeout  # Auto-expire after timeout
            )

            if not acquired:
                # Another instance is processing this message
                raise RuntimeError(f"Message {self.message_id} is being processed by another instance")

            # Check if already processed
            if redis_client.exists(self.processed_key):
                redis_client.delete(self.lock_key)
                raise RuntimeError(f"Message {self.message_id} already processed")

        else:
            # In-memory locking for single instance
            with local_lock:
                if self.message_id in processed_messages:
                    raise RuntimeError(f"Message {self.message_id} already processed")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release lock and mark as processed if successful"""
        if exc_type is None:  # No exception, processing succeeded
            if USE_REDIS:
                # Mark as processed (keep for 1 hour to prevent re-processing)
                redis_client.setex(self.processed_key, 3600, "done")
                redis_client.delete(self.lock_key)
            else:
                with local_lock:
                    processed_messages.add(self.message_id)
                    # Keep only last 1000 messages in memory
                    if len(processed_messages) > 1000:
                        processed_messages.pop()  # Remove arbitrary element
        else:
            # Exception occurred, release lock so another instance can retry
            if USE_REDIS:
                redis_client.delete(self.lock_key)


def generate_message_id(chat_id: str, from_phone: str, text: str, timestamp: str, message_id: str = None) -> str:
    """Generate unique message ID for deduplication"""
    # Use message_id from API if available (most reliable)
    if message_id:
        return f"msg_{message_id}"
    # Include timestamp and a hash of content for better uniqueness
    # Add a small random component to handle identical messages sent at same time
    import time
    content = f"{chat_id}:{from_phone}:{text}:{timestamp}:{time.time()}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]




def create_consumer():
    """Create and return a Kafka consumer with proper configuration"""
    return KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(','),
        security_protocol='SASL_SSL',
        sasl_mechanism='PLAIN',
        sasl_plain_username=KAFKA_API_KEY,
        sasl_plain_password=KAFKA_API_SECRET,
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        auto_offset_reset='earliest',
        enable_auto_commit=False,  # Manual commit for reliability
        group_id=KAFKA_CONSUMER_GROUP,
        # Connection and timeout settings for reliability
        # request_timeout_ms must be > session_timeout_ms
        request_timeout_ms=40000,  # 40 seconds (must be > session_timeout)
        session_timeout_ms=30000,  # 30 seconds
        heartbeat_interval_ms=10000,  # 10 seconds (should be < session_timeout/3)
        max_poll_records=50,  # Process more messages per batch
        max_poll_interval_ms=300000,  # 5 minutes max processing time
        consumer_timeout_ms=1000,  # Poll timeout (1 second)
    )


def process_message_with_lock(event: Dict[str, Any], message_count: int) -> bool:
    """
    Process a message event with locking and reply generation
    
    Args:
        event: The Kafka event data
        message_count: Sequential message number for logging
        
    Returns:
        bool: True if message was processed successfully, False otherwise
    """
    # First, handle non-message events (reactions, typing, etc.)
    if event.get('event_type') != 'message.received':
        return process_message(event, message_count)
    
    # Handle message.received events
    data = event.get('data', {})
    from_phone = data.get('from_phone', '')
    chat_id = data.get('chat_id', '')
    message_text = data.get('text', '')
    message_id = data.get('id', '')  # API message ID
    timestamp = event.get('created_at', '')
    
    if not from_phone:
        logger.warning(f"⚠️  Message #{message_count} - Missing from_phone, skipping")
        return True
    
    # Skip messages from the bot itself
    if from_phone == SENDER_NUMBER:
        logger.debug(f"⏭️  Message #{message_count} - Skipping message from bot itself")
        return True
    
    # Normalize phone number for comparison (remove +, spaces, dashes)
    normalized_from_phone = from_phone.replace("+", "").replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    normalized_allowed = [r.replace("+", "").replace(" ", "").replace("-", "").replace("(", "").replace(")", "") for r in ALLOWED_RECIPIENTS]
    
    # Optional: Log if message is from allowed recipients (for debugging)
    if ALLOWED_RECIPIENTS:
        if normalized_from_phone in normalized_allowed:
            logger.info(f"✅ Message #{message_count} - From allowed recipient: {from_phone}")
        else:
            logger.debug(f"📱 Message #{message_count} - From: {from_phone} (not in allowed list, but processing anyway)")
    
    # Generate unique message ID for deduplication (use API message ID if available)
    msg_id = generate_message_id(str(chat_id), from_phone, message_text or "", timestamp, message_id)
    logger.info(f"Message #{message_count} - Generated ID: {msg_id}")
    
    try:
        # Acquire lock to ensure only one instance processes this message
        with MessageLock(msg_id):
            # Process message and send reply
            return handle_message_and_reply(event, message_count, None)
    
    except RuntimeError as lock_error:
        # Message already being processed or was processed
        logger.info(f"⏭️  Message #{message_count} - Skipping (already processed): {lock_error}")
        return True  # Not an error, just duplicate
    except Exception as process_error:
        logger.error(f"❌ Message #{message_count} - Error processing: {process_error}", exc_info=True)
        return False


def listen_and_auto_reply():
    """
    Listen for incoming messages and automatically reply with Gen Z style messages
    Uses distributed locking to prevent duplicate responses from multiple instances
    Now with automatic reconnection and better error handling
    """
    global shutdown_flag
    
    logger.info(f"Connecting to Kafka topic: {KAFKA_TOPIC}")
    logger.info(f"Auto-replying to messages from everyone")
    if ALLOWED_RECIPIENTS:
        logger.info(f"📱 Allowed recipients (for logging): {', '.join(ALLOWED_RECIPIENTS)}")
    else:
        logger.info(f"📱 No recipient filter - processing all messages")

    retry_delay = 5  # seconds
    max_retry_delay = 60  # Maximum retry delay
    consumer = None
    message_count = 0
    last_heartbeat = time.time()
    consecutive_errors = 0
    max_consecutive_errors = 10

    while not shutdown_flag:
        try:
            # Initialize or reinitialize Kafka Consumer
            if consumer is None:
                logger.info("Initializing Kafka consumer...")
                try:
                    consumer = create_consumer()
                    logger.info("Connected to Kafka successfully")
                    logger.info("Listening for messages from everyone")
                    last_heartbeat = time.time()
                    consecutive_errors = 0  # Reset error counter on successful connection
                except Exception as e:
                    logger.error(f"Failed to connect to Kafka: {e}", exc_info=True)
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        logger.critical(f"Too many consecutive connection failures ({consecutive_errors}). Exiting.")
                        break
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 1.5, max_retry_delay)  # Exponential backoff
                    continue

            # Poll for messages with timeout
            try:
                message_batch = consumer.poll(timeout_ms=1000, max_records=50)
                
                if message_batch:
                    logger.info(f"📦 Received batch with {sum(len(msgs) for msgs in message_batch.values())} message(s)")
                    
                    # Process each partition's messages
                    processed_count = 0
                    failed_count = 0
                    all_succeeded = True  # Track if all messages in batch succeeded
                    
                    for topic_partition, messages in message_batch.items():
                        logger.info(f"Processing {len(messages)} message(s) from partition {topic_partition.partition}")
                        
                        for message in messages:
                            if shutdown_flag:
                                break
                                
                            message_count += 1
                            
                            try:
                                event = message.value
                                success = process_message_with_lock(event, message_count)
                                
                                if success:
                                    processed_count += 1
                                    last_heartbeat = time.time()
                                    consecutive_errors = 0
                                else:
                                    failed_count += 1
                                    all_succeeded = False
                                    logger.warning(f"⚠️  Message #{message_count} processing returned False")
                                    # Continue processing other messages, but mark batch as incomplete
                                
                            except RuntimeError as lock_error:
                                # Message already processed by another instance - safe to count as processed
                                logger.debug(f"⏭️  Message #{message_count} - Already processed: {lock_error}")
                                processed_count += 1
                            except Exception as msg_error:
                                failed_count += 1
                                all_succeeded = False
                                logger.error(f"❌ Exception processing message #{message_count}: {msg_error}", exc_info=True)
                                # Continue processing other messages
                    
                    # Commit offsets - be more permissive to avoid getting stuck
                    # Commit if we processed at least some messages successfully
                    # Failed messages will be retried, but we don't want to block progress
                    if processed_count > 0:
                        try:
                            consumer.commit()
                            if all_succeeded:
                                logger.info(f"✅ Committed offsets - Processed: {processed_count}, Failed: {failed_count}")
                            else:
                                logger.info(f"✅ Committed offsets (some failed) - Processed: {processed_count}, Failed: {failed_count} (failed will retry)")
                        except Exception as commit_error:
                            logger.error(f"❌ Error committing offsets: {commit_error}", exc_info=True)
                    elif failed_count > 0:
                        logger.warning(f"⚠️  Not committing offsets - all {failed_count} message(s) failed, will retry on next poll")
                    else:
                        logger.debug("No messages to commit")
                else:
                    # No messages, but connection is alive
                    current_time = time.time()
                    if current_time - last_heartbeat > 60:
                        # Log heartbeat every 60 seconds
                        logger.debug("Still listening... (no messages received)")
                        last_heartbeat = current_time
                
            except KafkaError as kafka_error:
                logger.error(f"Kafka error: {kafka_error}", exc_info=True)
                
                # Check if it's a connection error
                error_str = str(kafka_error).lower()
                if any(keyword in error_str for keyword in ["connection", "broker", "network", "timeout"]):
                    logger.warning("Connection lost, reconnecting...")
                    try:
                        consumer.close()
                    except:
                        pass
                    consumer = None
                    consecutive_errors += 1
                    time.sleep(retry_delay)
                    continue
                else:
                    # Other error, continue polling
                    time.sleep(1)
                    continue
            except Exception as poll_error:
                logger.error(f"Unexpected error polling Kafka: {poll_error}", exc_info=True)
                time.sleep(1)
                continue

        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
            shutdown_flag = True
            break
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
            
            # Try to recover
            if consumer:
                try:
                    consumer.close()
                except:
                    pass
            consumer = None
            consecutive_errors += 1
            if consecutive_errors >= max_consecutive_errors:
                logger.critical(f"Too many consecutive errors ({consecutive_errors}). Exiting.")
                break
            logger.info(f"Waiting {retry_delay} seconds before reconnecting...")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 1.5, max_retry_delay)
            continue

    # Cleanup
    if consumer:
        try:
            consumer.close()
            logger.info("Consumer closed gracefully")
        except Exception as e:
            logger.error(f"Error closing consumer: {e}")
    
    logger.info("Listener stopped")


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global shutdown_flag
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_flag = True


def main():
    """Main entry point"""
    global shutdown_flag
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("=" * 60)
    logger.info("iMessage Auto-Reply Bot with Gen Z Vibes")
    logger.info("=" * 60)
    logger.info(f"Sender: {SENDER_NUMBER}")
    if RECIPIENT_NUMBER:
        logger.info(f"Recipient: {RECIPIENT_NUMBER}")
    else:
        logger.info("Recipient: Anyone (bot will respond to first message)")
    logger.info(f"Lock mode: {'Distributed (Redis)' if USE_REDIS else 'Local (single instance)'}")

    # Optional: Send initial message if RECIPIENT_NUMBER is set
    if RECIPIENT_NUMBER:
        logger.info("Generating catchy Gen Z message...")
        try:
            message_list = generate_catchy_message("initial")
            # Handle list return - take first message for initial greeting
            if isinstance(message_list, list):
                message = message_list[0] if message_list else "hey! what's up?"
            else:
                message = message_list
            logger.info(f"Generated message: {message}")
            
            logger.info(f"Sending initial message to {RECIPIENT_NUMBER}...")
            result = api_client.create_chat([RECIPIENT_NUMBER], message, SENDER_NUMBER)
            
            if result:
                logger.info("Initial message sent successfully.")
            else:
                logger.warning("Failed to send initial message, but continuing to listen...")
        except Exception as e:
            logger.warning(f"Failed to send initial message: {e}, but continuing to listen...")
    else:
        logger.info("No RECIPIENT_NUMBER set - waiting for users to text first...")
    
    # Start listening and auto-replying (responds to anyone who texts)
    logger.info("Starting listener - will respond to anyone who texts...")
    listen_and_auto_reply()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Fatal error in main: {e}", exc_info=True)
        sys.exit(1)
