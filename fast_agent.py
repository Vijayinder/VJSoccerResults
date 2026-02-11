# fast_agent.py - ENHANCED VERSION WITH ADVANCED FILTERING
"""
Dribl Soccer Stats Fast Agent - Enhanced Edition
=================================================
Features:
- Personal team configuration (Heidelberg United FC U16)
- Advanced filtering for top scorers, yellow/red cards by team/age group
- Detailed player match-by-match stats
- Enhanced player profile with jersey, cards, etc.
- Date format: dd-mmm (e.g., 09-Feb)
- Non-player (coach/staff) support
- Time information for goals and cards
"""

import os
import json
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from rapidfuzz import process, fuzz

# ---------------------------------------------------------
# USER CONFIGURATION
# ---------------------------------------------------------
USER_CONFIG = {
    "team": "Heidelberg United FC U16",
    "club": "Heidelberg United FC",
    "age_group": "U16"
}

# ---------------------------------------------------------
# CLUB NAME ALIASES
# ---------------------------------------------------------
# Common variations of club names mapped to their canonical names
CLUB_ALIASES = {
    # Heidelberg variations
    "heidelberg": "Heidelberg United FC",
    "heidelberg united": "Heidelberg United FC",
    "heidelberg utd": "Heidelberg United FC",
    "heidelberg fc": "Heidelberg United FC",
    "heidelberg united fc": "Heidelberg United FC",
    "bergers": "Heidelberg United FC",  # Nickname
    "heid": "Heidelberg United FC",
    
    # Brunswick variations
    "brunswick": "Brunswick Juventus FC",
    "brunswick juventus": "Brunswick Juventus FC",
    "brunswick juve": "Brunswick Juventus FC",
    "juve": "Brunswick Juventus FC",
    "brunswick fc": "Brunswick Juventus FC",
    
    # Essendon variations
    "essendon": "Essendon Royals SC",
    "essendon royals": "Essendon Royals SC",
    "royals": "Essendon Royals SC",
    "essendon sc": "Essendon Royals SC",
    
    # Avondale variations
    "avondale": "Avondale FC",
    "avondale fc": "Avondale FC",
    
    # Altona variations
    "altona": "Altona Magic SC",
    "altona magic": "Altona Magic SC",
    "magic": "Altona Magic SC",
    "altona sc": "Altona Magic SC",
    
    # Box Hill variations
    "box hill": "Box Hill United SC",
    "box hill united": "Box Hill United SC",
    "boxhill": "Box Hill United SC",
    
    # Manningham variations
    "manningham": "Manningham United Blues FC",
    "manningham united": "Manningham United Blues FC",
    "manningham blues": "Manningham United Blues FC",
    "blues": "Manningham United Blues FC",
    
    # Bulleen variations
    "bulleen": "FC Bulleen Lions",
    "bulleen lions": "FC Bulleen Lions",
    "fc bulleen": "FC Bulleen Lions",
    "lions": "FC Bulleen Lions",
    
    # Bentleigh variations (to prevent false matches)
    "bentleigh": "Bentleigh Greens SC",
    "bentleigh greens": "Bentleigh Greens SC",
    "greens": "Bentleigh Greens SC",
    
    # Hume City variations
    "hume": "Hume City FC",
    "hume city": "Hume City FC",
    "hume city fc": "Hume City FC",

    # Add more as needed...
}

def get_canonical_club_name(query: str) -> Optional[str]:
    """
    Get canonical club name from query using aliases
    Returns the full club name without age group
    """
    query_lower = query.lower().strip()
    
    # Check direct match in aliases
    if query_lower in CLUB_ALIASES:
        return CLUB_ALIASES[query_lower]
    
    # Check if query contains any alias
    for alias, canonical in CLUB_ALIASES.items():
        if alias in query_lower:
            return canonical
    
    return None

# ---------------------------------------------------------
# 1. Load JSON data files
# ---------------------------------------------------------

# Get the directory where this file is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

