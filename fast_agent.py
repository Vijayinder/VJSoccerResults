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
import pytz
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
    
    # Eltham Redbacks FC variations
    "redbacks": "Eltham Redbacks FC",
    "eltham": "Eltham Redbacks FC",
        
     
    # Box Hill variations
    "box hill": "Box Hill United Pythagoras FC",
    "box hill united": "Box Hill United Pythagoras FC",
    "boxhill": "Box Hill United Pythagoras FC",
    
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
    elif "staff_summary" in name:
        return {"staff": []}
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
staff_data = load_json("staff_summary.json")
match_centre_data = load_json("master_match_centre.json")
lineups_data = load_json("master_lineups.json")
competition_overview = load_json("competition_overview.json")


def _normalize_person(p: Dict, is_player: bool) -> Dict:
    """
    Normalize person record to common format for tools.
    Handles dribl_player_details.py output (teams[], leagues[], jerseys{}, plain role string)
    and legacy build_player_summary.py format (role_slug, roles[]).
    """
    out = dict(p)

    # Team / league: prefer arrays, fall back to scalars
    if not out.get("team_name") and out.get("teams"):
        out["team_name"] = out["teams"][0] if out["teams"] else ""
    if not out.get("league_name") and out.get("leagues"):
        out["league_name"] = out["leagues"][0] if out["leagues"] else ""
    if not out.get("competition_name") and out.get("league_name"):
        out["competition_name"] = out["league_name"]

    # Role: dribl stores plain string; legacy used role_slug + roles[]
    if not out.get("role"):
        role_slug = out.get("role_slug", "player")
        roles     = out.get("roles", [])
        if role_slug == "player":
            out["role"] = "player"
        elif roles:
            out["role"] = roles[0]
        else:
            out["role"] = role_slug or "staff"

    # Staff don't have jersey
    if "jersey" not in out and not is_player:
        out["jersey"] = ""

    # Stats
    stats = out.get("stats", {})
    if "matches_played" not in stats:
        stats["matches_played"] = stats.get("matches_attended", 0)
    out["stats"] = stats

    # Deduplicate match entries by match_hash_id (player can appear in both
    # home and away lineup for the same match in some data formats)
    raw_matches = out.get("matches", [])
    seen_match_ids = set()
    deduped = []
    for m in raw_matches:
        mid = m.get("match_hash_id")
        if mid:
            if mid not in seen_match_ids:
                seen_match_ids.add(mid)
                deduped.append(m)
        else:
            deduped.append(m)
    out["matches"] = deduped

    # Flatten events into convenience fields on each match.
    # Handles both "type" (matchcentre) and "event_type" (lineup) keys.
    for m in out["matches"]:
        if "opponent_team_name" not in m and m.get("opponent"):
            m["opponent_team_name"] = m["opponent"]

        events = m.get("events", [])
        if not events:
            continue

        def _etype(e):
            return (e.get("type") or e.get("event_type") or "").lower()

        y_events = [e for e in events if _etype(e) == "yellow_card"]
        r_events = [e for e in events if _etype(e) == "red_card"]
        g_events = [e for e in events if _etype(e) == "goal"]

        if "yellow_cards"   not in m: m["yellow_cards"]   = len(y_events)
        if "yellow_minutes" not in m: m["yellow_minutes"]  = [e.get("minute") for e in y_events if e.get("minute")]
        if "red_cards"      not in m: m["red_cards"]       = len(r_events)
        if "red_minutes"    not in m: m["red_minutes"]     = [e.get("minute") for e in r_events if e.get("minute")]
        if "goals"          not in m: m["goals"]           = len(g_events)
        if "goal_minutes"   not in m: m["goal_minutes"]    = [e.get("minute") for e in g_events if e.get("minute")]

    return out


# Players only - for player queries (top scorers, stats for player, yellow cards for players)
_raw_players = players_data.get("players", [])
players_summary = [_normalize_person(p, is_player=True) for p in _raw_players]

# Staff only - for coach/staff queries (coaches yellow cards, staff list, etc.)
_raw_staff = staff_data.get("staff", [])
staff_summary = [_normalize_person(p, is_player=False) for p in _raw_staff]

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
    """Parse UTC date string and convert to Melbourne Local Time (AEST/AEDT)"""
    if not date_str:
        return None
    try:
        melbourne_tz = pytz.timezone('Australia/Melbourne')

        if 'Z' in date_str:
            # Explicit UTC marker
            utc_dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))

        elif 'T' in date_str and ('+' in date_str[10:] or '-' in date_str[10:]):
            # Has timezone offset already (e.g. +10:00) — parse as-is
            utc_dt = datetime.fromisoformat(date_str)

        elif 'T' in date_str:
            # Has time but no timezone — assume UTC
            utc_dt = datetime.fromisoformat(date_str).replace(tzinfo=pytz.UTC)

        else:
            # Date only (e.g. "2026-02-22") — assume midnight UTC
            utc_dt = datetime.fromisoformat(date_str).replace(
                hour=0, minute=0, second=0, tzinfo=pytz.UTC
            )

        return utc_dt.astimezone(melbourne_tz)

    except (ValueError, AttributeError, Exception):
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

def get_match_day_date() -> datetime.date:
    """
    Returns today's date in AEST if it's Sunday,
    otherwise returns the most recent Sunday in AEST.
    Always uses AEST — never raw UTC — so a UTC Saturday night
    that is Sunday AEST is treated correctly.
    """
    melbourne_tz = pytz.timezone('Australia/Melbourne')
    today_aest = datetime.now(melbourne_tz).date()

    # weekday(): Monday=0 ... Sunday=6
    if today_aest.weekday() == 6:
        return today_aest

    # How many days since last Sunday
    days_since_sunday = (today_aest.weekday() + 1) % 7
    return today_aest - timedelta(days=days_since_sunday)
            
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

# Build player index (players only - for "stats for X", top scorers, etc.)
player_names = []
player_lookup = {}

for p in players_summary:
    first = p.get("first_name", "")
    last = p.get("last_name", "")
    full_name = f"{first} {last}".strip()
    if full_name:
        player_names.append(full_name)
        player_lookup[full_name.lower()] = p

# Build staff index (for coach/staff queries - "coaches yellow cards", etc.)
staff_names = []
staff_lookup = {}
for p in staff_summary:
    first = p.get("first_name", "")
    last = p.get("last_name", "")
    full_name = f"{first} {last}".strip()
    if full_name:
        staff_names.append(full_name)
        staff_lookup[full_name.lower()] = p

# Build team/league/competition indices from BOTH players and staff
_all_people = players_summary + staff_summary
team_names = sorted({
    p.get("team_name", "") or (p.get("teams", [None])[0] or "")
    for p in _all_people
    if p.get("team_name") or p.get("teams")
})

league_names = sorted({
    p.get("league_name", "") or (p.get("leagues", [None])[0] or "")
    for p in _all_people
    if p.get("league_name") or p.get("leagues")
})

