"""
Reaction Utilities
Helper functions for determining reactions to messages using LLM-based intent understanding
"""
from typing import Optional
from app_logger import logger
from openai import OpenAI
from config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)


def determine_reaction(message_text: str, conversation_context: list = None) -> Optional[str]:
    """
    Determine what reaction to add based on user intent using LLM
    Only react when it genuinely makes sense contextually - don't react to everything
    
    Args:
        message_text: The user's message
        conversation_context: Optional list of recent messages for context
        
    Returns: 'love', 'like', 'laugh', 'question', 'emphasize', or None
    """
    if not message_text or len(message_text.strip()) < 3:
        return None
    
    # Don't react to very short messages (1-2 words) - they're usually just acknowledgments
    words = message_text.strip().split()
    if len(words) <= 2:
        return None
    
    try:
        # Build context if available
        context_str = ""
        if conversation_context:
            recent = conversation_context[-3:] if len(conversation_context) > 3 else conversation_context
            context_str = "\n\nRecent conversation:\n" + "\n".join([f"- {msg}" for msg in recent])
        
        # Use LLM to understand intent and determine if a reaction makes sense
        system_prompt = """You are analyzing a user message to determine if it needs a reaction emoji.

Available reactions:
- "love": User expressed strong positive emotion, love, appreciation, or said something very sweet/affectionate
- "like": User thanked you, gave a compliment, or showed appreciation
- "laugh": User said something funny, made a joke, or used humor
- "question": User asked a genuine question that needs an answer (NOT greetings like "how's it going" or rhetorical questions)
- "emphasize": User made a strong statement, expressed excitement, or used emphasis (!!!, omg, wow, etc.)
- "none": No reaction needed - normal conversation, statements, greetings, or casual messages

IMPORTANT RULES:
1. DON'T react to every question - only react if it's a genuine question that shows the user wants an answer
2. DON'T react to greetings like "how's it going", "what's up", "hey", etc.
3. DON'T react to normal statements or casual conversation
4. Only react when the user's intent clearly calls for it (genuine thanks, jokes, strong emotions, real questions)
5. Be selective - most messages don't need reactions

Return ONLY the reaction type (love, like, laugh, question, emphasize, or none) - nothing else."""

        user_prompt = f"User message: {message_text}{context_str}\n\nShould this message get a reaction? If yes, which one? If no, return 'none'."
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,  # Lower temperature for more consistent decisions
            max_tokens=10,  # Just need the reaction type
            timeout=5
        )
        
        reaction = response.choices[0].message.content.strip().lower()
        
        # Validate reaction type
        valid_reactions = ["love", "like", "laugh", "question", "emphasize"]
        if reaction in valid_reactions:
            logger.debug(f"[REACTION] LLM determined reaction: {reaction} for message: {message_text[:50]}")
            return reaction
        else:
            # LLM said "none" or something else - no reaction
            logger.debug(f"[REACTION] No reaction needed for: {message_text[:50]}")
            return None
            
    except Exception as e:
        logger.warning(f"[REACTION] Error determining reaction with LLM: {e}, falling back to no reaction")
        # Fallback: only react to very explicit cases
        text_lower = message_text.lower()
        
        # Only very explicit cases in fallback
        if any(word in text_lower for word in ["thanks", "thank you", "ty"]):
            return "like"
        if any(word in text_lower for word in ["lol", "lmao", "haha", "😂"]):
            return "laugh"
        if any(word in text_lower for word in ["love", "❤️", "💕"]):
            return "love"
        
        # Don't react otherwise in fallback
        return None

