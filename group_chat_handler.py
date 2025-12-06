"""
Advanced Group Chat Handler
Comprehensive Gen Z native features for group chats
Uses head agent pattern with tools.json for tool selection
"""
import time
import random
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set, Any
from collections import defaultdict, deque
from app_logger import logger
from agent import generate_catchy_message
from api_client import api_client
from openai import OpenAI
from config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)


class GroupChatHandler:
    """Advanced group chat handler with vibe detection, lore, and social features"""
    
    def __init__(self):
        # Load group tools from tools.json
        tools_path = os.path.join(os.path.dirname(__file__), "tools.json")
        try:
            with open(tools_path, 'r') as f:
                tools_data = json.load(f)
                # Load only group tools, not 1-on-1 tools
                self.tools = {tool['id']: tool for tool in tools_data.get('group_tools', [])}
                logger.info(f"[TOOLS] Loaded {len(self.tools)} group tools from tools.json")
        except Exception as e:
            logger.error(f"[ERROR] Failed to load tools.json: {e}")
            self.tools = {}
        
        # Message tracking
        self.recent_messages: Dict[int, deque] = {}  # chat_id -> deque of messages
        self.max_messages = 200  # Keep more messages for lore
        
        # Vibe & Mood tracking
        self.vibe_history: Dict[int, List[Dict]] = {}  # chat_id -> vibe snapshots
        self.aura_history: Dict[int, List[Dict]] = {}  # chat_id -> aura readings
        
        # Lore & Memory system
        self.lore: Dict[int, Dict[str, Any]] = {}  # chat_id -> lore entries
        self.core_memories: Dict[int, List[Dict]] = {}  # chat_id -> pinned memories
        self.user_activity: Dict[int, Dict[str, float]] = {}  # chat_id -> {phone: last_seen}
        
        # Decision & Coordination
        self.active_polls: Dict[int, Dict] = {}  # chat_id -> poll data
        self.anonymous_votes: Dict[int, Dict] = {}  # chat_id -> vote data
        self.accountability_tasks: Dict[int, List[Dict]] = {}  # chat_id -> tasks
        
        # Social Dynamics
        self.celebration_queue: Dict[int, List[Dict]] = {}  # chat_id -> celebrations
        self.ghost_detection: Dict[int, Dict[str, float]] = {}  # chat_id -> {phone: last_active}
        self.tension_tracker: Dict[int, float] = {}  # chat_id -> tension_score
        
        # Entertainment
        self.active_stories: Dict[int, List[str]] = {}  # chat_id -> story lines
        self.active_versus: Dict[int, Dict] = {}  # chat_id -> versus bracket
        
        # Gamification
        self.chat_streaks: Dict[int, int] = {}  # chat_id -> current streak
        self.achievements: Dict[int, Dict[str, Set[str]]] = {}  # chat_id -> {achievement: {users}}
        self.prediction_markets: Dict[int, Dict] = {}  # chat_id -> market data
        
        # Time zones (placeholder - would need user timezone data)
        self.user_timezones: Dict[str, str] = {}  # phone -> timezone
        
        # Story mode state
        self.story_mode_active: Dict[int, bool] = {}  # chat_id -> bool
        
    def add_message(self, chat_id: int, from_phone: str, text: str, is_bot: bool = False, timestamp: float = None):
        """Add a message to the chat history"""
        if chat_id not in self.recent_messages:
            self.recent_messages[chat_id] = deque(maxlen=self.max_messages)
        
        if timestamp is None:
            timestamp = time.time()
        
        msg = {
            "from": from_phone,
            "text": text,
            "is_bot": is_bot,
            "timestamp": timestamp
        }
        
        self.recent_messages[chat_id].append(msg)
        
        # Update user activity
        if not is_bot:
            if chat_id not in self.user_activity:
                self.user_activity[chat_id] = {}
            self.user_activity[chat_id][from_phone] = timestamp
            
            # Update ghost detection
            if chat_id not in self.ghost_detection:
                self.ghost_detection[chat_id] = {}
            self.ghost_detection[chat_id][from_phone] = timestamp
        
        # Auto-detect celebrations
        if not is_bot:
            self._detect_celebration(chat_id, from_phone, text)
        
        # Update tension tracker
        self._update_tension(chat_id, text)
    
    def get_recent_messages(self, chat_id: int, limit: int = 50) -> List[Dict]:
        """Get recent messages from a chat"""
        if chat_id not in self.recent_messages:
            return []
        messages = list(self.recent_messages[chat_id])
        return messages[-limit:]
    
    def _build_tool_functions(self) -> list:
        """Build OpenAI function definitions from tools.json"""
        functions = []
        for tool_id, tool in self.tools.items():
            if tool.get('auto_trigger', False):
                continue  # Skip auto-triggered tools
            
            # Build function schema
            properties = {
                "chat_id": {
                    "type": "integer",
                    "description": "The chat ID where the message was sent"
                }
            }
            required = ["chat_id"]
            
            # Add tool-specific parameters
            if tool_id == "roast":
                properties["target"] = {
                    "type": "string",
                    "description": "The person or thing to roast (extracted from message)"
                }
                properties["from_phone"] = {
                    "type": "string",
                    "description": "Phone number of the user requesting the roast"
                }
                required.extend(["target", "from_phone"])
            elif tool_id == "hype_train":
                properties["target"] = {
                    "type": "string",
                    "description": "The person to hype up (extracted from message)"
                }
                required.append("target")
            elif tool_id == "generate_catchup":
                properties["from_phone"] = {
                    "type": "string",
                    "description": "Phone number of the user requesting catchup"
                }
                required.append("from_phone")
            elif tool.get('extract_topic'):
                properties["topic"] = {
                    "type": "string",
                    "description": f"Topic extracted from the message (for {tool.get('name', tool_id)})"
                }
                required.append("topic")
            elif tool_id in ["pin_core_memory"]:
                properties["message_text"] = {
                    "type": "string",
                    "description": "The full message text for context"
                }
                required.append("message_text")
            
            # Build comprehensive description for LLM
            description_parts = [tool.get('description', '')]
            
            # Add when_to_use if available
            if tool.get('when_to_use'):
                description_parts.append(f"When to use: {tool.get('when_to_use')}")
            
            # Add user_intent_patterns if available
            if tool.get('user_intent_patterns'):
                patterns = ', '.join(tool.get('user_intent_patterns', []))
                description_parts.append(f"User intent patterns: {patterns}")
            
            # Add example if available
            if tool.get('example_usage'):
                description_parts.append(f"Example: {tool.get('example_usage')}")
            
            full_description = " ".join(description_parts)
            
            functions.append({
                "type": "function",
                "function": {
                    "name": tool_id,
                    "description": full_description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required
                    }
                }
            })
        
        return functions
    
    def should_respond(self, chat_id: int, message_text: str, from_phone: str) -> Tuple[bool, str, Optional[str]]:
        """
        Head Agent: Uses LLM to intelligently select which tool to call
        Uses OpenAI function calling instead of text matching
        
        Returns:
            (should_respond: bool, reason: str, response_text: Optional[str])
        """
        if not message_text:
            return (False, "empty_message", None)
        
        text_lower = message_text.lower().strip()
        
        # Get recent messages for context
        recent_messages = self.get_recent_messages(chat_id, limit=5)
        context = " | ".join([m['text'][:100] for m in recent_messages[-3:] if not m.get('is_bot', False)])
        
        # Build tool functions for OpenAI
        tools = self._build_tool_functions()
        
        if not tools:
            logger.warning("[TOOLS] No tools available for LLM selection")
            return (False, "no_tools", None)
        
        # Prepare system message with detailed tool descriptions from tools.json
        system_prompt = """You are Jada, an AI assistant for group chats. Your job is to understand what the user wants and select the appropriate tool/function to call.

You have access to various group chat tools. Read the tool descriptions carefully and understand when to use each one. The tool descriptions include detailed information about user intent patterns, when to use each tool, and examples.

IMPORTANT: 
- Read each tool's description, when_to_use, and user_intent_patterns to understand when to call it
- Users might phrase things differently than exact triggers - understand the intent
- Extract parameters from messages (e.g., who to roast, what to compare, what topic for lore)
- If the message doesn't match any tool intent, don't call any function (return null)
- Be smart about understanding context and user intent

The available tools are defined in the function definitions below. Each tool has a detailed description explaining when and how to use it."""
        
        # Prepare user message with context
        user_message = f"User message: {message_text}"
        if context:
            user_message += f"\n\nRecent context: {context}"
        
        try:
            # Call OpenAI with function calling
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                tools=tools,
                tool_choice="auto",  # Let model decide
                temperature=0.3,  # Lower temperature for more consistent tool selection
                max_tokens=150,
                timeout=10
            )
            
            message = response.choices[0].message
            
            # Check if model wants to call a function
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    tool_id = tool_call.function.name
                    
                    if tool_id not in self.tools:
                        logger.warning(f"[TOOLS] LLM selected unknown tool: {tool_id}")
                        continue
                    
                    tool = self.tools[tool_id]
                    method_name = tool.get('method')
                    
                    if not method_name or not hasattr(self, method_name):
                        logger.warning(f"[TOOLS] Tool {tool_id} has invalid method: {method_name}")
                        continue
                    
                    method = getattr(self, method_name)
                    
                    # Parse arguments from LLM
                    import json
                    try:
                        args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError as e:
                        logger.error(f"[ERROR] Failed to parse tool arguments: {e}")
                        continue
                    
                    # Call the method with parsed arguments
                    try:
                        # Handle special cases based on tool configuration
                        if tool_id == "roast":
                            result = method(chat_id, args.get('target', ''), args.get('from_phone', from_phone))
                        elif tool_id == "hype_train":
                            result = method(chat_id, args.get('target', ''))
                        elif tool_id == "generate_catchup":
                            result = method(chat_id, args.get('from_phone', from_phone))
                        elif tool_id == "context_aware_versus":
                            # Handle context-aware versus - create generic comparison without using exact names
                            # Just create a fun generic versus when user says "compare both"
                            try:
                                # Create a generic, fun versus topic without looking at specific messages
                                generic_prompt = """Create a fun, generic "versus" comparison topic for a group chat. 
                                Make it interesting and debatable. Examples: "Morning Person vs Night Owl", "Coffee vs Tea", "Beach vs Mountains", "Dogs vs Cats", "Summer vs Winter".
                                
                                Return ONLY: "topic1 vs topic2" (generic and fun, not specific to anything)"""
                                
                                comparison_text = generate_catchy_message("response", user_message=generic_prompt)
                                if isinstance(comparison_text, list):
                                    comparison_text = " ".join(comparison_text)
                                
                                # Extract the vs comparison
                                if " vs " in comparison_text.lower():
                                    vs_index = comparison_text.lower().find(" vs ")
                                    topics = [
                                        comparison_text[:vs_index].strip(),
                                        comparison_text[vs_index + 4:].strip()
                                    ]
                                    # Clean up topics (remove quotes, extra text)
                                    topics = [t.strip('"\'.,!?').strip() for t in topics]
                                    if len(topics) == 2 and topics[0] and topics[1]:
                                        versus_text = f"{topics[0]} vs {topics[1]}"
                                        result = method(chat_id, versus_text)
                                        logger.info(f"[TOOLS] Context-aware versus (generic): {versus_text}")
                                    else:
                                        # Fallback to generic
                                        result = method(chat_id, "Option 1 vs Option 2")
                                else:
                                    # Fallback to generic
                                    result = method(chat_id, "Option 1 vs Option 2")
                            except Exception as e:
                                logger.error(f"[ERROR] Error creating generic versus: {e}")
                                # Fallback to generic
                                result = method(chat_id, "Option 1 vs Option 2")
                        elif tool.get('extract_topic'):
                            result = method(chat_id, args.get('topic', ''))
                        elif 'message_text' in args:
                            result = method(chat_id, args['message_text'])
                        else:
                            # Default: just chat_id
                            result = method(chat_id)
                        
                        logger.info(f"[TOOLS] LLM selected tool: {tool_id} (method: {method_name})")
                        return (True, tool_id, result)
                    except Exception as e:
                        logger.error(f"[ERROR] Error calling tool {tool_id}: {e}", exc_info=True)
                        continue
            
            # No tool selected - normal chat
            logger.debug(f"[TOOLS] LLM did not select any tool for: {message_text[:50]}")
            return (False, "normal_chat", None)
            
        except Exception as e:
            logger.error(f"[ERROR] Error in LLM tool selection: {e}", exc_info=True)
            # Fallback: return normal chat if LLM fails
            return (False, "llm_error", None)
        
        # Step 2: Check auto-triggered tools (passive features)
        for tool_id, tool in self.tools.items():
            if not tool.get('auto_trigger', False):
                continue
            
            condition = tool.get('condition')
            method_name = tool.get('method')
            
            if not method_name or not hasattr(self, method_name):
                continue
            
            method = getattr(self, method_name)
            
            # Check condition
            should_trigger = False
            result = None
            try:
                if condition == "is_chat_dead":
                    # Don't check for dead chat right after someone texts - wait at least 30 minutes
                    # This prevents annoying "dead chat" messages right after someone starts texting
                    recent_messages = self.get_recent_messages(chat_id, limit=3)
                    if recent_messages:
                        last_message = recent_messages[-1]
                        last_message_time = last_message.get('timestamp', 0)
                        time_since_last = time.time() - last_message_time
                        # Only check for dead chat if last message was more than 30 minutes ago
                        # This prevents triggering right after someone starts texting
                        if time_since_last > 1800:  # 30 minutes
                            if self._is_chat_dead(chat_id):
                                result = method(chat_id)
                                if result and ("dead" in result.lower() or "quiet" in result.lower()):
                                    should_trigger = True
                elif condition == "always":
                    result = method(chat_id)
                    if result:
                        should_trigger = True
                elif condition == "needs_temperature_check":
                    if self._needs_temperature_check(chat_id):
                        result = method(chat_id)
                        should_trigger = True
                elif condition == "has_celebration":
                    if chat_id in self.celebration_queue and self.celebration_queue[chat_id]:
                        celebration = self.celebration_queue[chat_id].pop(0)
                        result = method(chat_id, celebration)
                        if result:
                            should_trigger = True
                elif condition == "story_mode_active":
                    if chat_id in self.story_mode_active and self.story_mode_active[chat_id]:
                        result = method(chat_id, message_text, from_phone)
                        if result:
                            should_trigger = True
                elif condition == "is_long_voice_message":
                    # This is handled separately in message_processor
                    continue
                
                if should_trigger:
                    logger.info(f"[TOOLS] Auto-triggered tool: {tool_id} (method: {method_name})")
                    return (True, tool_id, result)
            except Exception as e:
                logger.error(f"[ERROR] Error in auto-tool {tool_id}: {e}", exc_info=True)
                continue
        
        # Default: don't respond to normal chat
        return (False, "normal_chat", None)
    
    # =========================================================================
    # VIBE & MOOD LAYER
    # =========================================================================
    
    def check_vibe(self, chat_id: int) -> str:
        """Detect group energy from message patterns"""
        messages = self.get_recent_messages(chat_id, limit=30)
        if not messages:
            return "chat is dead rn 💀"
        
        # Analyze message patterns
        user_messages = [m for m in messages if not m.get('is_bot', False)]
        if len(user_messages) < 3:
            return "chat is dead rn 💀"
        
        # Check time gaps
        now = time.time()
        recent_activity = [m for m in user_messages if now - m.get('timestamp', 0) < 3600]  # Last hour
        
        if len(recent_activity) < 2:
            return "chat is dead rn 💀"
        
        # Analyze sentiment and energy
        text_content = " ".join([m['text'] for m in recent_activity[-10:]])
        text_lower = text_content.lower()
        
        # Energy indicators
        high_energy = any(word in text_lower for word in ["!!!", "omg", "yooo", "let's go", "fire", "slay", "hype"])
        chaotic = any(word in text_lower for word in ["chaos", "unhinged", "wild", "insane", "crazy"])
        positive = any(word in text_lower for word in ["love", "amazing", "best", "great", "awesome", "perfect"])
        negative = any(word in text_lower for word in ["sad", "bad", "worst", "hate", "ugh", "annoying"])
        
        # Generate vibe description
        if chaotic and high_energy:
            return "y'all are unhinged today 💀"
        elif high_energy and positive:
            return "vibes are immaculate rn ✨"
        elif negative:
            return "vibes are a bit off today 😬"
        elif len(recent_activity) > 10:
            return "chat is popping off rn 🔥"
        else:
            return "vibes are chill rn 😎"
    
    def read_aura(self, chat_id: int) -> str:
        """Periodically summarize the chat's 'aura' based on recent convos"""
        messages = self.get_recent_messages(chat_id, limit=50)
        if not messages:
            return "aura: empty void (chat just started)"
        
        user_messages = [m for m in messages if not m.get('is_bot', False)][-20:]
        if len(user_messages) < 5:
            return "aura: still forming (not enough data yet)"
        
        # Build context
        context = "\n".join([f"{m['from']}: {m['text']}" for m in user_messages])
        
        prompt = f"""Analyze the "aura" of this group chat based on recent conversations. 
        Give a Gen Z style aura reading (1-2 sentences max). Be creative and fun.
        
        Recent messages:
        {context}
        
        What's the aura?"""
        
        try:
            aura_list = generate_catchy_message("response", user_message=prompt)
            if isinstance(aura_list, list):
                return aura_list[0] if aura_list else "aura: mysterious"
            return aura_list
        except Exception as e:
            logger.error(f"Error generating aura: {e}")
            return "aura: chaotic neutral with hints of existential dread"
    
    # =========================================================================
    # MEMORY & LORE SYSTEM
    # =========================================================================
    
    def get_lore(self, chat_id: int, topic: Optional[str] = None) -> str:
        """Get lore about a topic or general lore"""
        if chat_id not in self.lore:
            return "no lore yet, make some memories first"
        
        if topic:
            # Search for topic in lore
            topic_lower = topic.lower()
            matching_lore = []
            for key, entry in self.lore[chat_id].items():
                if topic_lower in key.lower() or topic_lower in entry.get('description', '').lower():
                    matching_lore.append(entry)
            
            if matching_lore:
                entry = matching_lore[0]
                return f"lore on {topic}: {entry.get('description', 'no description')}"
            else:
                return f"no lore on {topic} yet"
        else:
            # Return general lore summary
            lore_entries = list(self.lore[chat_id].values())
            if not lore_entries:
                return "no lore yet"
            
            # Get most recent or most referenced
            recent = sorted(lore_entries, key=lambda x: x.get('timestamp', 0), reverse=True)[:3]
            descriptions = [e.get('description', '') for e in recent]
            return f"recent lore: {' | '.join(descriptions[:2])}"
    
    def add_to_lore(self, chat_id: int, description: str, context: Optional[str] = None):
        """Add an entry to the lore"""
        if chat_id not in self.lore:
            self.lore[chat_id] = {}
        
        lore_id = f"lore_{int(time.time())}"
        self.lore[chat_id][lore_id] = {
            "description": description,
            "context": context,
            "timestamp": time.time()
        }
    
    def generate_catchup(self, chat_id: int, user_phone: str) -> str:
        """Generate personalized catch-up for someone returning"""
        if chat_id not in self.user_activity:
            return "nothing happened while you were gone"
        
        # Find when user was last active
        last_seen = self.user_activity[chat_id].get(user_phone, 0)
        now = time.time()
        time_away = now - last_seen
        
        if time_away < 3600:  # Less than 1 hour
            return "you were gone for like 5 minutes, nothing happened"
        
        # Get messages since they left
        messages = self.get_recent_messages(chat_id, limit=100)
        recent_messages = [m for m in messages if m.get('timestamp', 0) > last_seen and not m.get('is_bot', False)]
        
        if not recent_messages:
            return "nothing happened while you were gone"
        
        # Build catch-up summary
        context = "\n".join([f"{m['from']}: {m['text']}" for m in recent_messages[-20:]])
        
        prompt = f"""Someone is returning to the group chat after being away. 
        Give them a personalized Gen Z style catch-up (2-3 sentences max). 
        Be fun and highlight interesting things that happened.
        
        Recent messages while they were gone:
        {context}
        
        Generate a "Previously On..." style catch-up."""
        
        try:
            catchup_list = generate_catchy_message("response", user_message=prompt)
            if isinstance(catchup_list, list):
                return " ".join(catchup_list[:2])
            return catchup_list
        except Exception as e:
            logger.error(f"Error generating catchup: {e}")
            return "while you were gone: stuff happened (couldn't generate full catchup)"
    
    def pin_core_memory(self, chat_id: int, message_text: Optional[str] = None) -> str:
        """Pin a moment as a core memory"""
        if chat_id not in self.core_memories:
            self.core_memories[chat_id] = []
        
        messages = self.get_recent_messages(chat_id, limit=10)
        recent_context = " | ".join([m['text'][:50] for m in messages[-5:] if not m.get('is_bot', False)])
        
        memory = {
            "description": message_text or recent_context,
            "timestamp": time.time(),
            "votes": 1  # Auto-vote from requester
        }
        
        self.core_memories[chat_id].append(memory)
        
        # Also add to lore
        self.add_to_lore(chat_id, message_text or recent_context, "core memory")
        
        return f"✨ pinned as core memory! (react to vote to save permanently)"
    
    # =========================================================================
    # DECISION & COORDINATION
    # =========================================================================
    
    # =========================================================================
    # SOCIAL DYNAMICS
    # =========================================================================
    
    def _detect_celebration(self, chat_id: int, from_phone: str, text: str):
        """Detect if message contains celebration/wins"""
        text_lower = text.lower()
        celebration_words = ["got", "won", "passed", "got accepted", "got the job", "promoted", "achieved", "finished", "completed", "yay", "celebrate"]
        
        if any(word in text_lower for word in celebration_words):
            if chat_id not in self.celebration_queue:
                self.celebration_queue[chat_id] = []
            
            self.celebration_queue[chat_id].append({
                "from": from_phone,
                "text": text,
                "timestamp": time.time()
            })
    
    def generate_hype(self, chat_id: int, celebration: Dict) -> str:
        """Generate hype for a celebration"""
        prompt = f"""Someone shared good news: "{celebration['text']}"
        Generate Gen Z style hype (1-2 messages max). Be excited and supportive."""
        
        try:
            hype_list = generate_catchy_message("response", user_message=prompt)
            if isinstance(hype_list, list):
                return " ".join(hype_list[:2])
            return hype_list
        except Exception as e:
            logger.error(f"Error generating hype: {e}")
            return "yooo that's fire 🔥"
    
    def check_ghosts(self, chat_id: int) -> Optional[str]:
        """Check for soft ghosting and send gentle message"""
        if chat_id not in self.ghost_detection:
            return None
        
        now = time.time()
        ghosts = []
        
        for phone, last_active in self.ghost_detection[chat_id].items():
            days_inactive = (now - last_active) / 86400  # Convert to days
            
            if days_inactive > 3:  # 3+ days inactive
                ghosts.append((phone, days_inactive))
        
        if ghosts:
            # Get most inactive
            phone, days = max(ghosts, key=lambda x: x[1])
            
            # Get user name (simplified - would need phone to name mapping)
            user_name = phone[-4:]  # Last 4 digits as identifier
            
            return f"we miss u {user_name} 👻 (been {int(days)} days)"
        
        return None
    
    def _update_tension(self, chat_id: int, text: str):
        """Update tension score based on message content"""
        if chat_id not in self.tension_tracker:
            self.tension_tracker[chat_id] = 0.0
        
        text_lower = text.lower()
        
        # Tension indicators
        tension_words = ["fight", "argue", "disagree", "hate", "stupid", "wrong", "bad", "annoying", "frustrated", "angry"]
        deescalation_words = ["sorry", "my bad", "no worries", "all good", "chill", "relax"]
        
        tension_increase = sum(1 for word in tension_words if word in text_lower) * 0.2
        tension_decrease = sum(1 for word in deescalation_words if word in text_lower) * 0.3
        
        self.tension_tracker[chat_id] += tension_increase - tension_decrease
        self.tension_tracker[chat_id] = max(0, min(10, self.tension_tracker[chat_id]))  # Clamp 0-10
    
    def temperature_check(self, chat_id: int) -> str:
        """Check chat temperature and offer de-escalation"""
        tension = self.tension_tracker.get(chat_id, 0)
        
        if tension > 7:
            return "y'all might need to take a breather? 🧊"
        elif tension > 4:
            return "vibes getting a bit tense, maybe switch topics? 🤔"
        else:
            return None  # Don't respond if tension is low
    
    # =========================================================================
    # CONTENT & ENTERTAINMENT
    # =========================================================================
    
    def would_you_rather(self, chat_id: int) -> str:
        """Generate contextually relevant would you rather prompt"""
        messages = self.get_recent_messages(chat_id, limit=20)
        context = " ".join([m['text'] for m in messages[-5:] if not m.get('is_bot', False)])
        
        prompt = f"""Generate a fun "would you rather" question based on recent chat context.
        Keep it Gen Z style and relevant to: {context[:200]}
        
        Return ONLY the would you rather question."""
        
        try:
            wyr_list = generate_catchy_message("response", user_message=prompt)
            if isinstance(wyr_list, list):
                return wyr_list[0] if wyr_list else "would you rather question"
            return wyr_list
        except Exception as e:
            logger.error(f"Error generating WYR: {e}")
            return "would you rather question (generation failed)"
    
    def roast(self, chat_id: int, target: str, from_phone: str) -> str:
        """Generate consensual fun roast"""
        # Get context about target
        messages = self.get_recent_messages(chat_id, limit=50)
        target_messages = [m for m in messages if target.lower() in m.get('from', '').lower() or target.lower() in m.get('text', '').lower()]
        
        context = " ".join([m['text'] for m in target_messages[-3:]])
        
        # Check if user requested specific language
        recent_msg = messages[-1]['text'] if messages else ""
        language_request = ""
        if "telugu" in recent_msg.lower() or "in telugu" in recent_msg.lower():
            language_request = " Respond in Telugu (Telugu script)."
        elif "hindi" in recent_msg.lower() or "in hindi" in recent_msg.lower():
            language_request = " Respond in Hindi (Devanagari script)."
        elif "spanish" in recent_msg.lower() or "in spanish" in recent_msg.lower():
            language_request = " Respond in Spanish."
        
        prompt = f"""Generate a fun, playful roast about: {target}
        
        Requirements:
        - Keep it lighthearted and Gen Z style (1-2 sentences max)
        - Be playful and funny, NOT mean or hurtful
        - Use Gen Z slang naturally (lowkey, fr, no cap, etc.)
        - Make it specific and creative, not generic{language_request}
        
        Context from recent messages: {context[:200]}
        
        Example style: "bro {target} is giving main character energy but forgot to read the assignment 💀" or "{target} really said 'let me cook' and served us nothing fr"
        
        Generate a creative, specific roast that's funny but friendly."""
        
        try:
            roast_list = generate_catchy_message("response", user_message=prompt)
            if isinstance(roast_list, list):
                roast_text = roast_list[0] if roast_list else ""
                if not roast_text or len(roast_text) < 10:
                    # Fallback if generation is too short
                    roast_text = f"{target} really said 'let me cook' and served us nothing fr 💀"
                return roast_text
            return roast_list if roast_list else f"{target} really said 'let me cook' and served us nothing fr 💀"
        except Exception as e:
            logger.error(f"Error generating roast: {e}")
            return f"{target} really said 'let me cook' and served us nothing fr 💀"
    
    def hype_train(self, chat_id: int, target: str) -> str:
        """Start collaborative compliment train"""
        messages = self.get_recent_messages(chat_id, limit=30)
        target_context = " ".join([m['text'] for m in messages if target.lower() in m.get('from', '').lower() or target.lower() in m.get('text', '').lower()][-3:])
        
        prompt = f"""Generate Gen Z style compliments/hype for: {target}
        Be genuine and fun (2-3 short messages). Context: {target_context[:200]}"""
        
        try:
            hype_list = generate_catchy_message("response", user_message=prompt)
            if isinstance(hype_list, list):
                return " ".join(hype_list[:3])
            return hype_list
        except Exception as e:
            logger.error(f"Error generating hype train: {e}")
            return f"hype for {target} 🔥"
    
    def start_story_mode(self, chat_id: int) -> str:
        """Start collaborative storytelling"""
        self.story_mode_active[chat_id] = True
        self.active_stories[chat_id] = []
        
        # Generate opening line
        prompt = "Generate an opening line for a collaborative story (1 sentence, Gen Z style, fun and creative)"
        
        try:
            opening_list = generate_catchy_message("response", user_message=prompt)
            if isinstance(opening_list, list):
                opening = opening_list[0] if opening_list else "Once upon a time..."
            else:
                opening = opening_list
            
            self.active_stories[chat_id].append(opening)
            return f"📖 STORY MODE ACTIVATED\n\n{opening}\n\n(add a line to continue the story)"
        except Exception as e:
            logger.error(f"Error starting story mode: {e}")
            return "📖 STORY MODE ACTIVATED\n\n(add a line to continue)"
    
    def continue_story(self, chat_id: int, new_line: str, from_phone: str) -> Optional[str]:
        """Continue collaborative story"""
        if chat_id not in self.active_stories:
            return None
        
        # Add user's line
        self.active_stories[chat_id].append(f"{from_phone}: {new_line}")
        
        # Every 3-5 lines, have bot add a line to keep it going
        if len(self.active_stories[chat_id]) % 4 == 0:
            story_so_far = "\n".join(self.active_stories[chat_id][-5:])
            prompt = f"""Continue this collaborative story with 1-2 sentences. Keep it Gen Z style and fun.
            
            Story so far:
            {story_so_far}
            
            Add the next part:"""
            
            try:
                continuation_list = generate_catchy_message("response", user_message=prompt)
                if isinstance(continuation_list, list):
                    continuation = continuation_list[0] if continuation_list else "..."
                else:
                    continuation = continuation_list
                
                self.active_stories[chat_id].append(f"bot: {continuation}")
                return f"📖 {continuation}"
            except Exception as e:
                logger.error(f"Error continuing story: {e}")
        
        return None  # Don't respond, just track
    
    # =========================================================================
    # GAMIFICATION
    # =========================================================================
    
    def show_achievements(self, chat_id: int) -> str:
        """Show group achievements"""
        if chat_id not in self.achievements:
            return "no achievements yet, keep chatting!"
        
        achievements = self.achievements[chat_id]
        if not achievements:
            return "no achievements yet"
        
        response = "🏆 ACHIEVEMENTS:\n\n"
        for achievement, users in achievements.items():
            user_count = len(users)
            response += f"{achievement}: {user_count} member(s)\n"
        
        return response
    
    def group_trivia(self, chat_id: int) -> str:
        """Generate trivia about the group's history"""
        messages = self.get_recent_messages(chat_id, limit=100)
        if len(messages) < 10:
            return "not enough history for trivia yet"
        
        # Build context
        context = "\n".join([f"{m['from']}: {m['text']}" for m in messages[-20:] if not m.get('is_bot', False)])
        
        prompt = f"""Generate a fun trivia question about this group chat's history.
        Base it on: {context[:500]}
        
        Return ONLY the trivia question."""
        
        try:
            trivia_list = generate_catchy_message("response", user_message=prompt)
            if isinstance(trivia_list, list):
                return trivia_list[0] if trivia_list else "trivia question"
            return trivia_list
        except Exception as e:
            logger.error(f"Error generating trivia: {e}")
            return "trivia question (generation failed)"
    
    # =========================================================================
    # ACCESSIBILITY & INCLUSIVITY
    # =========================================================================
    
        if "to spanish" in text_lower or "en español" in text_lower:
            target_lang = "spanish"
        elif "to french" in text_lower or "en français" in text_lower:
            target_lang = "french"
        elif "to " in text_lower:
            # Extract language
            parts = text_lower.split("to ")
            if len(parts) > 1:
                target_lang = parts[1].split()[0]
        
        # For now, return placeholder
        return f"[Translation to {target_lang} would go here - needs translation API]"
    
    def generate_voice_tldr(self, chat_id: int, transcribed_text: str) -> str:
        """Generate TLDR for voice messages"""
        if len(transcribed_text) < 100:
            return None  # Too short to need TLDR
        
        prompt = f"""Generate a short TLDR (1 sentence) for this voice message transcription:
        
        {transcribed_text[:500]}
        
        Return ONLY the TLDR."""
        
        try:
            tldr_list = generate_catchy_message("response", user_message=prompt)
            if isinstance(tldr_list, list):
                return tldr_list[0] if tldr_list else None
            return tldr_list
        except Exception as e:
            logger.error(f"Error generating TLDR: {e}")
            return None
    
    def suggest_tone_indicator(self, message_text: str) -> Optional[str]:
        """Suggest tone indicators for ambiguous messages"""
        text_lower = message_text.lower()
        
        # Check if already has tone indicator
        if any(indicator in text_lower for indicator in ["/s", "/j", "/gen", "/srs", "/lh"]):
            return None
        
        # Check for sarcasm indicators
        sarcasm_words = ["obviously", "totally", "sure", "yeah right", "as if"]
        if any(word in text_lower for word in sarcasm_words) and "?" not in message_text:
            return "💡 might want to add /s or /j?"
        
        # Check for jokes
        joke_indicators = ["lol", "haha", "jk", "just kidding", "not really"]
        if any(word in text_lower for word in joke_indicators):
            return "💡 might want to add /j?"
        
        return None
    
    def generate_alt_text(self, image_description: Optional[str] = None) -> str:
        """Generate alt text for images (placeholder)"""
        if image_description:
            return f"Image: {image_description}"
        return "Image: [alt text generation needs image analysis API]"
    
    def update_chat_streak(self, chat_id: int):
        """Update chat streak counter"""
        if chat_id not in self.chat_streaks:
            self.chat_streaks[chat_id] = 0
        
        # Check if streak should continue (messages within 24 hours)
        messages = self.get_recent_messages(chat_id, limit=2)
        if len(messages) >= 2:
            now = time.time()
            last_msg_time = messages[-1].get('timestamp', 0)
            prev_msg_time = messages[-2].get('timestamp', 0)
            
            # If messages are within 24 hours, increment streak
            if (now - last_msg_time) < 86400 and (last_msg_time - prev_msg_time) < 86400:
                self.chat_streaks[chat_id] += 1
            else:
                # Reset if gap too long
                self.chat_streaks[chat_id] = 1
    
    def award_achievement(self, chat_id: int, achievement: str, user_phone: str):
        """Award an achievement to a user"""
        if chat_id not in self.achievements:
            self.achievements[chat_id] = {}
        
        if achievement not in self.achievements[chat_id]:
            self.achievements[chat_id][achievement] = set()
        
        self.achievements[chat_id][achievement].add(user_phone)
        
        # Check for milestone achievements
        if len(self.achievements[chat_id][achievement]) == 1:
            return f"🏆 New achievement unlocked: {achievement}!"
        
        return None
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _extract_topic(self, text: str, phrases: List[str]) -> Optional[str]:
        """Extract topic from text after given phrases"""
        text_lower = text.lower()
        for phrase in phrases:
            if phrase in text_lower:
                topic = text_lower.split(phrase, 1)[1].strip()
                return topic[:50]  # Limit length
        return None
    
    def _extract_name(self, text: str) -> str:
        """Extract name/target from text"""
        text_lower = text.lower()
        if "hype " in text_lower:
            name = text_lower.split("hype ", 1)[1].strip()
            return name.split()[0]  # First word
        return "someone"
    
    def _is_chat_dead(self, chat_id: int) -> bool:
        """Check if chat is dead (no activity recently)"""
        if chat_id not in self.recent_messages:
            return False  # Don't consider new chats as dead
        
        messages = list(self.recent_messages[chat_id])
        if not messages:
            return False  # Don't consider empty chats as dead
        
        now = time.time()
        # Get most recent message
        most_recent = max([m.get('timestamp', 0) for m in messages])
        time_since_last = now - most_recent
        
        # Only consider chat dead if:
        # 1. Last message was more than 1 hour ago (not right after someone texts)
        # 2. Less than 3 messages in last 2 hours
        if time_since_last < 3600:  # Less than 1 hour since last message
            return False  # Chat is active, not dead
        
        # Check messages in last 2 hours
        recent = [m for m in messages if now - m.get('timestamp', 0) < 7200]  # Last 2 hours
        
        # Chat is dead if less than 3 messages in last 2 hours AND last message was more than 1 hour ago
        return len(recent) < 3
    
    def _needs_temperature_check(self, chat_id: int) -> bool:
        """Check if temperature check is needed"""
        tension = self.tension_tracker.get(chat_id, 0)
        return tension > 4
    
    def is_chat_id_a_group(self, chat_id: int) -> bool:
        """Check if chat_id is known as a group"""
        # Check if we have group data for this chat
        return chat_id in self.recent_messages and len(self.recent_messages[chat_id]) > 0


# Singleton instance
group_chat_handler = GroupChatHandler()
