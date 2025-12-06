#!/usr/bin/env python3
"""
Reset consumer group offset to re-read all messages
Use this if your bot is "stuck" and not processing messages
"""
import sys
from kafka import KafkaConsumer
from config import *

print("=" * 60)
print("Consumer Group Offset Reset")
print("=" * 60)
print(f"Consumer Group: {KAFKA_CONSUMER_GROUP}")
print(f"Topic: {KAFKA_TOPIC}\n")

response = input("⚠️  This will reset the consumer group to read ALL messages from the beginning.\nAre you sure? (yes/no): ")

if response.lower() != 'yes':
    print("Cancelled.")
    sys.exit(0)

print("\n🔄 Resetting consumer group offset...")

# Create consumer and seek to beginning
consumer = KafkaConsumer(
    KAFKA_TOPIC,
    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(','),
    security_protocol='SASL_SSL',
    sasl_mechanism='PLAIN',
    sasl_plain_username=KAFKA_API_KEY,
    sasl_plain_password=KAFKA_API_SECRET,
    group_id=KAFKA_CONSUMER_GROUP,
    enable_auto_commit=False
)

# Get all partitions for the topic
partitions = consumer.partitions_for_topic(KAFKA_TOPIC)

if not partitions:
    print(f"❌ No partitions found for topic {KAFKA_TOPIC}")
    sys.exit(1)

print(f"Found {len(partitions)} partition(s)")

# Seek to beginning for all partitions
from kafka import TopicPartition

for partition in partitions:
    tp = TopicPartition(KAFKA_TOPIC, partition)
    consumer.assign([tp])
    consumer.seek_to_beginning(tp)
    print(f"  ✓ Reset partition {partition} to beginning")

# Commit the offset
consumer.commit()

consumer.close()

print("\n✅ Consumer group offset has been reset!")
print("Next time you run main.py, it will process all messages from the beginning.\n")
