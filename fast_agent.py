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

def iso_date(date_str: str) -> str:
    """Return YYYY-MM-DD (ISO) string for use in st.dataframe Date columns.
    Streamlit DateColumn needs ISO format to sort correctly.
    Returns empty string for missing/invalid dates."""
    if not date_str:
        return ""
    try:
        date_part = date_str.split('T')[0] if 'T' in date_str else date_str
        dt = datetime.fromisoformat(date_part)
        return dt.strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return ""


def format_date_aest(date_str: str) -> str:
    """Convert UTC date string to dd-mmm format using AEST/AEDT local time."""
    if not date_str:
        return "TBD"
    try:
        dt = parse_date_utc_to_aest(date_str)
        if dt:
            return dt.strftime("%d-%b")
        # Fallback: no time component — treat as local date already
        date_part = date_str.split('T')[0] if 'T' in date_str else date_str
        return datetime.fromisoformat(date_part).strftime("%d-%b")
    except (ValueError, AttributeError):
        return date_str[:10] if len(date_str) >= 10 else date_str

def format_date_full_aest(date_str: str) -> str:
    """Convert UTC date string to dd-mmm-yyyy format using AEST/AEDT local time."""
    if not date_str:
        return "TBD"
    try:
        dt = parse_date_utc_to_aest(date_str)
        if dt:
            return dt.strftime("%d-%b-%Y")
        date_part = date_str.split('T')[0] if 'T' in date_str else date_str
        return datetime.fromisoformat(date_part).strftime("%d-%b-%Y")
    except (ValueError, AttributeError):
        return date_str[:10] if len(date_str) >= 10 else date_str

def iso_date_aest(date_str: str) -> str:
    """Return YYYY-MM-DD in AEST/AEDT local time (for sortable Streamlit DateColumn)."""
    if not date_str:
        return ""
    try:
        dt = parse_date_utc_to_aest(date_str)
        if dt:
            return dt.strftime("%Y-%m-%d")
        date_part = date_str.split('T')[0] if 'T' in date_str else date_str
        return datetime.fromisoformat(date_part).strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return ""

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
    """Parse date string and return as Melbourne local time (AEST/AEDT).

    Timezone handling rules:
    - Ends with 'Z'           → explicit UTC, convert to Melbourne
    - Has offset (+HH:MM)     → parse as-is, convert to Melbourne
    - Has 'T' but no tz info  → treat as ALREADY local Melbourne time (no conversion)
    - Date only               → treat as Melbourne midnight (no conversion)
    """
    if not date_str:
        return None
    try:
        melbourne_tz = pytz.timezone('Australia/Melbourne')

        if 'Z' in date_str:
            # Explicit UTC — convert to Melbourne
            utc_dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return utc_dt.astimezone(melbourne_tz)

        elif 'T' in date_str and ('+' in date_str[10:] or '-' in date_str[10:]):
            # Has timezone offset — parse and convert to Melbourne
            return datetime.fromisoformat(date_str).astimezone(melbourne_tz)

        elif 'T' in date_str:
            # Has time but NO timezone marker — treat as local Melbourne time already
            naive_dt = datetime.fromisoformat(date_str)
            return melbourne_tz.localize(naive_dt)

        else:
            # Date only — treat as local Melbourne midnight
            naive_dt = datetime.fromisoformat(date_str).replace(hour=0, minute=0, second=0)
            return melbourne_tz.localize(naive_dt)

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

    melbourne_tz = pytz.timezone('Australia/Melbourne')
    now_melbourne = datetime.now(melbourne_tz)

    # Determine base search term and limit
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

    # Pre-extract structured filters from the search term so we can match
    # age group and club independently (handles "U16 Heidelberg", "Heidelberg U16", etc.)
    q_lower       = search_term.lower().strip()
    age_group_f   = extract_age_group(q_lower)          # e.g. "U16"
    league_code_f = None
    for possible_league in ['ypl1', 'ypl2', 'ysl nw', 'ysl se', 'vpl men', 'vpl women']:
        if possible_league in q_lower:
            league_code_f = extract_league_from_league_name(possible_league)
            break

    # For club matching use the raw alias (short word like "heidelberg") — more robust
    # than the full canonical name which may differ slightly in fixture data
    club_token = None
    for alias in CLUB_ALIASES:
        if alias in q_lower:
            club_token = alias  # e.g. "heidelberg"
            break

    def _match_passes_filter(home: str, away: str, league: str) -> bool:
        search_blob = f"{home} {away} {league}".lower()
        match_league_code = extract_league_from_league_name(league)

        if league_code_f and match_league_code.lower() != league_code_f.lower():
            return False
        if age_group_f and age_group_f.lower() not in search_blob:
            return False
        if club_token and club_token not in search_blob:
            return False
        # If no structured filter found at all, fall back to plain substring
        if not age_group_f and not club_token and not league_code_f:
            return q_lower in search_blob
        return True

    upcoming = []
    for f in fixtures:
        attrs = f.get("attributes", {})
        date_str = attrs.get("date", "")

        match_dt = parse_date_utc_to_aest(date_str)
        if not match_dt:
            continue

        if match_dt < now_melbourne:
            continue

        home   = (attrs.get("home_team_name") or "")
        away   = (attrs.get("away_team_name") or "")
        league = (attrs.get("league_name") or "")

        if _match_passes_filter(home, away, league):
            upcoming.append((match_dt, attrs))

    upcoming.sort(key=lambda x: x[0])
    upcoming = upcoming[:limit]

    if not upcoming:
        return f"❌ No upcoming fixtures found for '{search_term}'."

    title_text = (f"All {USER_CONFIG['club']} Age Groups"
                  if not query and not use_user_team else search_term.title())
    lines = [f"📅 **Upcoming Fixtures: {title_text}**\n"]

    for i, (m_dt, attrs) in enumerate(upcoming, 1):
        days_until  = (m_dt.date() - now_melbourne.date()).days
        date_display = m_dt.strftime("%d-%b (%a) %I:%M %p")

        home  = attrs.get("home_team_name") or "Unknown"
        away  = attrs.get("away_team_name") or "Unknown"
        lg    = attrs.get("league_name") or ""
        venue = attrs.get("ground_name") or "TBD"

        if days_until == 0:
            status = "🔴 TODAY!"
        elif days_until == 1:
            status = "⚠️ Tomorrow"
        else:
            status = f"🗓️ In {days_until} days"

        lines.append(f"**{i}. {date_display}** — {status}")
        lines.append(f"    🏆 {lg}")
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
            # Default: show past full season (180 days), exclude future matches
            days_diff = (match_date - today).days
            if days_diff > 0 or days_diff < -180:
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
                "date":          match_dt.strftime("%d-%b"),
                "date_raw":      date_str,                    # raw for iso_date_aest
                "time":          match_dt.strftime("%I:%M %p"),
                "time_sort":     match_dt.time(),
                "datetime_sort": match_dt,
                "league":        extract_league_from_league_name(league),
                "home_team":     home_team,
                "away_team":     away_team,
                "round":         attrs.get("full_round", attrs.get("round", "")),
                "venue":         attrs.get("ground_name", "TBD"),
                "status":        status,
                "source":        attrs.get('source', 'unknown'),
                "home_score":    home_score,
                "away_score":    away_score
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
            row["Date"] = iso_date_aest(match["date_raw"])
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
    

