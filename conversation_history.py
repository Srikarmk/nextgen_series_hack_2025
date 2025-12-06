"""
Conversation History Tracker
Stores and manages conversation history for each chat (up to ~1000 tokens)
"""
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import deque
from app_logger import logger


@dataclass
class Message:
    """Represents a single message in conversation history"""
    role: str  # "user" or "assistant"
    content: str
    timestamp: float
    
    def to_dict(self) -> dict:
        """Convert to dict format for OpenAI API"""
        return {
            "role": self.role,
            "content": self.content
        }
    
    def estimate_tokens(self) -> int:
        """Rough token estimate: ~4 characters per token"""
        return len(self.content) // 4


class ConversationHistory:
    """Manages conversation history for each chat"""
    
    def __init__(self, max_tokens: int = 1000):
        # chat_id -> deque of Message objects
        self.histories: Dict[int, deque] = {}
        self.max_tokens = max_tokens
    
    def add_message(self, chat_id: int, role: str, content: str):
        """
        Add a message to conversation history
        
        Args:
            chat_id: Chat ID
            role: "user" or "assistant"
            content: Message content
        """
        if chat_id not in self.histories:
            self.histories[chat_id] = deque(maxlen=100)  # Max 100 messages
        
        message = Message(
            role=role,
            content=content,
            timestamp=time.time()
        )
        
        self.histories[chat_id].append(message)
        logger.debug(f"[CHAT] Added {role} message to chat {chat_id} history")
    
    def get_recent_history(self, chat_id: int, max_tokens: Optional[int] = None) -> List[dict]:
        """
        Get recent conversation history up to max_tokens
        
        Args:
            chat_id: Chat ID
            max_tokens: Maximum tokens (default: self.max_tokens)
            
        Returns:
            List of message dicts in OpenAI format
        """
        if max_tokens is None:
            max_tokens = self.max_tokens
        
        if chat_id not in self.histories or not self.histories[chat_id]:
            return []
        
        messages = list(self.histories[chat_id])
        result = []
        total_tokens = 0
        
        # Start from most recent and work backwards
        for message in reversed(messages):
            msg_tokens = message.estimate_tokens()
            if total_tokens + msg_tokens > max_tokens:
                break
            result.insert(0, message.to_dict())
            total_tokens += msg_tokens
        
        logger.debug(f"[HISTORY] Retrieved {len(result)} messages ({total_tokens} tokens) from chat {chat_id} history")
        return result
    
    def clear_history(self, chat_id: int):
        """Clear conversation history for a chat"""
        if chat_id in self.histories:
            del self.histories[chat_id]
            logger.info(f"[CLEAR]  Cleared history for chat {chat_id}")
    
    def get_history_length(self, chat_id: int) -> int:
        """Get number of messages in history"""
        if chat_id not in self.histories:
            return 0
        return len(self.histories[chat_id])
    
    def get_total_tokens(self, chat_id: int) -> int:
        """Get estimated total tokens for a chat"""
        if chat_id not in self.histories:
            return 0
        return sum(msg.estimate_tokens() for msg in self.histories[chat_id])


# Singleton instance
conversation_history = ConversationHistory(max_tokens=1000)

