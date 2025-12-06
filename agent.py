"""
Jada - AI Friend by Series.so
Message Generator using ChatGPT with Function Calling for Web Search
"""
import logging
import requests
import random
from openai import OpenAI
from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)
client = OpenAI(api_key=OPENAI_API_KEY)

# Music recommendations - Taylor Swift songs
MUSIC_SONGS = [
    {"name": "Welcome To New York (Taylor's Version)", "link": "https://music.apple.com/us/song/welcome-to-new-york-taylors-version/1713845554"},
    {"name": "Blank Space (Taylor's Version)", "link": "https://music.apple.com/us/song/blank-space-taylors-version/1713845737"},
    {"name": "Style (Taylor's Version)", "link": "https://music.apple.com/us/song/style-taylors-version/1713845746"},
    {"name": "Out Of The Woods (Taylor's Version)", "link": "https://music.apple.com/us/song/out-of-the-woods-taylors-version/1713845779"},
    {"name": "All You Had To Do Was Stay (Taylor's Version)", "link": "https://music.apple.com/us/song/all-you-had-to-do-was-stay-taylors-version/1713845784"},
    {"name": "Shake It Off (Taylor's Version)", "link": "https://music.apple.com/us/song/shake-it-off-taylors-version/1713845786"},
    {"name": "I Wish You Would (Taylor's Version)", "link": "https://music.apple.com/us/song/i-wish-you-would-taylors-version/1713845994"},
    {"name": "Bad Blood (Taylor's Version)", "link": "https://music.apple.com/us/song/bad-blood-taylors-version/1713846092"},
    {"name": "Wildest Dreams (Taylor's Version)", "link": "https://music.apple.com/us/song/wildest-dreams-taylors-version/1713846100"},
    {"name": "How You Get The Girl (Taylor's Version)", "link": "https://music.apple.com/us/song/how-you-get-the-girl-taylors-version/1713846103"},
    {"name": "This Love (Taylor's Version)", "link": "https://music.apple.com/us/song/this-love-taylors-version/1713846228"},
    {"name": "I Know Places (Taylor's Version)", "link": "https://music.apple.com/us/song/i-know-places-taylors-version/1713846232"},
    {"name": "Clean (Taylor's Version)", "link": "https://music.apple.com/us/song/clean-taylors-version/1713846238"},
    {"name": "Wonderland (Taylor's Version)", "link": "https://music.apple.com/us/song/wonderland-taylors-version/1713846243"},
    {"name": "You Are In Love (Taylor's Version)", "link": "https://music.apple.com/us/song/you-are-in-love-taylors-version/1713846248"},
    {"name": "New Romantics (Taylor's Version)", "link": "https://music.apple.com/us/song/new-romantics-taylors-version/1713846253"},
    {"name": "\"Slut!\" (Taylor's Version) [From The Vault]", "link": "https://music.apple.com/us/song/slut-taylors-version-from-the-vault/1713846497"},
    {"name": "Say Don't Go (Taylor's Version) [From The Vault]", "link": "https://music.apple.com/us/song/say-dont-go-taylors-version-from-the-vault/1713846513"},
    {"name": "Now That We Don't Talk (Taylor's Version) [From The Vault]", "link": "https://music.apple.com/us/song/now-that-we-dont-talk-taylors-version-from-the-vault/1713846523"},
    {"name": "Suburban Legends (Taylor's Version) [From The Vault]", "link": "https://music.apple.com/us/song/suburban-legends-taylors-version-from-the-vault/1713846651"},
    {"name": "Is It Over Now? (Taylor's Version) [From The Vault]", "link": "https://music.apple.com/us/song/is-it-over-now-taylors-version-from-the-vault/1713846658"},
    {"name": "Bad Blood (Taylor's Version) [feat. Kendrick Lamar]", "link": "https://music.apple.com/us/song/bad-blood-taylors-version-feat-kendrick-lamar/1713846670"}
]


def get_random_song() -> dict:
    """Get a random song from the music library"""
    return random.choice(MUSIC_SONGS)


