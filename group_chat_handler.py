"""
Advanced Group Chat Handler
Comprehensive Gen Z native features for group chats
"""
import logging
import time
import random
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set, Any
from collections import defaultdict, deque
from agent import generate_catchy_message
from api_client import api_client

logger = logging.getLogger(__name__)


class GroupChatHandler:
    """Advanced group chat handler with vibe detection, lore, and social features"""
    
    def __init__(self):
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
    
    def should_respond(self, chat_id: int, message_text: str, from_phone: str) -> Tuple[bool, str, Optional[str]]:
        """
        Determine if bot should respond and what to respond with
        
        Returns:
            (should_respond: bool, reason: str, response_text: Optional[str])
        """
        if not message_text:
            return (False, "empty_message", None)
        
        text_lower = message_text.lower().strip()
        
        # ===== VIBE & MOOD TRIGGERS =====
        if any(phrase in text_lower for phrase in ["vibe check", "what's the vibe", "how's the vibe"]):
            vibe = self.check_vibe(chat_id)
            return (True, "vibe_check", vibe)
        
        if any(phrase in text_lower for phrase in ["aura", "what's the aura", "read the aura"]):
            aura = self.read_aura(chat_id)
            return (True, "aura_reading", aura)
        
        # ===== LORE TRIGGERS =====
        if "what's the lore" in text_lower or "lore on" in text_lower:
            # Extract topic
            topic = self._extract_topic(text_lower, ["what's the lore", "lore on"])
            lore_entry = self.get_lore(chat_id, topic)
            return (True, "lore_request", lore_entry)
        
        if any(phrase in text_lower for phrase in ["previously on", "catch me up", "what did i miss"]):
            catchup = self.generate_catchup(chat_id, from_phone)
            return (True, "catchup_request", catchup)
        
        if "core memory" in text_lower or "pin this" in text_lower:
            # Try to pin current conversation as core memory
            memory = self.pin_core_memory(chat_id, message_text)
            return (True, "core_memory_pin", memory)
        
        # ===== DECISION & COORDINATION =====
        if any(phrase in text_lower for phrase in ["spin the wheel", "chaos wheel", "random pick"]):
            result = self.spin_chaos_wheel(chat_id, message_text)
            return (True, "chaos_wheel", result)
        
        if "anonymous vote" in text_lower or "anon vote" in text_lower:
            result = self.start_anonymous_vote(chat_id, message_text)
            return (True, "anonymous_vote", result)
        
        if "remind" in text_lower and ("every" in text_lower or "weekly" in text_lower or "daily" in text_lower):
            result = self.set_accountability_ping(chat_id, message_text)
            return (True, "accountability_ping", result)
        
        # ===== ENTERTAINMENT TRIGGERS =====
        if text_lower.startswith("versus") or " vs " in text_lower:
            result = self.start_versus(chat_id, message_text)
            return (True, "versus", result)
        
        if "would you rather" in text_lower or "wyr" in text_lower:
            result = self.would_you_rather(chat_id)
            return (True, "would_you_rather", result)
        
        if text_lower.startswith("roast "):
            target = text_lower.replace("roast ", "").strip()
            result = self.roast(chat_id, target, from_phone)
            return (True, "roast", result)
        
        if text_lower.startswith("hype ") or "hype up" in text_lower:
            target = self._extract_name(text_lower)
            result = self.hype_train(chat_id, target)
            return (True, "hype_train", result)
        
        if "story mode" in text_lower or "start story" in text_lower:
            result = self.start_story_mode(chat_id)
            return (True, "story_mode", result)
        
        # ===== GAMIFICATION =====
        if "achievements" in text_lower or "show achievements" in text_lower:
            result = self.show_achievements(chat_id)
            return (True, "achievements", result)
        
        if "trivia" in text_lower or "group trivia" in text_lower:
            result = self.group_trivia(chat_id)
            return (True, "trivia", result)
        
        if "prediction" in text_lower or "bet on" in text_lower:
            result = self.create_prediction_market(chat_id, message_text)
            return (True, "prediction_market", result)
        
        # ===== ACCESSIBILITY =====
        if "translate" in text_lower and "to" in text_lower:
            result = self.translate_message(chat_id, message_text)
            return (True, "translation", result)
        
        # ===== AUTO FEATURES (passive) =====
        # Auto vibe check if chat is dead
        if self._is_chat_dead(chat_id):
            vibe = self.check_vibe(chat_id)
            if "dead" in vibe.lower() or "quiet" in vibe.lower():
                return (True, "auto_vibe_check", vibe)
        
        # Auto ghost detection
        ghost_check = self.check_ghosts(chat_id)
        if ghost_check:
            return (True, "ghost_detection", ghost_check)
        
        # Auto temperature check
        if self._needs_temperature_check(chat_id):
            temp_check = self.temperature_check(chat_id)
            return (True, "temperature_check", temp_check)
        
        # Auto hype on celebrations
        if chat_id in self.celebration_queue and self.celebration_queue[chat_id]:
            celebration = self.celebration_queue[chat_id].pop(0)
            hype = self.generate_hype(chat_id, celebration)
            return (True, "auto_hype", hype)
        
        # Story mode continuation
        if chat_id in self.story_mode_active and self.story_mode_active[chat_id]:
            result = self.continue_story(chat_id, message_text, from_phone)
            if result:
                return (True, "story_continuation", result)
        
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
    
    def pin_core_memory(self, chat_id: int, context: Optional[str] = None) -> str:
        """Pin a moment as a core memory"""
        if chat_id not in self.core_memories:
            self.core_memories[chat_id] = []
        
        messages = self.get_recent_messages(chat_id, limit=10)
        recent_context = " | ".join([m['text'][:50] for m in messages[-5:] if not m.get('is_bot', False)])
        
        memory = {
            "description": context or recent_context,
            "timestamp": time.time(),
            "votes": 1  # Auto-vote from requester
        }
        
        self.core_memories[chat_id].append(memory)
        
        # Also add to lore
        self.add_to_lore(chat_id, context or recent_context, "core memory")
        
        return f"✨ pinned as core memory! (react to vote to save permanently)"
    
    # =========================================================================
    # DECISION & COORDINATION
    # =========================================================================
    
    def spin_chaos_wheel(self, chat_id: int, message_text: str) -> str:
        """Spin the chaos wheel for random decisions"""
        # Extract options from message
        text_lower = message_text.lower()
        
        # Try to find options
        if "between" in text_lower or "or" in text_lower:
            # Simple extraction
            parts = message_text.split(" or ")
            if len(parts) < 2:
                parts = message_text.split(" between ")
            
            if len(parts) >= 2:
                options = [p.strip() for p in parts[1:] if p.strip()]
            else:
                options = ["option 1", "option 2"]
        else:
            # Use AI to extract options
            prompt = f"""Extract decision options from: "{message_text}"
            Return 2-4 options separated by |"""
            
            try:
                options_text = generate_catchy_message("response", user_message=prompt)
                if isinstance(options_text, list):
                    options_text = " ".join(options_text)
                options = [opt.strip() for opt in options_text.split("|") if opt.strip()]
            except:
                options = ["option 1", "option 2"]
        
        if len(options) < 2:
            options = ["option 1", "option 2"]
        
        # Spin the wheel
        chosen = random.choice(options)
        return f"🎰 chaos wheel says: {chosen} (no backsies)"
    
    def start_anonymous_vote(self, chat_id: int, message_text: str) -> str:
        """Start an anonymous vote"""
        # Extract question
        text_lower = message_text.lower()
        question = message_text.replace("anonymous vote", "").replace("anon vote", "").strip()
        
        if not question or len(question) < 5:
            question = "What should we do?"
        
        # Generate options
        prompt = f"""Generate 2-4 voting options for: "{question}"
        Format as: option1 | option2 | option3"""
        
        try:
            options_text = generate_catchy_message("response", user_message=prompt)
            if isinstance(options_text, list):
                options_text = " ".join(options_text)
            options = [opt.strip() for opt in options_text.split("|") if opt.strip()]
        except:
            options = ["option 1", "option 2"]
        
        # Store vote
        vote_id = f"vote_{int(time.time())}"
        self.anonymous_votes[chat_id] = {
            "id": vote_id,
            "question": question,
            "options": options,
            "votes": {},
            "timestamp": time.time()
        }
        
        # Format response
        response = f"🗳️ Anonymous vote: {question}\n\n"
        for i, opt in enumerate(options[:4], 1):
            response += f"{i}. {opt}\n"
        response += "\nreply with number to vote (anonymous)"
        
        return response
    
    def set_accountability_ping(self, chat_id: int, message_text: str) -> str:
        """Set up accountability reminders"""
        if chat_id not in self.accountability_tasks:
            self.accountability_tasks[chat_id] = []
        
        # Extract task and frequency
        text_lower = message_text.lower()
        
        # Simple extraction
        task = message_text
        frequency = "weekly"
        
        if "daily" in text_lower:
            frequency = "daily"
        elif "weekly" in text_lower:
            frequency = "weekly"
        elif "monday" in text_lower:
            frequency = "monday"
        
        task_entry = {
            "description": task,
            "frequency": frequency,
            "timestamp": time.time()
        }
        
        self.accountability_tasks[chat_id].append(task_entry)
        
        return f"✅ accountability ping set: {task} ({frequency})"
    
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
    
    def start_versus(self, chat_id: int, message_text: str) -> str:
        """Start a versus debate bracket"""
        # Extract topics
        text_lower = message_text.lower()
        text_clean = message_text.replace("versus", "").replace("vs", "").strip()
        
        if " vs " in text_clean:
            topics = [t.strip() for t in text_clean.split(" vs ")]
        else:
            # Use AI to generate versus topics
            prompt = f"""Generate a fun "versus" debate topic based on: "{text_clean}"
            Format as: topic1 vs topic2"""
            
            try:
                topics_text = generate_catchy_message("response", user_message=prompt)
                if isinstance(topics_text, list):
                    topics_text = " ".join(topics_text)
                if " vs " in topics_text:
                    topics = [t.strip() for t in topics_text.split(" vs ")]
                else:
                    topics = ["option 1", "option 2"]
            except:
                topics = ["option 1", "option 2"]
        
        if len(topics) < 2:
            topics = ["option 1", "option 2"]
        
        # Store versus
        self.active_versus[chat_id] = {
            "topic1": topics[0],
            "topic2": topics[1],
            "votes": {"topic1": 0, "topic2": 0},
            "timestamp": time.time()
        }
        
        return f"⚔️ VERSUS: {topics[0]} vs {topics[1]}\n\nreact with 1 or 2 to vote"
    
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
        
        prompt = f"""Generate a fun, consensual roast about: {target}
        Keep it lighthearted and Gen Z style (1-2 sentences max). 
        Context: {context[:200]}
        
        Be playful, not mean."""
        
        try:
            roast_list = generate_catchy_message("response", user_message=prompt)
            if isinstance(roast_list, list):
                return roast_list[0] if roast_list else f"roast about {target}"
            return roast_list
        except Exception as e:
            logger.error(f"Error generating roast: {e}")
            return f"roast about {target} (generation failed)"
    
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
    
    def create_prediction_market(self, chat_id: int, message_text: str) -> str:
        """Create a prediction market on group decisions"""
        # Extract prediction question
        text_lower = message_text.lower()
        question = message_text.replace("prediction", "").replace("bet on", "").strip()
        
        if not question or len(question) < 5:
            question = "Will we actually do this?"
        
        market_id = f"market_{int(time.time())}"
        self.prediction_markets[chat_id] = {
            "id": market_id,
            "question": question,
            "yes_votes": 0,
            "no_votes": 0,
            "timestamp": time.time()
        }
        
        return f"📊 Prediction Market: {question}\n\nreact 👍 for yes, 👎 for no"
    
    # =========================================================================
    # ACCESSIBILITY & INCLUSIVITY
    # =========================================================================
    
    def translate_message(self, chat_id: int, message_text: str) -> str:
        """Translate message (placeholder - would need translation API)"""
        # Extract target language
        text_lower = message_text.lower()
        target_lang = "spanish"  # Default
        
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
            return True
        
        messages = list(self.recent_messages[chat_id])
        if not messages:
            return True
        
        now = time.time()
        recent = [m for m in messages if now - m.get('timestamp', 0) < 3600]  # Last hour
        
        return len(recent) < 2
    
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
