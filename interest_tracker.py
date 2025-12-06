"""
Interest Tracking and Group Matching System
Tracks user interests and creates groups when interests match
"""
import time
from typing import Dict, List, Set, Optional, Tuple
from collections import defaultdict
from app_logger import logger


class InterestTracker:
    """Tracks user interests and matches users for group creation"""
    
    def __init__(self):
        # phone_number -> set of interests
        self.user_interests: Dict[str, Set[str]] = {}
        
        # phone_number -> chat_id (1:1 chat)
        self.user_chat_ids: Dict[str, int] = {}
        
        # phone_number -> list of group_ids they're in
        self.user_groups: Dict[str, List[str]] = defaultdict(list)
        
        # group_id -> (display_name, members, shared_interests, chat_id)
        self.groups: Dict[str, Tuple[str, List[str], List[str], Optional[int]]] = {}
        
        # Interest -> set of phone numbers (inverted index for fast matching)
        self.interest_index: Dict[str, Set[str]] = defaultdict(set)
        
        # Track recent matches to avoid spam
        self.recent_matches: Dict[Tuple[str, str], float] = {}
        
        # Group counter
        self._group_counter = 0
        
        # Minimum shared interests to create a group (lowered to 1 so simple matches work)
        self.min_shared_interests = 1
    
    def add_interests(self, phone_number: str, interests: List[str], chat_id: Optional[int] = None):
        """
        Add interests for a user
        
        Args:
            phone_number: User's phone number
            interests: List of interest strings
            chat_id: Optional chat ID for this user
        """
        if phone_number not in self.user_interests:
            self.user_interests[phone_number] = set()
        
        # Normalize interests to lowercase
        normalized = [i.lower().strip() for i in interests if i.strip()]
        
        if not normalized:
            logger.warning(f"[WARN]  No valid interests to add for {phone_number}")
            return
        
        # Remove old interests from index
        old_interests = self.user_interests[phone_number].copy()
        for interest in old_interests:
            self.interest_index[interest].discard(phone_number)
        
        # Add new interests
        self.user_interests[phone_number].update(normalized)
        
        # Add to index
        for interest in normalized:
            self.interest_index[interest].add(phone_number)
        
        if chat_id:
            self.user_chat_ids[phone_number] = chat_id
        
        logger.info(f"[INTEREST] Updated interests for {phone_number}: {normalized} (total: {len(self.user_interests[phone_number])} interests)")
        logger.debug(f"[INTEREST] All users with interests: {list(self.user_interests.keys())}")
    
    def get_user_interests(self, phone_number: str) -> Set[str]:
        """Get interests for a user"""
        return self.user_interests.get(phone_number, set())
    
    def find_matches(self, phone_number: str, min_shared: Optional[int] = None) -> List[Tuple[str, List[str]]]:
        """
        Find users with shared interests
        
        Args:
            phone_number: User to find matches for
            min_shared: Minimum number of shared interests (default: self.min_shared_interests)
            
        Returns:
            List of (matched_phone, shared_interests) tuples
        """
        if min_shared is None:
            min_shared = self.min_shared_interests
        
        user_interests = self.get_user_interests(phone_number)
        if not user_interests:
            return []
        
        matches = []
        
        logger.debug(f"[MATCH] Finding matches for {phone_number} with interests: {user_interests}")
        logger.debug(f"[MATCH] Total users in tracker: {len(self.user_interests)}")
        
        for other_phone, other_interests in self.user_interests.items():
            if other_phone == phone_number:
                continue
            
            logger.debug(f"[MATCH] Checking {other_phone} with interests: {other_interests}")
            
            # Check cooldown (avoid spam)
            match_key = tuple(sorted([phone_number, other_phone]))
            if match_key in self.recent_matches:
                time_diff = time.time() - self.recent_matches[match_key]
                if time_diff < 300:  # 5 min cooldown
                    logger.debug(f"[SKIP]  Skipping {other_phone} - cooldown active ({time_diff:.0f}s remaining)")
                    continue
            
            # Find shared interests
            shared = user_interests & other_interests
            logger.debug(f"[MATCH] Shared interests with {other_phone}: {shared} (need {min_shared})")
            
            if len(shared) >= min_shared:
                matches.append((other_phone, list(shared)))
                logger.info(f"[OK] Found match: {phone_number} <-> {other_phone} (shared: {shared})")
        
        # Sort by number of shared interests (descending)
        matches.sort(key=lambda x: len(x[1]), reverse=True)
        
        logger.info(f"[MATCH] Found {len(matches)} match(es) for {phone_number}")
        return matches
    
    def find_group_candidates(self, phone_number: str) -> Optional[Tuple[List[str], List[str]]]:
        """
        Find a group of users to match together based on shared interests
        
        Args:
            phone_number: User to find group for
            
        Returns:
            (list of phone numbers, shared interests) or None
        """
        matches = self.find_matches(phone_number)
        
        if not matches:
            return None
        
        # Start with best match (most shared interests)
        best_match_phone, best_shared = matches[0]
        group_members = [phone_number, best_match_phone]
        group_interests = set(best_shared)
        
        # Try to add more members who share interests with the group
        for other_phone, shared_interests in matches[1:]:
            if len(group_members) >= 5:  # Max group size
                break
            
            # Check if this person shares interests with the group
            other_interests_set = set(shared_interests)
            common_with_group = group_interests & other_interests_set
            
            if len(common_with_group) >= self.min_shared_interests:
                group_members.append(other_phone)
                group_interests = common_with_group
        
        if len(group_members) >= 2:
            return (group_members, list(group_interests))
        
        return None
    
    def create_group(self, members: List[str], shared_interests: List[str], 
                    group_chat_id: Optional[int] = None, display_name: Optional[str] = None) -> str:
        """
        Create a new group
        
        Args:
            members: List of phone numbers in the group
            shared_interests: Interests shared by the group
            group_chat_id: Series API chat ID for the group
            display_name: Optional display name for the group
            
        Returns:
            group_id: Unique group identifier
        """
        self._group_counter += 1
        group_id = f"group_{self._group_counter}"
        
        if not display_name:
            display_name = self._generate_group_name(shared_interests)
        
        self.groups[group_id] = (display_name, members, shared_interests, group_chat_id)
        
        # Update user groups
        for phone in members:
            if group_id not in self.user_groups[phone]:
                self.user_groups[phone].append(group_id)
        
        # Mark as recently matched (cooldown)
        for i, phone1 in enumerate(members):
            for phone2 in members[i+1:]:
                match_key = tuple(sorted([phone1, phone2]))
                self.recent_matches[match_key] = time.time()
        
        logger.info(f"[OK] Created group '{display_name}' ({group_id}) with {len(members)} members: {shared_interests}")
        
        return group_id
    
    def _generate_group_name(self, interests: List[str]) -> str:
        """Generate a fun group name from interests"""
        if not interests:
            return "New Friends ✨"
        
        import random
        templates = [
            "{} Squad 🔥",
            "{} Crew ✨",
            "{} Gang 💪",
            "{} Buddies [MATCH]",
            "The {} People 🙌"
        ]
        
        template = random.choice(templates)
        main_interest = interests[0].title()
        
        return template.format(main_interest)
    
    def get_user_chat_id(self, phone_number: str) -> Optional[int]:
        """Get the 1:1 chat ID for a user"""
        return self.user_chat_ids.get(phone_number)
    
    def is_user_in_group(self, phone_number: str, group_id: str) -> bool:
        """Check if user is in a group"""
        return group_id in self.user_groups.get(phone_number, [])
    
    def find_existing_groups_to_join(self, phone_number: str) -> List[Tuple[str, List[str], int]]:
        """
        Find existing groups that this user can join based on shared interests
        
        Args:
            phone_number: User to find groups for
            
        Returns:
            List of (group_id, shared_interests, group_chat_id) tuples
        """
        user_interests = self.get_user_interests(phone_number)
        if not user_interests:
            return []
        
        matching_groups = []
        
        for group_id, (name, members, group_interests, chat_id) in self.groups.items():
            # Skip if user is already in this group
            if phone_number in members:
                continue
            
            # Check if user shares interests with the group
            group_interests_set = set(group_interests)
            shared = user_interests & group_interests_set
            
            if len(shared) >= self.min_shared_interests and chat_id:
                matching_groups.append((group_id, list(shared), chat_id))
        
        return matching_groups
    
    def add_member_to_group(self, phone_number: str, group_id: str) -> bool:
        """
        Add a user to an existing group
        
        Args:
            phone_number: User to add
            group_id: Group to add them to
            
        Returns:
            bool: True if successfully added
        """
        if group_id not in self.groups:
            return False
        
        name, members, interests, chat_id = self.groups[group_id]
        
        if phone_number in members:
            return False  # Already in group
        
        # Add to members
        members.append(phone_number)
        
        # Update user groups
        if group_id not in self.user_groups[phone_number]:
            self.user_groups[phone_number].append(group_id)
        
        # Update group in tracker
        self.groups[group_id] = (name, members, interests, chat_id)
        
        logger.info(f"[OK] Added {phone_number} to group {group_id}")
        return True
    
    def get_group_chat_id(self, group_id: str) -> Optional[int]:
        """Get the Series API chat ID for a group"""
        if group_id not in self.groups:
            return None
        _, _, _, chat_id = self.groups[group_id]
        return chat_id
    
    def is_chat_id_a_group(self, chat_id: int) -> bool:
        """
        Check if a chat_id belongs to a group we've created
        
        Args:
            chat_id: Chat ID to check
            
        Returns:
            bool: True if chat_id is a group chat
        """
        for group_id, (name, members, interests, group_chat_id) in self.groups.items():
            if group_chat_id == chat_id:
                return True
        return False
    
    def get_group_info_by_chat_id(self, chat_id: int) -> Optional[Tuple[str, List[str], List[str]]]:
        """
        Get group information by chat_id
        
        Args:
            chat_id: Chat ID to look up
            
        Returns:
            (group_id, display_name, members, shared_interests) or None
        """
        for group_id, (name, members, interests, group_chat_id) in self.groups.items():
            if group_chat_id == chat_id:
                return (group_id, name, members, interests)
        return None
    
    def get_stats(self) -> Dict:
        """Get tracker statistics"""
        return {
            "total_users": len(self.user_interests),
            "total_groups": len(self.groups),
            "interests_tracked": len(self.interest_index),
            "users_with_interests": sum(1 for interests in self.user_interests.values() if interests)
        }


# Singleton instance
interest_tracker = InterestTracker()

