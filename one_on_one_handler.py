"""
1-on-1 Chat Handler
Uses head agent pattern with tools.json for tool selection
All tools run automatically (no explicit triggers needed)
"""
import json
import os
from typing import Dict, List, Optional, Tuple, Any
from app_logger import logger
from agent import (
    generate_catchy_message, 
    extract_interests, 
    add_music_link_if_applicable,
    user_likes_music,
)
from reaction_utils import determine_reaction
from interest_tracker import interest_tracker
from conversation_history import conversation_history


class OneOnOneHandler:
    """Handler for 1-on-1 chats using tool calling pattern"""
    
    def __init__(self):
        # Load tools from tools.json
        tools_path = os.path.join(os.path.dirname(__file__), "tools.json")
        try:
            with open(tools_path, 'r') as f:
                tools_data = json.load(f)
                self.tools = {tool['id']: tool for tool in tools_data.get('one_on_one_tools', [])}
                logger.info(f"[TOOLS] Loaded {len(self.tools)} 1-on-1 tools from tools.json")
        except Exception as e:
            logger.error(f"[ERROR] Failed to load tools.json: {e}")
            self.tools = {}
        
        # Track message counts per chat to respond every 2-3 messages
        self.message_counts = {}  # chat_id -> count
        self.last_response_message_count = {}  # chat_id -> last message number we responded to
    
    def _should_respond_now(self, chat_id: int, message_text: str) -> Tuple[bool, str]:
        """
        Determine if we should respond to this message using LLM-based intent understanding
        Only responds every 2-3 messages AND when it's necessary
        
        Returns:
            (should_respond: bool, reason: str)
        """
        # Initialize counters
        if chat_id not in self.message_counts:
            self.message_counts[chat_id] = 0
        if chat_id not in self.last_response_message_count:
            self.last_response_message_count[chat_id] = 0
        
        # Increment message count
        self.message_counts[chat_id] += 1
        current_count = self.message_counts[chat_id]
        last_response_count = self.last_response_message_count[chat_id]
        messages_since_response = current_count - last_response_count
        
        # Always respond to first message
        if current_count == 1:
            return (True, "first_message")
        
        # Check if it's time to respond (every 2-3 messages)
        import random
        target_interval = random.randint(2, 3)  # Randomly choose 2 or 3
        
        if messages_since_response < target_interval:
            # Not time yet - use LLM to check if it's urgent/necessary
            try:
                from openai import OpenAI
                from config import OPENAI_API_KEY
                client = OpenAI(api_key=OPENAI_API_KEY)
                
                system_prompt = """You are analyzing a user message to determine if it requires an immediate response.

A response is ONLY necessary if:
1. User asked a direct question that needs an answer
2. User shared something important that needs acknowledgment
3. User is clearly waiting for a response or expecting one
4. User expressed strong emotion (positive or negative) that needs acknowledgment

DO NOT respond if:
- It's just a casual statement or update
- User is just sharing something without expecting a response
- It's a greeting or acknowledgment
- It's a normal part of conversation that doesn't need a reply

Return ONLY: "yes" if response is necessary, "no" if not necessary."""
                
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"User message: {message_text}\n\nDoes this require an immediate response?"}
                    ],
                    temperature=0.3,
                    max_tokens=5,
                    timeout=5
                )
                
                decision = response.choices[0].message.content.strip().lower()
                if decision == "yes":
                    logger.info(f"[RESPONSE] LLM determined response is necessary (message {current_count})")
                    self.last_response_message_count[chat_id] = current_count
                    return (True, "necessary_response")
                else:
                    logger.debug(f"[RESPONSE] Skipping response - not necessary (message {current_count}, {messages_since_response} since last)")
                    return (False, "not_necessary")
                    
            except Exception as e:
                logger.warning(f"[RESPONSE] Error checking if response necessary: {e}, defaulting to skip")
                return (False, "error_checking")
        
        # It's time to respond (2-3 messages have passed)
        logger.info(f"[RESPONSE] Time to respond (message {current_count}, {messages_since_response} since last)")
        self.last_response_message_count[chat_id] = current_count
        return (True, "interval_reached")
    
    def process_message(self, chat_id: int, message_text: str, from_phone: str, 
                       was_voice_message: bool = False, is_first_message: bool = False,
                       attachments: List[Dict] = None) -> Tuple[bool, str, Optional[List[str]]]:
        """
        Head Agent: Processes 1-on-1 message and calls appropriate tools
        Only responds every 2-3 messages AND when it's necessary
        
        Returns:
            (should_respond: bool, reason: str, response_messages: Optional[List[str]])
        """
        if not message_text:
            return (False, "empty_message", None), None
        
        # Check if we should respond now (every 2-3 messages + necessity check)
        should_respond, response_reason = self._should_respond_now(chat_id, message_text)
        
        if not should_respond:
            # Still track interests and add reactions, but don't send text response
            # Extract interests (always runs, even if not responding)
            if "extract_interests" in self.tools:
                try:
                    interests = extract_interests(message_text)
                    if interests:
                        interest_tracker.add_interests(from_phone, interests, chat_id)
                except:
                    pass
            
            # Add reaction if appropriate (always runs) - but NOT for voice messages
            reaction = None
            if "auto_reaction" in self.tools and not was_voice_message:
                try:
                    recent_context = []
                    if chat_id in conversation_history.histories:
                        recent_messages = list(conversation_history.histories[chat_id])[-5:]
                        for msg in recent_messages:
                            if msg.role == "user":
                                recent_context.append(msg.content)
                    reaction = determine_reaction(message_text, conversation_context=recent_context)
                    if reaction:
                        logger.info(f"[TOOLS] Determined reaction: {reaction} (skipping text response)")
                except:
                    pass
            
            # Return: (should_respond, reason, response_messages), reaction
            return (False, response_reason, None), reaction
        
        # Get known interests
        known_interests = list(interest_tracker.get_user_interests(from_phone))
        
        # Get conversation history
        history = []
        if chat_id:
            history = conversation_history.get_recent_history(chat_id, max_tokens=1000)
        
        # Step 1: Extract interests (always runs)
        interests = []
        if "extract_interests" in self.tools:
            try:
                interests = extract_interests(message_text)
                if interests:
                    logger.info(f"[TOOLS] Extracted interests: {interests}")
                    interest_tracker.add_interests(from_phone, interests, chat_id)
                    known_interests = list(interest_tracker.get_user_interests(from_phone))
            except Exception as e:
                logger.error(f"[ERROR] Error extracting interests: {e}")
        
        # Step 2: Generate response (always runs)
        response_messages = []
        if "gen_z_response" in self.tools:
            try:
                # Check if it's a question (for web search)
                is_question = (
                    "?" in message_text or 
                    any(word in message_text.lower() for word in [
                        "what", "when", "where", "who", "why", "how", 
                        "tell me", "search", "find", "look up"
                    ])
                )
                
                # Generate response
                response_messages = generate_catchy_message(
                    "response",
                    user_message=message_text,
                    is_voice_message=was_voice_message,
                    conversation_history=history,
                    is_first_message=is_first_message,
                    known_interests=known_interests
                )
                
                logger.info(f"[TOOLS] Generated Gen Z response: {len(response_messages)} messages")
            except Exception as e:
                logger.error(f"[ERROR] Error generating response: {e}", exc_info=True)
                response_messages = ["gotchu, what's up"]
        
        # Step 3: Add music recommendation if applicable (only if current message explicitly mentions music)
        if "music_recommendation" in self.tools:
            try:
                # Check if CURRENT message explicitly mentions music (not just past interests)
                current_message_lower = message_text.lower()
                
                # Explicit music keywords (not too broad)
                music_keywords = ["music", "song", "songs", "taylor", "swift", "listening to", "spotify", "apple music", "playlist", "album", "artist", "band"]
                
                # Explicit music requests
                explicit_music_requests = [
                    "music recommendation", "song recommendation", "recommend music", "recommend a song",
                    "what song", "what music", "need music", "want music", "give me music", "play music",
                    "music suggestions", "song suggestions", "music rec", "song rec"
                ]
                
                # Only add music if current message explicitly mentions music or asks for recommendations
                has_music_keyword = any(keyword in current_message_lower for keyword in music_keywords)
                has_explicit_request = any(phrase in current_message_lower for phrase in explicit_music_requests)
                
                if has_music_keyword or has_explicit_request:
                    response_messages = add_music_link_if_applicable(
                        response_messages,
                        known_interests,
                        "response",
                        message_text
                    )
                    logger.info(f"[TOOLS] Added music recommendation (current message about music)")
            except Exception as e:
                logger.error(f"[ERROR] Error adding music recommendation: {e}")
        
        # Step 4: Auto reaction (always runs) - uses LLM to understand intent
        # BUT: Never add reactions to voice/audio messages (takes too long)
        reaction = None
        if "auto_reaction" in self.tools and not was_voice_message:
            try:
                # Get recent conversation context for better intent understanding
                recent_context = []
                if chat_id in conversation_history.histories:
                    recent_messages = list(conversation_history.histories[chat_id])[-5:]  # Last 5 messages
                    for msg in recent_messages:
                        if msg.role == "user":
                            recent_context.append(msg.content)
                
                # Use LLM-based intent understanding for reactions
                reaction = determine_reaction(message_text, conversation_context=recent_context)
                if reaction:
                    logger.info(f"[TOOLS] Determined reaction: {reaction} (based on intent)")
            except Exception as e:
                logger.error(f"[ERROR] Error determining reaction: {e}")
        
        # Step 5: Group matching (runs if interests found)
        if interests and "group_matching" in self.tools:
            try:
                from api_client import api_client
                from config import SENDER_NUMBER
                
                # Check for matches and create/join groups
                existing_groups = interest_tracker.find_existing_groups_to_join(from_phone)
                if existing_groups:
                    group_id, shared_interests, group_chat_id = existing_groups[0]
                    if interest_tracker.add_member_to_group(from_phone, group_id):
                        logger.info(f"[TOOLS] Added user to existing group: {group_id}")
                        # Send message to the group about new member
                        try:
                            api_client.send_message(
                                chat_id=group_chat_id,
                                message_text="you got new friend with same interests haha"
                            )
                        except Exception as msg_error:
                            logger.error(f"[ERROR] Error sending message to group: {msg_error}")
                
                # Check for new group creation
                if not existing_groups:
                    group_candidates = interest_tracker.find_group_candidates(from_phone)
                    if group_candidates:
                        group_members, shared_interests = group_candidates
                        logger.info(f"[TOOLS] Found group candidates: {group_members}")
                        
                        # Check if group already exists (avoid duplicates)
                        existing_group = None
                        for gid, (name, members, _, _) in interest_tracker.groups.items():
                            if set(members) == set(group_members):
                                existing_group = gid
                                break
                        
                        if not existing_group:
                            # Create group chat via API
                            try:
                                member_phones = [p for p in group_members if p != SENDER_NUMBER]
                                
                                if len(member_phones) >= 2:
                                    group_name = interest_tracker._generate_group_name(shared_interests)
                                    shared_interests_str = ', '.join(shared_interests[:3])
                                    group_chat = api_client.create_chat(
                                        phone_numbers=member_phones,
                                        message_text=f"yo you both like {shared_interests_str} how interesting",
                                        send_from=SENDER_NUMBER,
                                        display_name=group_name
                                    )
                                    
                                    if group_chat and group_chat.get('data'):
                                        group_chat_id = group_chat['data'].get('id')
                                        if group_chat_id:
                                            interest_tracker.create_group(
                                                members=group_members,
                                                shared_interests=shared_interests,
                                                group_chat_id=group_chat_id,
                                                display_name=group_name
                                            )
                                            logger.info(f"[TOOLS] Created group chat '{group_name}' (ID: {group_chat_id})")
                            except Exception as group_error:
                                logger.error(f"[ERROR] Error creating group: {group_error}", exc_info=True)
            except Exception as e:
                logger.error(f"[ERROR] Error in group matching: {e}", exc_info=True)
        
        return (True, "gen_z_response", response_messages), reaction
    
    def get_reaction(self, message_text: str) -> Optional[str]:
        """Get reaction for a message"""
        # Use LLM-based intent understanding for reactions
        return determine_reaction(message_text, conversation_context=None)

