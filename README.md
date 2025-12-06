# iMessage Auto-Reply Bot

Auto-reply bot with distributed locking support and Gen Z style messages powered by ChatGPT.

## Features

- **Distributed Locking**: Prevents duplicate responses when running multiple instances (uses Redis or in-memory)
- **Gen Z Messages**: ChatGPT generates catchy, casual initial messages and responses
- **Environment Variables**: All secrets stored securely in `.env` file
- **Kafka Consumer**: Listens for incoming messages in real-time
- **Deduplication**: Each message is processed exactly once across all instances

## Setup

1. **Install dependencies**:
   ```bash
   cd test_app_001
   pip install -r requirements.txt
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your actual API keys
   ```

3. **Run the bot**:
   ```bash
   python main.py
   ```

## Environment Variables

All configuration is done via `.env` file:

- `SERIES_API_KEY` - Your Series API key
- `SENDER_NUMBER` - Your phone number
- `RECIPIENT_NUMBER` - Who you're messaging
- `KAFKA_*` - Kafka configuration
- `OPENAI_API_KEY` - ChatGPT API key for Gen Z messages
- `REDIS_URL` - (Optional) For distributed locking when running multiple instances

## How It Works

1. Bot generates a catchy Gen Z greeting using ChatGPT
2. Sends initial message to recipient
3. Listens for responses via Kafka
4. When a message arrives:
   - Acquires a distributed lock (prevents duplicates)
   - Generates Gen Z style response
   - Sends reply automatically

## Running Multiple Instances

To run multiple instances without duplicate responses:

1. Set up Redis:
   ```bash
   # Using Docker
   docker run -d -p 6379:6379 redis
   ```

2. Add Redis URL to `.env`:
   ```
   REDIS_URL=redis://localhost:6379
   ```

3. Run multiple instances - they'll coordinate via Redis to prevent duplicates!

## Single Instance Mode

If you don't need multiple instances, leave `REDIS_URL` empty. The bot will use in-memory locking.

## Troubleshooting

### Run Diagnostics

First, run the diagnostic script to verify your setup:

```bash
python debug_test.py
```

This will test:
- Environment variables are loaded correctly
- OpenAI API connection and message generation
- Series API connection
- Kafka connection and message reception

### "Sometimes works, sometimes doesn't"

If you're experiencing intermittent issues:

1. **Check Kafka offset reset**: The consumer uses `auto_offset_reset='earliest'` to process all messages. If you only want new messages, change it to `'latest'` in main.py line 222.

2. **Check phone number format**: Make sure `RECIPIENT_NUMBER` in `.env` matches exactly (including country code like +1).

3. **Multiple instances running**: If you or teammates are running multiple instances without Redis, you'll get duplicate/missed messages. Either:
   - Use Redis (see "Running Multiple Instances" above)
   - Coordinate to run only one instance at a time

4. **Check the logs**: The verbose logging will show:
   - If messages are being received
   - If phone numbers match
   - If locks are being acquired
   - Any API errors

5. **API rate limits**: If sending too many messages, you might hit rate limits.

### Common Issues

**"Chat ID: N/A"**
- This happens if the API response format is different than expected
- Check the "Full API Response" in the logs to see the actual structure
- The initial message still sends successfully even if ID shows N/A

**"No messages received"**
- Kafka might be slow to deliver messages
- Try sending a test message to the recipient
- Check that `KAFKA_TOPIC` and other Kafka settings are correct

**"Lock acquired but no reply sent"**
- OpenAI API might be down or rate limited
- Check your `OPENAI_API_KEY` is valid
- Check network connectivity

**Multiple responses to same message**
- Multiple instances running without Redis
- Set up Redis for distributed locking