def load_json(name: str):
    """Load and parse JSON file from data directory"""
    possible_paths = [
        os.path.join(DATA_DIR, name),
        os.path.join("data", name),
        name
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    
    # Return appropriate empty data structure based on filename
    if "players_summary" in name:
        return {"players": []}
    elif "competition_overview" in name:
        return {}
    elif "fixtures" in name or "results" in name or "match_centre" in name or "lineups" in name:
        return []
    else:
        return {}

# Load data
results = load_json("master_results.json")
fixtures = load_json("fixtures.json")
players_data = load_json("players_summary.json")
players_summary = players_data.get("players", [])
match_centre_data = load_json("master_match_centre.json")
lineups_data = load_json("master_lineups.json")
competition_overview = load_json("competition_overview.json")

# ---------------------------------------------------------
# 2. Date formatting helper
# ---------------------------------------------------------

def format_date(date_str: str) -> str:
    """Convert date string to dd-mmm format (e.g., 09-Feb)"""
    if not date_str:
        return "TBD"
    try:
        date_part = date_str.split('T')[0] if 'T' in date_str else date_str
        dt = datetime.fromisoformat(date_part)
        return dt.strftime("%d-%b")
    except (ValueError, AttributeError):
        return date_str[:10] if len(date_str) >= 10 else date_str

def format_date_full(date_str: str) -> str:
    """Convert date string to dd-mmm-yyyy format (e.g., 09-Feb-2026)"""
    if not date_str:
        return "TBD"
    try:
        date_part = date_str.split('T')[0] if 'T' in date_str else date_str
        dt = datetime.fromisoformat(date_part)
        return dt.strftime("%d-%b-%Y")
    except (ValueError, AttributeError):
        return date_str[:10] if len(date_str) >= 10 else date_str

def parse_date(date_str: str) -> datetime.date:
    """Parse date string to date object"""
    if not date_str:
        return datetime.min.date()
    try:
        date_part = date_str.split('T')[0] if 'T' in date_str else date_str
        return datetime.fromisoformat(date_part).date()
    except (ValueError, AttributeError):
        return datetime.min.date()

def parse_date_utc_to_aest(date_str: str) -> Optional[datetime]:
    """Parse UTC date string and convert to AEST datetime"""
    if not date_str:
        return None
    try:
        # Parse UTC datetime
        if 'Z' in date_str:
            # Remove 'Z' and parse
            utc_dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        elif 'T' in date_str:
            utc_dt = datetime.fromisoformat(date_str)
        else:
            return None
        
        # Convert to AEST (UTC+10 or UTC+11 depending on DST)
        from datetime import timezone, timedelta
        aest = timezone(timedelta(hours=10))  # Standard time (non-DST)
        aest_dt = utc_dt.astimezone(aest)
        return aest_dt
    except (ValueError, AttributeError):
        return None

def get_last_sunday() -> datetime.date:
    """Get the date of last Sunday"""
 #   today = datetime.now().date()
    melbourne_tz = pytz.timezone('Australia/Melbourne')
    today = datetime.now(melbourne_tz).date()
    days_since_sunday = (today.weekday() + 1) % 7  # Monday = 0, Sunday = 6
    if days_since_sunday == 0:
        # Today is Sunday, return last Sunday
        last_sunday = today - timedelta(days=7)
    else:
        last_sunday = today - timedelta(days=days_since_sunday)
    return last_sunday

def format_minutes(minutes_list: List) -> str:
    """Format list of minutes into readable string"""
    if not minutes_list:
        return ""
    try:
        # Convert to integers and sort
        mins = sorted([int(m) for m in minutes_list if m])
        if not mins:
            return ""
        # Return as comma-separated string with ' suffix
        return ", ".join([f"{m}'" for m in mins])
    except (ValueError, TypeError):
        return ""

# ---------------------------------------------------------
# 3. Build search indices
# ---------------------------------------------------------

def fuzzy_find(query: str, choices: List[str], threshold: int = 60) -> Optional[str]:
    if not choices:
        return None
    res = process.extractOne(query, choices, scorer=fuzz.WRatio)
    if not res:
        return None
    match, score, _ = res
    return match if score >= threshold else None

# Build player index
player_names = []
player_lookup = {}

for p in players_summary:
    first = p.get("first_name", "")
    last = p.get("last_name", "")
    full_name = f"{first} {last}".strip()
    
    if full_name:
        player_names.append(full_name)
        player_lookup[full_name.lower()] = p

# Build team index
team_names = sorted({
    p.get("team_name", "")
    for p in players_summary
    if p.get("team_name")
})

# Build league index
league_names = sorted({
    p.get("league_name", "")
    for p in players_summary
    if p.get("league_name")
})

# Build competition index
competition_names = sorted({
    p.get("competition_name", "")
    for p in players_summary
    if p.get("competition_name")
})

def fuzzy_team(q: str) -> Optional[str]:
    """
    Improved team matching with better precision
    Prioritizes exact substring matches over fuzzy matches
    """
    q_lower = q.lower().strip()
    team_names_lower = [t.lower() for t in team_names]
    
    # Step 1: Check for exact match
    if q_lower in team_names_lower:
        return q_lower
    
    # Step 2: Check for exact substring match (team name contains the query)
    exact_matches = [t for t in team_names_lower if q_lower in t]
    if len(exact_matches) == 1:
        return exact_matches[0]
    elif len(exact_matches) > 1:
        # Multiple matches - try to find the shortest one (most specific)
        return min(exact_matches, key=len)
    
    # Step 3: Check if query contains team name (query is longer than team name)
    reverse_matches = [t for t in team_names_lower if t in q_lower]
    if len(reverse_matches) == 1:
        return reverse_matches[0]
    elif len(reverse_matches) > 1:
        # Multiple matches - return the longest match (most specific)
        return max(reverse_matches, key=len)
    
    # Step 4: Fall back to fuzzy matching with higher threshold
    return fuzzy_find(q_lower, team_names_lower, threshold=75)

def normalize_team(query: str) -> Optional[str]:
    """Resolve a query string to a canonical team name using aliases and fuzzy matching."""
    if not query:
        return None
    
    q_lower = query.lower().strip()
    
    # NEW: Check for club aliases first to ensure "Heidelberg" -> "Heidelberg United FC"
    canonical_club = get_canonical_club_name(q_lower)
    age_group = extract_age_group(q_lower)
    
    # If we found an alias, rebuild the query to be more specific
    if canonical_club:
        if age_group:
            query = f"{canonical_club} {age_group}"
        else:
            query = canonical_club

    # Now proceed with the existing fuzzy search logic
    return fuzzy_team(query)
# ---------------------------------------------------------
# 4. Core search utilities
# ---------------------------------------------------------

def find_matches_by_teams_or_hash(
    home_like: Optional[str] = None,
    away_like: Optional[str] = None,
    match_hash_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    matches = []
    for m in match_centre_data:
        mh = m.get("match_hash_id")
        result = m.get("result", {})
        attrs = result.get("attributes", {})

        if match_hash_id and mh == match_hash_id:
            matches.append(m)
            continue

        home = attrs.get("home_team_name", "")
        away = attrs.get("away_team_name", "")

        if home_like:
            norm_home = normalize_team(home_like) or home_like
            if norm_home.lower() not in home.lower():
                continue

        if away_like:
            norm_away = normalize_team(away_like) or away_like
            if norm_away.lower() not in away.lower():
                continue

        if home_like or away_like:
            matches.append(m)

    return matches

def find_lineup_by_match_hash(match_hash_id: str) -> Optional[Dict[str, Any]]:
    for l in lineups_data:
        if l.get("match_hash_id") == match_hash_id:
            return l
    return None

# ---------------------------------------------------------
# 5. FILTERING HELPERS
# ---------------------------------------------------------

def extract_age_group(text: str) -> Optional[str]:
    """Extract age group from text (e.g., 'U16', 'U15')"""
    match = re.search(r'\bu(\d{2})\b', text.lower())
    if match:
        return f"U{match.group(1)}"
    return None

def extract_team_name(text: str) -> Optional[str]:
    """
    Extract full team name from text (with age group)
    Only returns a value if we can match to an exact existing team
    """
    # Remove common keywords
    clean = re.sub(r'\b(top|scorer|scorers?|yellow|red|card|cards?|in|for|details?|show|list|with|non|player|players?|staff|coach|coaches?)\b', '', text, flags=re.IGNORECASE).strip()
    
    # If only age group remains (like "U16"), don't treat as team name
    if re.match(r'^u\d{2}$', clean.lower().strip()):
        return None
    
    # Check if there's a recognizable full team name (exact match in team_names)
    if clean:
        # Try exact match first
        for team in team_names:
            if clean.lower() == team.lower():
                return team
        
        # Try normalized match
        normalized = normalize_team(clean)
        if normalized and normalized in team_names:
            return normalized
    
    return None

def extract_base_club_name(text: str) -> Optional[str]:
    """
    Extract base club name (without age group) from text
    E.g., "Heidelberg United" from "yellow cards Heidelberg United"
    Improved to handle partial club names with alias lookup
    """
    # Remove common keywords
    clean = re.sub(r'\b(top|scorer|scorers?|yellow|red|card|cards?|in|for|details?|show|list|with|non|player|players?|staff|coach|coaches?|team|stats?)\b', '', text, flags=re.IGNORECASE).strip()
    
    # Remove age group pattern if present
    clean = re.sub(r'\s*u\d{2}\s*$', '', clean, flags=re.IGNORECASE).strip()
    
    if clean:
        # FIRST: Try club alias lookup
        canonical = get_canonical_club_name(clean)
        if canonical:
            return canonical
        
        # SECOND: Try direct substring matching in team names (more lenient)
        clean_lower = clean.lower()
        
        # Find all teams that contain this substring
        matching_teams = [t for t in team_names if clean_lower in t.lower()]
        
        if matching_teams:
            # Extract base club names (without age group)
            base_names = set()
            for team in matching_teams:
                base = re.sub(r'\s+U\d{2}$', '', team).strip()
                base_names.add(base)
            
            # If all matches share the same base name, return it
            if len(base_names) == 1:
                return base_names.pop()
            # If multiple base names, try fuzzy matching
            elif len(base_names) > 1:
                # Return the one that's most similar to the query
                best_match = fuzzy_find(clean_lower, [b.lower() for b in base_names], threshold=60)
                if best_match:
                    return next((b for b in base_names if b.lower() == best_match), None)
        
        # THIRD: Fallback to old method
        normalized = normalize_team(clean)
        if normalized:
            base = re.sub(r'\s+U\d{2}$', '', normalized).strip()
            return base
    
    return None

def filter_players_by_criteria(players: List[Dict], query: str, include_non_players: bool = False) -> List[Dict]:
    """
    Filter players by age group and/or team name from query
    
    Args:
        players: List of player/person dictionaries
        query: Search query string
        include_non_players: If True, only return non-players (coaches/staff)
    """
    age_group = extract_age_group(query)
    team_name = extract_team_name(query)  # Full team name with age group
    base_club = extract_base_club_name(query)  # Club name without age group
    
    filtered = players
    
    # Filter by role if looking for non-players
    if include_non_players:
        filtered = [
            p for p in filtered
            if p.get("role") and p.get("role") != "player"
        ]
    else:
        # Only players
        filtered = [
            p for p in filtered
            if not p.get("role") or p.get("role") == "player"
        ]
    
    # Now apply team/age filters
    # Priority order:
    # 1. Specific team name (full name with age group) - most specific
    # 2. Base club + age group - build exact match
    # 3. Base club only - match all age groups
    # 4. Age group only - match all clubs
    
    if team_name:
        # Has full team name - use exact match
        filtered = [
            p for p in filtered
            if team_name.lower() in p.get("team_name", "").lower()
        ]
    elif base_club and age_group:
        # Has both club and age group - build exact team name
        exact_team = f"{base_club} {age_group}"
        filtered = [
            p for p in filtered
            if exact_team.lower() in p.get("team_name", "").lower()
        ]
    elif base_club:
        # Has club only - match all age groups from this club
        filtered = [
            p for p in filtered
            if base_club.lower() in p.get("team_name", "").lower()
        ]
    elif age_group:
        # Has age group only - match all clubs with this age group
        filtered = [
            p for p in filtered
            if age_group.lower() in p.get("team_name", "").lower()
        ]
    
    return filtered

# ---------------------------------------------------------
# 6. FIXTURES TOOL
# ---------------------------------------------------------

def tool_fixtures(query: str = "", limit: int = 10, use_user_team: bool = False) -> str:
    """Show upcoming fixtures with correct AEST timezone logic"""
    if use_user_team and not query:
        query = USER_CONFIG["team"]
    
    melbourne_tz = pytz.timezone('Australia/Melbourne')
    today = datetime.now(melbourne_tz).date()  

    upcoming = []
    for f in fixtures:
        attrs = f.get("attributes", {})
        date_str = attrs.get("date", "")
        
        # Shift UTC to AEST to get the correct day and time
        match_dt = parse_date_utc_to_aest(date_str)
        if not match_dt:
            continue
            
        fixture_date = match_dt.date()
        if fixture_date >= today:
            # Store the date, the local time string, and attributes
            local_time = match_dt.strftime("%I:%M %p")
            upcoming.append((fixture_date, local_time, attrs))
    
    # Sort by date
    upcoming.sort(key=lambda x: x[0])
    
    # Filter by team if query provided
    if query:
        team = normalize_team(query) or query
        filtered = []
        for date, l_time, attrs in upcoming:
            home = attrs.get("home_team_name", "")
            away = attrs.get("away_team_name", "")
            if team.lower() in home.lower() or team.lower() in away.lower():
                filtered.append((date, l_time, attrs))
        upcoming = filtered
    
    if not upcoming:
        team_name = query if query else "any team"
        return f"❌ No upcoming fixtures found for {team_name}"
    
    upcoming = upcoming[:limit]
    
    # Heading logic
    if use_user_team and query == USER_CONFIG["team"]:
        lines = [f"📅 **Your Upcoming Matches** ({len(upcoming)} matches)\n"]
    else:
        team_display = query if query else "All Teams"
        lines = [f"📅 **Upcoming Fixtures - {team_display}** ({len(upcoming)} matches)\n"]
    
    for i, (fixture_date, local_time, attrs) in enumerate(upcoming, 1):
        home = attrs.get("home_team_name", "Unknown")
        away = attrs.get("away_team_name", "Unknown")
        venue = attrs.get("ground_name", attrs.get("venue", "TBD")) # Ground name is more accurate in Dribl
        competition = attrs.get("competition_name", "")
        
        date_display = fixture_date.strftime("%d-%b-%Y (%a)")
        days_until = (fixture_date - today).days
        
        # Status Badge
        if days_until == 0:
            days_str = "🔴 TODAY!"
        elif days_until == 1:
            days_str = "⚠️ Tomorrow"
        else:
            days_str = f"🗓️ In {days_until} days"
        
        # User Team specific display (HOME/AWAY indicator)
        if use_user_team and query == USER_CONFIG["team"]:
            if USER_CONFIG["club"].lower() in home.lower():
                match_type = "🏠 HOME"
                opponent = away
            else:
                match_type = "✈️ AWAY"
                opponent = home
            
            lines.append(f"**Match {i}:** {days_str}")
            lines.append(f"    📅 {date_display} at {local_time}")
            lines.append(f"    {match_type} vs {opponent}")
            lines.append(f"    🏟️ {venue}")
        else:
            lines.append(f"**{date_display}** {days_str}")
            lines.append(f"    ⏰ {local_time} | 🏟️ {venue}")
            lines.append(f"    ⚽ {home} vs {away}")
            
        if competition:
            lines.append(f"    🏆 {competition}")
        lines.append("")
    
    return "\n".join(lines)

# ---------------------------------------------------------
# 6B. MISSING SCORES TOOL
# ---------------------------------------------------------

def tool_missing_scores(query: str = "") -> Any:
    # 1. SETUP TIMEZONES AND BOUNDARIES FIRST
    melbourne_tz = pytz.timezone('Australia/Melbourne')
    now_aest = datetime.now(melbourne_tz)
    today = now_aest.date()
    
    # Optional: Keep last_sunday if you want to limit how far back to look,
    # but for "Missing Scores", usually you want all overdue matches.
    last_sunday = get_last_sunday() 

    missing_scores = []

    # ... (Your logic for target_leagues and include_all_leagues) ...

    for fixture in fixtures:
        attrs = fixture.get("attributes", {})
        date_str = attrs.get("date", "")
        if not date_str:
            continue
        
        # 2. PARSE UTC TO AEST
        match_datetime = parse_date_utc_to_aest(date_str)
        if not match_datetime:
            continue
        
        match_date = match_datetime.date()
        
        # 3. FIX THE BOUNDARY
        # Change from '>= last_sunday' to '> today' 
        # This ensures Feb 8 (Sunday) is INCLUDED if today is Feb 11.
        if match_date > today:
            continue
        
        # ... (League and Query filtering logic) ...

        # 4. IDENTIFY MISSING SCORE
        status = attrs.get("status", "").lower()
        home_score = attrs.get("home_score")
        away_score = attrs.get("away_score")
        
        # A score is missing if it's not played/complete OR scores are null
        has_missing_score = (
            status != "complete" or 
            home_score is None or 
            away_score is None
        )

        if has_missing_score:
            missing_scores.append({
                "match_date": match_date,
                "match_datetime": match_datetime, # This is already AEST from parse_date_utc_to_aest
                "home_team": attrs.get("home_team_name", "Unknown"),
                "away_team": attrs.get("away_team_name", "Unknown"),
                "league": attrs.get("league_name", ""),
                "competition": attrs.get("competition_name", ""),
                "round": attrs.get("full_round", attrs.get("round", "")),
                "venue": attrs.get("ground_name", ""),
                "status": status,
                "days_overdue": (today - match_date).days
            })
    
    if not missing_scores:
        return f"✅ No missing scores found! All matches have been entered."
    
    # Sort oldest first
    missing_scores.sort(key=lambda x: x["match_date"])
    
    # 5. FORMAT TABLE DATA
    data = []
    for i, match in enumerate(missing_scores, 1):
        # Format the AEST datetime for display
        # Use %I:%M %p for 12-hour clock (e.g. 03:30 PM)
        aest_display = match["match_datetime"].strftime("%d-%b %I:%M %p")
        
        data.append({
            "#": i,
            "Kickoff (AEST)": aest_display,
            "Days Overdue": match["days_overdue"],
            "Home Team": match["home_team"],
            "Away Team": match["away_team"],
            "Round": match["round"],
            "Venue": match["venue"]
        })
    
    return {
        "type": "table",
        "data": data,
        "title": f"⚠️ Missing Scores ({len(missing_scores)} matches overdue)"
    }
def extract_league_from_league_name(league_name: str) -> str:
    """Extract league from league name (YPL1, YPL2, YSL NW, etc.)"""
    if not league_name:
        return "Other"
    
    league_name_lower = str(league_name).lower()
    
    if "ypl1" in league_name_lower or "ypl 1" in league_name_lower:
        return "YPL1"
    if "ypl2" in league_name_lower or "ypl 2" in league_name_lower:
        return "YPL2"
    if "ysl" in league_name_lower and ("north-west" in league_name_lower or "nw" in league_name_lower or "north west" in league_name_lower):
        return "YSL NW"
    if "ysl" in league_name_lower and ("south-east" in league_name_lower or "se" in league_name_lower or "south east" in league_name_lower):
        return "YSL SE"
    if "vpl men" in league_name_lower:
        return "VPL Men"
    if "vpl women" in league_name_lower:
        return "VPL Women"
    if "ysl" in league_name_lower:
        return "YSL"
    
    return "Other"

# ---------------------------------------------------------
# 7. ENHANCED CARD QUERIES WITH FILTERING AND TIME INFO
# ---------------------------------------------------------

def tool_yellow_cards(query: str = "", show_details: bool = False, include_non_players: bool = False) -> str:
    """List all people with yellow cards - supports age group and team filtering"""
    
    # Initialize variables to avoid UnboundLocalError
    age_group = None
    team_name = None
    base_club = None
    
    # 1. Get everyone with a yellow card
    players_with_yellows = [
        p for p in players_summary 
        if p.get("stats", {}).get("yellow_cards", 0) > 0
    ]
    
    # 2. Apply filters based on the query
    if query:
        # Extract filters from the query text
        age_group = extract_age_group(query)
        team_name = extract_team_name(query)
        base_club = extract_base_club_name(query)
        
        # filter_players_by_criteria handles the logic for specific team/club/age group
        players_with_yellows = filter_players_by_criteria(players_with_yellows, query, include_non_players=include_non_players)
    elif include_non_players:
        # If no query but non-players requested, filter to non-players only
        players_with_yellows = [p for p in players_with_yellows if p.get("role") and p.get("role") != "player"]
    
    if not players_with_yellows:
        filter_desc = f" matching '{query}'" if query else ""
        person_type = "non-players" if include_non_players else "players"
        return f"❌ No {person_type} with yellow cards found{filter_desc}"
    
    # Sort by yellow card count (descending)
    players_with_yellows.sort(key=lambda x: x.get("stats", {}).get("yellow_cards", 0), reverse=True)
    
    # 3. Build filter description for the title/header
    filter_parts = []
    if include_non_players:
        filter_parts.append("Non-Players")
    if age_group and not team_name:
        filter_parts.append(age_group)
    elif base_club and not age_group and not team_name:
        filter_parts.append(base_club)
    elif team_name:
        filter_parts.append(team_name)
    
    filter_desc = " - " + " ".join(filter_parts) if filter_parts else ""
    
    # 4. Return detailed text format or structured table data
    if show_details:
        lines = [f"🟨 **Yellow Cards{filter_desc}** ({len(players_with_yellows)} total)\n"]
        
        for p in players_with_yellows[:50]:
            stats = p.get("stats", {})
            yellows = stats.get("yellow_cards", 0)
            role = p.get("role", "player")
            role_display = f" ({role.title()})" if role != "player" else ""
            
            lines.append(
                f"👤 **{p.get('first_name')} {p.get('last_name')}**{role_display} (#{p.get('jersey')})\n"
                f"   {p.get('team_name')} | 🟨 {yellows} card(s)"
            )
            
            matches = p.get("matches", [])
            for m in matches:
                if m.get("yellow_cards", 0) > 0:
                    venue = "🏠" if m.get('home_or_away') == 'home' else "✈️"
                    date_str = format_date(m.get('date', ''))
                    # Ensure format_minutes helper is used for yellow card times
                    yellow_mins = format_minutes(m.get('yellow_minutes', []))
                    yellow_display = f"🟨 {m.get('yellow_cards')}" + (f" ({yellow_mins})" if yellow_mins else "")
                    lines.append(
                        f"   {venue} vs {m.get('opponent_team_name')} - {date_str} - {yellow_display}"
                    )
            lines.append("")
        
        return "\n".join(lines)
    else:
        # Return as table data (e.g. for top scorers style view)
        data = []
        for i, p in enumerate(players_with_yellows[:30], 1):
            stats = p.get("stats", {})
            yellows = stats.get("yellow_cards", 0)
            role = p.get("role", "player")
            name = f"{p.get('first_name')} {p.get('last_name')}"
            if role != "player":
                name += f" ({role.title()})"
            team = p.get('team_name', '')
            
            row_data = {
                "Rank": i,
                "Name": name,
                "Team": team,
                "Yellow Cards": yellows,
            }
            
            # Only add Matches and Goals for players
            if role == "player" or not role:
                row_data["Matches"] = stats.get("matches_played", 0)
                row_data["Goals"] = stats.get("goals", 0)
            
            data.append(row_data)
        
        return {
            "type": "table",
            "data": data,
            "title": f"🟨 Yellow Cards{filter_desc} ({len(players_with_yellows)} total, showing top 30)"
        }

def tool_red_cards(query: str = "", show_details: bool = False, include_non_players: bool = False) -> str:
    """List all people with red cards - supports age group and team filtering"""
    players_with_reds = [
        p for p in players_summary 
        if p.get("stats", {}).get("red_cards", 0) > 0
    ]
    
    # Apply filters
    if query:
        players_with_reds = filter_players_by_criteria(players_with_reds, query, include_non_players=include_non_players)
    elif include_non_players:
        # Filter for non-players even without query
        players_with_reds = [p for p in players_with_reds if p.get("role") and p.get("role") != "player"]
    
    if not players_with_reds:
        filter_desc = f" matching '{query}'" if query else ""
        person_type = "non-players" if include_non_players else "players"
        return f"❌ No {person_type} with red cards found{filter_desc}"
    
    players_with_reds.sort(key=lambda x: x.get("stats", {}).get("red_cards", 0), reverse=True)
    
    # Build filter description based on what was actually extracted
    age_group = extract_age_group(query) if query else None
    team_name = extract_team_name(query) if query else None
    base_club = extract_base_club_name(query) if query else None
    
    filter_parts = []
    if include_non_players:
        filter_parts.append("Non-Players")
    if age_group and not team_name:
        filter_parts.append(age_group)
    elif base_club and not age_group and not team_name:
        filter_parts.append(base_club)
    elif team_name:
        filter_parts.append(team_name)
    
    filter_desc = " - " + " ".join(filter_parts) if filter_parts else ""
    
    if show_details:
        lines = [f"🟥 **Red Cards{filter_desc}** ({len(players_with_reds)} total)\n"]
        
        for p in players_with_reds:
            stats = p.get("stats", {})
            reds = stats.get("red_cards", 0)
            role = p.get("role", "player")
            role_display = f" ({role.title()})" if role != "player" else ""
            
            lines.append(
                f"👤 **{p.get('first_name')} {p.get('last_name')}**{role_display} (#{p.get('jersey')})\n"
                f"   {p.get('team_name')} | 🟥 {reds} card(s)"
            )
            
            matches = p.get("matches", [])
            for m in matches:
                if m.get("red_cards", 0) > 0:
                    venue = "🏠" if m.get('home_or_away') == 'home' else "✈️"
                    date_str = format_date(m.get('date', ''))
                    red_mins = format_minutes(m.get('red_minutes', []))
                    red_display = "🟥 RED CARD" + (f" ({red_mins})" if red_mins else "")
                    lines.append(
                        f"   {venue} vs {m.get('opponent_team_name')} - {date_str} - {red_display}"
                    )
            lines.append("")
        
        return "\n".join(lines)
    else:
        # Return as table data
        data = []
        for i, p in enumerate(players_with_reds, 1):
            stats = p.get("stats", {})
            reds = stats.get("red_cards", 0)
            role = p.get("role", "player")
            name = f"{p.get('first_name')} {p.get('last_name')}"
            if role != "player":
                name += f" ({role.title()})"
            team = p.get('team_name', '')
            
            row_data = {
                "Rank": i,
                "Name": name,
                "Team": team,
                "Red Cards": reds,
            }
            
            # Only add Matches and Goals for players
            if role == "player" or not role:
                row_data["Matches"] = stats.get("matches_played", 0)
                row_data["Goals"] = stats.get("goals", 0)
            
            data.append(row_data)
        
        return {
            "type": "table",
            "data": data,
            "title": f"🟥 Red Cards{filter_desc} ({len(players_with_reds)} total)"
        }


# ---------------------------------------------------------
# 8. ENHANCED TOP SCORERS WITH FILTERING
# ---------------------------------------------------------

def tool_top_scorers(query: str = "", limit: int = 20):
    """List top goal scorers - supports age group and team filtering"""
    scorers = [
        p for p in players_summary 
        if p.get("stats", {}).get("goals", 0) > 0
        and (not p.get("role") or p.get("role") == "player")  # Only players
    ]
    
    # Apply filters
    if query:
        scorers = filter_players_by_criteria(scorers, query, include_non_players=False)
    
    if not scorers:
        filter_desc = f" matching '{query}'" if query else ""
        return {"type": "error", "message": f"❌ No goal scorers found{filter_desc}"}
    
    scorers.sort(key=lambda x: x.get("stats", {}).get("goals", 0), reverse=True)
    
    # Build filter description based on what was actually extracted
    age_group = extract_age_group(query) if query else None
    team_name = extract_team_name(query) if query else None
    base_club = extract_base_club_name(query) if query else None
    
    filter_parts = []
    if age_group and not team_name:
        # Only age group specified
        filter_parts.append(age_group)
    elif base_club and not age_group and not team_name:
        # Only base club specified
        filter_parts.append(base_club)
    elif team_name:
        # Specific team specified
        filter_parts.append(team_name)
    
    filter_desc = " - " + " ".join(filter_parts) if filter_parts else ""
    
    # Return as structured data for table display
    data = []
    for i, p in enumerate(scorers[:limit], 1):
        stats = p.get("stats", {})
        goals = stats.get("goals", 0)
        matches = stats.get("matches_played", 0)
        yellows = stats.get("yellow_cards", 0)
        reds = stats.get("red_cards", 0)
        name = f"{p.get('first_name')} {p.get('last_name')}"
        team = p.get('team_name', '')
        
        data.append({
            "Rank": i,
            "Player": name,
            "Team": team,
            "Goals": goals,
            "Matches": matches,
            "Goals/Match": round(goals / matches, 2) if matches > 0 else 0,
            "Yellow": yellows,
            "Red": reds
        })
    
    return {
        "type": "table",
        "data": data,
        "title": f"⚽ Top Scorers{filter_desc} ({len(scorers)} players with goals, showing top {min(limit, len(scorers))})"
    }


# ---------------------------------------------------------
# 9. TEAM STATS
# ---------------------------------------------------------

def tool_team_stats(query: str = "") -> str:
    """Get team statistics including squad overview and top performers"""
    # If query is just an age group, use user's club
    age_groups = ['u13', 'u14', 'u15', 'u16', 'u17', 'u18']
    query_lower = query.lower().strip()
    
    if query_lower in age_groups:
        team_query = f"{USER_CONFIG['club']} {query.upper()}"
    else:
        team_query = query
    
    # Try to get canonical club name first
    canonical_club = get_canonical_club_name(team_query)
    age_group = extract_age_group(team_query)
    
    # Build the team filter
    if canonical_club and age_group:
        # Exact team match: "Heidelberg United FC U16"
        team_filter = f"{canonical_club} {age_group}"
    elif canonical_club:
        # Club only: match all age groups
        team_filter = canonical_club
    else:
        # Fall back to normalize_team
        team_filter = normalize_team(team_query) or team_query
    
    # Filter players - use exact match if we have canonical name, otherwise substring
    if canonical_club:
        # Exact matching for canonical club names
        if age_group:
            players = [p for p in players_summary if p.get("team_name", "") == team_filter]
        else:
            # Match all teams from this club (any age group)
            players = [p for p in players_summary if p.get("team_name", "").startswith(canonical_club)]
    else:
        # Substring matching for other cases
        players = [p for p in players_summary if team_filter.lower() in p.get("team_name", "").lower()]
    
    # Filter to only players (not coaches/staff)
    players = [p for p in players if not p.get("role") or p.get("role") == "player"]
    
    if not players:
        return f"❌ No players found for team: {query}"
    
    lines = [f"📊 **Team Statistics: {players[0].get('team_name', team_filter)}**\n"]
    
    # Overall stats
    total_goals = sum(p.get("stats", {}).get("goals", 0) for p in players)
    total_yellows = sum(p.get("stats", {}).get("yellow_cards", 0) for p in players)
    total_reds = sum(p.get("stats", {}).get("red_cards", 0) for p in players)
    
    lines.append(f"**Squad Size:** {len(players)} players")
    lines.append(f"**Total Goals:** {total_goals}")
    lines.append(f"**Discipline:** 🟨 {total_yellows} Yellow | 🟥 {total_reds} Red\n")
    
    # Top scorers
    scorers = sorted(players, key=lambda x: x.get("stats", {}).get("goals", 0), reverse=True)[:10]
    if scorers[0].get("stats", {}).get("goals", 0) > 0:
        lines.append("**🥇 Top Scorers:**")
        for i, p in enumerate(scorers, 1):
            goals = p.get("stats", {}).get("goals", 0)
            if goals > 0:
                matches = p.get("stats", {}).get("matches_played", 0)
                avg = f"({goals/matches:.2f}/match)" if matches > 0 else ""
                lines.append(f"  {i}. {p.get('first_name')} {p.get('last_name')} - ⚽ {goals} {avg}")
            if i >= 5:
                break
    
    # Most carded
    carded = sorted(players, key=lambda x: x.get("stats", {}).get("yellow_cards", 0) + x.get("stats", {}).get("red_cards", 0) * 2, reverse=True)[:5]
    if carded[0].get("stats", {}).get("yellow_cards", 0) + carded[0].get("stats", {}).get("red_cards", 0) > 0:
        lines.append("\n**🟨 Discipline Record:**")
        for i, p in enumerate(carded, 1):
            yellows = p.get("stats", {}).get("yellow_cards", 0)
            reds = p.get("stats", {}).get("red_cards", 0)
            if yellows + reds > 0:
                lines.append(f"  {i}. {p.get('first_name')} {p.get('last_name')} - 🟨 {yellows} 🟥 {reds}")
            if i >= 5:
                break
    
    # Recent team results
    team_results = []
    team_name_to_match = players[0].get('team_name', '') if players else team_filter
    for r in results:
        a = r.get("attributes", {})
        home = a.get("home_team_name", "")
        away = a.get("away_team_name", "")
        if team_name_to_match.lower() in home.lower() or team_name_to_match.lower() in away.lower():
            team_results.append(a)

    team_results.sort(key=lambda x: x.get("date", ""), reverse=True)
    if team_results:
        lines.append(f"\n**📅 Recent Results:**")
        for a in team_results[:5]:
            date_str = format_date(a.get('date', ''))
            hs = a.get('home_score')
            as_ = a.get('away_score')
            
            is_home = team_name_to_match.lower() in a.get('home_team_name', '').lower()
            if is_home:
                result = "🟢 W" if int(hs) > int(as_) else ("🔴 L" if int(hs) < int(as_) else "🟡 D")
            else:
                result = "🟢 W" if int(as_) > int(hs) else ("🔴 L" if int(as_) < int(hs) else "🟡 D")
            
            lines.append(f"  {result} {date_str}: {a.get('home_team_name')} {hs}-{as_} {a.get('away_team_name')}")

    return "\n".join(lines)


def tool_competition_overview(query: str = ""):
    """Display competition overview showing club rankings across all age groups"""
    q = query.upper().strip()
    
    comp_mapping = {
        "YPL1": "YPL1",
        "YPL 1": "YPL1",
        "YPL2": "YPL2",
        "YPL 2": "YPL2",
        "YSL NW": "YSL NW",
        "YSL NORTH WEST": "YSL NW",
        "YSL SE": "YSL SE",
        "YSL SOUTH EAST": "YSL SE",
        "VPL MEN": "VPL Men",
        "VPL WOMEN": "VPL Women"
    }
    
    competition_key = None
    for key, value in comp_mapping.items():
        if key in q or value in q:
            competition_key = value
            break
    
    if not competition_key or competition_key not in competition_overview:
        lines = ["🏆 **Available Competitions:**\n"]
        for comp in sorted(competition_overview.keys()):
            club_count = len(competition_overview[comp]["clubs"])
            age_groups = competition_overview[comp]["age_groups"]
            lines.append(f"**{comp}**: {club_count} clubs, {len(age_groups)} age groups ({', '.join(age_groups)})")
        lines.append("\n💡 Try: 'YPL1 overview', 'YPL2 standings', 'competition overview YSL NW'")
        return "\n".join(lines)
    
    comp_data = competition_overview[competition_key]
    age_groups = sorted(comp_data["age_groups"])
    clubs = comp_data["clubs"]
    
    table_data = []
    for club_data in clubs:
        row = {
            "Rank": club_data["overall_rank"],
            "Club": club_data["club"]
        }
        
        for age in age_groups:
            if age in club_data["age_groups"]:
                row[age] = club_data["age_groups"][age]["position"]
            else:
                row[age] = "-"
        
        row["Total Pos"] = club_data["total_position_points"]
        row["GF"] = club_data["total_gf"]
        row["GA"] = club_data["total_ga"]
        row["GD"] = club_data["total_gf"] - club_data["total_ga"]
        row["Teams"] = club_data["age_group_count"]
        
        table_data.append(row)
    
    return {
        "type": "table",
        "data": table_data,
        "title": f"🏆 {competition_key} Competition Overview - Club Rankings Across Age Groups"
    }


# ---------------------------------------------------------
# 10. PLAYER STATS - ENHANCED WITH TABLE FORMAT AND TIME INFO
# ---------------------------------------------------------

def tool_players(query: str, detailed: bool = False) -> str:
    """Search for player and show stats"""
    q = query.lower().strip()
    
    # Exact substring match
    exact_matches = []
    for full_name, player_data in player_lookup.items():
        if q in full_name:
            exact_matches.append(player_data)
    
    if exact_matches:
        if len(exact_matches) == 1:
            p = exact_matches[0]
            stats = p.get("stats", {})
            matches = p.get("matches", [])
            
            lines = [
                f"👤 **{p.get('first_name')} {p.get('last_name')}**",
                f"   Jersey: #{p.get('jersey')}",
                f"   Club: {p.get('team_name')}",
                f"   League: {p.get('league_name')}",
                f"   Competition: {p.get('competition_name')}\n",
                f"📊 **Season Statistics:**",
                f"   ⚽ Goals: {stats.get('goals', 0)}",
                f"   🎮 Matches Played: {stats.get('matches_played', 0)}",
                f"   🟢 Matches Started: {stats.get('matches_started', 0)}",
                f"   🪑 Bench Appearances: {stats.get('bench_appearances', 0)}",
                f"   🟨 Yellow Cards: {stats.get('yellow_cards', 0)}",
                f"   🟥 Red Cards: {stats.get('red_cards', 0)}",
            ]
            
            if stats.get('matches_played', 0) > 0:
                avg = stats.get('goals', 0) / stats.get('matches_played', 0)
                lines.append(f"   📈 Goals per Match: {avg:.2f}")
            
            if detailed and matches:
                lines.append(f"\n📅 **Match-by-Match Details:** ({len(matches)} matches)\n")
                
                for i, m in enumerate(matches, 1):
                    venue = "🏠 Home" if m.get('home_or_away') == 'home' else "✈️ Away"
                    date_str = format_date(m.get('date', ''))
                    opponent = m.get('opponent_team_name')
                    started = "Started" if m.get('started') else "Bench"
                    
                    performance = []
                    if m.get('goals', 0) > 0:
                        goal_mins = format_minutes(m.get('goal_minutes', []))
                        goal_str = f"⚽ {m.get('goals')} goal(s)"
                        if goal_mins:
                            goal_str += f" ({goal_mins})"
                        performance.append(goal_str)
                    if m.get('yellow_cards', 0) > 0:
                        yellow_mins = format_minutes(m.get('yellow_minutes', []))
                        yellow_str = "🟨 Yellow"
                        if yellow_mins:
                            yellow_str += f" ({yellow_mins})"
                        performance.append(yellow_str)
                    if m.get('red_cards', 0) > 0:
                        red_mins = format_minutes(m.get('red_minutes', []))
                        red_str = "🟥 Red"
                        if red_mins:
                            red_str += f" ({red_mins})"
                        performance.append(red_str)
                    if not performance:
                        performance.append("No goals/cards")
                    
                    lines.append(
                        f"**Match {i}:** {date_str}\n"
                        f"   {venue} vs {opponent}\n"
                        f"   Status: {started}\n"
                        f"   Performance: {', '.join(performance)}\n"
                    )
            elif matches and not detailed:
                lines.append(f"\n📅 **Recent Matches:** (showing last 5)")
                for m in matches[:5]:
                    venue = "🏠" if m.get('home_or_away') == 'home' else "✈️"
                    date_str = format_date(m.get('date', ''))
                    
                    # Build performance string with times
                    perf_parts = []
                    if m.get('goals', 0) > 0:
                        goal_mins = format_minutes(m.get('goal_minutes', []))
                        perf_parts.append(f"⚽×{m.get('goals')}" + (f"({goal_mins})" if goal_mins else ""))
                    if m.get('yellow_cards', 0) > 0:
                        perf_parts.append("🟨")
                    if m.get('red_cards', 0) > 0:
                        perf_parts.append("🟥")
                    
                    perf_str = " ".join(perf_parts) if perf_parts else ""
                    
                    lines.append(
                        f"   {venue} vs {m.get('opponent_team_name')} - {date_str} {perf_str}"
                    )
                
                lines.append(f"\n💡 Use 'details for {p.get('first_name')} {p.get('last_name')}' for match-by-match breakdown")
            
            return "\n".join(lines)
        else:
            # Multiple players found - return as table
            data = []
            for p in exact_matches[:10]:
                stats = p.get("stats", {})
                data.append({
                    "Player": f"{p.get('first_name')} {p.get('last_name')}",
                    "Jersey": f"#{p.get('jersey')}",
                    "Team": p.get('team_name', ''),
                    "Goals": stats.get('goals', 0),
                    "Matches": stats.get('matches_played', 0),
                    "Yellow": stats.get('yellow_cards', 0),
                    "Red": stats.get('red_cards', 0)
                })
            
            return {
                "type": "table",
                "data": data,
                "title": f"👤 Found {len(exact_matches)} players matching '{query}' (showing {min(10, len(exact_matches))})"
            }
    
    # Fuzzy match fallback
    matched_name = fuzzy_find(q, [n.lower() for n in player_names], threshold=50)
    
    if matched_name and matched_name in player_lookup:
        p = player_lookup[matched_name]
        stats = p.get("stats", {})
        return (
            f"Did you mean:\n\n"
            f"👤 **{p.get('first_name')} {p.get('last_name')}** (#{p.get('jersey')})\n"
            f"   {p.get('team_name')}\n"
            f"   ⚽ {stats.get('goals', 0)} | 🎮 {stats.get('matches_played', 0)} | "
            f"🟨 {stats.get('yellow_cards', 0)} | 🟥 {stats.get('red_cards', 0)}"
        )
    
    similar = process.extract(q, [n.lower() for n in player_names], scorer=fuzz.WRatio, limit=5)
    if similar:
        lines = [f"No exact match. Did you mean:\n"]
        for name, score, _ in similar:
            actual = next((n for n in player_names if n.lower() == name), name)
            lines.append(f"  - {actual} ({score}%)")
        return "\n".join(lines)
    
    return f"❌ No player found: {query}"


# ---------------------------------------------------------
# 11. Other tools (matches, team_overview, ladder, form, etc.)
# ---------------------------------------------------------

def tool_matches(query: str) -> str:
    q = query.lower()
    norm_team = normalize_team(q)
    lines = []

    for r in results:
        a = r.get("attributes", {})
        home = a.get("home_team_name", "")
        away = a.get("away_team_name", "")
        if norm_team and norm_team.lower() not in (home.lower() + away.lower()):
            continue
        date_str = format_date(a.get('date', ''))
        lines.append(f"📅 {date_str}: {home} {a.get('home_score')}-{a.get('away_score')} {away}")

    for f in fixtures:
        a = f.get("attributes", {})
        home = a.get("home_team_name", "")
        away = a.get("away_team_name", "")
        if norm_team and norm_team.lower() not in (home.lower() + away.lower()):
            continue
        date_str = format_date(a.get('date', ''))
        lines.append(f"🔜 {date_str}: {home} vs {away}")

    if not lines:
        return f"❌ No matches for: {query}"

    return "\n".join(lines[:20])

def tool_team_overview(query: str) -> str:
    """Get team overview with stats"""
    # Try to get canonical club name first
    canonical_club = get_canonical_club_name(query)
    age_group = extract_age_group(query)
    
    # Build the team filter
    if canonical_club and age_group:
        # Exact team match: "Heidelberg United FC U16"
        team_filter = f"{canonical_club} {age_group}"
    elif canonical_club:
        # Club only: match all age groups
        team_filter = canonical_club
    else:
        # Fall back to normalize_team
        team_filter = normalize_team(query) or query
    
    lines = [f"🏟️ **{query}**\n"]

    # Filter players - use exact match if we have canonical name, otherwise substring
    if canonical_club:
        # Exact matching for canonical club names
        if age_group:
            players = [p for p in players_summary if p.get("team_name", "") == team_filter]
        else:
            # Match all teams from this club (any age group)
            players = [p for p in players_summary if p.get("team_name", "").startswith(canonical_club)]
    else:
        # Substring matching for other cases
        players = [p for p in players_summary if team_filter.lower() in p.get("team_name", "").lower()]
    
    # Filter to only players (not coaches/staff)
    players = [p for p in players if not p.get("role") or p.get("role") == "player"]
    
    if players:
        total_goals = sum(p.get("stats", {}).get("goals", 0) for p in players)
        total_yellows = sum(p.get("stats", {}).get("yellow_cards", 0) for p in players)
        total_reds = sum(p.get("stats", {}).get("red_cards", 0) for p in players)
        
        lines.append(f"**Squad:** {len(players)} players")
        lines.append(f"**Total Goals:** {total_goals}")
        lines.append(f"**Discipline:** 🟨 {total_yellows} | 🟥 {total_reds}\n")
        
        top_scorers = sorted(players, key=lambda x: x.get("stats", {}).get("goals", 0), reverse=True)[:5]
        if top_scorers[0].get("stats", {}).get("goals", 0) > 0:
            lines.append("**Top Scorers:**")
            for p in top_scorers:
                goals = p.get("stats", {}).get("goals", 0)
                if goals > 0:
                    lines.append(f"  ⚽ {p.get('first_name')} {p.get('last_name')} - {goals}")
    
    # Get team name to match in results
    team_name_to_match = players[0].get('team_name', '') if players else team_filter
    
    team_results = []
    for r in results:
        a = r.get("attributes", {})
        home = a.get("home_team_name", "")
        away = a.get("away_team_name", "")
        if team_name_to_match.lower() in home.lower() or team_name_to_match.lower() in away.lower():
            team_results.append(a)

    team_results.sort(key=lambda x: x.get("date", ""), reverse=True)
    if team_results:
        lines.append(f"\n**Recent Results:**")
        for a in team_results[:5]:
            date_str = format_date(a.get('date', ''))
            lines.append(f"  {date_str}: {a.get('home_team_name')} {a.get('home_score')}-{a.get('away_score')} {a.get('away_team_name')}")

    return "\n".join(lines)

def tool_ladder(query: str) -> str:
    q = query.lower()
    league = fuzzy_find(q, [l.lower() for l in league_names], threshold=50)
    comp = fuzzy_find(q, [c.lower() for c in competition_names], threshold=50)

    table = defaultdict(lambda: {"P": 0, "W": 0, "D": 0, "L": 0, "GF": 0, "GA": 0, "PTS": 0})

    for r in results:
        a = r.get("attributes", {})
        if league and league not in a.get("league_name", "").lower():
            continue
        if comp and comp not in a.get("competition_name", "").lower():
            continue

        home = a.get("home_team_name", "")
        away = a.get("away_team_name", "")
        try:
            hs = int(a.get("home_score", 0))
            as_ = int(a.get("away_score", 0))
        except (ValueError, TypeError):
            continue

        table[home]["P"] += 1
        table[away]["P"] += 1
        table[home]["GF"] += hs
        table[home]["GA"] += as_
        table[away]["GF"] += as_
        table[away]["GA"] += hs

        if hs > as_:
            table[home]["W"] += 1
            table[away]["L"] += 1
            table[home]["PTS"] += 3
        elif hs < as_:
            table[away]["W"] += 1
            table[home]["L"] += 1
            table[away]["PTS"] += 3
        else:
            table[home]["D"] += 1
            table[away]["D"] += 1
            table[home]["PTS"] += 1
            table[away]["PTS"] += 1

    if not table:
        return f"❌ No ladder for: {query}"

    ladder = sorted(
        table.items(),
        key=lambda kv: (kv[1]["PTS"], kv[1]["GF"] - kv[1]["GA"], kv[1]["GF"]),
        reverse=True,
    )

    lines = [f"📊 **{query}**\n", "Pos | Team | P | W | D | L | GF | GA | GD | PTS", "-" * 55]
    for pos, (team, row) in enumerate(ladder[:20], 1):
        gd = row["GF"] - row["GA"]
        lines.append(
            f"{pos:>2}. {team[:25]:<25} {row['P']:>2} {row['W']:>2} {row['D']:>2} {row['L']:>2} "
            f"{row['GF']:>2} {row['GA']:>2} {gd:>+3} {row['PTS']:>3}"
        )

    return "\n".join(lines)

def tool_form(query: str) -> str:
    team = normalize_team(query) or query
    matches = []

    for r in results:
        a = r.get("attributes", {})
        home = a.get("home_team_name", "")
        away = a.get("away_team_name", "")
        if team.lower() in home.lower() or team.lower() in away.lower():
            matches.append(a)

    matches.sort(key=lambda x: x.get("date", ""), reverse=True)
    matches = matches[:5]

    if not matches:
        return f"❌ No form data for: {team}"

    form = []
    lines = [f"📈 **{team}**\n"]
    
    for m in matches:
        try:
            hs = int(m.get("home_score", 0))
            as_ = int(m.get("away_score", 0))
        except (ValueError, TypeError):
            continue
            
        home = m.get("home_team_name", "")
        away = m.get("away_team_name", "")

        if team.lower() in home.lower():
            result = "W" if hs > as_ else ("L" if hs < as_ else "D")
            icon = "🟢" if result == "W" else ("🔴" if result == "L" else "🟡")
        else:
            result = "W" if as_ > hs else ("L" if as_ < hs else "D")
            icon = "🟢" if result == "W" else ("🔴" if result == "L" else "🟡")
        
        form.append(result)
        date_str = format_date(m.get('date', ''))
        lines.append(f"{icon} {date_str}: {home} {hs}-{as_} {away}")

    lines.insert(1, f"**{' '.join(form)}**\n")
    return "\n".join(lines)

def tool_match_centre(query: str) -> str:
    q = query.strip()
    matches = find_matches_by_teams_or_hash(match_hash_id=q)
    if not matches:
        parts = [p.strip() for p in q.replace("vs", "v").replace(" v ", " v ").split(" v ")]
        home_like = parts[0] if parts else None
        away_like = parts[1] if len(parts) > 1 else None
        matches = find_matches_by_teams_or_hash(home_like=home_like, away_like=away_like)

    if not matches:
        return f"❌ No match found: {query}"

    m = matches[0]
    result = m.get("result", {})
    r_attrs = result.get("attributes", {})
    date_str = format_date(r_attrs.get('date', ''))

    return (
        f"⚽ **{r_attrs.get('home_team_name')} {r_attrs.get('home_score')} - "
        f"{r_attrs.get('away_score')} {r_attrs.get('away_team_name')}**\n"
        f"📅 {date_str}\n"
        f"🏆 {r_attrs.get('competition_name')}"
    )

def tool_lineups(query: str) -> str:
    q = query.strip()
    matches = find_matches_by_teams_or_hash(match_hash_id=q)
    if not matches:
        parts = [p.strip() for p in q.replace("vs", "v").split("v")]
        home_like = parts[0] if parts else None
        away_like = parts[1] if len(parts) > 1 else None
        matches = find_matches_by_teams_or_hash(home_like=home_like, away_like=away_like)

    if not matches:
        return f"❌ No match: {query}"

    m = matches[0]
    match_hash_id = m.get("match_hash_id")
    result = m.get("result", {})
    r_attrs = result.get("attributes", {})

    lineup = find_lineup_by_match_hash(match_hash_id)
    if not lineup:
        return "❌ No lineup data available"

    home_lineup = lineup.get("home_lineup", [])
    away_lineup = lineup.get("away_lineup", [])

    lines = [f"⚽ **{r_attrs.get('home_team_name')} vs {r_attrs.get('away_team_name')}**\n", "**Home XI:**"]
    
    for p in [x for x in home_lineup if x.get('starting')][:11]:
        name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
        lines.append(f"  - {name}")

    lines.append("\n**Away XI:**")
    for p in [x for x in away_lineup if x.get('starting')][:11]:
        name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
        lines.append(f"  - {name}")

    return "\n".join(lines)

# ---------------------------------------------------------
# 11. NON-PLAYER QUERIES
# ---------------------------------------------------------

def tool_non_players(query: str = "") -> str:
    """List non-players (coaches, staff) with optional team filtering and card info"""
    non_players = [
        p for p in players_summary 
        if p.get("role") and p.get("role") != "player"
    ]
    
    if not non_players:
        return "❌ No non-players (coaches/staff) found in the data"
    
    # Apply filters
    if query:
        non_players = filter_players_by_criteria(non_players, query, include_non_players=True)
    
    if not non_players:
        return f"❌ No non-players found matching '{query}'"
    
    # Build filter description
    age_group = extract_age_group(query) if query else None
    team_name = extract_team_name(query) if query else None
    base_club = extract_base_club_name(query) if query else None
    
    filter_parts = []
    if age_group and not team_name:
        filter_parts.append(age_group)
    elif base_club and not age_group and not team_name:
        filter_parts.append(base_club)
    elif team_name:
        filter_parts.append(team_name)
    
    filter_desc = " - " + " ".join(filter_parts) if filter_parts else ""
    
    # Sort by total cards (yellow + red * 2), then by name
    non_players.sort(key=lambda x: (
        -(x.get("stats", {}).get("yellow_cards", 0) + x.get("stats", {}).get("red_cards", 0) * 2),
        x.get("last_name", ""),
        x.get("first_name", "")
    ))
    
    # Return as table data
    data = []
    for i, p in enumerate(non_players, 1):
        stats = p.get("stats", {})
        yellows = stats.get("yellow_cards", 0)
        reds = stats.get("red_cards", 0)
        role = p.get("role", "staff").title()
        name = f"{p.get('first_name')} {p.get('last_name')}"
        team = p.get('team_name', '')
        
        data.append({
            "Rank": i,
            "Name": name,
            "Role": role,
            "Team": team,
            "Yellow": yellows,
            "Red": reds
        })
    
    # Add a conversational title
    filter_desc = f" for {team_name}" if team_name else ""
    title = f"📋 I found {len(non_players)} staff members{filter_desc}:"
    
    return {
        "type": "table",
        "data": data,
        "title": title
    }

# ---------------------------------------------------------
# 12. Smart Query Router
# ---------------------------------------------------------

class FastQueryRouter:
    """Enhanced pattern-based query router with personal team support"""
    
    def __init__(self):
        pass
        
def process(self, query: str):
    """Route query to appropriate handler"""
    q = query.lower().strip()
    
    # 1. INITIALIZE ALL VARIABLES (Prevents UnboundLocalError)
    filter_query = ""
    show_details = False
    is_non_player_query = any(keyword in q for keyword in ['non player', 'non-player', 'coach', 'staff', 'manager'])
    is_personal_query = any(keyword in q for keyword in ['my next', 'when do i play', 'where do i play', 'my schedule', 'when is my', 'where is my', 'our next'])

    # 2. MISSING SCORES
    missing_keywords = ['missing score', 'missing scores', 'no score', 'scores not entered', 'overdue', 'matches without scores']
    if any(keyword in q for keyword in missing_keywords):
        filter_query = re.sub(r'\b(missing|score|scores?|no|not|entered|overdue|matches?|without|for|show|list)\b', '', q).strip()
        include_all = 'all leagues' in q or 'all league' in q
        return tool_missing_scores(filter_query, include_all_leagues=include_all)
    
    # 3. COMPETITION OVERVIEW
    comp_overview_keywords = ['competition overview', 'competition standings', 'ypl1 overview', 'ypl2 overview', 'ysl overview', 'vpl overview', 'club rankings', 'overall standings']
    if any(keyword in q for keyword in comp_overview_keywords) or any(comp in q for comp in ['ypl1', 'ypl2', 'ysl nw', 'ysl se', 'vpl']):
        if any(word in q for word in ['overview', 'standings', 'ranking', 'competition']):
            return tool_competition_overview(query)
    
    # 4. FIXTURES / NEXT MATCH
    fixture_keywords = ['next match', 'next game', 'upcoming', 'when do i play', 'where do i play', 'my next', 'schedule', 'fixture', 'fixtures', 'when is my', 'where is my', 'our next']
    if any(keyword in q for keyword in fixture_keywords):
        if is_personal_query:
            return tool_fixtures(query="", limit=5, use_user_team=True)
        else:
            team_query = re.sub(r'\b(next|match|game|upcoming|when|where|do|i|play|my|schedule|fixtures?|is)\b', '', q).strip()
            limit = 5 if team_query else 10
            return tool_fixtures(team_query, limit, use_user_team=False)
    
    # 5. DISCIPLINE (Yellow / Red Cards) - Merged Logic
    if any(word in q for word in ["yellow card", "yellows"]):
        show_details = "detail" in q
        filter_query = re.sub(r'\b(yellow|card|cards|details?|show|list|with|for|me)\b', '', q).strip()
        return tool_yellow_cards(filter_query, show_details, include_non_players=is_non_player_query)

    if any(word in q for word in ["red card", "reds"]):
        show_details = "detail" in q
        filter_query = re.sub(r'\b(red|card|cards|details?|show|list|with|for|me)\b', '', q).strip()
        return tool_red_cards(filter_query, show_details, include_non_players=is_non_player_query)
    
    # 6. STANDALONE NON-PLAYER / STAFF LIST
    if is_non_player_query:
        filter_query = re.sub(r'\b(non|player|players?|staff|coach|coaches?|manager|managers|for|all|show|list|with|get|me)\b', '', q).strip()
        return tool_non_players(filter_query)
    
    # 7. TOP SCORERS
    if any(word in q for word in ["top scorer","leading scorer", "top scorers", "golden boot"]):
        clean = re.sub(r'\b(top|scorer|scorers?|golden|boot|in|for|show|me|list)\b', '', q).strip()
        team_context = clean if clean else USER_CONFIG["team"]
        result = tool_top_scorers(team_context)
        if isinstance(result, dict) and result.get("type") == "table":
            result["title"] = f"🏆 Here are the top performers for {result.get('title', team_context)}:"
        return result
        
    # 8. TEAM AND PLAYER STATS
    if any(word in q for word in ["stats for", "team stats", "show me", "details for"]):
        clean = re.sub(r'\b(stats?|for|team|show|me|get|find|details?|profile|about)\b', '', q).strip()
        detailed = "detail" in q
        
        recognized_team = normalize_team(clean)
        if recognized_team:
            result = tool_team_stats(recognized_team)
            if isinstance(result, dict) and result.get("type") == "table":
                result["title"] = f"📊 Here is the latest performance data for **{recognized_team}**:"
            return result
        else:
            result = tool_players(clean, detailed)
            if isinstance(result, dict) and result.get("type") == "table":
                result["title"] = f"👟 Recent match-by-match stats for **{clean.title()}**:"
            return result
            
    # 9. LADDER, LINEUP, MATCH CENTRE, FORM
    if any(word in q for word in ["ladder", "table", "standings"]):
        return tool_ladder(query)
    
    if "lineup" in q or "starting" in q:
        return tool_lineups(query)
    
    if " vs " in q or " v " in q:
        return tool_match_centre(query)
    
    if "form" in q:
        team = normalize_team(query)
        return tool_form(team if team else query)
    
    if "team" in q or "overview" in q:
        team = normalize_team(query)
        return tool_team_overview(team if team else query)
    
    # 10. DEFAULT FALLBACK
    team = normalize_team(query)
    if team:
        return tool_form(team)
    return tool_matches(query)