def tool_todays_results(query: str = "", round_filter: int = None) -> Any:
    """
    Show results from today (if Sunday) or last Sunday.
    Supports filtering by league, age group, club, or round number.
    Properly deduplicates by match_hash_id (result takes priority over fixture).
    """
    melbourne_tz = pytz.timezone('Australia/Melbourne')
    today = datetime.now(melbourne_tz).date()

    # Determine match day
    try:
        force_last_sunday = FORCE_LAST_SUNDAY
    except NameError:
        force_last_sunday = False

    if force_last_sunday:
        match_day = get_last_sunday()
    else:
        match_day = get_match_day_date()

    if match_day == today:
        date_display = f"📅 **TODAY ({today.strftime('%A, %d %B %Y')})**"
    else:
        date_display = f"📅 **LAST SUNDAY ({match_day.strftime('%A, %d %B %Y')})**"

    # ── Build a deduplicated match map keyed on match_hash_id ──────────────
    # Results take priority; fixtures fill in matches not yet in results.
    match_map: dict = {}

    for result in results:
        attrs = dict(result.get("attributes", {}))
        mid = attrs.get("match_hash_id")
        attrs["_source"] = "result"
        if mid:
            match_map[mid] = attrs
        else:
            match_map[id(attrs)] = attrs

    for fixture in fixtures:
        attrs = dict(fixture.get("attributes", {}))
        mid = attrs.get("match_hash_id")
        attrs["_source"] = "fixture"
        if mid and mid not in match_map:
            match_map[mid] = attrs
        elif not mid:
            match_map[id(attrs)] = attrs

    # ── Parse query filters ────────────────────────────────────────────────
    q_lower = query.lower().strip() if query else ""
    age_group_filter   = extract_age_group(q_lower) if q_lower else None
    canonical_club     = get_canonical_club_name(q_lower) if q_lower else None
    query_league_code  = None
    if q_lower:
        for possible_league in ['ypl1', 'ypl2', 'ysl nw', 'ysl se', 'vpl men', 'vpl women', 'ypl 1', 'ypl 2']:
            if possible_league in q_lower:
                query_league_code = extract_league_from_league_name(possible_league)
                break

    # Extract round from query if not passed directly  e.g. "results round 5"
    if round_filter is None and q_lower:
        rm = re.search(r'\bround\s*(\d+)\b', q_lower)
        if rm:
            round_filter = int(rm.group(1))

    # ── Filter and collect ────────────────────────────────────────────────
    matched = []
    for attrs in match_map.values():
        date_str = attrs.get("date", "")
        if not date_str:
            continue

        match_dt = parse_date_utc_to_aest(date_str)
        if not match_dt:
            continue

        match_date = match_dt.date()

        # Date filter: must be on the match day (unless filtering by round only)
        if round_filter is None:
            if match_date != match_day:
                continue
        else:
            # Round mode: ignore date, filter by round number below
            pass

        home_team = attrs.get("home_team_name", "Unknown")
        away_team = attrs.get("away_team_name", "Unknown")
        league    = attrs.get("league_name", "")

        # Skip bye matches
        if not attrs.get("home_team_hash_id") or not attrs.get("away_team_hash_id"):
            continue

        match_league_code = extract_league_from_league_name(league)
        search_blob = f"{home_team} {away_team} {league} {match_league_code}".lower()

        # Round filter
        if round_filter is not None:
            match_round_str = str(attrs.get("round", "") or attrs.get("full_round", "") or "")
            round_num_match = re.search(r'(\d+)', match_round_str)
            if not round_num_match or int(round_num_match.group(1)) != round_filter:
                continue

        # League filter
        if query_league_code and match_league_code.lower() != query_league_code.lower():
            continue

        # Age group filter
        if age_group_filter and age_group_filter.lower() not in search_blob:
            continue

        # Club filter
        if canonical_club and canonical_club.lower() not in search_blob:
            continue

        # Fallback substring match (only when no structured filter found)
        if q_lower and not age_group_filter and not canonical_club and not query_league_code and not round_filter:
            # Strip round words before fallback check
            clean_q = re.sub(r'\b(round|r)\s*\d+\b', '', q_lower).strip()
            if clean_q and clean_q not in search_blob:
                continue

        # Must have scores entered
        home_score = attrs.get("home_score")
        away_score = attrs.get("away_score")
        status     = (attrs.get("status") or "").lower()

        if status == "complete" and home_score is not None and away_score is not None:
            match_round = attrs.get("full_round") or attrs.get("round") or ""
            matched.append({
                "datetime_sort": match_dt,
                "time":          match_dt.strftime("%I:%M %p"),
                "league":        match_league_code,
                "home_team":     home_team,
                "away_team":     away_team,
                "home_score":    home_score,
                "away_score":    away_score,
                "round":         match_round,
            })

    if not matched:
        filter_text = f" matching '{query}'" if query else ""
        round_text  = f" Round {round_filter}" if round_filter else ""
        return f"{date_display}\n❌ No results found{round_text}{filter_text}"

    matched.sort(key=lambda x: x["datetime_sort"])

    data = []
    for i, m in enumerate(matched, 1):
        data.append({
            "#":      i,
            "Time":   m["time"],
            "League": m["league"],
            "Round":  m["round"],
            "Home":   m["home_team"],
            "Score":  f"{m['home_score']}-{m['away_score']}",
            "Away":   m["away_team"],
        })

    filter_parts = []
    if round_filter:    filter_parts.append(f"Round {round_filter}")
    if query_league_code: filter_parts.append(query_league_code)
    if age_group_filter:  filter_parts.append(age_group_filter)
    if canonical_club:    filter_parts.append(canonical_club)
    filter_suffix = " — " + " / ".join(filter_parts) if filter_parts else ""

    return {
        "type":  "table",
        "data":  data,
        "title": f"{date_display}\n⚽ Results{filter_suffix} ({len(matched)} matches)",
    }


def tool_all_results(query: str = "", round_filter: int = None, limit: int = 60) -> Any:
    """
    Show all completed results (across all dates) filtered by league, age group, club, or round.
    Results sorted most recent first.
    """
    q_lower = query.lower().strip() if query else ""

    # Parse filters
    age_group_filter  = extract_age_group(q_lower) if q_lower else None
    canonical_club    = get_canonical_club_name(q_lower) if q_lower else None
    query_league_code = None
    if q_lower:
        for possible_league in ['ypl1', 'ypl2', 'ysl nw', 'ysl se', 'vpl men', 'vpl women', 'ypl 1', 'ypl 2']:
            if possible_league in q_lower:
                query_league_code = extract_league_from_league_name(possible_league)
                break

    # Extract round from query if not passed directly
    if round_filter is None and q_lower:
        rm = re.search(r'\bround\s*(\d+)\b', q_lower)
        if rm:
            round_filter = int(rm.group(1))

    # Club token for flexible matching
    club_token = None
    for alias in CLUB_ALIASES:
        if alias in q_lower:
            club_token = alias
            break

    matched = []
    seen_ids = set()

    for r in results:
        attrs = r.get("attributes", {})
        mid = attrs.get("match_hash_id")
        if mid and mid in seen_ids:
            continue
        if mid:
            seen_ids.add(mid)

        status = (attrs.get("status") or "").lower()
        if status != "complete":
            continue

        home_score = attrs.get("home_score")
        away_score = attrs.get("away_score")
        if home_score is None or away_score is None:
            continue

        # Skip byes
        if not attrs.get("home_team_hash_id") or not attrs.get("away_team_hash_id"):
            continue

        home   = attrs.get("home_team_name", "") or ""
        away   = attrs.get("away_team_name", "") or ""
        league = attrs.get("league_name", "") or ""
        match_league_code = extract_league_from_league_name(league)
        search_blob = f"{home} {away} {league}".lower()

        # Apply filters
        if query_league_code and match_league_code.lower() != query_league_code.lower():
            continue
        if age_group_filter and age_group_filter.lower() not in search_blob:
            continue
        if club_token and club_token not in search_blob:
            continue
        if q_lower and not age_group_filter and not club_token and not query_league_code and not round_filter:
            if q_lower not in search_blob:
                continue

        # Round filter
        if round_filter is not None:
            match_round_str = str(attrs.get("round", "") or attrs.get("full_round", "") or "")
            rn = re.search(r'(\d+)', match_round_str)
            if not rn or int(rn.group(1)) != round_filter:
                continue

        date_str = attrs.get("date", "")
        match_dt = parse_date_utc_to_aest(date_str)
        date_display = iso_date_aest(date_str) if date_str else ""
        match_round = attrs.get("full_round") or attrs.get("round") or ""

        matched.append({
            "sort_key": date_str,
            "Date":     date_display,
            "League":   match_league_code,
            "Round":    match_round,
            "Home":     home,
            "Score":    f"{home_score}-{away_score}",
            "Away":     away,
        })

    if not matched:
        filter_text = f" for '{query}'" if query else ""
        return {"type": "error", "message": f"❌ No completed results found{filter_text}"}

    matched.sort(key=lambda x: x["sort_key"], reverse=True)
    matched = matched[:limit]

    # Strip internal sort key before sending to table
    data = [{k: v for k, v in row.items() if k != "sort_key"} for row in matched]

    filter_parts = []
    if round_filter:          filter_parts.append(f"Round {round_filter}")
    if query_league_code:     filter_parts.append(query_league_code)
    if age_group_filter:      filter_parts.append(age_group_filter)
    if canonical_club:        filter_parts.append(canonical_club)
    elif club_token:          filter_parts.append(club_token.title())
    filter_suffix = " — " + " / ".join(filter_parts) if filter_parts else ""

    return {
        "type":  "table",
        "data":  data,
        "title": f"⚽ Results{filter_suffix} ({len(data)} matches)",
    }



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