competition_names = sorted({
    p.get("competition_name", "") or p.get("league_name", "") or (p.get("leagues", [None])[0] or "")
    for p in _all_people
    if p.get("competition_name") or p.get("league_name") or p.get("leagues")
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

def _person_teams(p: Dict) -> List[str]:
    """Get all team names for a person (handles both team_name and teams array)."""
    teams = p.get("teams", [])
    if teams:
        return teams
    tn = p.get("team_name", "")
    return [tn] if tn else []


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
    
    # Filter by role if looking for non-players (only when source may contain both)
    if include_non_players:
        filtered = [
            p for p in filtered
            if p.get("role") and str(p.get("role", "")).lower() != "player"
        ]
    else:
        # Only players
        filtered = [
            p for p in filtered
            if not p.get("role") or str(p.get("role", "")).lower() == "player"
        ]
    
    def _team_match(p: Dict, check_fn) -> bool:
        """Check if any of person's teams matches the criterion."""
        for t in _person_teams(p):
            if check_fn(t):
                return True
        return False
    
    # Now apply team/age filters (handles multi-team staff)
    if team_name:
        filtered = [p for p in filtered if _team_match(p, lambda t: team_name.lower() in (t or "").lower())]
    elif base_club and age_group:
        exact_team = f"{base_club} {age_group}"
        filtered = [p for p in filtered if _team_match(p, lambda t: exact_team.lower() in (t or "").lower())]
    elif base_club:
        filtered = [p for p in filtered if _team_match(p, lambda t: base_club.lower() in (t or "").lower())]
    elif age_group:
        filtered = [p for p in filtered if _team_match(p, lambda t: age_group.lower() in (t or "").lower())]
    
    return filtered

# ---------------------------------------------------------
# 6. FIXTURES TOOL
# ---------------------------------------------------------

def tool_fixtures(query: str = "", limit: int = 10, use_user_team: bool = False) -> str:
    """Show upcoming fixtures with full DST-aware time support"""
    
    # Get the precise 'now' in Melbourne
    melbourne_tz = pytz.timezone('Australia/Melbourne')
    now_melbourne = datetime.now(melbourne_tz)
    
    # Logic for determining the search term and limit
    if not query and not use_user_team:
        search_term = USER_CONFIG["club"]
        limit = 10
    elif use_user_team and not query:
        search_term = USER_CONFIG["team"]
        limit = 5
    else:
        search_term = query
        has_specific_age = any(age in query.upper() for age in ["U13", "U14", "U15", "U16", "U18", "U21"])
        limit = 5 if has_specific_age else 10

    upcoming = []
    for f in fixtures:
        attrs = f.get("attributes", {})
        date_str = attrs.get("date", "")
        
        # Convert UTC -> Melbourne (AEDT/AEST)
        match_dt = parse_date_utc_to_aest(date_str)
        if not match_dt:
            continue
            
        # Only show matches that haven't started yet
        if match_dt >= now_melbourne:
            # Handle None values - use 'or ""' to ensure string
            home = (attrs.get("home_team_name") or "").lower()
            away = (attrs.get("away_team_name") or "").lower()
            league = (attrs.get("league_name") or "").lower()
            
            if search_term.lower() in home or search_term.lower() in away or search_term.lower() in league:
                upcoming.append((match_dt, attrs))
    
    # Sort strictly by the full datetime (Day + Time)
    upcoming.sort(key=lambda x: x[0])
    upcoming = upcoming[:limit]
    
    if not upcoming:
        return f"❌ No upcoming fixtures found for '{search_term}'."

    title_text = f"All {USER_CONFIG['club']} Age Groups" if not query and not use_user_team else search_term.title()
    lines = [f"📅 **Upcoming Fixtures: {title_text}**\n"]
    
    for i, (m_dt, attrs) in enumerate(upcoming, 1):
        # Calculate days until using midnight boundaries for natural language
        days_until = (m_dt.date() - now_melbourne.date()).days
        
        # Format: 15-Feb (Sun) 10:30 AM
        date_display = m_dt.strftime("%d-%b (%a) %I:%M %p")
        
        # Handle None values properly
        home = attrs.get("home_team_name") or "Unknown"
        away = attrs.get("away_team_name") or "Unknown"
        league = attrs.get("league_name") or ""
        venue = attrs.get("ground_name") or "TBD"
        
        if days_until == 0:
            status = "🔴 TODAY!"
        elif days_until == 1:
            status = "⚠️ Tomorrow"
        else:
            status = f"🗓️ In {days_until} days"

        lines.append(f"**{i}. {date_display}** — {status}")
        lines.append(f"    🏆 {league}")
        lines.append(f"    ⚽ {home} vs {away}")
        lines.append(f"    🏟️ {venue}\n")
        
    return "\n".join(lines)
# ---------------------------------------------------------
# 6B. MISSING SCORES TOOL
# ---------------------------------------------------------

#def tool_missing_scores(query: str = "") -> Any:
def tool_missing_scores(query: str = "", include_all_leagues: bool = False, today_only: bool = False, last_week: bool = False, round_filter: int = None) -> Any:
    """
    Show matches without scores entered.
    
    Args:
        query: Filter by team/league name
        include_all_leagues: Show all leagues or just target leagues
        today_only: Only show today's (or last Sunday's) matches
        last_week: Show the Sunday before the current match day
        round_filter: If set, filter by this round number (ignores date window)
    """
    melbourne_tz = pytz.timezone('Australia/Melbourne')
    today = datetime.now(melbourne_tz).date()

    print(f"\n{'='*80}")
    print(f"DEBUG tool_missing_scores START")
    print(f"  query='{query}', today_only={today_only}, last_week={last_week}, round_filter={round_filter}")

    # Target leagues if not showing all
    target_leagues = ["YPL1", "YPL2", "YSL NW", "YSL SE", "VPL"] if not include_all_leagues else []

    missing_scores = []

    # --- Determine date mode ---
    match_day = None
    day_label = ""
    date_display = ""

    if round_filter is not None:
        # Round mode — no date window, filter by round number instead
        day_label = f" for Round {round_filter}"
        date_display = f"📋 **Round {round_filter}**"

    elif today_only:
        match_day = get_match_day_date()
        if match_day == today:
            day_label = " for Today"
            date_display = f"📅 **TODAY ({today.strftime('%A, %d %B %Y')})**"
        else:
            day_label = f" for Last Sunday ({match_day.strftime('%d-%b')})"
            date_display = f"📅 **LAST SUNDAY ({match_day.strftime('%A, %d %B %Y')})**"

    elif last_week:
        # The Sunday before the current match day
        current_match_day = get_match_day_date()
        match_day = current_match_day - timedelta(days=7)
        day_label = f" for Last Week ({match_day.strftime('%d-%b')})"
        date_display = f"📅 **LAST WEEK — {match_day.strftime('%A, %d %B %Y')}**"

    else:
        day_label = ""
        date_display = ""
    
    # Build result lookup keyed by match_hash_id
    result_lookup = {}
    for result in results:
        r_attrs = result.get("attributes", {})
        mid = r_attrs.get("match_hash_id")
        if mid:
            result_lookup[mid] = r_attrs

    print(f"\n  DATA SOURCES:")
    print(f"    Fixtures available: {len(fixtures)}")
    print(f"    Results available (lookup): {len(result_lookup)}")

    # Use fixtures as single source — merge result data in where it exists
    # This prevents every match appearing twice (once from fixture, once from result)
    all_matches = []
    for fixture in fixtures:
        f_attrs = fixture.get("attributes", {})
        mid = f_attrs.get("match_hash_id")
        if mid and mid in result_lookup:
            merged = dict(f_attrs)
            merged.update(result_lookup[mid])  # result overwrites score/status fields
            merged["source"] = "result"
        else:
            merged = dict(f_attrs)
            merged["source"] = "fixture_only"
        all_matches.append(merged)

    print(f"    Total unique matches: {len(all_matches)} ({len(result_lookup)} have results)")
    
    matches_on_target_date = 0
    matches_with_target_leagues = 0
    matches_after_query_filter = 0
    date_sample = []  # Sample of dates we're seeing
    
    for attrs in all_matches:
        date_str = attrs.get("date", "")
        if not date_str:
            continue
        
        # Parse to Melbourne date
        match_dt = parse_date_utc_to_aest(date_str)
        if not match_dt:
            continue
        
        match_date = match_dt.date()
        
        # Collect sample dates for debugging
        if len(date_sample) < 5:
            date_sample.append({
                'utc': date_str,
                'aest': match_dt.strftime('%Y-%m-%d %H:%M %Z'),
                'date': match_date,
                'home': attrs.get("home_team_name", "")[:30],
                'away': attrs.get("away_team_name", "")[:30]
            })
        
        # If today_only, filter to that specific date
        if today_only and match_day:
            if match_date != match_day:
                continue
            matches_on_target_date += 1
            
            # Debug first 3 matches on target date
            if matches_on_target_date <= 3:
                print(f"\n  MATCH #{matches_on_target_date} ON TARGET DATE:")
                print(f"    UTC: {date_str}")
                print(f"    AEST: {match_dt.strftime('%Y-%m-%d %H:%M')}")
                print(f"    Home: {attrs.get('home_team_name', 'Unknown')}")
                print(f"    Away: {attrs.get('away_team_name', 'Unknown')}")
                print(f"    League: {attrs.get('league_name', 'Unknown')}")
                print(f"    Status: {attrs.get('status', 'Unknown')}")
                print(f"    Home Score: {attrs.get('home_score')}")
                print(f"    Away Score: {attrs.get('away_score')}")
                print(f"    Source: {attrs.get('source')}")
        
        # If not today_only, skip matches that are too far in the future or past
        # --- Date window filtering ---
        if round_filter is not None:
            # Round mode: skip date window entirely, filter by round number below
            pass

        elif match_day is not None:
            # today_only or last_week: must be exactly that Sunday
            if match_date != match_day:
                continue

        else:
            # Default: show past 14 days only (no future matches — they can't be "missing" yet)
            days_diff = (match_date - today).days
            if days_diff > 0 or days_diff < -14:
                continue
        
        home_team = attrs.get("home_team_name", "Unknown")
        away_team = attrs.get("away_team_name", "Unknown")
        league = attrs.get("league_name", "")

        # Skip bye matches — identified by missing team hash IDs
        if not attrs.get("home_team_hash_id") or not attrs.get("away_team_hash_id"):
            continue
        # Filter by target leagues if specified
        if target_leagues:
            league_code = extract_league_from_league_name(league)
            if league_code not in target_leagues:
                continue
            matches_with_target_leagues += 1
        # Get round info for this match (needed for both round_filter and search blob)
        match_round = str(attrs.get("round", "") or attrs.get("full_round", "") or "")

        # Round filter — skip matches not in that round
        if round_filter is not None:
            round_number_match = re.search(r'(\d+)', match_round)
            if not round_number_match or int(round_number_match.group(1)) != round_filter:
                continue

        # Apply query filter
        if query:
            q_lower = query.lower().strip()
            
            # Extract filters from query
            age_group = extract_age_group(q_lower)
            canonical_club = get_canonical_club_name(q_lower)
            
            # Extract league code from the match
            match_league_code = extract_league_from_league_name(league)
            
            # Build comprehensive search blob including round
            search_blob = f"{home_team} {away_team} {league} {match_league_code} {match_round}".lower()
            # Check if query specifies a league code (YPL1, YPL2, YSL NW, etc.)
            query_league_code = None
            for possible_league in ['ypl1', 'ypl2', 'ysl nw', 'ysl se', 'vpl men', 'vpl women', 'ypl 1', 'ypl 2']:
                if possible_league in q_lower:
                    query_league_code = extract_league_from_league_name(possible_league)
                    break
            
            # If user specified a league code, match must have it
            if query_league_code and match_league_code.lower() != query_league_code.lower():
                continue
            
            # If user specified age group, match must have it
            if age_group and age_group.lower() not in search_blob:
                continue
            
            # If user specified club name, match must have it
            if canonical_club and canonical_club.lower() not in search_blob:
                continue
            
            # Fallback: if no specific filters, do basic substring match
            if not age_group and not canonical_club and not query_league_code:
                if q_lower not in search_blob:
                    continue
        
        matches_after_query_filter += 1
        
        # Check if scores are missing
        status = (attrs.get("status") or "").lower()
        home_score = attrs.get("home_score")
        away_score = attrs.get("away_score")

        # Only flag as missing if match has already taken place (past or today)
        # Future scheduled fixtures should never appear as "missing scores"
        is_past_or_today = match_date <= today

        needs_score = (
            is_past_or_today and (
                status != "complete" or
                home_score is None or
                away_score is None
            )
        )
        
        if needs_score:
            missing_scores.append({
                "date": match_dt.strftime("%d-%b"),
                "time": match_dt.strftime("%I:%M %p"),
                "time_sort": match_dt.time(),  # Add sortable time object
                "datetime_sort": match_dt,  # Keep full datetime for sorting
                "league": extract_league_from_league_name(league),
                "home_team": home_team,
                "away_team": away_team,
                "round": attrs.get("full_round", attrs.get("round", "")),
                "venue": attrs.get("ground_name", "TBD"),
                "status": status,
                "source": attrs.get('source', 'unknown'),
                "home_score": home_score,
                "away_score": away_score
            })
    
    print(f"\n  FILTERING SUMMARY:")
    if date_sample:
        print(f"    Sample dates in data:")
        for i, sample in enumerate(date_sample, 1):
            print(f"      {i}. {sample['utc'][:10]} UTC -> {sample['aest'][:10]} AEST: {sample['home']} vs {sample['away']}")
    
    if today_only:
        print(f"    Matches on target date ({match_day}): {matches_on_target_date}")
    if target_leagues:
        print(f"    Matches in target leagues: {matches_with_target_leagues}")
    print(f"    Matches after all filters: {matches_after_query_filter}")
    print(f"    Matches with missing scores: {len(missing_scores)}")
    
    if len(missing_scores) > 0:
        print(f"\n  MISSING SCORES DETAILS:")
        for i, m in enumerate(missing_scores[:5], 1):
            print(f"    {i}. {m['home_team']} vs {m['away_team']}")
            print(f"       Time: {m['time']}, Status: '{m['status']}', Scores: {m['home_score']}-{m['away_score']}, Source: {m['source']}")
    
    print(f"{'='*80}\n")
    
    if not missing_scores:
        filter_text = f" matching '{query}'" if query else ""
        league_text = f" in {', '.join(target_leagues)}" if target_leagues else ""
        debug_info = f" (Checked {matches_after_query_filter} matches"
        if today_only:
            debug_info += f", {matches_on_target_date} on {match_day}"
        debug_info += ")"
        return f"✅ All scores entered{day_label}{league_text}{filter_text}!{debug_info}"
    
    # Sort by date/time
    missing_scores.sort(key=lambda x: x["datetime_sort"])
    # Format as table
    data = []
    for i, match in enumerate(missing_scores, 1):
        row = {
            "#": i,
            "League": match["league"],
            "Match": f"{match['home_team']} vs {match['away_team']}",
            "Round": match["round"],
            "Venue": match["venue"]
        }
        
        # Only add date column if not today_only (since date is the same)
        if not today_only:
            row["Date"] = match["date"]
            row["Time"] = match["time"]
        else:
            row["Time"] = match["time"]
        
        data.append(row)
    
    filter_suffix = f" - {query}" if query else ""
    league_suffix = f" ({', '.join(target_leagues)})" if target_leagues else ""
    
    return {
        "type": "table",
        "data": data,
        "title": f"{date_display}\n⚠️ Missing Scores{league_suffix}{filter_suffix} ({len(missing_scores)} matches)"
    }
    

def tool_todays_results(query: str = "") -> Any:
    """
    Show results from today (if Sunday) or last Sunday.
    Optionally filter by team/club.
    """
    
    # ========== TESTING OVERRIDE - UNCOMMENT TO FORCE LAST SUNDAY ==========
    #FORCE_LAST_SUNDAY = True  # Uncomment this line to test with last Sunday's data
    # ========================================================================
    
    # Check if testing override is active
    try:
        force_last_sunday = FORCE_LAST_SUNDAY
    except NameError:
        force_last_sunday = False
    
    melbourne_tz = pytz.timezone('Australia/Melbourne')
    today = datetime.now(melbourne_tz).date()
    
    if force_last_sunday:
        # TESTING MODE: Force last Sunday
        match_day = get_last_sunday()
        print(f"⚠️  TESTING MODE (todays_results): Forcing last Sunday ({match_day})")
    else:
        # NORMAL MODE: Use today if Sunday, else last Sunday
        match_day = get_match_day_date()
    
    # Determine the label and prominent date display
    if match_day == today:
        day_label = "Today"
        date_display = f"📅 **TODAY ({today.strftime('%A, %d %B %Y')})**"
    else:
        day_label = f"Last Sunday ({match_day.strftime('%d-%b')})"
        date_display = f"📅 **LAST SUNDAY ({match_day.strftime('%A, %d %B %Y')})**"
    
    # ADD DEBUG
    print(f"DEBUG tool_todays_results - Looking for matches on: {match_day}")
    print(f"DEBUG tool_todays_results - Day label: {day_label}")
    
    # ✅ NEW: Check BOTH fixtures and results data sources
    all_matches = []
    
    # Add fixtures
    for fixture in fixtures:
        attrs = fixture.get("attributes", {})
        attrs['source'] = 'fixtures'
        all_matches.append(attrs)
    
    # Add results
    for result in results:
        attrs = result.get("attributes", {})
        attrs['source'] = 'results'
        all_matches.append(attrs)
    
    print(f"DEBUG tool_todays_results - Checking {len(all_matches)} total matches ({len(fixtures)} fixtures + {len(results)} results)")
    
    # Filter results for this date
    todays_results = []
    
    for attrs in all_matches:
        date_str = attrs.get("date", "")
        if not date_str:
            continue
        
        # Parse to Melbourne date
        match_dt = parse_date_utc_to_aest(date_str)
        if not match_dt:
            continue
        
        match_date = match_dt.date()
        
        # ADD DEBUG - show first few matches
        if len(todays_results) < 3:
            print(f"  Checking match: {attrs.get('home_team_name')} vs {attrs.get('away_team_name')} on {match_date} (from {attrs.get('source')})")
        
        # Check if match is on our target date
        if match_date != match_day:
            continue

        home_team = attrs.get("home_team_name", "Unknown")
        away_team = attrs.get("away_team_name", "Unknown")
        league = attrs.get("league_name", "")

        # Skip bye matches — identified by missing team hash IDs
        if not attrs.get("home_team_hash_id") or not attrs.get("away_team_hash_id"):
            continue
        # Enhanced query filter - supports league, team, club, age group
        if query:
            q_lower = query.lower().strip()
            
            # Extract filters from query
            age_group = extract_age_group(q_lower)
            canonical_club = get_canonical_club_name(q_lower)
            
            # Extract league code from the match
            match_league_code = extract_league_from_league_name(league)
            
            # Build comprehensive search blob
            search_blob = f"{home_team} {away_team} {league} {match_league_code}".lower()
            
            # Check if query specifies a league code (YPL1, YPL2, YSL NW, etc.)
            query_league_code = None
            for possible_league in ['ypl1', 'ypl2', 'ysl nw', 'ysl se', 'vpl men', 'vpl women', 'ypl 1', 'ypl 2']:
                if possible_league in q_lower:
                    query_league_code = extract_league_from_league_name(possible_league)
                    break
            
            # If user specified a league code, match must have it
            if query_league_code and match_league_code.lower() != query_league_code.lower():
                continue
            
            # If user specified age group, match must have it
            if age_group and age_group.lower() not in search_blob:
                continue
            
            # If user specified club name, match must have it
            if canonical_club and canonical_club.lower() not in search_blob:
                continue
            
            # Fallback: if no specific filters, do basic substring match
            if not age_group and not canonical_club and not query_league_code:
                if q_lower not in search_blob:
                    continue
        
        # Check if scores are entered
        home_score = attrs.get("home_score")
        away_score = attrs.get("away_score")
        status = (attrs.get("status") or "").lower()
        
        if status == "complete" and home_score is not None and away_score is not None:
            todays_results.append({
                "time": match_dt.strftime("%I:%M %p"),
                "datetime_sort": match_dt,  # For proper time sorting
                "league": extract_league_from_league_name(attrs.get("league_name", "")),
                "home_team": home_team,
                "away_team": away_team,
                "home_score": home_score,
                "away_score": away_score,
                "round": attrs.get("full_round", attrs.get("round", "")),
                "source": attrs.get("source", "unknown")
            })
    
    # ADD DEBUG
    print(f"DEBUG tool_todays_results - Found {len(todays_results)} completed results")
    if todays_results:
        print(f"DEBUG tool_todays_results - First result: {todays_results[0]['home_team']} {todays_results[0]['home_score']}-{todays_results[0]['away_score']} {todays_results[0]['away_team']} (from {todays_results[0]['source']})")
    
    if not todays_results:
        filter_text = f" matching '{query}'" if query else ""
        return f"{date_display}\n❌ No results found{filter_text}"
    
    # Sort by actual datetime object, not string
    todays_results.sort(key=lambda x: x["datetime_sort"])
    
    # Format as table with separate columns for better visibility
    data = []
    for i, match in enumerate(todays_results, 1):
        data.append({
            "#": i,
            "Time": match["time"],
            "League": match["league"],
            "Home": match["home_team"],
            "Score": f"{match['home_score']}-{match['away_score']}",
            "Away": match["away_team"],
            "Round": match["round"]
        })
    filter_suffix = f" - {query}" if query else ""
    return {
        "type": "table",
        "data": data,
        "title": f"{date_display}\n⚽ Results{filter_suffix} ({len(todays_results)} matches)"
    }

def tool_top_scorers_today(query: str = "") -> Any:
    """
    Show players who scored goals today (if Sunday) or last Sunday.
    Filter by league, team, club, or age group.
    """
    match_day = get_match_day_date()
    
    melbourne_tz = pytz.timezone('Australia/Melbourne')
    today = datetime.now(melbourne_tz).date()
    
    # Determine the label
    if match_day == today:
        day_label = "Today"
    else:
        day_label = f"Last Sunday ({match_day.strftime('%d-%b')})"
    
    # Get all goal events from today's matches
    goal_scorers = {}  # player_name: [goals_list]
    
    for result in results:
        attrs = result.get("attributes", {})
        date_str = attrs.get("date", "")
        if not date_str:
            continue
        
        match_dt = parse_date_utc_to_aest(date_str)
        if not match_dt:
            continue
        
        match_date = match_dt.date()
        
        if match_date != match_day:
            continue
        
        # Apply query filter (league, team, club, age group)
        home_team = attrs.get("home_team_name", "")
        away_team = attrs.get("away_team_name", "")
        league = attrs.get("league_name", "")

        # Enhanced query filter - supports league, team, club, age group
        if query:
            q_lower = query.lower().strip()
            
            # Extract filters from query
            age_group = extract_age_group(q_lower)
            canonical_club = get_canonical_club_name(q_lower)
            
            # Extract league code from the match
            match_league_code = extract_league_from_league_name(league)
            
            # Build comprehensive search blob
            search_blob = f"{home_team} {away_team} {league} {match_league_code}".lower()
            
            # Check if query specifies a league code (YPL1, YPL2, YSL NW, etc.)
            query_league_code = None
            for possible_league in ['ypl1', 'ypl2', 'ysl nw', 'ysl se', 'vpl men', 'vpl women', 'ypl 1', 'ypl 2']:
                if possible_league in q_lower:
                    query_league_code = extract_league_from_league_name(possible_league)
                    break
            
            # If user specified a league code, match must have it
            if query_league_code and match_league_code.lower() != query_league_code.lower():
                continue
            
            # If user specified age group, match must have it
            if age_group and age_group.lower() not in search_blob:
                continue
            
            # If user specified club name, match must have it
            if canonical_club and canonical_club.lower() not in search_blob:
                continue
            
            # Fallback: if no specific filters, do basic substring match
            if not age_group and not canonical_club and not query_league_code:
                if q_lower not in search_blob:
                    continue
        # Extract goal scorers from this match
        match_hash = result.get("match_hash_id", "")
        if not match_hash:
            continue
        
        # Get match centre data for this match
        match_data = next((m for m in match_centre_data if m.get("match_hash_id") == match_hash), None)
        if not match_data:
            continue
        
        events = match_data.get("events", [])
        for event in events:
            if event.get("event_type") == "goal":
                player_name = event.get("player_name", "Unknown")
                team = event.get("team_name", "")
                minute = event.get("minute", "")
                
                if player_name not in goal_scorers:
                    goal_scorers[player_name] = {
                        "goals": 0,
                        "team": team,
                        "minutes": []
                    }
                
                goal_scorers[player_name]["goals"] += 1
                if minute:
                    goal_scorers[player_name]["minutes"].append(minute)
    
    if not goal_scorers:
        filter_text = f" matching '{query}'" if query else ""
        return f"⚽ No goals scored for {day_label}{filter_text}"
    
    # Sort by goals (descending)
    sorted_scorers = sorted(goal_scorers.items(), key=lambda x: x[1]["goals"], reverse=True)
    
    # Format as table
    data = []
    for i, (name, info) in enumerate(sorted_scorers, 1):
        minutes_str = format_minutes(info["minutes"])
        data.append({
            "Rank": i,
            "Player": name,
            "Team": info["team"],
            "Goals": info["goals"],
            "Minutes": minutes_str
        })
    
    filter_suffix = f" - {query}" if query else ""
    return {
        "type": "table",
        "data": data,
        "title": f"⚽ Top Scorers for {day_label}{filter_suffix} ({len(goal_scorers)} players)"
    }

def tool_teams_lost_today(query: str = "") -> Any:
    """
    Show teams that lost matches today (if Sunday) or last Sunday.
    Filter by league, club, or age group.
    """
    match_day = get_match_day_date()
    
    melbourne_tz = pytz.timezone('Australia/Melbourne')
    today = datetime.now(melbourne_tz).date()
    
    # Determine the label
    if match_day == today:
        day_label = "Today"
    else:
        day_label = f"Last Sunday ({match_day.strftime('%d-%b')})"
    
    lost_teams = []
    
    for result in results:
        attrs = result.get("attributes", {})
        date_str = attrs.get("date", "")
        if not date_str:
            continue
        
        match_dt = parse_date_utc_to_aest(date_str)
        if not match_dt:
            continue
        
        match_date = match_dt.date()
        
        if match_date != match_day:
            continue
        
        home_team = attrs.get("home_team_name", "Unknown")
        away_team = attrs.get("away_team_name", "Unknown")
        league = attrs.get("league_name", "")
        home_score = attrs.get("home_score")
        away_score = attrs.get("away_score")
        status = (attrs.get("status") or "").lower()
        
        # Only process completed matches with scores
        if status != "complete" or home_score is None or away_score is None:
            continue
        
        try:
            hs = int(home_score)
            as_score = int(away_score)
        except (ValueError, TypeError):
            continue
        
        # Enhanced query filter - supports league, team, club, age group
        if query:
            q_lower = query.lower().strip()
            
            # Extract filters from query
            age_group = extract_age_group(q_lower)
            canonical_club = get_canonical_club_name(q_lower)
            
            # Extract league code from the match
            match_league_code = extract_league_from_league_name(league)
            
            # Build comprehensive search blob
            search_blob = f"{home_team} {away_team} {league} {match_league_code}".lower()
            
            # Check if query specifies a league code (YPL1, YPL2, YSL NW, etc.)
            query_league_code = None
            for possible_league in ['ypl1', 'ypl2', 'ysl nw', 'ysl se', 'vpl men', 'vpl women', 'ypl 1', 'ypl 2']:
                if possible_league in q_lower:
                    query_league_code = extract_league_from_league_name(possible_league)
                    break
            
            # If user specified a league code, match must have it
            if query_league_code and match_league_code.lower() != query_league_code.lower():
                continue
            
            # If user specified age group, match must have it
            if age_group and age_group.lower() not in search_blob:
                continue
            
            # If user specified club name, match must have it
            if canonical_club and canonical_club.lower() not in search_blob:
                continue
            
            # Fallback: if no specific filters, do basic substring match
            if not age_group and not canonical_club and not query_league_code:
                if q_lower not in search_blob:
                    continue
        
        # Determine losers
        if hs > as_score:
            # Away team lost
            lost_teams.append({
                "team": away_team,
                "league": extract_league_from_league_name(league),
                "opponent": home_team,
                "score": f"{as_score}-{hs}",
                "venue": "Away"
            })
        elif as_score > hs:
            # Home team lost
            lost_teams.append({
                "team": home_team,
                "league": extract_league_from_league_name(league),
                "opponent": away_team,
                "score": f"{hs}-{as_score}",
                "venue": "Home"
            })
    
    if not lost_teams:
        filter_text = f" matching '{query}'" if query else ""
        return f"✅ No teams lost for {day_label}{filter_text} (or no completed matches)"
    
    # Sort by team name
    lost_teams.sort(key=lambda x: x["team"])
    
    # Format as table
    data = []
    for i, team in enumerate(lost_teams, 1):
        data.append({
            "#": i,
            "Team": team["team"],
            "League": team["league"],
            "Opponent": team["opponent"],
            "Score": team["score"],
            "H/A": team["venue"]
        })
    
    filter_suffix = f" - {query}" if query else ""
    return {
        "type": "table",
        "data": data,
        "title": f"🔴 Teams That Lost on {day_label}{filter_suffix} ({len(lost_teams)} teams)"
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
    """List all people with yellow cards - supports age group and team filtering.
    Uses staff_summary for coach/staff queries, players_summary for players."""
    
    # Initialize variables to avoid UnboundLocalError
    age_group = None
    team_name = None
    base_club = None
    
    # 1. Use staff_summary for coach/staff queries, players_summary otherwise
    source = staff_summary if include_non_players else players_summary
    players_with_yellows = [
        p for p in source
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
    """List all people with red cards - supports age group and team filtering.
    Uses staff_summary for coach/staff queries, players_summary for players."""
    source = staff_summary if include_non_players else players_summary
    players_with_reds = [
        p for p in source
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
    
    # Filter players - use _person_teams for multi-team support
    def _matches_team(p, check):
        return any(check(t) for t in _person_teams(p))
    if canonical_club:
        if age_group:
            players = [p for p in players_summary if _matches_team(p, lambda t: t == team_filter)]
        else:
            players = [p for p in players_summary if _matches_team(p, lambda t: (t or "").startswith(canonical_club))]
    else:
        players = [p for p in players_summary if _matches_team(p, lambda t: team_filter.lower() in (t or "").lower())]
    
    # Filter to only players (not coaches/staff)
    players = [p for p in players if not p.get("role") or str(p.get("role", "")).lower() == "player"]
    
    if not players:
        return f"❌ No players found for team: {query}"
    
    display_team = _person_teams(players[0])[0] if _person_teams(players[0]) else team_filter
    lines = [f"📊 **Team Statistics: {display_team}**\n"]
    
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
            
            # Handle None values properly
            home_team = a.get('home_team_name') or ''
            away_team = a.get('away_team_name') or ''
            
            is_home = team_name_to_match.lower() in home_team.lower()
            if is_home:
                result = "🟢 W" if int(hs) > int(as_) else ("🔴 L" if int(hs) < int(as_) else "🟡 D")
            else:
                result = "🟢 W" if int(as_) > int(hs) else ("🔴 L" if int(as_) < int(hs) else "🟡 D")
            
            lines.append(f"\n  {result} {date_str}: {home_team} {hs}-{as_} {away_team}")

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
    """Search for player or staff and show stats. Uses players_summary for players, staff_summary for staff."""
    q = query.lower().strip()
        # ===== DEBUG: Show what we're routing =====
    print(f"\n{'='*60}")
    print(f"🔍 ROUTER RECEIVED: '{query}'")
    print(f"🔍 LOWERCASE: '{q}'")
    print(f"{'='*60}")
    # Exact substring match in players first
    exact_matches = []
    for full_name, player_data in player_lookup.items():
        if q in full_name:
            exact_matches.append(player_data)
    
    # If no player match, try staff (e.g. "stats for Coach Name")
    if not exact_matches:
        staff_matches = []
        for full_name, staff_data in staff_lookup.items():
            if q in full_name:
                staff_matches.append(staff_data)
        if len(staff_matches) == 1:
            p = staff_matches[0]
            stats = p.get("stats", {})
            teams = ", ".join(p.get("teams", []) or [p.get("team_name", "")])
            role = (p.get("roles") or [p.get("role", "Staff")])[0] if (p.get("roles") or p.get("role")) else "Staff"
            lines = [
                f"👤 **{p.get('first_name')} {p.get('last_name')}** ({role})",
                f"   Teams: {teams}",
                f"   Matches Attended: {stats.get('matches_attended', stats.get('matches_played', 0))}",
                f"   🟨 Yellow Cards: {stats.get('yellow_cards', 0)}",
                f"   🟥 Red Cards: {stats.get('red_cards', 0)}",
            ]
            matches = p.get("matches", [])
            if detailed and matches:
                lines.append(f"\n📅 **Match-by-Match:** ({len(matches)} matches)\n")
                for m in matches:
                    date_str = format_date(m.get('date', ''))
                    opp = m.get('opponent_team_name') or m.get('opponent', '')
                    role_match = m.get('role_in_match', '')
                    perf = []
                    if m.get('yellow_cards', 0) > 0:
                        ym = format_minutes(m.get('yellow_minutes', []))
                        perf.append(f"🟨 ({ym})" if ym else "🟨")
                    if m.get('red_cards', 0) > 0:
                        rm = format_minutes(m.get('red_minutes', []))
                        perf.append(f"🟥 ({rm})" if rm else "🟥")
                    lines.append(f"   {date_str} vs {opp} - {role_match} " + (" ".join(perf) if perf else ""))
            return "\n".join(lines)
        elif len(staff_matches) > 1:
            data = [{"Name": f"{s.get('first_name')} {s.get('last_name')}", "Role": (s.get("roles") or ["Staff"])[0], "Team": (s.get("teams") or [""])[0], "Yellow": s.get("stats", {}).get("yellow_cards", 0), "Red": s.get("stats", {}).get("red_cards", 0)} for s in staff_matches[:10]]
            return {"type": "table", "data": data, "title": f"👤 Found {len(staff_matches)} staff matching '{query}'"}
    
    if exact_matches:
        if len(exact_matches) == 1:
            p = exact_matches[0]
            stats   = p.get("stats", {})
            matches = p.get("matches", [])   # already deduped by _normalize_person

            all_teams   = p.get("teams", []) or ([p.get("team_name")] if p.get("team_name") else [])
            all_leagues = p.get("leagues", []) or ([p.get("league_name")] if p.get("league_name") else [])
            jerseys_map = p.get("jerseys", {})
            is_dual_reg = len(all_teams) > 1
            pname       = f"{p.get('first_name')} {p.get('last_name')}"

            # Does the JSON have team_name on match entries? (new dribl format)
            has_team_in_matches = any(m.get("team_name") for m in matches)

            # ── Registration row per club ──────────────────────────────
            reg_rows = []
            for i, t in enumerate(all_teams):
                jersey = jerseys_map.get(t) or p.get("jersey", "—")
                league = all_leagues[i] if i < len(all_leagues) else p.get("league_name", "")

                if has_team_in_matches:
                    tm  = [m for m in matches if m.get("team_name") == t]
                    mp  = len(tm)
                    g   = sum(m.get("goals", 0) for m in tm)
                    yc  = sum(m.get("yellow_cards", 0) for m in tm)
                    rc  = sum(m.get("red_cards", 0) for m in tm)
                else:
                    # Old JSON without team_name on matches — show totals on first row
                    if i == 0:
                        mp = stats.get("matches_played", len(matches))
                        g  = stats.get("goals", 0)
                        yc = stats.get("yellow_cards", 0)
                        rc = stats.get("red_cards", 0)
                    else:
                        mp, g, yc, rc = "—", "—", "—", "—"

                reg_rows.append({
                    "Club":    t,
                    "League":  league,
                    "Jersey":  f"#{jersey}",
                    "Matches": mp,
                    "⚽":      g,
                    "🟨":      yc,
                    "🟥":      rc,
                })

            # ── Match history rows ─────────────────────────────────────
            display_matches = matches if detailed else matches[:5]
            match_rows = []
            for m in display_matches:
                events  = m.get("events", [])
                def _etype(e): return (e.get("type") or e.get("event_type") or "").lower()
                goals   = m.get("goals",       sum(1 for e in events if _etype(e) == "goal"))
                yellows = m.get("yellow_cards", sum(1 for e in events if _etype(e) == "yellow_card"))
                reds    = m.get("red_cards",    sum(1 for e in events if _etype(e) == "red_card"))
                row = {
                    "Date":     format_date(m.get("date", "")),
                    "H/A":      "🏠" if m.get("home_or_away") == "home" else "✈️",
                    "Opponent": m.get("opponent_team_name", "—"),
                    "Started":  "✅" if m.get("started") else "🪑",
                    "⚽":       goals,
                    "🟨":       yellows,
                    "🟥":       reds,
                }
                # Show Club column for dual-reg players when data is available
                if is_dual_reg and m.get("team_name"):
                    row["Club"] = m["team_name"]
                match_rows.append(row)

            note = ""
            if is_dual_reg and not has_team_in_matches:
                note = "Per-club split unavailable — re-run dribl_player_details.py to regenerate JSON"

            return {
                "type":          "player_profile",
                "name":          pname,
                "is_dual":       is_dual_reg,
                "registrations": reg_rows,
                "season_stats": {
                    "Played":   stats.get("matches_played", 0),
                    "Started":  stats.get("matches_started", 0),
                    "Bench":    stats.get("bench_appearances", 0),
                    "⚽ Goals": stats.get("goals", 0),
                    "🟨":       stats.get("yellow_cards", 0),
                    "🟥":       stats.get("red_cards", 0),
                },
                "matches":  match_rows,
                "detailed": detailed,
                "note":     note,
            }
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

    def _mt(p, check):
        return any(check(t) for t in _person_teams(p))
    if canonical_club:
        if age_group:
            players = [p for p in players_summary if _mt(p, lambda t: t == team_filter)]
        else:
            players = [p for p in players_summary if _mt(p, lambda t: (t or "").startswith(canonical_club))]
    else:
        players = [p for p in players_summary if _mt(p, lambda t: team_filter.lower() in (t or "").lower())]
    
    players = [p for p in players if not p.get("role") or str(p.get("role", "")).lower() == "player"]
    
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
    team_name_to_match = (_person_teams(players[0])[0] if _person_teams(players[0]) else players[0].get('team_name', '')) if players else team_filter
    
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

    print(f"DEBUG tool_ladder - Query: '{query}'")

    # Step 1: Try to extract competition code directly from the query
    # This is the most reliable method — handles "YPL2", "YPL 2", "ypl2" etc
    competition_to_use = extract_league_from_league_name(q)

    # Step 2: Only fall back to fuzzy matching if direct extraction failed
    if not competition_to_use or competition_to_use == "Other":
        league = fuzzy_find(q, [l.lower() for l in league_names], threshold=60)
        comp = fuzzy_find(q, [c.lower() for c in competition_names], threshold=60)
        print(f"DEBUG tool_ladder - Fuzzy matched league: {league}, comp: {comp}")

        if league:
            competition_to_use = extract_league_from_league_name(league)
        elif comp:
            competition_to_use = extract_league_from_league_name(comp)

    if not competition_to_use or competition_to_use == "Other":
        return f"❌ No ladder found for: {query}\n\nTry: 'YPL1 ladder', 'YPL2 ladder', 'YSL NW ladder'"

    # Extract age group separately — never concatenate with competition
    # Data stores them in different orders e.g. "U16 Boys Victorian Youth Premier League 2"
    age_group = extract_age_group(query)
    age_group_lower = age_group.lower() if age_group else None

    competition_to_use = competition_to_use.lower()
    print(f"DEBUG tool_ladder - Using competition: {competition_to_use}, age_group: {age_group_lower}")

    table = defaultdict(lambda: {"P": 0, "W": 0, "D": 0, "L": 0, "GF": 0, "GA": 0, "PTS": 0})

    matches_found = 0
    for r in results:
        a = r.get("attributes", {})
        league_name = (a.get("league_name") or "").lower()
        comp_name = (a.get("competition_name") or "").lower()

        # Check competition code appears in league or comp name
        comp_match = competition_to_use in league_name or competition_to_use in comp_name
        if not comp_match:
            continue

        # If age group was specified, ALSO check it appears in the league name separately
        if age_group_lower and age_group_lower not in league_name and age_group_lower not in comp_name:
            continue
        
        matches_found += 1

        home = a.get("home_team_name") or ""
        away = a.get("away_team_name") or ""
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
    
    print(f"DEBUG tool_ladder - Matches found: {matches_found}")
    print(f"DEBUG tool_ladder - Teams in table: {len(table)}")

    if not table:
        return f"❌ No ladder for: {query}\n\nFound competition '{competition_to_use.upper()}' but no completed matches.\n\nTry: 'YPL1 ladder', 'YPL2 ladder', 'YSL NW ladder'"

    ladder = sorted(
        table.items(),
        key=lambda kv: (kv[1]["PTS"], kv[1]["GF"] - kv[1]["GA"], kv[1]["GF"]),
        reverse=True,
    )

    data = []
    for pos, (team, row) in enumerate(ladder, 1):
        gd = row["GF"] - row["GA"]
        data.append({
            "Pos": pos,
            "Team": team,
            "P": row["P"],
            "W": row["W"],
            "D": row["D"],
            "L": row["L"],
            "GF": row["GF"],
            "GA": row["GA"],
            "GD": gd,
            "PTS": row["PTS"]
        })
    
    return {
        "type": "table",
        "data": data,
        "title": f"📊 {competition_to_use.upper()} Ladder ({len(ladder)} teams)"
    }
    
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
    match_data = []
    
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
        
        match_data.append({
            "Date": date_str,
            "Result": icon + " " + result,
            "Match": f"{home} {hs}-{as_} {away}",
            "Score": f"{hs}-{as_}"
        })
    
    # Return table format
    return {
        "type": "table",
        "data": match_data,
        "title": f"📈 Recent Form: {team} - {' '.join(form)}"
    }

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
    """List non-players (coaches, staff) with optional team filtering and card info.
    Uses staff_summary.json as the data source."""
    non_players = list(staff_summary)
    
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
# 11B. DUAL REGISTRATION / PLAYING IN MULTIPLE TEAMS
# ---------------------------------------------------------

def tool_dual_registration(query: str = "") -> Any:
    """
    Find players registered in multiple teams (dual registration).
    Supports filtering by club name, age group, or league.

    Query examples:
      "dual registration"
      "players in 2 teams"
      "playing for 2 clubs heidelberg"
      "dual reg U16"
    """
    age_group_filter = extract_age_group(query) if query else None
    base_club_filter = extract_base_club_name(query) if query else None
    league_code_filter = None
    if query:
        for lc in ['ypl1', 'ypl2', 'ysl nw', 'ysl se', 'vpl men', 'vpl women']:
            if lc in query.lower():
                league_code_filter = lc.upper()
                break

    dual_players = []
    for p in players_summary:
        teams = p.get("teams", [])
        if not isinstance(teams, list) or len(teams) < 2:
            # Also check legacy: player has a team_name but also appears in more than one league
            leagues = p.get("leagues", [])
            if not (isinstance(leagues, list) and len(leagues) >= 2):
                continue

        # Age group filter — at least one team must match
        if age_group_filter:
            if not any(age_group_filter.lower() in (t or "").lower() for t in teams):
                continue

        # Club filter — at least one team must contain the club name
        if base_club_filter:
            if not any(base_club_filter.lower() in (t or "").lower() for t in teams):
                continue

        # League code filter
        if league_code_filter:
            player_leagues = p.get("leagues", [])
            if not any(league_code_filter in extract_league_from_league_name(lg).upper() for lg in player_leagues):
                continue

        dual_players.append(p)

    if not dual_players:
        filter_text = f" matching '{query}'" if query else ""
        return f"❌ No players found registered in multiple teams{filter_text}"

    # Sort by name
    dual_players.sort(key=lambda p: f"{p.get('first_name','')} {p.get('last_name','')}")

    data = []
    for i, p in enumerate(dual_players, 1):
        name = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
        teams = p.get("teams", [])
        leagues = p.get("leagues", [])
        # Shorten league names for display
        short_leagues = [extract_league_from_league_name(lg) for lg in leagues] if leagues else []
        stats = p.get("stats", {})
        data.append({
            "#": i,
            "Player": name,
            "Teams": " / ".join(teams),
            "Age Groups": " / ".join([t.split()[-1] for t in teams if t.split()]),
            "Leagues": " / ".join(short_leagues) if short_leagues else "—",
            "Goals": stats.get("goals", 0),
            "🟨": stats.get("yellow_cards", 0),
            "🟥": stats.get("red_cards", 0),
        })

    filter_suffix = f" — {query.title()}" if query else ""
    return {
        "type": "table",
        "data": data,
        "title": f"🔄 Dual / Multi-Team Registrations{filter_suffix} ({len(dual_players)} players found)"
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
 
        # ADD THIS DEBUG BLOCK RIGHT HERE
        print("="*60)
        print(f"ROUTER DEBUG: Received query: '{query}'")
        print(f"ROUTER DEBUG: Lowercase query: '{q}'")
        print(f"ROUTER DEBUG: 'missing' in q: {'missing' in q}")
        print(f"ROUTER DEBUG: 'today' in q: {'today' in q}")
        print("="*60) 
        # --- 1. INITIALIZE ALL VARIABLES AT THE START ---
        # This prevents the UnboundLocalError by ensuring they exist immediately
        filter_query = ""
        show_details = False
        is_non_player_query = any(keyword in q for keyword in ['non player', 'non-player', 'coach', 'coaches', 'staff', 'manager'])
        is_personal_query = any(keyword in q for keyword in ['my next', 'when do i play', 'where do i play', 'my schedule', 'when is my', 'where is my', 'our next'])

        # --- 1B. DUAL REGISTRATION / MULTI-TEAM PLAYERS ---
        dual_keywords = [
            'dual registration', 'dual reg', 'playing for 2', 'playing for two',
            '2 clubs', '2 teams', 'two clubs', 'two teams', 'multi-team',
            'multiple teams', 'multiple clubs', 'playing in 2', 'registered in 2',
            'two leagues', '2 leagues', 'both teams', 'in 2 age groups'
        ]
        if any(keyword in q for keyword in dual_keywords):
            filter_query = re.sub(
                r'\b(dual|registration|reg|playing|for|in|two|2|clubs?|teams?|multiple|multi|registered|both|leagues?|age|groups?)\b',
                '', q
            ).strip()
            return tool_dual_registration(filter_query)

        # --- 2. MISSING SCORES ---
        missing_keywords = ['missing score', 'missing scores', 'no score', 'scores not entered', 'overdue', 'matches without scores', 'todays missing', 'missing scores today']
        if any(keyword in q for keyword in missing_keywords):
            today_only = 'today' in q or 'todays' in q or "today's" in q
            last_week = 'last week' in q or 'previous week' in q

            # Extract round number if present e.g. "round 5" or "r5"
            round_match = re.search(r'\bround\s*(\d+)\b', q)
            round_filter = int(round_match.group(1)) if round_match else None

            # Strip known keywords including round/week words
            filter_query = re.sub(
                r'\b(missing|score|scores?|no|not|entered|overdue|matches?|without|for|show|list|today|todays|today\'s|last|previous|week|round|\d+)\b',
                '', q
            ).strip()

            include_all = 'all leagues' in q or 'all league' in q

            return tool_missing_scores(
                filter_query,
                include_all_leagues=include_all,
                today_only=today_only,
                last_week=last_week,
                round_filter=round_filter
            )       

        # --- 2B. TODAY'S RESULTS ---
        todays_results_keywords = [
            'today results', 
            'todays results', 
            'results today', 
            'todays results',
            'results for today',
            'today s results'   # No apostrophe (space)
        ]
        print(f"🔍 Checking todays_results keywords: {any(keyword in q for keyword in todays_results_keywords)}")  # ADD THIS
        if any(keyword in q for keyword in todays_results_keywords):
            print(f"✅ MATCHED todays_results!")  # ADD THIS
            filter_query = re.sub(r'\b(today|todays|today\'s|results?|for|show|list|me)\b', '', q).strip()
            print(f"✅ Calling tool_todays_results with filter: '{filter_query}'")  # ADD THIS
            return tool_todays_results(filter_query)
        # --- 2C. TOP SCORERS TODAY ---
        top_scorers_today_keywords = ['top scorers today', 'goals today', 'who scored today', 'scorers today', "today's scorers", "today's goals"]
        if any(keyword in q for keyword in top_scorers_today_keywords):
            filter_query = re.sub(r'\b(top|scorer|scorers?|goals?|who|scored|today|todays|today\'s|for|show|list|me)\b', '', q).strip()
            return tool_top_scorers_today(filter_query)
        
        # --- 2D. TEAMS THAT LOST TODAY ---
        teams_lost_keywords = ['teams that lost today', 'who lost today', 'losses today', 'teams lost today', "today's losses"]
        if any(keyword in q for keyword in teams_lost_keywords):
            filter_query = re.sub(r'\b(teams?|that|who|lost|losses?|today|todays|today\'s|for|show|list|me)\b', '', q).strip()
            return tool_teams_lost_today(filter_query)

        # --- 2E. MISSING SCORES TODAY ---
        missing_today_keywords = ['missing scores today', 'missing today', 'scores not entered today', 'todays missing scores']
        if any(keyword in q for keyword in missing_today_keywords):
            filter_query = re.sub(r'\b(missing|today|todays|today\'s|scores?|not|entered|for|show|list|me)\b', '', q).strip()
            return tool_missing_scores(filter_query, include_all_leagues=False, today_only=True)
            
        # --- 3. COMPETITION OVERVIEW ---
        comp_overview_keywords = ['competition overview', 'competition standings', 'ypl1 overview', 'ypl2 overview', 'ysl overview', 'vpl overview', 'club rankings', 'overall standings']
        if any(keyword in q for keyword in comp_overview_keywords) or any(comp in q for comp in ['ypl1', 'ypl2', 'ysl nw', 'ysl se', 'vpl']):
            if any(word in q for word in ['overview', 'standings', 'ranking', 'competition']):
                return tool_competition_overview(query)

        # --- 4. FIXTURES / NEXT MATCH ---
        fixture_keywords = ['next match', 'next game', 'upcoming', 'when do i play', 'where do i play', 'my next', 'schedule', 'fixture', 'fixtures', 'when is my', 'where is my', 'our next']
        if any(keyword in q for keyword in fixture_keywords):
            if is_personal_query:
                return tool_fixtures(query="", limit=5, use_user_team=True)
            else:
                team_query = re.sub(r'\b(next|match|game|upcoming|when|where|do|i|play|my|schedule|fixtures?|is)\b', '', q).strip()
                limit = 5 if team_query else 10
                return tool_fixtures(team_query, limit, use_user_team=False)

        # --- 5. YELLOW CARDS ---
        if "yellow card" in q or "yellows" in q:
            show_details = "detail" in q
            filter_query = re.sub(r'\b(yellow|card|cards|details?|show|list|with|for|me)\b', '', q).strip()
            return tool_yellow_cards(filter_query, show_details, include_non_players=is_non_player_query)

        # --- 6. RED CARDS ---
        if "red card" in q or "reds" in q:
            show_details = "detail" in q
            filter_query = re.sub(r'\b(red|card|cards|details?|show|list|with|for|me)\b', '', q).strip()
            return tool_red_cards(filter_query, show_details, include_non_players=is_non_player_query)

        # --- 7. STANDALONE NON-PLAYER LIST ---
        if is_non_player_query:
            filter_query = re.sub(r'\b(non|player|players?|staff|coach|coaches?|manager|managers|for|all|show|list|with|get|me)\b', '', q).strip()
            return tool_non_players(filter_query)

        # --- 8. TOP SCORERS ---
        if any(word in q for word in ["top scorer","leading scorer", "top scorers", "golden boot"]):
            clean = re.sub(r'\b(top|scorer|scorers?|golden|boot|in|for|show|me|list)\b', '', q).strip()
            team_context = clean if clean else USER_CONFIG["team"]
            result = tool_top_scorers(team_context)
            if isinstance(result, dict) and result.get("type") == "table":
                result["title"] = f"🏆 Here are the top performers for {result.get('title', team_context)}:"
            return result
            
        # --- 9. TEAM AND PLAYER STATS ---
        if any(word in q for word in ["stats for", "team stats", "show me", "details for"]):
            clean = re.sub(r'\b(stats?|for|team|show|me|get|find|details?|profile|about)\b', '', q).strip()
            detailed = "detail" in q
            recognized_team = normalize_team(clean)
            if recognized_team:
                result = tool_team_stats(recognized_team)
                if isinstance(result, dict) and result.get("type") == "table":
                    result["title"] = f"📊 Performance data for **{recognized_team}**:"
                return result
            else:
                result = tool_players(clean, detailed)
                if isinstance(result, dict) and result.get("type") == "table":
                    result["title"] = f"👟 Recent stats for **{clean.title()}**:"
                return result

        # --- 10. LADDER & OTHER TOOLS ---
        if any(word in q for word in ["ladder", "table", "standings"]):
            return tool_ladder(query)
        if "lineup" in q or "starting" in q:
            return tool_lineups(query)
        if " vs " in q or " v " in q:
            return tool_match_centre(query)
        if "form" in q:
            team = normalize_team(query)
            return tool_form(team if team else query)
        
        # --- 11. DEFAULT FALLBACK ---
        team = normalize_team(query)
        if team:
            return tool_form(team)
        return tool_matches(query)