def user_likes_music(known_interests: list) -> bool:
    """Check if user is interested in music"""
    if not known_interests:
        return False
    music_keywords = ["music", "song", "songs", "taylor", "swift", "taylor swift", "listening", "spotify", "apple music"]
    interests_lower = [i.lower() for i in known_interests]
    return any(keyword in interests_lower for keyword in music_keywords) or \
           any(keyword in interest for interest in interests_lower for keyword in music_keywords)

# Jada - Your AI Friend by Series.so
JADA_PROMPT = """You are **Jada**, a bestie who's part of Series - an AI-powered social network that helps people find their tribe. You text like an actual friend - casual, unfiltered, and real. You're plugged into culture and talk like Gen Z/Gen Alpha without being cringe or trying too hard.

### Your Language Vibe

- Use slang naturally: lowkey, highkey, no cap, fr fr, slay, ate that, it's giving, bussin, valid, based, bet, im weak, deadass, rent free, main character energy, understood the assignment, core (like cottagecore, brainrot core), delulu, era, ick, beige flag, serving, mother, ate and left no crumbs, real ones, ngl, wya, iykyk

- Type in lowercase mostly, minimal punctuation

- Use abbreviations: rn, ngl, tbh, imo, wbu, hbu, omg, pls, ur, u, v (very), sm (so much), def

- React with energy: "wait stoppp", "no bc why is this so real", "obsessed", "this>>> ", "ur so valid for that"

- Keep it snappy - you're texting not writing essays

### Response Format

**ALWAYS respond in valid JSON format with 1-4 message keys based on context.**

Split responses like real texts - no one sends paragraphs.

```json
{
  "1": "first reaction/thought",
  "2": "follow-up comment",
  "3": "question to vibe check (optional)",
  "4": "extra thought if hyped (optional)"
}
```

### Message Count Guide:

- **1 message**: Quick reaction or simple answer
- **2 messages**: Reaction + question OR two quick thoughts
- **3 messages**: Reaction + comment + question (most common)
- **4 messages**: Only when ur actually hyped about something

### Your Energy

- You're a friend first, not some corporate bot
- Genuinely curious about people and what makes them tick
- Hype up your friends and validate their interests
- You're part of Series so connecting people is literally your thing
- Futuristic mindset - you believe in real connections over fake metrics

### Stay In Your Lane

Only talk about:
- Series and finding your people
- Vibes, interests, hobbies (to match users with others)
- Making genuine connections

Off-topic? Redirect smooth: "ok that's not rly my thing but tell me what ur into tho i wanna find ur people"

### Series Info (when asked):

- AI-powered social network by two yale founders (nathaneo & sean)
- Raised $3.1M, backed by reddit's ceo and other big names
- Connects u with people based on actual vibes not follower count
- For students rn (needs .edu)
- The vision: one billion real connections, no cap

### Interest Discovery

- FIRST MESSAGE: If you don't know their interests yet, naturally ask what they're into after responding to their message
- If you KNOW their interests, reference them naturally when relevant (but don't force it)
- They mention something they like? acknowledge it and maybe ask more or relate it to their known interests
- Keep it casual and conversational - don't make it feel like a survey

**CRITICAL: ALWAYS return valid JSON with message keys "1", "2", "3", "4" as needed. Never return plain text.**
"""

def add_music_link_if_applicable(messages: list, known_interests: list, prompt_type: str = "response", probability: float = 0.3) -> list:
    """
    Randomly add a music link to messages if user likes music
    
    Args:
        messages: List of message strings
        known_interests: List of user interests
        prompt_type: Type of message (only add for "response" type)
        probability: Probability of adding a music link (default 0.3 = 30%)
        
    Returns:
        list: Messages with potentially added music link
    """
    # Only add music links for response messages, not initial or hype
    if prompt_type != "response" or not messages or not user_likes_music(known_interests):
        return messages
    
    # Randomly decide to add music link (30% chance)
    if random.random() < probability:
        song = get_random_song()
        # Add music link as a new message (keep it casual and Gen Z style)
        music_phrases = [
            f"btw this song is hitting rn: {song['link']}",
            f"ok but this song >>> {song['link']}",
            f"this song is rent free in my head: {song['link']}",
            f"lowkey obsessed with this rn: {song['link']}",
            f"this song is giving main character energy: {song['link']}"
        ]
        music_message = random.choice(music_phrases)
        messages.append(music_message)
        logger.info(f"🎵 Added music recommendation: {song['name']}")
    
    return messages


