"""
Series API Client - All API functions from the spec
"""
import logging
import requests
from typing import Optional, Dict, Any, List
from config import SERIES_API_KEY, SERIES_BASE_URL

logger = logging.getLogger(__name__)


class SeriesAPIClient:
    """Client for interacting with the Series iMessage API"""
    
    def __init__(self):
        self.base_url = SERIES_BASE_URL.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {SERIES_API_KEY}",
            "Content-Type": "application/json"
        }
    
    # =========================================================================
    # CHAT OPERATIONS
    # =========================================================================
    
    def create_chat(self, phone_numbers: List[str], message_text: str, 
                   send_from: str, display_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Create a chat and send initial message
        
        Args:
            phone_numbers: List of recipient phone numbers (E.164 format)
            message_text: Initial message text
            send_from: Phone number to send from (E.164 format)
            display_name: Optional chat display name (for group chats)
        
        Returns:
            dict: API response with chat and message details
        """
        url = f"{self.base_url}/api/chats"
        payload = {
            "send_from": send_from,
            "chat": {
                "phone_numbers": phone_numbers
            },
            "message": {
                "text": message_text
            }
        }
        
        if display_name:
            payload["chat"]["display_name"] = display_name
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error creating chat: {e}")
            return None
    
    def get_chat(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """Get chat details"""
        url = f"{self.base_url}/api/chats/{chat_id}"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting chat: {e}")
            return None
    
    def list_chats(self, phone_number: Optional[str] = None, 
                   page: int = 1, per_page: int = 25) -> Optional[Dict[str, Any]]:
        """
        List chats with optional filtering and pagination
        
        Args:
            phone_number: Filter by participant phone number (E.164)
            page: Page number (default 1)
            per_page: Items per page (max 100, default 25)
        """
        url = f"{self.base_url}/api/chats"
        params = {"page": page, "per_page": min(per_page, 100)}
        if phone_number:
            params["phone_number"] = phone_number
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error listing chats: {e}")
            return None
    
    def mark_chat_as_read(self, chat_id: int) -> bool:
        """Mark all messages in a chat as read"""
        url = f"{self.base_url}/api/chats/{chat_id}/mark_as_read"
        try:
            response = requests.put(url, headers=self.headers, timeout=5)
            response.raise_for_status()
            logger.debug(f"Marked chat {chat_id} as read")
            return True
        except Exception as e:
            logger.warning(f"Failed to mark chat as read: {e}")
            return False
    
    # =========================================================================
    # MESSAGE OPERATIONS
    # =========================================================================
    
    def send_message(self, chat_id: int, message_text: str, 
                    attachments: Optional[List[Dict[str, str]]] = None) -> Optional[Dict[str, Any]]:
        """
        Send a message to a chat
        
        Args:
            chat_id: The chat ID
            message_text: Message text
            attachments: Optional list of attachments with:
                - filename: str
                - mime_type: str
                - data_base64: str (base64 encoded, no data URI prefix)
        
        Returns:
            dict: API response with message details
        """
        url = f"{self.base_url}/api/chats/{chat_id}/chat_messages"
        payload = {
            "message": {
                "text": message_text
            }
        }
        
        if attachments:
            payload["message"]["attachments"] = attachments
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response is not None:
                logger.error(f"Error sending message: {e.response.status_code} - {e.response.text}")
            else:
                logger.error(f"Error sending message: {e}")
            return None
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return None
    
    def get_message(self, chat_id: int, message_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific message"""
        url = f"{self.base_url}/api/chats/{chat_id}/chat_messages/{message_id}"
        try:
            logger.debug(f"🔍 GET {url}")
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            result = response.json()
            logger.debug(f"✅ Got message {message_id}: {result}")
            return result
        except requests.exceptions.HTTPError as e:
            if e.response is not None:
                logger.error(f"❌ Error getting message: {e.response.status_code} - {e.response.text}")
            else:
                logger.error(f"❌ Error getting message: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Error getting message: {e}", exc_info=True)
            return None
    
    def list_messages(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """List all messages in a chat"""
        url = f"{self.base_url}/api/chats/{chat_id}/chat_messages"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error listing messages: {e}")
            return None
    
    def edit_message(self, chat_id: int, message_id: int, new_text: str) -> bool:
        """
        Edit a message (within 15 minutes of creation)
        
        Args:
            chat_id: The chat ID
            message_id: The message ID to edit
            new_text: New message text
        
        Returns:
            bool: True if successful
        """
        url = f"{self.base_url}/api/chats/{chat_id}/chat_messages/{message_id}/edit"
        payload = {"text": new_text}
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            response.raise_for_status()
            logger.info(f"Edited message {message_id} in chat {chat_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to edit message: {e}")
            return False
    
    def delete_message(self, chat_id: int, message_id: int) -> bool:
        """Delete a message"""
        url = f"{self.base_url}/api/chats/{chat_id}/chat_messages/{message_id}"
        try:
            response = requests.delete(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            logger.info(f"Deleted message {message_id} from chat {chat_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to delete message: {e}")
            return False
    
    # =========================================================================
    # REACTION OPERATIONS
    # =========================================================================
    
    def add_reaction(self, message_id: int, reaction_type: str) -> bool:
        """
        Add a reaction to a message
        
        Args:
            message_id: The message ID to react to
            reaction_type: One of: love, like, dislike, laugh, emphasize, question
        
        Returns:
            bool: True if successful
        """
        url = f"{self.base_url}/api/chat_messages/{message_id}/reactions"
        payload = {
            "operation": "add",
            "type": reaction_type
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=5)
            response.raise_for_status()
            logger.info(f"Added {reaction_type} reaction to message {message_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to add reaction: {e}")
            return False
    
    def remove_reaction(self, message_id: int, reaction_type: str) -> bool:
        """Remove a reaction from a message"""
        url = f"{self.base_url}/api/chat_messages/{message_id}/reactions"
        payload = {
            "operation": "remove",
            "type": reaction_type
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=5)
            response.raise_for_status()
            logger.info(f"Removed {reaction_type} reaction from message {message_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to remove reaction: {e}")
            return False
    
    def get_reaction(self, reaction_id: int) -> Optional[Dict[str, Any]]:
        """Get reaction details"""
        url = f"{self.base_url}/api/chat_message_reactions/{reaction_id}"
        try:
            response = requests.get(url, headers=self.headers, timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(f"Failed to get reaction: {e}")
            return None
    
    # =========================================================================
    # TYPING INDICATORS
    # =========================================================================
    
    def start_typing(self, chat_id: int) -> bool:
        """Start typing indicator in a chat"""
        url = f"{self.base_url}/api/chats/{chat_id}/start_typing"
        try:
            response = requests.post(url, headers=self.headers, timeout=5)
            response.raise_for_status()
            logger.debug(f"Started typing indicator for chat {chat_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to start typing indicator: {e}")
            return False
    
    def stop_typing(self, chat_id: int) -> bool:
        """Stop typing indicator in a chat"""
        url = f"{self.base_url}/api/chats/{chat_id}/stop_typing"
        try:
            response = requests.delete(url, headers=self.headers, timeout=5)
            response.raise_for_status()
            logger.debug(f"Stopped typing indicator for chat {chat_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to stop typing indicator: {e}")
            return False
    
    # =========================================================================
    # UTILITY OPERATIONS
    # =========================================================================
    
    def check_imessage_availability(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """
        Check if a phone number supports iMessage
        
        Args:
            phone_number: Phone number in E.164 format (with or without +)
        
        Returns:
            dict: API response with availability info
        """
        url = f"{self.base_url}/api/i_message_availability/check"
        payload = {"phone_number": phone_number}
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(f"Failed to check iMessage availability: {e}")
            return None


# Global instance
api_client = SeriesAPIClient()