def _card_minutes(m: dict, card_type: str) -> str:
    """Return formatted minutes string like '45', 78'' for cards in a match."""
    events = m.get("events", [])
    mins = [
        str(e.get("minute"))
        for e in events
        if (e.get("type") or e.get("event_type") or "").lower() == card_type
        and e.get("minute") is not None
    ]
    return ", ".join(f"{x}'" for x in mins) if mins else ""


def _card_date_range(date_mode: str):
    """Return (start_date, end_date, label) or (None, None, '')."""
    if not date_mode:
        return None, None, ""
    match_day = get_match_day_date()
    if date_mode == "last_week":
        day = match_day - timedelta(days=7)
        return day, day, f" — Last Week ({day.strftime('%d %b')})"
    return match_day, match_day, f" — This Week ({match_day.strftime('%d %b')})"


def _match_in_date_range(m: dict, start_date, end_date) -> bool:
    raw = m.get("date", "")
    if not raw:
        return False
    try:
        mdate = datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
        return start_date <= mdate <= end_date
    except Exception:
        return False


def _build_card_source(card_type: str, query: str, include_non_players: bool,
                       staff_only: bool = False):
    """Return filtered + sorted list of people with the given card type.

    staff_only=True  → ONLY coaches/staff (e.g. "red card staff")
    include_non_players=True, staff_only=False → players + staff combined
    include_non_players=False → players only (default)
    """
    stat_key = "yellow_cards" if card_type == "yellow" else "red_cards"

    # Build candidate pool
    if staff_only:
        candidates = list(staff_summary)
    elif include_non_players:
        candidates = list(players_summary) + list(staff_summary)
    else:
        candidates = list(players_summary)

    # Always apply role filter so the pool is clean before card check
    if staff_only:
        candidates = [p for p in candidates
                      if p.get("role") and str(p.get("role", "")).lower() != "player"]
    elif not include_non_players:
        candidates = [p for p in candidates
                      if not p.get("role") or str(p.get("role", "")).lower() == "player"]

    with_cards = [p for p in candidates if p.get("stats", {}).get(stat_key, 0) > 0]

    if query:
        with_cards = filter_players_by_criteria(
            with_cards, query, include_non_players=(include_non_players or staff_only)
        )

    with_cards.sort(key=lambda x: x.get("stats", {}).get(stat_key, 0), reverse=True)
    return with_cards


def tool_yellow_cards(query: str = "", show_details: bool = False,
                      include_non_players: bool = False,
                      staff_only: bool = False,
                      date_mode: str = "") -> Any:
    """List people with yellow cards. Supports club/age/date filtering and non-players."""
    stat_key = "yellow_cards"

    age_group = extract_age_group(query) if query else None
    base_club = extract_base_club_name(query) if query else None
    team_name = extract_team_name(query) if query else None

    start_date, end_date, date_label = _card_date_range(date_mode)
    people_list = _build_card_source("yellow", query, include_non_players, staff_only=staff_only)

    # If date filter, keep only people who got a yellow IN that window
    if start_date:
        def _had_yellow(p):
            for m in p.get("matches", []):
                if not _match_in_date_range(m, start_date, end_date):
                    continue
                events = m.get("events", [])
                yc = m.get("yellow_cards",
                    sum(1 for e in events
                        if (e.get("type") or e.get("event_type","")).lower() == "yellow_card"))
                if yc > 0:
                    return True
            return False
        people_list = [p for p in people_list if _had_yellow(p)]

    if not people_list:
        who = "staff/coaches" if staff_only else ("non-players" if include_non_players else "players")
        return (f"❌ No {who} with yellow cards found"
                + (f" matching '{query}'" if query else "") + date_label)

    filter_parts = []
    if staff_only:             filter_parts.append("Staff/Coaches")
    elif include_non_players:  filter_parts.append("All (Players + Staff)")
    if age_group and not team_name:   filter_parts.append(age_group)
    elif base_club and not team_name: filter_parts.append(base_club)
    elif team_name:                   filter_parts.append(team_name)
    filter_desc = (" — " + " / ".join(filter_parts)) if filter_parts else ""
    title = f"🟨 Yellow Cards{filter_desc}{date_label} ({len(people_list)} total)"

    if show_details:
        lines = [f"**{title}**\n"]
        for p in people_list[:50]:
            stats  = p.get("stats", {})
            role   = p.get("role") or (p.get("roles") or [""])[0] or "player"
            role_d = f" ({role.title()})" if role.lower() not in ("player","") else ""
            team   = (p.get("teams") or [p.get("team_name","")])[0]
            lines.append(
                f"👤 **{p.get('first_name')} {p.get('last_name')}**{role_d} — {team}"
                f" | 🟨 {stats.get(stat_key, 0)}"
            )
            for m in p.get("matches", []):
                if start_date and not _match_in_date_range(m, start_date, end_date):
                    continue
                events = m.get("events", [])
                yc = m.get("yellow_cards",
                    sum(1 for e in events
                        if (e.get("type") or e.get("event_type","")).lower() == "yellow_card"))
                if yc > 0:
                    venue = "🏠" if m.get("home_or_away") == "home" else "✈️"
                    mins  = _card_minutes(m, "yellow_card")
                    lines.append(
                        f"   {venue} vs {m.get('opponent_team_name','?')} "
                        f"— {format_date(m.get('date',''))} "
                        f"— 🟨 {yc}" + (f" ({mins})" if mins else "")
                    )
            lines.append("")
        return "\n".join(lines)

    # Table output — always includes This Week, Last Week, Total columns
    data = []

    # Pre-compute date ranges for the two weekly windows
    this_week_day = get_match_day_date()
    last_week_day = this_week_day - timedelta(days=7)

    for i, p in enumerate(people_list[:50], 1):
        stats = p.get("stats", {})
        role  = p.get("role") or (p.get("roles") or [""])[0] or "player"
        name  = f"{p.get('first_name')} {p.get('last_name')}"
        if role.lower() not in ("player",""):
            name += f" ({role.title()})"
        team = (p.get("teams") or [p.get("team_name","")])[0]

        # Count cards per window
        this_week_count = 0
        last_week_count = 0
        all_mins = []

        for m in p.get("matches", []):
            events = m.get("events", [])
            yc = m.get("yellow_cards",
                sum(1 for e in events
                    if (e.get("type") or e.get("event_type","")).lower() == "yellow_card"))

            if _match_in_date_range(m, this_week_day, this_week_day):
                this_week_count += yc
            if _match_in_date_range(m, last_week_day, last_week_day):
                last_week_count += yc

            # Collect minutes for date-filtered or unfiltered display
            if start_date:
                if _match_in_date_range(m, start_date, end_date):
                    mins = _card_minutes(m, "yellow_card")
                    if mins:
                        all_mins.append(mins)
            else:
                mins = _card_minutes(m, "yellow_card")
                if mins:
                    all_mins.append(mins)

        total_count = stats.get(stat_key, 0)

        row = {
            "#":         i,
            "Name":      name,
            "Team":      team,
            "This Week": this_week_count,
            "Last Week": last_week_count,
            "Total 🟨":  total_count,
            "Min":       ", ".join(all_mins) if all_mins else "—",
        }
        if role.lower() in ("player",""):
            row["M"]  = stats.get("matches_played", 0)
            row["⚽"] = stats.get("goals", 0)
        data.append(row)

    return {"type": "table", "data": data, "title": title}