def parse_jada_response(response_text: str) -> list:
    """
    Parse Jada's JSON response into a list of messages
    
    Args:
        response_text: The raw response text (should be JSON)
        
    Returns:
        list: List of message strings to send
    """
    import json
    import re
    
    try:
        # Try to extract JSON from markdown code blocks if present
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(1)
        else:
            # Try to find JSON object in the text
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)
        
        # Parse JSON
        data = json.loads(response_text)
        
        # Extract messages in order (1, 2, 3, 4)
        messages = []
        for key in ["1", "2", "3", "4"]:
            if key in data and data[key]:
                msg = str(data[key]).strip()
                if msg:
                    messages.append(msg)
        
        if messages:
            logger.debug(f"📱 Parsed {len(messages)} message(s) from JSON response")
            return messages
        else:
            logger.warning("No messages found in JSON response, using fallback")
            return [response_text.strip()] if response_text.strip() else ["gotchu, what's up"]
            
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON response: {e}, using raw text")
        # Fallback: return the raw text as a single message
        return [response_text.strip()] if response_text.strip() else ["gotchu, what's up"]
    except Exception as e:
        logger.warning(f"Error parsing response: {e}, using raw text")
        return [response_text.strip()] if response_text.strip() else ["gotchu, what's up"]


def web_search(query: str) -> str:
    """
    Perform a web search and return results
    
    Args:
        query: Search query string
        
    Returns:
        str: Search results summary
    """
    try:
        # Using DuckDuckGo instant answer API (no API key needed)
        # For production, you might want to use Google Custom Search, Bing, or SerpAPI
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1"
        }
        
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        # Extract relevant information
        results = []
        
        if data.get("AbstractText"):
            results.append(f"Summary: {data['AbstractText']}")
        
        if data.get("Answer"):
            results.append(f"Answer: {data['Answer']}")
        
        if data.get("RelatedTopics"):
            for topic in data["RelatedTopics"][:3]:  # Top 3 related topics
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append(topic["Text"][:200])  # Limit length
        
        if results:
            return "\n".join(results)
        else:
            # Fallback: return that we searched but found limited results
            return f"Searched for '{query}' but found limited results. Try rephrasing or being more specific."
            
    except Exception as e:
        logger.warning(f"Web search error: {e}")
        return f"Couldn't search for '{query}' right now. Try asking again later."


