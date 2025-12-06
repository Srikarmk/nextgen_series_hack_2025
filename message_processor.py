"""
Message Processing Logic
Handles message processing, reactions, and interactions
"""
import time
import base64
from typing import Dict, Any, Optional
from app_logger import logger
from api_client import api_client
from agent import generate_catchy_message, extract_interests
from audio_processor import process_voice_message, text_to_speech, is_audio_attachment
from interest_tracker import interest_tracker
from conversation_history import conversation_history
from group_chat_handler import group_chat_handler
from one_on_one_handler import OneOnOneHandler
from reaction_utils import determine_reaction
from config import SENDER_NUMBER

# Initialize 1-on-1 handler
one_on_one_handler = OneOnOneHandler()




def process_message(event: Dict[str, Any], message_count: int) -> bool:
    """
    Process a single message event
    
    Args:
        event: The Kafka event data
        message_count: Sequential message number for logging
        
    Returns:
        bool: True if message was processed successfully, False otherwise
    """
    event_type = event.get('event_type', 'unknown')
    timestamp = event.get('created_at', 'N/A')
    
    logger.info(f"Message #{message_count} received - Type: {event_type}, Timestamp: {timestamp}")

    if event_type == 'message.received':
        data = event.get('data', {})
        from_phone = data.get('from_phone', '')
        chat_id = data.get('chat_id', '')
        message_text = data.get('text', '')
        message_id = data.get('id')  # Message ID for reactions
        attachments = data.get('attachments', [])

        logger.info(f"Message #{message_count} details - From: {from_phone}, Chat ID: {chat_id}, Message ID: {message_id}, Text: {message_text[:100]}...")
        
        # Process all messages from everyone (no phone number filtering)
        if not from_phone:
            logger.warning(f"[WARN]  Message #{message_count} - Missing from_phone, skipping")
            return True

        # Check for voice message attachments
        if attachments:
            logger.info(f"[ATTACH] Message #{message_count} has {len(attachments)} attachment(s)")
            
            # Log attachment details for debugging
            for i, att in enumerate(attachments):
                logger.debug(f"Attachment {i}: {att.get('filename', 'N/A')}, mime_type: {att.get('mime_type', 'N/A')}, has_data: {bool(att.get('data_base64'))}")
            
            # Process voice messages - transcribe and understand what user said
            # Only try if we have base64 data in attachments
            has_audio_data = any(
                is_audio_attachment(att) and att.get('data_base64') 
                for att in attachments
            )
            
            if has_audio_data:
                transcribed_text = process_voice_message(attachments)
                if transcribed_text:
                    logger.info(f"[AUDIO] Voice message transcribed: {transcribed_text}")
                    logger.info(f"[TEXT] Understanding what user said: {transcribed_text[:200]}...")
                    
                    # Use transcribed text as the message text
                    message_text = transcribed_text
                    # Update event data for processing
                    data['text'] = transcribed_text
                    event['data'] = data
                    
                    # Mark that this was a voice message for better context
                    data['_was_voice_message'] = True
                    event['data'] = data
                else:
                    logger.warning(f"[WARN]  Voice message detected but transcription failed. Will try to process with existing text if available.")
            else:
                logger.info(f"[ATTACH] Attachments found but no audio data_base64 available (might need to fetch from API)")

        # Mark chat as read
        if chat_id:
            api_client.mark_chat_as_read(chat_id)

        # Add reaction to the message based on content (if message_id is available)
        # This is handled by the tool calling system, but we keep it here as fallback
        # Note: Reactions are now handled by LLM-based intent understanding in one_on_one_handler
        if message_id and message_text:
            # Use LLM-based intent understanding (no context available in fallback)
            reaction = determine_reaction(message_text, conversation_context=None)
            if reaction:
                # Small delay to make it feel natural
                time.sleep(0.3)
                api_client.add_reaction(message_id, reaction)
        
        # Return True - actual reply handling is done in handle_message_and_reply
        return True

    elif event_type == 'reaction.received':
        data = event.get('data', {})
        reaction_type = data.get('reaction', 'unknown')
        message_id = data.get('chat_message_id', 'N/A')
        from_phone = data.get('from_phone', 'N/A')
        logger.info(f"[CHAT] Reaction received - Type: {reaction_type}, Message ID: {message_id}, From: {from_phone}")
        # Could add logic here to respond to reactions
        
    elif event_type == 'reaction.sent':
        data = event.get('data', {})
        reaction_type = data.get('reaction', 'unknown')
        message_id = data.get('chat_message_id', 'N/A')
        logger.debug(f"Reaction sent - Type: {reaction_type}, Message ID: {message_id}")

    elif event_type == 'typing_indicator.received':
        data = event.get('data', {})
        chat_id = data.get('chat_id', 'N/A')
        logger.info(f"[TYPING]  Someone is typing in chat {chat_id}")

    elif event_type == 'typing_indicator.removed':
        data = event.get('data', {})
        chat_id = data.get('chat_id', 'N/A')
        logger.debug(f"Typing stopped in chat {chat_id}")

    elif event_type == 'message.sent':
        logger.debug(f"Message sent event received")

    elif event_type == 'message.read':
        data = event.get('data', {})
        message_id = data.get('id', 'N/A')
        logger.debug(f"Message {message_id} was read")

    else:
        logger.info(f"[EVENT] Unhandled event type: {event_type}")

    return True