def tool_red_cards(query: str = "", show_details: bool = False,
                   include_non_players: bool = False,
                   staff_only: bool = False,
                   date_mode: str = "") -> Any:
    """List people with red cards. Supports club/age/date filtering and non-players."""
    stat_key = "red_cards"

    age_group = extract_age_group(query) if query else None
    base_club = extract_base_club_name(query) if query else None
    team_name = extract_team_name(query) if query else None

    start_date, end_date, date_label = _card_date_range(date_mode)
    people_list = _build_card_source("red", query, include_non_players, staff_only=staff_only)

    if start_date:
        def _had_red(p):
            for m in p.get("matches", []):
                if not _match_in_date_range(m, start_date, end_date):
                    continue
                events = m.get("events", [])
                rc = m.get("red_cards",
                    sum(1 for e in events
                        if (e.get("type") or e.get("event_type","")).lower() == "red_card"))
                if rc > 0:
                    return True
            return False
        people_list = [p for p in people_list if _had_red(p)]

    if not people_list:
        who = "staff/coaches" if staff_only else ("non-players" if include_non_players else "players")
        return (f"❌ No {who} with red cards found"
                + (f" matching '{query}'" if query else "") + date_label)

    filter_parts = []
    if staff_only:             filter_parts.append("Staff/Coaches")
    elif include_non_players:  filter_parts.append("All (Players + Staff)")
    if age_group and not team_name:   filter_parts.append(age_group)
    elif base_club and not team_name: filter_parts.append(base_club)
    elif team_name:                   filter_parts.append(team_name)
    filter_desc = (" — " + " / ".join(filter_parts)) if filter_parts else ""
    title = f"🟥 Red Cards{filter_desc}{date_label} ({len(people_list)} total)"

    if show_details:
        lines = [f"**{title}**\n"]
        for p in people_list:
            stats  = p.get("stats", {})
            role   = p.get("role") or (p.get("roles") or [""])[0] or "player"
            role_d = f" ({role.title()})" if role.lower() not in ("player","") else ""
            team   = (p.get("teams") or [p.get("team_name","")])[0]
            lines.append(
                f"👤 **{p.get('first_name')} {p.get('last_name')}**{role_d} — {team}"
                f" | 🟥 {stats.get(stat_key, 0)}"
            )
            for m in p.get("matches", []):
                if start_date and not _match_in_date_range(m, start_date, end_date):
                    continue
                events = m.get("events", [])
                rc = m.get("red_cards",
                    sum(1 for e in events
                        if (e.get("type") or e.get("event_type","")).lower() == "red_card"))
                if rc > 0:
                    venue = "🏠" if m.get("home_or_away") == "home" else "✈️"
                    mins  = _card_minutes(m, "red_card")
                    lines.append(
                        f"   {venue} vs {m.get('opponent_team_name','?')} "
                        f"— {format_date(m.get('date',''))} "
                        f"— 🟥 RED CARD" + (f" ({mins})" if mins else "")
                    )
            lines.append("")
        return "\n".join(lines)

    data = []

    # Pre-compute date ranges for the two weekly windows
    this_week_day = get_match_day_date()
    last_week_day = this_week_day - timedelta(days=7)

    for i, p in enumerate(people_list, 1):
        stats = p.get("stats", {})
        role  = p.get("role") or (p.get("roles") or [""])[0] or "player"
        name  = f"{p.get('first_name')} {p.get('last_name')}"
        if role.lower() not in ("player",""):
            name += f" ({role.title()})"
        team = (p.get("teams") or [p.get("team_name","")])[0]

        this_week_count = 0
        last_week_count = 0
        all_mins = []

        for m in p.get("matches", []):
            events = m.get("events", [])
            rc = m.get("red_cards",
                sum(1 for e in events
                    if (e.get("type") or e.get("event_type","")).lower() == "red_card"))

            if _match_in_date_range(m, this_week_day, this_week_day):
                this_week_count += rc
            if _match_in_date_range(m, last_week_day, last_week_day):
                last_week_count += rc

            if start_date:
                if _match_in_date_range(m, start_date, end_date):
                    mins = _card_minutes(m, "red_card")
                    if mins:
                        all_mins.append(mins)
            else:
                mins = _card_minutes(m, "red_card")
                if mins:
                    all_mins.append(mins)

        total_count = stats.get(stat_key, 0)

        row = {
            "#":         i,
            "Name":      name,
            "Team":      team,
            "This Week": this_week_count,
            "Last Week": last_week_count,
            "Total 🟥":  total_count,
            "Min":       ", ".join(all_mins) if all_mins else "—",
        }
        if role.lower() in ("player",""):
            row["M"]  = stats.get("matches_played", 0)
            row["⚽"] = stats.get("goals", 0)
        data.append(row)

    return {"type": "table", "data": data, "title": title}