def generate_catchy_message(prompt_type="initial", user_message: str = None, 
                           is_voice_message: bool = False, conversation_history: list = None,
                           is_first_message: bool = False, known_interests: list = None):
    """
    Generate Jada's response using ChatGPT with function calling for web search
    Returns a list of messages (1-4) to send separately like real texts

    Args:
        prompt_type: Type of message to generate
            - "initial": First message to start conversation
            - "response": Quick response to incoming message (can use web search if question detected)
            - "hype": Excited/hyped message
        user_message: The incoming user message (for response type, to detect if web search is needed)
        is_voice_message: Whether this message came from a voice transcription
        conversation_history: List of previous messages in OpenAI format [{"role": "user/assistant", "content": "..."}]
        is_first_message: Whether this is the first message from the user (no previous conversation)
        known_interests: List of interests we already know about this user

    Returns:
        list: List of message strings (1-4 messages) to send separately
    """
    if conversation_history is None:
        conversation_history = []
    if known_interests is None:
        known_interests = []
    
    prompts = {
        "initial": "Generate a casual greeting to start a text conversation. Ask what they're up to in a chill way. Return JSON with 1-2 messages.",
        "response": "Read the user's message. Understand what they're saying and respond meaningfully. Split into 1-4 messages like real texts. If they asked a question, answer it briefly. If they shared something, respond to it. If they need info, use web_search. Return JSON format.",
        "hype": "Generate an excited response about matching with someone cool. Return JSON with 2-4 messages.",
    }

    user_prompt = prompts.get(prompt_type, prompts["initial"])
    
    # If it's a response and we have a user message, understand it properly
    if prompt_type == "response" and user_message:
        # Check if message contains a question mark or question words (better detection)
        user_lower = user_message.lower()
        is_question = (
            "?" in user_message or 
            any(word in user_lower for word in [
                "what", "when", "where", "who", "why", "how", 
                "tell me", "search", "find", "look up", "what's", 
                "what is", "can you", "do you know", "is there"
            ]) or
            user_lower.startswith(("what", "when", "where", "who", "why", "how"))
        )
        
        if is_question:
            # Use function calling to potentially search the web
            voice_note = ""
            if is_voice_message:
                voice_note = "\n\nNOTE: This was a voice message - the user SPOKE this question. Understand their tone and respond naturally."
            
            # Build interest context for questions too
            interest_context = ""
            if is_first_message and not known_interests:
                interest_context = "\n\nIMPORTANT: This is the FIRST message from this user. After answering their question, naturally ask what they're into."
            elif known_interests:
                interests_str = ", ".join(known_interests[:3])
                interest_context = f"\n\nYou know this user is into: {interests_str}. Reference these interests naturally when relevant."
            
            messages = [
                {"role": "system", "content": JADA_PROMPT + voice_note + interest_context + "\n\nIMPORTANT: Understand what the user is asking. Answer questions DIRECTLY and clearly. If it's a simple question (like math, facts), answer it directly. If they need current information, facts, or real-time data, use web_search function. Then give them a meaningful answer based on the search results, not just generic responses."}
            ]
            
            # Add conversation history if available
            if conversation_history:
                messages.extend(conversation_history)
                logger.debug(f"📚 Added {len(conversation_history)} messages from conversation history")
            
            # Build user message prompt
            user_prompt_content = f"User message: {user_message}\n\nWhat are they asking? Generate a response in JSON format with 1-4 messages. If you need current info, use web_search first, then give a brief answer."
            if is_first_message and not known_interests:
                user_prompt_content += " After answering, naturally ask what they're into (games, music, hobbies, etc.) in a chill way."
            messages.append({"role": "user", "content": user_prompt_content})
            
            # Define the web_search function for OpenAI
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "description": "Search the web for current information, facts, or answers to questions. Use this when the user asks about current events, facts, definitions, or anything that needs up-to-date information.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "The search query to look up on the web. Make it specific and clear."
                                }
                            },
                            "required": ["query"]
                        }
                    }
                }
            ]
            
            try:
                # First call - model decides if it needs to search
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",  # Let model decide if it needs to search
                    temperature=0.8,
                    max_tokens=200,  # Allow for JSON format
                    timeout=15
                )
                
                message = response.choices[0].message
                
                # Check if model wants to call a function
                if message.tool_calls:
                    for tool_call in message.tool_calls:
                        if tool_call.function.name == "web_search":
                            # Extract query
                            import json
                            args = json.loads(tool_call.function.arguments)
                            search_query = args.get("query", user_message)
                            
                            logger.info(f"🔍 Performing web search: {search_query}")
                            
                            # Execute web search
                            search_results = web_search(search_query)
                            
                            # Add function result to messages and get final response
                            messages.append(message)
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": "web_search",
                                "content": search_results
                            })
                            
                            # Get final response with search results (history already included in messages)
                            final_response = client.chat.completions.create(
                                model="gpt-4o-mini",
                                messages=messages,
                                temperature=0.8,
                                max_tokens=200,  # Allow for JSON format
                                timeout=15
                            )
                            
                            result = final_response.choices[0].message.content.strip()
                            logger.info(f"Generated response with web search results")
                            parsed = parse_jada_response(result)
                            return add_music_link_if_applicable(parsed, known_interests, prompt_type)
                
                # No function call needed, return regular response
                parsed = parse_jada_response(message.content.strip())
                return add_music_link_if_applicable(parsed, known_interests, prompt_type)
                
            except Exception as e:
                logger.warning(f"Error with function calling: {e}, falling back to regular generation")
                # Fall through to regular generation
    
    # Regular generation without function calling - but ALWAYS with user message context
    try:
        if prompt_type == "response" and user_message:
            # Build context-aware prompt
            voice_context = ""
            if is_voice_message:
                voice_context = "\n\nNOTE: This message was transcribed from a voice message. The user spoke this, so understand their tone and intent from what they said. Respond naturally as if they spoke to you."
            
            # Build interest context
            interest_context = ""
            if is_first_message and not known_interests:
                # First message - ask about interests naturally
                interest_context = "\n\nIMPORTANT: This is the FIRST message from this user. You don't know their interests yet. After responding to their message, naturally ask about what they're into (games, music, hobbies, food, etc.) in a chill Gen Z way. Keep it casual - don't make it feel like an interview. Example: 'yoo what's good! what you into?' or 'hey! what games/music you into?' or 'what's up! what you like to do for fun?'"
            elif known_interests:
                # We know their interests - reference them naturally in conversation
                interests_str = ", ".join(known_interests[:3])
                interest_context = f"\n\nYou know this user is into: {interests_str}. Reference these interests naturally in your response when relevant, but don't force it. Keep the conversation flowing based on what they said."
            
            # Always include the actual user message for context
            messages = [
                {"role": "system", "content": JADA_PROMPT + voice_context + interest_context}
            ]
            
            # Add conversation history if available
            if conversation_history:
                messages.extend(conversation_history)
                logger.debug(f"📚 Added {len(conversation_history)} messages from conversation history")
            
            # Build user message prompt
            user_prompt_content = f"User said: {user_message}\n\nRead this carefully. If they asked a question, ANSWER IT DIRECTLY. If it's simple (like math, facts), just give the answer. If they're asking how you are, respond naturally. Return your response in JSON format with 1-4 messages."
            
            if is_first_message and not known_interests:
                user_prompt_content += " After responding, naturally ask what they're into (games, music, hobbies, food, etc.) in a chill way."
            else:
                user_prompt_content += " Understand what they're saying and respond meaningfully, but keep it brief like real texting. Split into multiple messages if needed."
            
            messages.append({"role": "user", "content": user_prompt_content})
        else:
            messages = [
                {"role": "system", "content": JADA_PROMPT},
                {"role": "user", "content": user_prompt}
            ]
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.8,  # Slightly lower for more consistent meaningful responses
            max_tokens=200 if prompt_type == "response" else 150,  # Allow for JSON format
            timeout=15
        )
        message = response.choices[0].message.content.strip()
        logger.debug(f"Generated {prompt_type} message: {message}")
        parsed = parse_jada_response(message)
        return add_music_link_if_applicable(parsed, known_interests, prompt_type)
    except Exception as e:
        logger.warning(f"Error generating message: {e}, using fallback")
        # Fallback messages - still try to be meaningful (return as single message list)
        if prompt_type == "response" and user_message:
            # Try to give a basic meaningful response even if API fails
            user_lower = user_message.lower()
            if "?" in user_message:
                return ["hmm not sure about that, lemme think"]
            elif any(word in user_lower for word in ["tired", "sad", "bad", "stressed"]):
                return ["aw that's rough, hope things get better"]
            elif any(word in user_lower for word in ["happy", "excited", "good", "great"]):
                return ["yooo that's awesome fr"]
            else:
                return ["gotchu, what's up"]
        else:
            fallbacks = {
                "initial": ["yoo what's good"],
                "response": ["gotchu, what's up"],
                "hype": ["yooo this is sick fr"]
            }
            return fallbacks.get(prompt_type, ["hey"])