def send_multiple_messages(chat_id: int, messages: list, send_as_voice: bool = False) -> bool:
    """
    Send multiple messages separately like real texts
    
    Args:
        chat_id: The chat ID to send to
        messages: List of message strings to send
        send_as_voice: If True, convert text to speech and send as audio attachment
    
    Returns:
        bool: True if all messages sent successfully
    """
    if not messages:
        logger.warning("No messages to send")
        return False
    
    all_success = True
    for i, msg_text in enumerate(messages):
        if not msg_text or not msg_text.strip():
            continue
        
        # Show typing indicator for first message
        if i == 0:
            api_client.start_typing(chat_id)
            typing_delay = min(2.0, 0.5 + len(msg_text) * 0.02)
            time.sleep(typing_delay)
            api_client.stop_typing(chat_id)
        else:
            # Small delay between messages to feel natural
            time.sleep(0.5 + (len(msg_text) * 0.01))
        
        # Send message (text or voice - only first message as voice if requested)
        if send_as_voice and i == 0:
            tts_result = text_to_speech(msg_text, format="m4a")
            if tts_result:
                audio_data, mime_type, filename = tts_result
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                attachments = [{
                    "filename": filename,
                    "mime_type": mime_type,
                    "data_base64": audio_base64
                }]
                result = api_client.send_message(chat_id, " ", attachments=attachments)
            else:
                logger.warning("TTS failed, sending as text instead")
                result = api_client.send_message(chat_id, msg_text)
        else:
            # Send as text
            result = api_client.send_message(chat_id, msg_text)
        
        if result:
            logger.debug(f"Sent message {i+1}/{len(messages)} to chat {chat_id}")
        else:
            logger.error(f"Failed to send message {i+1}/{len(messages)} to chat {chat_id}")
            all_success = False
    
    if all_success:
        logger.info(f"Successfully sent {len(messages)} message(s) to chat {chat_id}")
    return all_success


def send_reply_with_typing(chat_id: int, message_text: str, send_as_voice: bool = False) -> bool:
    """
    Send a reply with typing indicator for natural feel
    
    Args:
        chat_id: The chat ID to send to
        message_text: The message text to send
        send_as_voice: If True, convert text to speech and send as audio attachment
    
    Returns:
        bool: True if successful
    """
    # Show typing indicator
    api_client.start_typing(chat_id)
    # Simulate typing time based on message length (roughly 50 WPM)
    typing_delay = min(2.0, 0.5 + len(message_text) * 0.02)
    time.sleep(typing_delay)
    api_client.stop_typing(chat_id)
    
    # Send message (text or voice)
    if send_as_voice:
        # Convert text to speech (returns m4a format)
        tts_result = text_to_speech(message_text, format="m4a")
        if tts_result:
            audio_data, mime_type, filename = tts_result
            # Encode audio to base64
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            # Create attachment with m4a format
            attachments = [{
                "filename": filename,
                "mime_type": mime_type,
                "data_base64": audio_base64
            }]
            
            # Send with audio attachment (API requires text field, so send a space)
            # The audio file is the main content, text is minimal for API requirement
            result = api_client.send_message(chat_id, " ", attachments=attachments)
        else:
            # Fallback to text if TTS fails
            logger.warning("TTS failed, sending as text instead")
            result = api_client.send_message(chat_id, message_text)
    else:
        # Send as text
        result = api_client.send_message(chat_id, message_text)
    
    if result:
        logger.info(f"Successfully sent reply to chat {chat_id} ({'voice' if send_as_voice else 'text'})")
        return True
    else:
        logger.error(f"Failed to send reply to chat {chat_id}")
        return False