def tool_top_scorers(query: str = "", limit: int = 50):
    """List top goal scorers across all leagues/divisions, with optional filtering."""
    scorers = [
        p for p in players_summary
        if p.get("stats", {}).get("goals", 0) > 0
        and (not p.get("role") or p.get("role") == "player")
    ]

    # Apply team/club/age-group filter only if a specific query was given
    if query:
        scorers = filter_players_by_criteria(scorers, query, include_non_players=False)

    if not scorers:
        filter_desc = f" matching '{query}'" if query else ""
        return {"type": "error", "message": f"❌ No goal scorers found{filter_desc}"}

    # Sort by goals descending
    scorers.sort(key=lambda x: x.get("stats", {}).get("goals", 0), reverse=True)

    # Build filter description
    age_group = extract_age_group(query) if query else None
    team_name = extract_team_name(query) if query else None
    base_club = extract_base_club_name(query) if query else None
    filter_parts = []
    if team_name:
        filter_parts.append(team_name)
    elif base_club and age_group:
        filter_parts.append(f"{base_club} {age_group}")
    elif base_club:
        filter_parts.append(base_club)
    elif age_group:
        filter_parts.append(age_group)
    filter_desc = " — " + " ".join(filter_parts) if filter_parts else ""

    data = []
    for i, p in enumerate(scorers[:limit], 1):
        stats   = p.get("stats", {})
        goals   = stats.get("goals", 0)
        yellows = stats.get("yellow_cards", 0)
        reds    = stats.get("red_cards", 0)
        name    = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()

        # Recalculate matches from match-level data (available or started = counts)
        all_matches   = p.get("matches", [])
        played_matches = [m for m in all_matches
                          if m.get("available", False) or m.get("started", False)]
        matches_played = len(played_matches)

        # Team: prefer first entry in teams array
        teams  = p.get("teams", []) or ([p.get("team_name")] if p.get("team_name") else [])
        team   = teams[0] if teams else ""

        # League: extract short code from player's leagues list
        leagues     = p.get("leagues", []) or ([p.get("league_name")] if p.get("league_name") else [])
        league_code = extract_league_from_league_name(leagues[0]) if leagues else "—"

        # Age group from team name
        ag_m    = re.search(r'U\d{2}', team, re.IGNORECASE)
        age_grp = ag_m.group(0).upper() if ag_m else "—"

        # Base club name (strip age group suffix)
        club = re.sub(r'\s+U\d{2}$', '', team, flags=re.IGNORECASE).strip() or team

        data.append({
            "#":       i,
            "Player":  name,
            "Club":    club,
            "Div":     age_grp,
            "League":  league_code,
            "M":       matches_played,
            "⚽":      goals,
            "G/M":     round(goals / matches_played, 2) if matches_played > 0 else 0,
            "🟨":      yellows,
            "🟥":      reds,
        })

    return {
        "type":  "table",
        "data":  data,
        "title": f"⚽ Top Scorers{filter_desc} — {len(scorers)} players with goals, showing top {min(limit, len(scorers))}"
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
    team_name_to_match = _person_teams(players[0])[0] if _person_teams(players[0]) else team_filter
    for r in results:
        a = r.get("attributes", {})
        home = a.get("home_team_name", "")
        away = a.get("away_team_name", "")
        if team_name_to_match.lower() in home.lower() or team_name_to_match.lower() in away.lower():
            team_results.append(a)

    team_results.sort(key=lambda x: x.get("date", ""), reverse=True)

    results_table = []
    for a in team_results[:8]:
        hs = a.get("home_score")
        as_ = a.get("away_score")
        home_team = a.get("home_team_name") or ""
        away_team = a.get("away_team_name") or ""
        is_home = team_name_to_match.lower() in home_team.lower()
        opponent = _strip_age_group(away_team) if is_home else _strip_age_group(home_team)
        ha = "🏠" if is_home else "✈️"
        try:
            our = int(hs) if is_home else int(as_)
            opp = int(as_) if is_home else int(hs)
            icon = "🟢" if our > opp else ("🔴" if our < opp else "🟡")
            score = f"{our}-{opp}"
            result_str = f"{icon} {'W' if our > opp else ('L' if our < opp else 'D')}"
        except (TypeError, ValueError):
            score = "—"
            result_str = "—"
        results_table.append({
            "Date":     format_date_aest(a.get("date", "")),
            "H/A":      ha,
            "Opponent": opponent,
            "Score":    score,
            "Result":   result_str,
        })

    return {
        "type":    "team_stats",
        "summary": "\n".join(lines),
        "results": results_table,
        "team":    display_team,
    }


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
                    date_str = format_date_aest(m.get('date', ''))
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

            # Recalculate played/started/bench from match-level flags:
            # A match only counts if available=True OR started=True
            def _counts_as_played(m):
                return m.get("available", False) or m.get("started", False)

            played_matches = [m for m in matches if _counts_as_played(m)]
            recalc_played  = len(played_matches)
            recalc_started = sum(1 for m in played_matches if m.get("started", False))
            recalc_bench   = sum(1 for m in played_matches
                                 if m.get("available", False) and not m.get("started", False))

            # ── Registration row per club ──────────────────────────────
            reg_rows = []
            for i, t in enumerate(all_teams):
                jersey = jerseys_map.get(t) or p.get("jersey", "—")
                league = all_leagues[i] if i < len(all_leagues) else p.get("league_name", "")

                if has_team_in_matches:
                    tm  = [m for m in matches if m.get("team_name") == t]
                    # Only count matches where player was actually available/started
                    tm_played = [m for m in tm if _counts_as_played(m)]
                    mp  = len(tm_played)
                    g   = sum(m.get("goals", 0) for m in tm_played)
                    yc  = sum(m.get("yellow_cards", 0) for m in tm_played)
                    rc  = sum(m.get("red_cards", 0) for m in tm_played)
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
            # Only show matches where the player was actually available or started
            sorted_matches = sorted(
                [m for m in matches if m.get("available", False) or m.get("started", False)],
                key=lambda m: m.get("date", ""),
                reverse=True
            )
            # Always show all recent matches (most recent first); no arbitrary top-5 limit
            display_matches = sorted_matches
            match_rows = []
            for m in display_matches:
                events  = m.get("events", [])
                def _etype(e): return (e.get("type") or e.get("event_type") or "").lower()
                goals   = m.get("goals",       sum(1 for e in events if _etype(e) == "goal"))
                yellows = m.get("yellow_cards", sum(1 for e in events if _etype(e) == "yellow_card"))
                reds    = m.get("red_cards",    sum(1 for e in events if _etype(e) == "red_card"))

                # Build started/role indicator: ✅ started, 🪑 bench, + captain © and goalie 🧤
                started_icon = "✅" if m.get("started") else "🪑"
                if m.get("captain"):
                    started_icon += " ©"
                if m.get("goalie"):
                    started_icon += " 🧤"

                row = {
                    "Date":     iso_date_aest(m.get("date", "")),
                    "H/A":      "🏠" if m.get("home_or_away") == "home" else "✈️",
                    "Opponent": m.get("opponent_team_name", "—"),
                    "Started":  started_icon,
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
                    "Played":   recalc_played,
                    "Started":  recalc_started,
                    "Bench":    recalc_bench,
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

def _build_ladder_table(results_list, competition_code_lower, age_group_lower=None):
    """
    Build a ladder dict for a given competition code and optional age group filter.
    Returns sorted list of row dicts, or empty list if no data.
    """
    table = defaultdict(lambda: {"P": 0, "W": 0, "D": 0, "L": 0, "GF": 0, "GA": 0, "PTS": 0})
    for r in results_list:
        a = r.get("attributes", {})
        league_name = (a.get("league_name") or "").lower()
        comp_name   = (a.get("competition_name") or "").lower()
        if competition_code_lower not in league_name and competition_code_lower not in comp_name:
            continue
        if age_group_lower and age_group_lower not in league_name and age_group_lower not in comp_name:
            continue
        home = a.get("home_team_name") or ""
        away = a.get("away_team_name") or ""
        try:
            hs = int(a.get("home_score", 0))
            as_ = int(a.get("away_score", 0))
        except (ValueError, TypeError):
            continue
        for t in (home, away):
            table[t]  # ensure key exists
        table[home]["P"] += 1; table[away]["P"] += 1
        table[home]["GF"] += hs; table[home]["GA"] += as_
        table[away]["GF"] += as_; table[away]["GA"] += hs
        if hs > as_:
            table[home]["W"] += 1; table[away]["L"] += 1; table[home]["PTS"] += 3
        elif hs < as_:
            table[away]["W"] += 1; table[home]["L"] += 1; table[away]["PTS"] += 3
        else:
            table[home]["D"] += 1; table[away]["D"] += 1
            table[home]["PTS"] += 1; table[away]["PTS"] += 1
    if not table:
        return []
    ladder = sorted(table.items(),
                    key=lambda kv: (kv[1]["PTS"], kv[1]["GF"] - kv[1]["GA"], kv[1]["GF"]),
                    reverse=True)
    return [{"Pos": pos, "Team": team, "P": r["P"], "W": r["W"], "D": r["D"],
             "L": r["L"], "GF": r["GF"], "GA": r["GA"], "GD": r["GF"] - r["GA"], "PTS": r["PTS"]}
            for pos, (team, r) in enumerate(ladder, 1)]


def tool_ladder(query: str) -> str:
    q = query.lower()

    # Step 1: Extract competition code from query
    competition_to_use = extract_league_from_league_name(q)

    # Step 2: Fuzzy fallback if not found directly
    if not competition_to_use or competition_to_use == "Other":
        league_match = fuzzy_find(q, [l.lower() for l in league_names], threshold=60)
        comp_match   = fuzzy_find(q, [c.lower() for c in competition_names], threshold=60)
        if league_match:
            competition_to_use = extract_league_from_league_name(league_match)
        elif comp_match:
            competition_to_use = extract_league_from_league_name(comp_match)

    if not competition_to_use or competition_to_use == "Other":
        return f"❌ No ladder found for: {query}\n\nTry: 'YPL1 ladder', 'YPL2 ladder', 'YSL NW ladder'"

    age_group       = extract_age_group(query)
    age_group_lower = age_group.lower() if age_group else None
    comp_lower      = competition_to_use.lower()

    # ── If a specific age group was requested → single table (original behaviour) ──
    if age_group_lower:
        data = _build_ladder_table(results, comp_lower, age_group_lower)
        if not data:
            return f"❌ No ladder for {competition_to_use.upper()} {age_group} — no completed matches found."
        return {
            "type":  "table",
            "data":  data,
            "title": f"📊 {competition_to_use.upper()} {age_group} Ladder ({len(data)} teams)"
        }

    # ── No age group → discover every age group in this competition and return all ──
    age_groups_found = set()
    for r in results:
        a = r.get("attributes", {})
        ln = (a.get("league_name") or "").lower()
        cn = (a.get("competition_name") or "").lower()
        if comp_lower not in ln and comp_lower not in cn:
            continue
        # Extract U-code from the league name
        ag_m = re.search(r'\bu(\d{2})\b', ln or cn)
        if ag_m:
            age_groups_found.add(f"u{ag_m.group(1)}")

    if not age_groups_found:
        # No age groups found — fall back to single combined table
        data = _build_ladder_table(results, comp_lower)
        if not data:
            return f"❌ No ladder for {competition_to_use.upper()} — no completed matches found."
        return {
            "type":  "table",
            "data":  data,
            "title": f"📊 {competition_to_use.upper()} Ladder ({len(data)} teams)"
        }

    # Build one table per age group, sorted by age group number
    sorted_age_groups = sorted(age_groups_found, key=lambda x: int(x[1:]))
    tables = []
    for ag in sorted_age_groups:
        data = _build_ladder_table(results, comp_lower, ag)
        if data:
            tables.append({
                "title": f"{ag.upper()} — {competition_to_use.upper()}",
                "data":  data,
            })

    if not tables:
        return f"❌ No completed matches found for {competition_to_use.upper()}."

    return {
        "type":   "multi_table",
        "title":  f"📊 {competition_to_use.upper()} — All Age Groups ({len(tables)} divisions)",
        "tables": tables,
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
        date_str = iso_date(m.get('date', ''))
        
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

def _strip_age_group(team_name: str) -> str:
    """Strip age group suffix to get base club name. E.g. 'Heidelberg United FC U16' -> 'Heidelberg United FC'"""
    return re.sub(r'\s+U\d{2}$', '', (team_name or ""), flags=re.IGNORECASE).strip()


def tool_dual_registration(query: str = "", different_clubs_only: bool = False) -> Any:
    """
    Find players registered in multiple teams (dual registration).
    Supports filtering by club name, age group, league, or cross-club only.

    Args:
        query:               Optional filter string (club name, age group, league code)
        different_clubs_only: If True, only return players registered at 2+ DIFFERENT clubs
                              (excludes players who are just playing up/down an age group
                               at the same club)

    Query examples:
      "dual registration"
      "different clubs"
      "cross club players"
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

        # --- different_clubs_only filter ---
        # Strip age group from each team to get base club names, then check uniqueness
        if different_clubs_only:
            base_clubs = {_strip_age_group(t) for t in teams if t}
            if len(base_clubs) < 2:
                # All teams belong to the same club — skip
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
        mode_text = " at different clubs" if different_clubs_only else ""
        return f"❌ No players found registered in multiple teams{mode_text}{filter_text}"

    # Sort by name
    dual_players.sort(key=lambda p: f"{p.get('first_name','')} {p.get('last_name','')}")

    data = []
    for i, p in enumerate(dual_players, 1):
        name    = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
        teams   = p.get("teams", [])
        leagues = p.get("leagues", [])

        # Count played matches per team + find first/last date per team
        team_match_count: dict = {}
        team_first_date:  dict = {}
        team_last_date:   dict = {}
        for m in p.get("matches", []):
            if not (m.get("available", False) or m.get("started", False)):
                continue
            tn    = m.get("team_name", "")
            mdate = m.get("date", "")
            if not tn or not mdate:
                continue
            team_match_count[tn] = team_match_count.get(tn, 0) + 1
            if mdate < team_first_date.get(tn, "9999"):
                team_first_date[tn] = mdate
            if mdate > team_last_date.get(tn, ""):
                team_last_date[tn] = mdate

        # Sort all teams by most recent match date (most recent first = To Club)
        sorted_teams = sorted(teams, key=lambda t: team_last_date.get(t, ""), reverse=True)

        # Build per-team metadata
        all_base_clubs = [_strip_age_group(t) for t in sorted_teams]
        all_age_groups = [
            re.search(r'U\d{2}', t, re.IGNORECASE).group(0).upper()
            if re.search(r'U\d{2}', t, re.IGNORECASE) else "—"
            for t in sorted_teams
        ]
        short_leagues = [extract_league_from_league_name(lg) for lg in leagues] if leagues else []
        stats         = p.get("stats", {})

        # Distinct base clubs (most recent first → To Club, second → From Club)
        seen_clubs: list = []
        for bc in all_base_clubs:
            if bc and bc not in seen_clubs:
                seen_clubs.append(bc)

        to_club   = seen_clubs[0] if len(seen_clubs) > 0 else "—"
        from_club = seen_clubs[1] if len(seen_clubs) > 1 else "—"

        # Match counts per club (sum across all teams at that club)
        def _club_match_count(club_name):
            return sum(cnt for tn, cnt in team_match_count.items()
                       if _strip_age_group(tn).lower() == club_name.lower())

        to_m   = _club_match_count(to_club)
        from_m = _club_match_count(from_club)

        # First ISO date the player appeared for the To Club (for sortable DateColumn)
        to_club_teams  = [t for t in sorted_teams if _strip_age_group(t).lower() == to_club.lower()]
        first_to_dates = [team_first_date[t] for t in to_club_teams if t in team_first_date]
        first_to_iso   = iso_date_aest(min(first_to_dates)) if first_to_dates else ""

        # Unique age groups
        unique_age_groups = []
        for ag in all_age_groups:
            if ag not in unique_age_groups:
                unique_age_groups.append(ag)

        # Cross-club or same-club
        unique_base_clubs_set = {c for c in all_base_clubs if c}
        is_cross_club = len(unique_base_clubs_set) > 1
        reg_type      = "⚡ Cross-Club" if is_cross_club else "🔁 Same Club"

        row = {
            "#":           i,
            "Player":      name,
            "Type":        reg_type,
            "From Club":   from_club,
            "From M":      from_m,
            "To Club":     to_club,
            "To M":        to_m,
            "First @ To":  first_to_iso,
            "Age Groups":  " / ".join(unique_age_groups),
            "Leagues":     " / ".join(short_leagues) if short_leagues else "—",
            "Goals":       stats.get("goals", 0),
            "🟨":          stats.get("yellow_cards", 0),
            "🟥":          stats.get("red_cards", 0),
        }
        if len(seen_clubs) > 2:
            row["Club 3"] = seen_clubs[2]
        data.append(row)

    cross_count   = sum(1 for row in data if row["Type"] == "⚡ Cross-Club")
    same_count    = len(data) - cross_count
    mode_label    = "⚡ Cross-Club" if different_clubs_only else "🔄 Dual / Multi-Team"
    filter_suffix = f" — {query.title()}" if query else ""
    breakdown     = f"  ·  {cross_count} cross-club, {same_count} same-club" if not different_clubs_only else ""
    return {
        "type":  "table",
        "data":  data,
        "title": f"{mode_label} Registrations{filter_suffix} ({len(dual_players)} players{breakdown})"
    }


def tool_dual_player_detail(player_name: str) -> Any:
    """
    For a dual-registered player, show matches played broken down by team/club.
    Returns a multi_table result — one tab per team.
    Query examples: 'dual matches for John Smith', 'show matches John Smith both teams'
    """
    q = player_name.lower().strip()

    # Find the player
    matched = []
    for p in players_summary:
        full = f"{p.get('first_name','')} {p.get('last_name','')}".lower()
        if q in full or full in q:
            matched.append(p)

    if not matched:
        return {"type": "error", "message": f"❌ No player found matching '{player_name}'"}

    p = matched[0]
    name = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
    teams = p.get("teams", [])

    if len(teams) < 2:
        return {"type": "error", "message": f"ℹ️ {name} is only registered with one team."}

    # Group matches by team_name
    matches_by_team: dict = {}
    for m in p.get("matches", []):
        tn = m.get("team_name", "Unknown")
        if tn not in matches_by_team:
            matches_by_team[tn] = []
        matches_by_team[tn].append(m)

    # Sort teams: most recent match first
    def _latest(tn):
        ms = matches_by_team.get(tn, [])
        return max((m.get("date","") for m in ms), default="")

    sorted_teams = sorted(matches_by_team.keys(), key=_latest, reverse=True)

    tables = []
    for team in sorted_teams:
        team_matches = sorted(matches_by_team[team],
                              key=lambda m: m.get("date",""), reverse=True)
        # Only count matches where player was available/started
        played = [m for m in team_matches
                  if m.get("available", False) or m.get("started", False)]
        rows = []
        for m in played:
            events = m.get("events", [])
            goals = sum(1 for e in events
                        if (e.get("type") or e.get("event_type","")).lower() in ("goal","goal_scored"))
            goals = goals or m.get("goals", 0)
            yellows = m.get("yellow_cards", sum(1 for e in events
                        if (e.get("type") or e.get("event_type","")).lower() == "yellow_card"))
            reds = m.get("red_cards", sum(1 for e in events
                        if (e.get("type") or e.get("event_type","")).lower() == "red_card"))
            started_icon = "✅" if m.get("started") else "🪑"
            if m.get("captain"):   started_icon += " ©"
            if m.get("goalie"):    started_icon += " 🧤"
            rows.append({
                "Date":     iso_date_aest(m.get("date","")),
                "H/A":      "🏠" if m.get("home_or_away") == "home" else "✈️",
                "Opponent": _strip_age_group(m.get("opponent_team_name","") or ""),
                "Started":  started_icon,
                "⚽":       goals if goals else "",
                "🟨":       yellows if yellows else "",
                "🟥":       reds if reds else "",
            })

        ag_m = re.search(r'U\d{2}', team, re.IGNORECASE)
        ag   = ag_m.group(0).upper() if ag_m else ""
        club = _strip_age_group(team)
        tab_label = f"{club} {ag}".strip() if ag else club
        tables.append({
            "title": f"{tab_label} ({len(played)} matches)",
            "data":  rows,
        })

    return {
        "type":   "multi_table",
        "title":  f"🔄 {name} — Matches by Team",
        "tables": tables,
    }


def tool_club_vs_club(query: str) -> Any:
    """
    Compare two clubs' ladder positions across all shared age groups / competitions.
    Scans both fixtures and results to discover shared competitions.
    Query examples: 'altona vs heidelberg', 'heidelberg v brunswick'
    """
    vs_parts = re.split(r'\s+v(?:s|ersus)?\s+', query.lower())
    if len(vs_parts) < 2:
        return {"type": "error", "message": "\u274c Please use 'Club A vs Club B' format."}

    noise = r'\b(match|matches|games?|compare|head|to|h2h|record|ladder|position|ranking)\b'
    token_a = re.sub(noise, '', vs_parts[0].strip()).strip()
    token_b = re.sub(noise, '', vs_parts[1].strip()).strip()

    def _resolve(token):
        for alias in sorted(CLUB_ALIASES.keys(), key=len, reverse=True):
            if alias in token:
                return alias, CLUB_ALIASES[alias]
        return token, token

    alias_a, canon_a = _resolve(token_a)
    alias_b, canon_b = _resolve(token_b)
    short_a = canon_a.split()[0] if canon_a else alias_a.title()
    short_b = canon_b.split()[0] if canon_b else alias_b.title()

    # Discover shared (comp, age_group) by scanning BOTH fixtures AND results
    comp_ag_clubs: dict = {}
    for r in list(fixtures) + list(results):
        a = r.get("attributes", {})
        league = (a.get("league_name") or "").strip()
        comp   = extract_league_from_league_name(league)
        if comp in ("Other", ""):
            continue
        home = (a.get("home_team_name") or "")
        away = (a.get("away_team_name") or "")
        for team_name in (home, away):
            ag_m = re.search(r'U\d{2}', team_name, re.IGNORECASE)
            ag   = ag_m.group(0).upper() if ag_m else None
            if not ag:
                continue
            key = (comp, ag)
            comp_ag_clubs.setdefault(key, set())
            comp_ag_clubs[key].add(_strip_age_group(team_name).lower())

    # Keep only combos where BOTH clubs appear (substring check)
    shared_keys = [
        key for key, clubs in comp_ag_clubs.items()
        if any(alias_a in club for club in clubs)
        and any(alias_b in club for club in clubs)
    ]

    if not shared_keys:
        return {"type": "error",
                "message": f"\u274c No shared competitions found between **{short_a}** and **{short_b}**. They may be in different leagues."}

    rows = []
    for (comp, ag) in sorted(shared_keys,
                              key=lambda k: (k[0], int(k[1][1:]) if k[1][1:].isdigit() else 999)):
        ladder = _build_ladder_table(results, comp.lower(), ag.lower())
        if not ladder:
            continue

        pos_a = pts_a = gd_a = None
        pos_b = pts_b = gd_b = None
        for entry in ladder:
            team_base = _strip_age_group(entry["Team"]).lower()
            if alias_a in team_base and pos_a is None:
                pos_a = entry["Pos"]
                pts_a = entry["PTS"]
                gd_a  = entry["GD"]
            if alias_b in team_base and pos_b is None:
                pos_b = entry["Pos"]
                pts_b = entry["PTS"]
                gd_b  = entry["GD"]

        if pos_a is None and pos_b is None:
            continue

        total_teams = len(ladder)

        if pos_a is not None and pos_b is not None:
            if pos_a < pos_b:
                edge = f"\u2191 {short_a} ahead by {pos_b - pos_a}"
            elif pos_b < pos_a:
                edge = f"\u2191 {short_b} ahead by {pos_a - pos_b}"
            else:
                edge = "= Level"
        elif pos_a is not None:
            edge = f"{short_b} no results yet"
        else:
            edge = f"{short_a} no results yet"

        rows.append({
            "Age":              ag,
            "League":           comp,
            f"{short_a} Pos":  f"{pos_a}/{total_teams}" if pos_a is not None else "\u2014",
            f"{short_a} Pts":  pts_a if pts_a is not None else "\u2014",
            f"{short_a} GD":   gd_a  if gd_a  is not None else "\u2014",
            f"{short_b} Pos":  f"{pos_b}/{total_teams}" if pos_b is not None else "\u2014",
            f"{short_b} Pts":  pts_b if pts_b is not None else "\u2014",
            f"{short_b} GD":   gd_b  if gd_b  is not None else "\u2014",
            "Gap":              edge,
        })

    if not rows:
        return {"type": "error",
                "message": f"\u274c Shared competitions found but no ladder data yet for {short_a} vs {short_b}"}

    return {
        "type":  "table",
        "data":  rows,
        "title": f"\u2694\ufe0f {short_a} vs {short_b} \u2014 Ladder Positions by Age Group ({len(rows)} divisions)",
    }

def tool_squad_list(query: str = "") -> Any:
    """
    Return a formatted player table for a team/club query.
    Each row includes: jersey, age group, matches, goals, cards,
    and a dual-registration indicator.

    Routes: "show me Heidelberg U16", "players for Brunswick U18",
            "list players Heidelberg", "squad heidelberg u16"
    """
    # Resolve the team/club from the query
    age_group_filter = extract_age_group(query) if query else None
    canonical_club   = get_canonical_club_name(query) if query else None

    # Build team filter string
    if canonical_club and age_group_filter:
        team_filter = f"{canonical_club} {age_group_filter}"
    elif canonical_club:
        team_filter = canonical_club
    else:
        team_filter = normalize_team(query) or query

    # Filter players
    def _matches_team(p):
        for t in _person_teams(p):
            if team_filter.lower() in (t or "").lower():
                return True
        return False

    players = [
        p for p in players_summary
        if _matches_team(p)
        and (not p.get("role") or str(p.get("role", "")).lower() == "player")
    ]

    if not players:
        return f"❌ No players found for: {query}"

    # Sort: by most goals desc, then name
    players.sort(key=lambda p: (
        -p.get("stats", {}).get("goals", 0),
        p.get("last_name", ""),
        p.get("first_name", ""),
    ))

    data = []
    for i, p in enumerate(players, 1):
        stats   = p.get("stats", {})
        teams   = p.get("teams", []) or ([p.get("team_name")] if p.get("team_name") else [])
        jerseys = p.get("jerseys", {})

        # Pick jersey for the matched team
        matched_team = next((t for t in teams if team_filter.lower() in (t or "").lower()), teams[0] if teams else "")
        jersey = jerseys.get(matched_team) or p.get("jersey", "—")

        # Age group from the matched team name
        ag_m = re.search(r'U\d{2}', matched_team, re.IGNORECASE)
        age_grp = ag_m.group(0).upper() if ag_m else ""

        # Dual-reg indicator — show badge + match count at other team
        dual_label = ""
        if len(teams) > 1:
            other_teams = [t for t in teams if t != matched_team]
            same_club, diff_club = [], []
            for ot in other_teams:
                ot_base = re.sub(r'\s+U\d{2}$', '', ot, flags=re.IGNORECASE).strip()
                mt_base = re.sub(r'\s+U\d{2}$', '', matched_team, flags=re.IGNORECASE).strip()
                ag_ot   = re.search(r'U\d{2}', ot, re.IGNORECASE)
                # Count matches played at this other team
                other_m = sum(
                    1 for m in p.get("matches", [])
                    if m.get("team_name") == ot
                    and (m.get("available", False) or m.get("started", False))
                )
                m_str = f"({other_m}M)" if other_m else ""
                if ot_base.lower() == mt_base.lower():
                    ag_str = ag_ot.group(0).upper() if ag_ot else ot
                    same_club.append(f"{ag_str} {m_str}".strip())
                else:
                    club_short = ot_base.split()[0]
                    diff_club.append(f"{club_short} {m_str}".strip())
            parts = []
            if same_club:
                parts.append("🔁 " + "/".join(same_club))
            if diff_club:
                parts.append("⚡ " + "/".join(diff_club))
            dual_label = " ".join(parts)

        data.append({
            "#":        i,
            "Player":   f"{p.get('first_name','')} {p.get('last_name','')}".strip(),
            "#Jersey":  f"#{jersey}" if jersey and jersey != "—" else "—",
            "Age":      age_grp,
            "M":        stats.get("matches_played", 0),
            "G":        stats.get("goals", 0),
            "🟨":       stats.get("yellow_cards", 0),
            "🟥":       stats.get("red_cards", 0),
            "Dual Reg": dual_label,
        })

    # Nice display title
    if canonical_club and age_group_filter:
        title_team = f"{canonical_club} {age_group_filter}"
    elif canonical_club:
        title_team = canonical_club
    else:
        title_team = team_filter.title()

    dual_count = sum(1 for row in data if row["Dual Reg"])
    subtitle   = f"  ({dual_count} dual-registered)" if dual_count else ""

    return {
        "type":  "table",
        "data":  data,
        "title": f"👥 Squad — {title_team}  ·  {len(players)} players{subtitle}"
    }



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

        # --- 1A. DUAL PLAYER MATCH DETAIL ---
        dual_detail_keywords = [
            'dual matches', 'matches both teams', 'matches each team',
            'matches for both', 'matches per team', 'matches per club',
            'breakdown', 'both clubs matches', 'each club matches',
        ]
        if any(kw in q for kw in dual_detail_keywords):
            clean = re.sub(
                r'\b(dual|matches?|both|each|teams?|clubs?|for|per|breakdown|show|me|detail)\b',
                '', q
            ).strip()
            return tool_dual_player_detail(clean)

        # --- 1B. DUAL REGISTRATION / MULTI-TEAM PLAYERS ---

        # Keywords that specifically mean DIFFERENT clubs (cross-club registrations)
        diff_club_keywords = [
            # Explicit "different" phrasing
            'different clubs', 'different club', 'cross club', 'cross-club',
            'two different clubs', '2 different clubs', 'another club',
            'other club', 'other clubs', 'outside club', 'second club',
            # "2 clubs / playing for 2 clubs" — user intent is always different clubs
            '2 clubs', 'two clubs', 'playing for 2', 'playing for two',
            '2 or more clubs', 'more than one club', 'more than 1 club',
            'multiple clubs', 'played for multiple', 'registered at 2',
            'registered at two', 'plays for two', 'plays for 2',
        ]
        is_diff_club_query = any(keyword in q for keyword in diff_club_keywords)

        # Broader set that also catches same-club age-group dual reg
        dual_keywords = diff_club_keywords + [
            'dual registration', 'dual reg', 'multi-team',
            '2 teams', 'two teams', 'multiple teams',
            'playing in 2', 'registered in 2',
            'two leagues', '2 leagues', 'both teams', 'in 2 age groups',
            '2 or more teams', 'more than one team', 'more than 1 team',
        ]

        if any(keyword in q for keyword in dual_keywords):
            filter_query = re.sub(
                r'\b(dual|registration|reg|playing|for|in|two|2|clubs?|teams?|multiple|multi|registered|both|leagues?|age|groups?|different|cross|another|other|outside|second|or|more|than|one|1)\b',
                '', q
            ).strip()
            return tool_dual_registration(filter_query, different_clubs_only=is_diff_club_query)

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
            'today results', 'todays results', 'results today',
            'results for today', "today's results", 'today s results',
        ]
        is_today_results = any(keyword in q for keyword in todays_results_keywords)

        # Broad results query (no "today" — show all completed results for the filter)
        is_broad_results = (
            not is_today_results and
            q.startswith('results') and len(q) > 7
        )

        if is_today_results:
            filter_query = re.sub(
                r'\b(today|todays|today\'s|results?|for|show|list|me|this|last|week)\b',
                '', q
            ).strip()
            round_m = re.search(r'\bround\s*(\d+)\b', q)
            r_num = int(round_m.group(1)) if round_m else None
            filter_query = re.sub(r'\bround\s*\d+\b', '', filter_query).strip()
            return tool_todays_results(filter_query, round_filter=r_num)

        if is_broad_results:
            filter_query = re.sub(
                r'\b(results?|for|show|list|me)\b', '', q
            ).strip()
            round_m = re.search(r'\bround\s*(\d+)\b', q)
            r_num = int(round_m.group(1)) if round_m else None
            filter_query = re.sub(r'\bround\s*\d+\b', '', filter_query).strip()
            return tool_all_results(filter_query, round_filter=r_num)
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
            _date_mode   = ("last_week" if any(x in q for x in ["last week", "previous week", "last round"])
                            else ("this_week" if any(x in q for x in ["this week", "today", "this round"]) else ""))
            # staff_only = query is ABOUT staff (not just mentioning them alongside players)
            _staff_only       = is_non_player_query and not any(x in q for x in ["player", "players"])
            _non_player_cards = is_non_player_query and not _staff_only   # mixed mode
            filter_query = re.sub(r'\b(yellow|card|cards|details?|show|list|with|for|me|this|last|week|previous|round|coach|coaches|staff|non|player|players|manager)\b', '', q).strip()
            return tool_yellow_cards(filter_query, show_details,
                                     include_non_players=_non_player_cards,
                                     staff_only=_staff_only,
                                     date_mode=_date_mode)

        # --- 6. RED CARDS ---
        if "red card" in q or "reds" in q:
            show_details = "detail" in q
            _date_mode   = ("last_week" if any(x in q for x in ["last week", "previous week", "last round"])
                            else ("this_week" if any(x in q for x in ["this week", "today", "this round"]) else ""))
            _staff_only       = is_non_player_query and not any(x in q for x in ["player", "players"])
            _non_player_cards = is_non_player_query and not _staff_only
            filter_query = re.sub(r'\b(red|card|cards|details?|show|list|with|for|me|this|last|week|previous|round|coach|coaches|staff|non|player|players|manager)\b', '', q).strip()
            return tool_red_cards(filter_query, show_details,
                                  include_non_players=_non_player_cards,
                                  staff_only=_staff_only,
                                  date_mode=_date_mode)

        # --- 7. STANDALONE NON-PLAYER LIST ---
        if is_non_player_query:
            filter_query = re.sub(r'\b(non|player|players?|staff|coach|coaches?|manager|managers|for|all|show|list|with|get|me)\b', '', q).strip()
            return tool_non_players(filter_query)

        # --- 8. TOP SCORERS ---
        if any(word in q for word in ["top scorer","leading scorer", "top scorers", "golden boot"]):
            clean = re.sub(r'\b(top|scorer|scorers?|golden|boot|in|for|show|me|list|all|leagues?|divisions?)\b', '', q).strip()
            # If no specific team/club filter remains, show ALL leagues (pass empty string)
            result = tool_top_scorers(clean, limit=50)
            if isinstance(result, dict) and result.get("type") == "table":
                if clean:
                    result["title"] = f"🏆 Top scorers — {clean.title()}"
                else:
                    result["title"] = f"🏆 Top Scorers — All Leagues & Divisions"
            return result
            
        # --- 9. SQUAD LIST / TEAM PLAYER TABLE ---
        squad_keywords = [
            "show me", "players for", "players in", "list players",
            "squad for", "squad", "who plays for", "who plays in",
            "players at", "team players",
        ]
        if any(word in q for word in squad_keywords):
            clean = re.sub(
                r'\b(show|me|players?|for|in|list|squad|who|plays?|at|team)\b',
                '', q
            ).strip()
            return tool_squad_list(clean)

        # --- 9B. TEAM STATS (detailed summary) ---
        if any(word in q for word in ["stats for", "team stats", "details for"]):
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

        # Club vs Club comparison (two recognised clubs on either side of vs/v)
        if " vs " in q or " v " in q:
            vs_parts = re.split(r'\s+v(?:s)?\s+', q)
            club_a_token = vs_parts[0].strip() if len(vs_parts) > 0 else ""
            club_b_token = vs_parts[1].strip() if len(vs_parts) > 1 else ""
            has_club_a = any(alias in club_a_token for alias in CLUB_ALIASES)
            has_club_b = any(alias in club_b_token for alias in CLUB_ALIASES)
            if has_club_a and has_club_b:
                return tool_club_vs_club(query)
            # Fall through to match centre for single match lookups
            return tool_match_centre(query)

        if "form" in q:
            team = normalize_team(query)
            return tool_form(team if team else query)
        
        # --- 11. DEFAULT FALLBACK ---
        team = normalize_team(query)
        if team:
            return tool_form(team)
        return tool_matches(query)