def extract_interests(message: str) -> list:
    """
    Extract interests from a user's message using OpenAI
    
    Args:
        message: User's message text
        
    Returns:
        list: List of interest strings (e.g., ["gaming", "anime", "boba"])
    """
    try:
        extraction_prompt = """Extract interests/hobbies from this message. Look for:
- Things they like, love, enjoy, are into (food, drinks, music, games, sports, activities, etc.)
- Hobbies they mention
- Things they're passionate about
- Preferences they express (e.g., "I like water" → "water" or "hydration")

Be GENEROUS - if someone says "I like X", extract X as an interest.
Even simple things like "water", "coffee", "music" are interests.

Return ONLY a JSON array of interest strings, lowercase, short phrases (1-2 words max).
Example: ["gaming", "anime", "boba", "basketball", "water", "coffee"]

If no clear interests, return empty array: []

Message: "{message}"

Return ONLY the JSON array, nothing else. No explanations."""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You extract interests from messages. Be generous - if someone mentions liking something, it's an interest. Return ONLY a JSON array of interest strings, no explanations."},
                {"role": "user", "content": extraction_prompt.format(message=message)}
            ],
            temperature=0.3,
            max_tokens=200
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Parse JSON (handle markdown code blocks)
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0]
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0]
        
        import json
        try:
            result = json.loads(result_text)
            
            # Handle both array format and object format
            if isinstance(result, list):
                interests = result
            elif isinstance(result, dict):
                # Try common keys
                interests = result.get("interests", result.get("interest", []))
                if not isinstance(interests, list):
                    interests = []
            else:
                interests = []
        except json.JSONDecodeError:
            # If JSON parsing fails, try to extract array from text
            import re
            array_match = re.search(r'\[(.*?)\]', result_text)
            if array_match:
                # Try to parse the array content
                try:
                    # Simple extraction of quoted strings
                    interests = re.findall(r'"([^"]+)"', array_match.group(0))
                except:
                    interests = []
            else:
                interests = []
        
        # Filter out empty strings and normalize
        interests = [i.lower().strip() for i in interests if i and i.strip()]
        
        # Fallback: if still empty, try simple keyword extraction
        if not interests:
            message_lower = message.lower()
            # Common interest keywords
            interest_keywords = [
                "like", "love", "enjoy", "into", "passionate", "favorite", "favourite",
                "hobby", "hobbies", "interest", "interests"
            ]
            if any(kw in message_lower for kw in interest_keywords):
                # Try to extract the thing they like
                # Simple pattern: "I like X" or "love X" or "into X"
                import re
                patterns = [
                    r"(?:like|love|enjoy|into|passionate about)\s+([a-z]+)",
                    r"([a-z]+)\s+(?:is|are)\s+(?:my|a)\s+(?:favorite|favourite|hobby|interest)",
                ]
                for pattern in patterns:
                    matches = re.findall(pattern, message_lower)
                    if matches:
                        interests = [m for m in matches if len(m) > 2]  # Filter out short words
                        break
        
        logger.info(f"🎯 Extracted interests: {interests}")
        return interests
        
    except Exception as e:
        logger.warning(f"Error extracting interests: {e}", exc_info=True)
        # Fallback: simple extraction
        try:
            message_lower = message.lower()
            # Look for "I like X" pattern
            import re
            match = re.search(r"(?:like|love|enjoy)\s+([a-z]+)", message_lower)
            if match:
                interest = match.group(1)
                if len(interest) > 2:  # Filter out short words
                    logger.info(f"🎯 Fallback extracted interest: {interest}")
                    return [interest]
        except:
            pass
        return []


if __name__ == "__main__":
    print("Initial message:", generate_catchy_message("initial"))
    print("Response:", generate_catchy_message("response"))
    print("Hype:", generate_catchy_message("hype"))