def handle_message_and_reply(event: Dict[str, Any], message_count: int, 
                            message_lock_context) -> bool:
    """
    Handle a message event and generate/send a reply
    
    Args:
        event: The Kafka event data
        message_count: Sequential message number
        message_lock_context: MessageLock context manager (already acquired)
    
    Returns:
        bool: True if successful
    """
    data = event.get('data', {})
    from_phone = data.get('from_phone', '')
    chat_id = data.get('chat_id', '')
    message_text = data.get('text', '')
    attachments = data.get('attachments', [])
    
    logger.info(f"[OK] Message #{message_count} - Lock acquired, processing message from {from_phone}")

    # Check if this is a group chat or 1-on-1 chat
    is_group_chat = False
    group_name = None
    if chat_id:
        try:
            chat_id_int = int(chat_id) if chat_id else None
            if chat_id_int:
                # First check if we know this chat_id as a group from our tracker
                is_group_chat = interest_tracker.is_chat_id_a_group(chat_id_int)
                
                if is_group_chat:
                    group_info = interest_tracker.get_group_info_by_chat_id(chat_id_int)
                    if group_info:
                        _, group_name, _, _ = group_info
                        logger.info(f"[GROUP] Known group chat: {group_name}")
                
                # If not in tracker, check via API
                # Group = 3+ participants (2+ users + bot)
                # 1-on-1 = 2 participants (1 user + bot) = NOT a group
                if not is_group_chat:
                    chat_info = api_client.get_chat(chat_id_int)
                    if chat_info and chat_info.get('data'):
                        chat_data = chat_info['data']
                        chat_handles = chat_data.get('chat_handles', [])
                        num_participants = len(chat_handles)
                        
                        # Group needs 3+ participants (2+ users + bot)
                        # 2 participants = 1 user + bot = NOT a group
                        is_group_chat = num_participants >= 3
                        
                        if is_group_chat:
                            group_name = chat_data.get('display_name', 'Unnamed Group')
                            num_users = num_participants - 1  # Subtract bot
                            logger.info(f"[GROUP] Detected group chat via API: {group_name} ({num_participants} participants = {num_users} users + bot)")
                        else:
                            logger.info(f"[CHAT] Detected 1-on-1 chat via API ({num_participants} participants = 1 user + bot)")
        except (ValueError, TypeError) as e:
            logger.warning(f"[WARN]  Error converting chat_id to int: {e}")
        except Exception as e:
            logger.warning(f"[WARN]  Error checking if chat is group: {e}")
    
    if is_group_chat:
        logger.info(f"[GROUP] Message #{message_count} - This is a GROUP chat")
    else:
        logger.info(f"[CHAT] Message #{message_count} - This is a 1-on-1 chat")

    # Check if original message was a voice message
    was_voice_message = any(is_audio_attachment(att) for att in attachments) if attachments else False
    
    # If it's a voice message but no text, try to transcribe
    if was_voice_message and not message_text:
        logger.info(f"[AUDIO] Voice message detected, checking for audio data...")
        
        # Check if attachments have base64 data
        has_audio_data = any(
            is_audio_attachment(att) and att.get('data_base64') 
            for att in attachments
        )
        
        if has_audio_data:
            logger.info(f"Attempting to transcribe voice message...")
            transcribed_text = process_voice_message(attachments)
            if transcribed_text:
                message_text = transcribed_text
                logger.info(f"[AUDIO] Transcribed voice message: {message_text[:100]}...")
                
                # Generate TLDR for long voice messages in group chats
                if is_group_chat and len(transcribed_text) > 100:
                    tldr = group_chat_handler.generate_voice_tldr(chat_id, transcribed_text)
                    if tldr:
                        logger.info(f"[TEXT] Generated TLDR for voice message: {tldr}")
                        # Could send TLDR as separate message or append
            else:
                logger.warning("[WARN]  Transcription failed. Note: Kafka events may not include full attachment data.")
                # Try to fetch message from API to get attachment data
                message_id = data.get('id')
                if message_id and chat_id:
                    logger.info(f"Attempting to fetch message {message_id} from API to get attachment data...")
                    try:
                        full_message = api_client.get_message(chat_id, message_id)
                        if full_message and full_message.get('data'):
                            msg_data = full_message['data']
                            api_attachments = msg_data.get('attachments', [])
                            if api_attachments:
                                logger.info(f"Found {len(api_attachments)} attachment(s) in API response")
                                # Try transcribing with API attachment data
                                transcribed_text = process_voice_message(api_attachments)
                                if transcribed_text:
                                    message_text = transcribed_text
                                    logger.info(f"[AUDIO] Transcribed from API data: {message_text[:100]}...")
                    except Exception as e:
                        logger.warning(f"Failed to fetch message from API: {e}")
                
                # If still no transcription, use fallback
                if not message_text:
                    logger.info("Using fallback response for voice message")
                    message_text = "got your voice message"
        else:
            logger.info("[INFO]  Voice message detected but no base64 data in Kafka event. Trying to fetch from API...")
            # Try to fetch message from API
            message_id = data.get('id')
            if message_id and chat_id:
                logger.info(f"[FETCH] Fetching message {message_id} from chat {chat_id} via API...")
                try:
                    full_message = api_client.get_message(chat_id, message_id)
                    if full_message:
                        logger.debug(f"[API] API response: {full_message}")
                        if full_message.get('data'):
                            msg_data = full_message['data']
                            api_attachments = msg_data.get('attachments', [])
                            logger.info(f"[ATTACH] Found {len(api_attachments)} attachment(s) in API response")
                            if api_attachments:
                                # Check if attachments have base64 data
                                for i, att in enumerate(api_attachments):
                                    filename = att.get('filename', 'unknown')
                                    mime_type = att.get('mime_type', 'unknown')
                                    has_data = bool(att.get('data_base64'))
                                    data_length = len(att.get('data_base64', '')) if att.get('data_base64') else 0
                                    logger.info(f"[ATTACH] Attachment #{i+1}: filename='{filename}', mime='{mime_type}', has_base64={has_data}, data_len={data_length}")
                                    logger.debug(f"[ATTACH] Full attachment keys: {list(att.keys())}")
                                    # Check if attachment has URL instead of base64
                                    if not has_data:
                                        # Check for URL or download link
                                        attachment_url = att.get('url') or att.get('download_url') or att.get('file_url')
                                        if attachment_url:
                                            logger.info(f"[ATTACH] Attachment has URL instead of base64: {attachment_url}")
                                            # TODO: Download from URL if needed
                                
                                transcribed_text = process_voice_message(api_attachments)
                                if transcribed_text:
                                    message_text = transcribed_text
                                    logger.info(f"[AUDIO] [OK] Transcribed from API: {message_text[:100]}...")
                                else:
                                    logger.warning("[WARN]  Transcription failed even with API data - checking why...")
                                    # Debug why transcription failed
                                    for att in api_attachments:
                                        if is_audio_attachment(att):
                                            base64_data = att.get('data_base64')
                                            if not base64_data:
                                                logger.warning(f"[WARN]  Audio attachment missing data_base64 field")
                                            else:
                                                logger.warning(f"[WARN]  Audio attachment has data but transcription failed - data length: {len(base64_data)}")
                            else:
                                logger.warning("[WARN]  No attachments found in API response")
                        else:
                            logger.warning(f"[WARN]  API response missing 'data' field: {full_message}")
                    else:
                        logger.warning("[WARN]  API returned None or empty response")
                except Exception as e:
                    logger.error(f"[ERROR] Failed to fetch message from API: {e}", exc_info=True)
            else:
                logger.warning(f"[WARN]  Cannot fetch from API - missing message_id ({message_id}) or chat_id ({chat_id})")
            
            # Fallback if API fetch fails
            if not message_text:
                logger.warning("[WARN]  Using fallback text - voice transcription failed")
                message_text = "got your voice message"
    
    # If we still don't have message_text, use a fallback
    if not message_text:
        logger.info("[INFO]  No message text available, using fallback")
        message_text = "hey"
    
    # Check if this is the first message (no conversation history or very short)
    is_first_message = False
    if chat_id:
        history_length = conversation_history.get_history_length(chat_id)
        # If history is empty or only has 1-2 messages (just user's message), it's likely first interaction
        is_first_message = history_length <= 1
        logger.debug(f"[STATS] Chat {chat_id} history length: {history_length}, is_first_message: {is_first_message}")
    
    # Store user message in conversation history
    if message_text and chat_id:
        conversation_history.add_message(chat_id, "user", message_text)
        # Also track in group chat handler if it's a group
        if is_group_chat:
            timestamp = time.time()
            group_chat_handler.add_message(chat_id, from_phone, message_text, is_bot=False, timestamp=timestamp)
    
    # Log what we're responding to
    chat_type = "GROUP" if is_group_chat else "1-on-1"
    if was_voice_message:
        logger.info(f"[AUDIO] Processing voice message ({chat_type}) - User said: {message_text[:100]}...")
    else:
        logger.info(f"[CHAT] Processing text message ({chat_type}) - User said: {message_text[:100]}...")
    
    # Suggest tone indicators for ambiguous messages (in group chats)
    if is_group_chat and message_text:
        tone_suggestion = group_chat_handler.suggest_tone_indicator(message_text)
        if tone_suggestion:
            logger.debug(f"[SUGGEST] Tone suggestion: {tone_suggestion}")
            # Could send as separate message or include in response
    
    # Note: Interest extraction and group matching are now handled by tool calling system
    # (in one_on_one_handler for 1-on-1 chats, or group_chat_handler for group chats)
    
    # Check if bot should respond (group chat logic)
    should_respond = True
    response_reason = "normal_response"
    reply = None
    
    if is_group_chat:
        should_respond, response_reason, reply = group_chat_handler.should_respond(chat_id, message_text, from_phone)
        
        if not should_respond:
            logger.info(f"[SKIP]  Message #{message_count} - Skipping reply in group chat (reason: {response_reason})")
            return True  # Not an error, just configured to not reply
        
        # If handler already generated a response, use it
        if reply:
            logger.info(f"[OK] Message #{message_count} - Will respond in group chat (reason: {response_reason})")
            # reply is already set, continue to sending
        else:
            # Handler didn't generate response, need to generate one
            logger.info(f"[OK] Message #{message_count} - Will respond in group chat (reason: {response_reason})")
            
            # Get conversation history for context
            history = []
            if chat_id:
                history = conversation_history.get_recent_history(chat_id, max_tokens=1000)
                logger.debug(f"[HISTORY] Using {len(history)} messages from conversation history")
            
            try:
                reply = generate_catchy_message(
                    "response", 
                    user_message=message_text, 
                    is_voice_message=was_voice_message,
                    conversation_history=history,
                    is_first_message=is_first_message,
                    known_interests=known_interests
                )
                logger.info(f"Message #{message_count} - Generated reply: {reply}")
            except Exception as gen_error:
                logger.error(f"[ERROR] Message #{message_count} - Error generating reply: {gen_error}", exc_info=True)
                return False
    else:
        # 1-on-1 chat - use head agent with tool calling
        logger.info(f"[1-ON-1] Message #{message_count} - Processing with tool calling")
        try:
            # Use 1-on-1 handler with tool calling
            result = one_on_one_handler.process_message(
                chat_id=chat_id,
                message_text=message_text,
                from_phone=from_phone,
                was_voice_message=was_voice_message,
                is_first_message=is_first_message,
                attachments=attachments
            )
            
            (should_respond, response_reason, reply), reaction = result
            
            if not should_respond:
                logger.info(f"[SKIP] Message #{message_count} - Not responding (reason: {response_reason})")
                return True
            
            logger.info(f"[1-ON-1] Message #{message_count} - Tool calling result: {response_reason}")
            
            # Add reaction if determined - but NOT for voice messages (takes too long)
            message_id = data.get('id')
            if reaction and message_id and not was_voice_message:
                time.sleep(0.3)
                api_client.add_reaction(message_id, reaction)
            elif was_voice_message and reaction:
                logger.debug(f"[REACTION] Skipping reaction for voice message (takes too long)")
                
        except Exception as gen_error:
            logger.error(f"[ERROR] Message #{message_count} - Error in 1-on-1 tool calling: {gen_error}", exc_info=True)
            return False

    # If original message was voice, reply with voice too (optional - you can change this)
    send_as_voice = was_voice_message  # Reply in same format as received
    
    # Handle reply as list of messages
    if isinstance(reply, list):
        # Send multiple messages separately
        success = send_multiple_messages(chat_id, reply, send_as_voice=send_as_voice)
        
        # Store all messages in conversation history (join for history)
        if chat_id and reply:
            full_reply_text = " ".join(reply)  # Join for conversation history
            conversation_history.add_message(chat_id, "assistant", full_reply_text)
            # Also track in group chat handler if it's a group
            if is_group_chat:
                for msg in reply:
                    group_chat_handler.add_message(chat_id, SENDER_NUMBER, msg, is_bot=True)
    else:
        # Fallback: handle as single message (for backward compatibility)
        success = send_reply_with_typing(chat_id, reply, send_as_voice=send_as_voice)
        if chat_id and reply:
            conversation_history.add_message(chat_id, "assistant", reply)
            if is_group_chat:
                group_chat_handler.add_message(chat_id, SENDER_NUMBER, reply, is_bot=True)

    if success:
        logger.info(f"[OK] Message #{message_count} - Successfully sent reply to chat {chat_id}")
        return True
    else:
        logger.error(f"[ERROR] Message #{message_count} - Failed to send reply to chat {chat_id}")
        return False

