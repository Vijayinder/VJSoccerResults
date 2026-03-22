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

    "northcote": "Northcote City FC",
    "northcote city": "Northcote City FC",
    "ballarat": "Ballarat City FC",
    "ballarat city": "Ballarat City FC",
    "dandenong": "Dandenong Thunder FC",
    "thunder": "Dandenong Thunder FC",
    "dandenong thunder": "Dandenong Thunder FC",
    "geelong": "Geelong SC",
    "murray": "Murray United FC",
    "murray united": "Murray United FC",
    "pascoevale": "Pascoe Vale FC",
    "paco": "Pascoe Vale FC",
    "pascoe vale": "Pascoe Vale FC",
    "pascovale": "Pascoe Vale FC",
    "north geelong": "North Geelong Warriors FC",
    "warriors": "North Geelong Warriors FC",
    "knights": "Melbourne Knights FC",
    "melbourne knights": "Melbourne Knights FC",
    "berwick": "Berwick City SC",
    "berwick city": "Berwick City SC",
    "berwick city sc": "Berwick City SC",
    "berwick city fc": "Berwick City SC",
    "oakleigh": "Oakleigh Cannons FC",
    "oakleigh cannons": "Oakleigh Cannons FC",
    "cannons": "Oakleigh Cannons FC",
    "south melbourne": "South Melbourne FC",
    "south melb": "South Melbourne FC",
    "port melbourne": "Port Melbourne SC",
    "port melb": "Port Melbourne SC",
    "werribee": "Werribee City FC",
    "fitzroy": "Fitzroy City SC",
    "fitzroy city": "Fitzroy City SC",
    "narre warren": "Narre Warren FC",
    "narre": "Narre Warren FC",
    "casey": "Casey Comets FC",
    # Malvern
    "malvern": "Malvern City FC",
    "malvern city": "Malvern City FC",
    "malvern city fc": "Malvern City FC",
    # Kingston
    "kingston city": "Kingston City FC",
    "kingston": "Kingston City FC",
    # Boroondara
    "boroondara": "Boroondara Eagles FC",
    "boroondara eagles": "Boroondara Eagles FC",
    "eagles": "Boroondara Eagles FC",
    # Green Gully
    "green gully": "Green Gully FC",
    "gully": "Green Gully FC",
    # Sunshine
    "sunshine": "Sunshine FC",
    "sunshine george cross": "Sunshine George Cross SC",
    # Werribee
    "werribee city": "Werribee City FC",
    # Preston
    "preston": "Preston Lions FC",
    "preston lions": "Preston Lions FC",

    
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
    elif "fixtures" in name or "results" in name or "match_centre" in name or "lineups" in name or "predictions" in name:
        return []
    else:
        return {}

# ── Cached data loader — reloads every 30 minutes ───────────────────────
try:
    import streamlit as _st
    @_st.cache_data(ttl=1800, show_spinner=False)
    def _load_all_data():
        _results             = load_json("master_results.json")
        _fixtures            = load_json("fixtures.json")
        _players_data        = load_json("players_summary.json")
        _staff_data          = load_json("staff_summary.json")
        _match_centre_data   = load_json("master_match_centre.json")
        _lineups_data        = load_json("master_lineups.json")
        _competition_overview = load_json("competition_overview.json")
        _raw_players = _players_data.get("players", [])
        _raw_staff   = _staff_data.get("staff", [])
        return (
            _results, _fixtures, _players_data, _staff_data,
            _match_centre_data, _lineups_data, _competition_overview,
            _raw_players, _raw_staff
        )
except ImportError:
    def _load_all_data():
        _results             = load_json("master_results.json")
        _fixtures            = load_json("fixtures.json")
        _players_data        = load_json("players_summary.json")
        _staff_data          = load_json("staff_summary.json")
        _match_centre_data   = load_json("master_match_centre.json")
        _lineups_data        = load_json("master_lineups.json")
        _competition_overview = load_json("competition_overview.json")
        _raw_players = _players_data.get("players", [])
        _raw_staff   = _staff_data.get("staff", [])
        return (
            _results, _fixtures, _players_data, _staff_data,
            _match_centre_data, _lineups_data, _competition_overview,
            _raw_players, _raw_staff
        )

def _refresh_data():
    global results, fixtures, players_data, staff_data
    global match_centre_data, lineups_data, competition_overview
    global players_summary, staff_summary
    global player_names, player_lookup, staff_names, staff_lookup
    global _all_people, team_names
    (
        results, fixtures, players_data, staff_data,
        match_centre_data, lineups_data, competition_overview,
        _raw_players, _raw_staff
    ) = _load_all_data()
    players_summary = [_normalize_person(p, is_player=True)  for p in _raw_players]
    staff_summary   = [_normalize_person(p, is_player=False) for p in _raw_staff]
    player_names[:] = []; player_lookup.clear()
    for p in players_summary:
        fn = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
        if fn: player_names.append(fn); player_lookup[fn.lower()] = p
    staff_names[:] = []; staff_lookup.clear()
    for p in staff_summary:
        fn = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
        if fn: staff_names.append(fn); staff_lookup[fn.lower()] = p
    _all_people[:] = players_summary + staff_summary
    team_names[:] = sorted({
        p.get("team_name","") or (p.get("teams",[None])[0] or "")
        for p in _all_people if p.get("team_name") or p.get("teams")
    })

# Initial load at import time
(
    results, fixtures, players_data, staff_data,
    match_centre_data, lineups_data, competition_overview,
    _raw_p, _raw_s
) = _load_all_data()


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
        g_events  = [e for e in events if _etype(e) in ("goal", "goal_scored") and not e.get("own_goal") and _etype(e) != "own_goal"]
        og_events = [e for e in events if _etype(e) == "own_goal" or ((_etype(e) in ("goal","goal_scored")) and e.get("own_goal"))]

        if "yellow_cards"   not in m: m["yellow_cards"]   = len(y_events)
        if "yellow_minutes" not in m: m["yellow_minutes"]  = [e.get("minute") for e in y_events if e.get("minute")]
        if "red_cards"      not in m: m["red_cards"]       = len(r_events)
        if "red_minutes"    not in m: m["red_minutes"]     = [e.get("minute") for e in r_events if e.get("minute")]
        if "goals"          not in m: m["goals"]           = len(g_events)
        if "goal_minutes"   not in m: m["goal_minutes"]    = [e.get("minute") for e in g_events if e.get("minute")]
        if "own_goals"      not in m: m["own_goals"]       = len(og_events)
        if "og_minutes"     not in m: m["og_minutes"]      = [e.get("minute") for e in og_events if e.get("minute")]

    return out


players_summary = [_normalize_person(p, is_player=True)  for p in _raw_p]
staff_summary   = [_normalize_person(p, is_player=False) for p in _raw_s]

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
    - Ends with 'Z'              → explicit UTC, convert to Melbourne
    - Has offset (+HH:MM)        → parse as-is, convert to Melbourne
    - Space-separated datetime   → results format (e.g. "2026-02-08 06:30:00"), treat as UTC
    - Has 'T' but no tz info     → fixtures without Z, treat as UTC
    - Date only (10 chars)       → Melbourne midnight, no time available
    """
    if not date_str:
        return None
    try:
        melbourne_tz = pytz.timezone('Australia/Melbourne')
        utc_tz = pytz.utc

        if 'Z' in date_str:
            # e.g. "2026-01-31T21:30:00.000000Z" — explicit UTC
            utc_dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return utc_dt.astimezone(melbourne_tz)

        elif 'T' in date_str and ('+' in date_str[10:] or date_str.count('-') > 2):
            # Has explicit timezone offset — parse and convert
            return datetime.fromisoformat(date_str).astimezone(melbourne_tz)

        elif ' ' in date_str and len(date_str) > 10:
            # e.g. "2026-02-08 06:30:00" — results format, stored as UTC
            naive_dt = datetime.strptime(date_str[:19], "%Y-%m-%d %H:%M:%S")
            utc_dt = utc_tz.localize(naive_dt)
            return utc_dt.astimezone(melbourne_tz)

        elif 'T' in date_str:
            # e.g. "2026-01-31T21:30:00" — no tz marker, treat as UTC
            naive_dt = datetime.fromisoformat(date_str)
            utc_dt = utc_tz.localize(naive_dt)
            return utc_dt.astimezone(melbourne_tz)

        else:
            # Date only e.g. "2026-02-08" — no time available, use midnight
            naive_dt = datetime.fromisoformat(date_str[:10]).replace(hour=0, minute=0, second=0)
            return melbourne_tz.localize(naive_dt)

    except (ValueError, AttributeError, Exception):
        return None


def _format_time_aest(match_dt, date_str: str = "") -> str:
    """Format match time. Returns '—' if original date_str had no time component."""
    if match_dt is None:
        return "—"
    # Has time if: contains T (fixtures) or space with time part (results)
    has_time = 'T' in date_str or (' ' in date_str and len(date_str) > 10)
    if not date_str or not has_time:
        return "—"
    return match_dt.strftime("%I:%M %p").lstrip("0")

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

player_names  = []
player_lookup = {}
staff_names   = []
staff_lookup  = {}
_all_people   = []
team_names    = []

def _build_indices():
    player_names[:] = []; player_lookup.clear()
    for p in players_summary:
        fn = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
        if fn: player_names.append(fn); player_lookup[fn.lower()] = p
    staff_names[:] = []; staff_lookup.clear()
    for p in staff_summary:
        fn = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
        if fn: staff_names.append(fn); staff_lookup[fn.lower()] = p
    _all_people[:] = players_summary + staff_summary
    team_names[:] = sorted({
        p.get("team_name","") or (p.get("teams",[None])[0] or "")
        for p in _all_people if p.get("team_name") or p.get("teams")
    })

_build_indices()

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
        # Prefer the candidate whose age group exactly matches the query age group
        q_ag = re.search(r'\bu(\d{2})\b', q_lower)
        if q_ag:
            ag_str = f"u{q_ag.group(1)}"
            ag_exact = [t for t in exact_matches if re.search(r'\b' + re.escape(ag_str) + r'\b', t)]
            if len(ag_exact) == 1:
                return ag_exact[0]
            if ag_exact:
                exact_matches = ag_exact  # narrow down, then fall through
        return min(exact_matches, key=len)
    
    # Step 3: Check if query contains team name (query is longer than team name)
    reverse_matches = [t for t in team_names_lower if t in q_lower]
    if len(reverse_matches) == 1:
        return reverse_matches[0]
    elif len(reverse_matches) > 1:
        # Prefer age-group-exact match
        q_ag = re.search(r'\bu(\d{2})\b', q_lower)
        if q_ag:
            ag_str = f"u{q_ag.group(1)}"
            ag_exact = [t for t in reverse_matches if re.search(r'\b' + re.escape(ag_str) + r'\b', t)]
            if ag_exact:
                return max(ag_exact, key=len)
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

        def _cn(s):
            """Core name: strip age group + club-type suffix for fuzzy matching."""
            import re as _re2
            s = s.lower().strip()
            s = _re2.sub(r'\bu\d{2}\b', '', s)
            s = _re2.sub(r'\b(fc|sc|afc|fk|ac|bfc)\b', '', s)
            return _re2.sub(r'\s+', ' ', s).strip()

        if home_like:
            norm_home = normalize_team(home_like) or home_like
            nh_lower  = norm_home.lower()
            h_lower   = home.lower()
            if nh_lower not in h_lower and _cn(norm_home) not in _cn(home):
                continue

        if away_like:
            norm_away = normalize_team(away_like) or away_like
            na_lower  = norm_away.lower()
            a_lower   = away.lower()
            if na_lower not in a_lower and _cn(norm_away) not in _cn(away):
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
    # Sort longest first so "dandenong thunder" matches before "dandenong"
    club_token = None
    for alias in sorted(CLUB_ALIASES, key=len, reverse=True):
        if alias in q_lower:
            club_token = alias  # e.g. "dandenong thunder"
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
    target_leagues = ["YPL1", "YPL2", "YSL NW", "YSL SE", "YSL", "VPL", "VPL Men", "VPL Women"] if not include_all_leagues else []

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
            if not any(league_code == tl or league_code.startswith(tl) or tl.startswith(league_code)
                       for tl in target_leagues):
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

        # Treat empty string the same as None — score not entered
        def _score_missing(v):
            return v is None or str(v).strip() == ""

        # Only flag as missing if match has already taken place (past or today)
        is_past_or_today = match_date <= today

        needs_score = (
            is_past_or_today and (
                status not in ("complete", "completed") or
                _score_missing(home_score) or
                _score_missing(away_score)
            )
        )
        
        if needs_score:
            try:
                _time_str = _format_time_aest(match_dt, date_str)
            except Exception:
                _time_str = "—"
            missing_scores.append({
                "date":          match_dt.strftime("%d-%b"),
                "date_raw":      date_str,
                "time":          _time_str,
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
                "time":          _format_time_aest(match_dt, date_str),
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

    # Club token for flexible matching — longest alias first to avoid
    # "dandenong" matching before "dandenong thunder"
    club_token = None
    for alias in sorted(CLUB_ALIASES, key=len, reverse=True):
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

        # Determine result label from the filtered team's perspective
        _result = ""

        def _core_name(s):
            """Strip age group and club-type suffixes to get comparable base name.
            e.g. 'Berwick City FC U16' → 'berwick city'
                 'Berwick City SC'     → 'berwick city'
            """
            s = s.lower().strip()
            s = re.sub(r'\bu\d{2}\b', '', s)            # remove U16, U18 etc
            s = re.sub(r'\b(fc|sc|afc|fk|ac|bfc)\b', '', s)  # remove club type
            s = re.sub(r'\s+', ' ', s).strip()
            return s

        # Build query team core from best available source
        _q_src = canonical_club or (CLUB_ALIASES.get(club_token, club_token) if club_token else "") or q_lower
        _q_core = _core_name(_q_src)
        _home_core = _core_name(home)
        _away_core = _core_name(away)

        _is_home = bool(_q_core and _q_core in _home_core)
        _is_away = bool(_q_core and _q_core in _away_core)
        # Also try reverse: home/away core contains query core
        if not _is_home and _q_core:
            _is_home = _home_core in _q_core and bool(_home_core)
        if not _is_away and _q_core:
            _is_away = _away_core in _q_core and bool(_away_core)

        if _is_home or _is_away:
            try:
                _hs, _as = int(home_score), int(away_score)
                if _hs == _as:
                    _result = "🟰 D"
                elif (_is_home and _hs > _as) or (_is_away and _as > _hs):
                    _result = "✅ W"
                else:
                    _result = "❌ L"
            except (ValueError, TypeError):
                pass

        if len(matched) < 3:  # debug first 3 rows
            print(f"  [results debug] home={home!r} away={away!r} scores={home_score!r}-{away_score!r} q_core={_q_core!r} result={_result!r}")
        matched.append({
            "sort_key": date_str,
            "Date":     date_display,
            "League":   match_league_code,
            "Round":    match_round,
            "Home":     home,
            "Score":    f"{home_score}-{away_score}",
            "Away":     away,
            "Result":   _result,
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
        "type":  "match_list",
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

        # If filtered by team/age, count only cards from matches for that team
        if age_group or base_club or team_name:
            filter_team = team_name or (f"{base_club} {age_group}".strip() if base_club and age_group else base_club or "")
            team_card_count = 0
            for m in p.get("matches", []):
                m_team = m.get("team_name", "")
                # Match the match to the right team
                if filter_team and m_team and filter_team.lower() not in m_team.lower():
                    if age_group and age_group.lower() not in m_team.lower():
                        continue
                    if base_club and base_club.lower() not in m_team.lower():
                        continue
                events = m.get("events", [])
                yc = m.get("yellow_cards",
                    sum(1 for e in events
                        if (e.get("type") or e.get("event_type","")).lower() == "yellow_card"))
                team_card_count += yc
            total_count = team_card_count
        else:
            total_count = stats.get(stat_key, 0)

        if total_count == 0 and this_week_count == 0 and last_week_count == 0:
            continue  # skip players with no cards in this context

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

        # If filtered by team/age, count only cards from matches for that team
        if age_group or base_club or team_name:
            filter_team = team_name or (f"{base_club} {age_group}".strip() if base_club and age_group else base_club or "")
            team_card_count = 0
            for m in p.get("matches", []):
                m_team = m.get("team_name", "")
                if filter_team and m_team and filter_team.lower() not in m_team.lower():
                    if age_group and age_group.lower() not in m_team.lower():
                        continue
                    if base_club and base_club.lower() not in m_team.lower():
                        continue
                events = m.get("events", [])
                rc = m.get("red_cards",
                    sum(1 for e in events
                        if (e.get("type") or e.get("event_type","")).lower() == "red_card"))
                team_card_count += rc
            total_count = team_card_count
        else:
            total_count = stats.get(stat_key, 0)

        if total_count == 0 and this_week_count == 0 and last_week_count == 0:
            continue

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


def tool_own_goals(query: str = "") -> Any:
    """List players who scored own goals, with match details. Clickable → match detail."""
    ag    = extract_age_group(query)
    club  = extract_base_club_name(query)

    rows = []
    for p in players_summary:
        pname = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
        for m in p.get("matches", []):
            if not (m.get("available", False) or m.get("started", False)):
                continue
            og = m.get("own_goals", 0)
            if not og:
                events = m.get("events", [])
                def _et(e): return (e.get("type") or e.get("event_type","")).lower()
                og = sum(1 for e in events if _et(e) == "own_goal" or (_et(e) in ("goal","goal_scored") and e.get("own_goal")))
            if og == 0:
                continue
            m_team = m.get("team_name","")
            if ag   and ag.lower()   not in m_team.lower(): continue
            if club and club.lower() not in m_team.lower(): continue
            rows.append({
                "Player":   pname,
                "Team":     m_team,
                "Date":     iso_date_aest(m.get("date","")),
                "Opponent": m.get("opponent_team_name","—"),
                "H/A":      "🏠" if m.get("home_or_away") == "home" else "✈️",
                "🥅 OG":    og,
                "_hash":    m.get("match_hash_id",""),
                "_date_raw": m.get("date",""),
            })

    if not rows:
        return f"❌ No own goals found" + (f" for '{query}'" if query else "")

    rows.sort(key=lambda r: (r.get("_date_raw") or ""), reverse=True)

    filters = []
    if ag:   filters.append(ag)
    if club: filters.append(club)
    fs = " — " + " / ".join(filters) if filters else ""
    title = f"🥅 Own Goals{fs} ({len(rows)} entries)"

    # Strip internal fields
    display = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
    hashes  = [r["_hash"] for r in rows]
    dates   = [(r.get("_date_raw") or "")[:10] for r in rows]

    return {
        "type":    "own_goal_list",
        "data":    display,
        "hashes":  hashes,
        "dates":   dates,
        "title":   title,
    }


def _extract_league_code(query: str) -> str:
    """Extract a league code from a query string. Covers all known leagues."""
    q = query.lower()
    # Check longer codes first to avoid partial matches
    for code in ['ysl nw', 'ysl se', 'ysl north west', 'ysl south east',
                 'ypl1', 'ypl 1', 'ypl2', 'ypl 2',
                 'vpl men', 'vpl women', 'vpl',
                 'ysl', 'npl', 'ffv']:
        if code in q:
            return extract_league_from_league_name(code)
    return ""


def tool_cards_this_week(query: str = "", last_week: bool = False) -> dict:
    """
    Combined yellow + red cards this or last week.
    Supports filtering by age group, club, or league (e.g. YPL2, U16).
    Returns type='cards_this_week'.
    """
    _refresh_data()

    age_group   = extract_age_group(query) if query else None
    base_club   = extract_base_club_name(query) if query else None
    league_code = _extract_league_code(query) if query else ""

    this_week_day = get_match_day_date()
    if last_week:
        match_day = this_week_day - timedelta(days=7)
    else:
        match_day = this_week_day
    start_date = match_day
    end_date   = match_day

    def _build_rows(stat_key: str, card_type_lower: str) -> list:
        rows = []
        pool = list(players_summary) + list(staff_summary)
        for p in pool:
            pname = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
            role  = p.get("role") or (p.get("roles") or [""])[0] or "player"
            for m in p.get("matches", []):
                if not _match_in_date_range(m, start_date, end_date):
                    continue
                m_team = m.get("team_name", "") or ""
                if base_club and base_club.lower() not in m_team.lower():
                    continue
                if age_group and age_group.lower() not in m_team.lower():
                    continue
                if league_code:
                    m_league = extract_league_from_league_name(
                        m.get("league_name", "") or m.get("competition_name", ""))
                    if m_league != league_code:
                        continue
                events = m.get("events", [])
                count  = m.get(stat_key,
                    sum(1 for e in events
                        if (e.get("type") or e.get("event_type","")).lower() == card_type_lower))
                if count == 0:
                    continue
                mins = _card_minutes(m, card_type_lower)
                ag_m = re.search(r'U\d{2}', m_team, re.IGNORECASE)
                rows.append({
                    "Date":     iso_date_aest(m.get("date", "")),
                    "Player":   pname,
                    "Team":     re.sub(r'\s+U\d{2}$', '', m_team, flags=re.IGNORECASE).strip(),
                    "Age":      ag_m.group(0).upper() if ag_m else "—",
                    "Opponent": m.get("opponent_team_name", "?"),
                    "Min":      mins or "—",
                    "Role":     role.title() if role.lower() not in ("player","") else "Player",
                    "_pname":   pname,
                })
        rows.sort(key=lambda x: (x["Team"], x["Player"]))
        return rows

    yellow_rows = _build_rows("yellow_cards", "yellow_card")
    red_rows    = _build_rows("red_cards",    "red_card")

    date_label  = f" — {match_day.strftime('%d %b %Y')}" if match_day else ""
    week_label  = "Last Week" if last_week else "This Week"
    filter_str  = ""
    if league_code: filter_str += f" {league_code}"
    if base_club:   filter_str += f" {base_club}"
    if age_group:   filter_str += f" {age_group}"

    return {
        "type":        "cards_this_week",
        "title":       f"🟨🟥 Cards {week_label}{filter_str}{date_label}",
        "date":        match_day.strftime("%d %b %Y") if match_day else "",
        "yellow_rows": yellow_rows,
        "red_rows":    red_rows,
    }


def tool_all_cards(query: str = "") -> dict:
    """
    All cards for the season — no date filter.
    Supports filtering by age group, club, or league (e.g. YPL2, U16).
    Returns type='cards_this_week' (reuses same renderer).
    """
    _refresh_data()

    age_group   = extract_age_group(query) if query else None
    base_club   = extract_base_club_name(query) if query else None
    league_code = _extract_league_code(query) if query else ""

    def _build_rows(stat_key: str, card_type_lower: str) -> list:
        rows = []
        pool = list(players_summary) + list(staff_summary)
        for p in pool:
            pname = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
            role  = p.get("role") or (p.get("roles") or [""])[0] or "player"
            for m in p.get("matches", []):
                m_team = m.get("team_name", "") or ""
                if base_club and base_club.lower() not in m_team.lower():
                    continue
                if age_group and age_group.lower() not in m_team.lower():
                    continue
                if league_code:
                    m_league = extract_league_from_league_name(
                        m.get("league_name", "") or m.get("competition_name", ""))
                    if m_league != league_code:
                        continue
                events = m.get("events", [])
                count  = m.get(stat_key,
                    sum(1 for e in events
                        if (e.get("type") or e.get("event_type","")).lower() == card_type_lower))
                if count == 0:
                    continue
                mins = _card_minutes(m, card_type_lower)
                ag_m = re.search(r'U\d{2}', m_team, re.IGNORECASE)
                rows.append({
                    "Date":     iso_date_aest(m.get("date", "")),
                    "Player":   pname,
                    "Team":     re.sub(r'\s+U\d{2}$', '', m_team, flags=re.IGNORECASE).strip(),
                    "Age":      ag_m.group(0).upper() if ag_m else "—",
                    "Opponent": m.get("opponent_team_name", "?"),
                    "Min":      mins or "—",
                    "Role":     role.title() if role.lower() not in ("player","") else "Player",
                    "_pname":   pname,
                })
        rows.sort(key=lambda x: (-len([r for r in rows if r["Player"] == x["Player"]]),
                                 x["Team"], x["Player"]))
        return rows

    yellow_rows = _build_rows("yellow_cards", "yellow_card")
    red_rows    = _build_rows("red_cards",    "red_card")

    filter_str = ""
    if league_code: filter_str += f" {league_code}"
    if base_club:   filter_str += f" {base_club}"
    if age_group:   filter_str += f" {age_group}"

    return {
        "type":        "cards_this_week",
        "title":       f"🟨🟥 All Cards — Season{filter_str}",
        "date":        "",
        "yellow_rows": yellow_rows,
        "red_rows":    red_rows,
    }


def tool_card_summary(query: str = "") -> Any:
    """
    Cards aggregated by CLUB (stripped of age group).
    If a specific club is in the query, break down by age group for that club.
    If a specific age group AND club are given, list players.
    Example queries:
      "cards per club"           → all clubs, total yellows+reds
      "cards per club Heidelberg"→ Heidelberg broken down by age group
      "card summary U16 Heidelberg" → players with cards in Heidelberg U16
    """
    q = query.lower().strip()

    age_group  = extract_age_group(query)
    league_code = None
    for pl in ['ypl1', 'ypl2', 'ysl nw', 'ysl se', 'vpl men', 'vpl women']:
        if pl in q:
            league_code = extract_league_from_league_name(pl)
            break

    # Build raw club filter from query — strip age, league, card AND role keywords
    # Use RAW substring match (not alias lookup) so "Dandenong City" stays "Dandenong City"
    _club_q = re.sub(r'\b(card|cards?|summary|per|by|total|club|clubs?|show|me|list|all|each|staff|coaches?|managers?|non.?player|everyone|combined)\b', '', q, flags=re.IGNORECASE)
    if age_group:
        _club_q = re.sub(re.escape(age_group), '', _club_q, flags=re.IGNORECASE)
    if league_code:
        _club_q = re.sub(re.escape(league_code), '', _club_q, flags=re.IGNORECASE)
    for pl in ['ypl1', 'ypl2', 'ysl nw', 'ysl se', 'vpl men', 'vpl women']:
        _club_q = _club_q.replace(pl, "")
    base_club = _club_q.strip()

    # Staff-only filter
    staff_only = any(kw in q for kw in ["staff", "coach", "coaches", "non-player", "non player", "manager"])
    players_only = not staff_only and not any(kw in q for kw in ["all", "everyone", "combined"])

    # Mode: for staff there are few people so skip age breakdown — go club → players directly
    # For players: club → age → players
    if base_club and (age_group or staff_only):
        mode = "players"
    elif base_club:
        mode = "age"
    else:
        mode = "club"

    totals: dict = {}

    if staff_only:
        _pool = list(staff_summary)
    elif players_only:
        _pool = list(players_summary)
    else:
        _pool = list(players_summary) + list(staff_summary)

    for p in _pool:
        for m in p.get("matches", []):
            # Players need available/started; staff just need a match entry
            _is_player = not p.get("role") or str(p.get("role","")).lower() == "player"
            if _is_player and not (m.get("available", False) or m.get("started", False)):
                continue
            m_team = m.get("team_name", "")
            if not m_team:
                continue

            # Apply league filter
            if league_code:
                m_league = extract_league_from_league_name(
                    m.get("league_name", "") or m.get("competition_name", "")
                )
                if m_league.lower() != league_code.lower():
                    continue

            # Apply club filter
            if base_club and base_club.lower() not in m_team.lower():
                continue
            # Apply age filter
            if age_group and age_group.lower() not in m_team.lower():
                continue

            # Count cards for this match
            events = m.get("events", [])
            yc = m.get("yellow_cards",
                sum(1 for e in events if (e.get("type") or e.get("event_type","")).lower() == "yellow_card"))
            rc = m.get("red_cards",
                sum(1 for e in events if (e.get("type") or e.get("event_type","")).lower() == "red_card"))

            pname = f"{p.get('first_name','')} {p.get('last_name','')}".strip()

            # Determine grouping key
            if mode == "players":
                role = p.get("role") or (p.get("roles") or [""])[0] or "player"
                # For staff, append age group from team name so you see "John Smith (U16)"
                if staff_only:
                    ag_m2 = re.search(r'U\d{2}', m_team, re.IGNORECASE)
                    ag_sfx = f" ({ag_m2.group(0).upper()})" if ag_m2 else ""
                    key = pname + ag_sfx
                else:
                    key = pname if role.lower() in ("player", "") else f"{pname} ({role.title()})"
            elif mode == "age":
                ag_m = re.search(r'U\d{2}', m_team, re.IGNORECASE)
                key  = ag_m.group(0).upper() if ag_m else "Other"
            else:  # club
                key = re.sub(r'\s+U\d{2}$', '', m_team, flags=re.IGNORECASE).strip()

            if key not in totals:
                totals[key] = {"yc": 0, "rc": 0, "players": set(), "matches": 0}
            totals[key]["yc"] += yc
            totals[key]["rc"] += rc
            totals[key]["players"].add(pname)
            totals[key]["matches"] += 1

    if not totals:
        return f"❌ No card data found" + (f" for '{query}'" if query else "")

    # Build rows — skip zero-card entries
    data = []
    for key, v in sorted(totals.items(), key=lambda x: -(x[1]["yc"] + x[1]["rc"] * 2)):
        if v["yc"] == 0 and v["rc"] == 0:
            continue
        row = {
            "🟨 Yellow": v["yc"],
            "🟥 Red":    v["rc"],
            "Total":     v["yc"] + v["rc"],
            "Players":   len(v["players"]),
        }
        if mode == "players":
            row["Player"] = key
        elif mode == "age":
            row["Age"] = key
        else:
            row["Club"] = key
        # Reorder so name col is first
        ordered = {list(row.keys())[-1]: list(row.values())[-1]}
        ordered.update({k: v2 for k, v2 in row.items() if k != list(row.keys())[-1]})
        data.append(ordered)

    filters = []
    if base_club: filters.append(base_club)
    if age_group: filters.append(age_group)
    if league_code: filters.append(league_code)
    filter_str = " — " + " / ".join(filters) if filters else ""

    if mode == "players":
        label = f"Players with cards — {base_club} {age_group}"
        col_key = "Player"
    elif mode == "age":
        label = f"Cards by Age Group — {base_club}"
        col_key = "Age"
    else:
        label = "Cards by Club"
        col_key = "Club"

    title = f"📊 {label}{filter_str} ({len(data)} entries)"

    return {
        "type":       "card_summary",
        "mode":       mode,
        "col_key":    col_key,
        "base_club":  base_club or "",
        "age_group":  age_group or "",
        "staff_only": staff_only,
        "data":       data,
        "title":      title,
    }


def tool_most_appearances(query: str = "", limit: int = 50):
    """List players with most matches played, optionally filtered by age group, club or league."""
    players = [
        p for p in players_summary
        if (not p.get("role") or p.get("role") == "player")
    ]

    if query:
        players = filter_players_by_criteria(players, query, include_non_players=False)

    if not players:
        filter_desc = f" matching '{query}'" if query else ""
        return {"type": "error", "message": f"❌ No players found{filter_desc}"}

    # Build filter description
    age_group   = extract_age_group(query) if query else None
    base_club   = extract_base_club_name(query) if query else None
    filter_parts = []
    if base_club and age_group:
        filter_parts.append(f"{base_club} {age_group}")
    elif base_club:
        filter_parts.append(base_club)
    elif age_group:
        filter_parts.append(age_group)
    filter_desc = " — " + " ".join(filter_parts) if filter_parts else ""

    data = []
    for p in players:
        stats  = p.get("stats", {})
        all_m  = p.get("matches", [])
        played = [m for m in all_m if m.get("available", False) or m.get("started", False)]
        mp     = len(played)
        if mp == 0:
            continue
        name   = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
        teams  = p.get("teams", []) or ([p.get("team_name")] if p.get("team_name") else [])
        team   = teams[0] if teams else ""
        leagues = p.get("leagues", []) or ([p.get("league_name")] if p.get("league_name") else [])
        league_code = extract_league_from_league_name(leagues[0]) if leagues else "—"
        ag_m   = re.search(r'U\d{2}', team, re.IGNORECASE)
        age_grp = ag_m.group(0).upper() if ag_m else "—"
        club   = re.sub(r'\s+U\d{2}$', '', team, flags=re.IGNORECASE).strip() or team
        goals  = stats.get("goals", 0)
        data.append({
            "Player":  name,
            "Club":    club,
            "Div":     age_grp,
            "League":  league_code,
            "M":       mp,
            "⚽":      goals,
            "🟨":      stats.get("yellow_cards", 0),
            "🟥":      stats.get("red_cards", 0),
        })

    # Sort by matches played descending
    data.sort(key=lambda x: x["M"], reverse=True)

    # Add rank after sort
    for i, row in enumerate(data[:limit], 1):
        row["#"] = i
    # Reorder columns
    cols = ["#", "Player", "Club", "Div", "League", "M", "⚽", "🟨", "🟥"]
    data = [{c: row[c] for c in cols} for row in data[:limit]]

    total = len(data)
    return {
        "type":  "table",
        "data":  data,
        "title": f"👟 Most Appearances{filter_desc} — showing top {min(limit, total)}",
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
            "Date":     iso_date_aest(a.get("date", "")),
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
        "upcoming": _get_upcoming_for_team(team_name_to_match),
    }


def _get_upcoming_for_team(team_name: str) -> list:
    """Return upcoming fixtures for a team, sorted by date."""
    import pytz as _pytz
    melbourne_tz = _pytz.timezone('Australia/Melbourne')
    now = datetime.now(melbourne_tz)
    upcoming = []
    for f in fixtures:
        a    = f.get("attributes", {})
        home = a.get("home_team_name", "")
        away = a.get("away_team_name", "")
        if team_name.lower() not in home.lower() and team_name.lower() not in away.lower():
            continue
        match_dt = parse_date_utc_to_aest(a.get("date", ""))
        if not match_dt or match_dt <= now:
            continue
        is_home  = team_name.lower() in home.lower()
        opponent = _strip_age_group(away if is_home else home)
        days     = (match_dt.date() - now.date()).days
        when     = "TODAY" if days == 0 else ("Tomorrow" if days == 1 else f"In {days}d")
        opp_full = away if is_home else home
        # Ladder position for opponent
        league_name = a.get("league_name", "") or a.get("competition_name", "")
        comp_code   = extract_league_from_league_name(league_name).lower()
        ag_m        = re.search(r'u\d{2}', league_name.lower())
        age_grp_lc  = ag_m.group(0) if ag_m else ""
        opp_pos = None
        try:
            table   = _build_ladder_table(results, comp_code, age_grp_lc or None)
            opp_row = next((row for row in table
                            if _strip_age_group(opp_full).lower() in row["Team"].lower()), None)
            if opp_row:
                opp_pos = f"{opp_row['Pos']}/{len(table)} · {opp_row['PTS']}pts · W{opp_row['W']} D{opp_row['D']} L{opp_row['L']}"
        except Exception:
            pass
        upcoming.append({
            "Date":         match_dt.strftime("%Y-%m-%d"),
            "Time":         match_dt.strftime("%I:%M %p").lstrip("0") if match_dt.hour or match_dt.minute else "TBC",
            "H/A":          "🏠" if is_home else "✈️",
            "Opponent":     opponent,
            "Venue":        (a.get("ground_name") or "TBD")[:20],
            "When":         when,
            "Opp Standing": opp_pos or "—",
        })
    upcoming.sort(key=lambda x: x["When"])
    return upcoming


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
            role = (p.get("roles") or [p.get("role", "Staff")])[0] if (p.get("roles") or p.get("role")) else "Staff"
            pname = f"{p.get('first_name')} {p.get('last_name')}"
            matches = p.get("matches", [])
            # Build match-by-match table
            rows = []
            for m in sorted(matches, key=lambda x: x.get("date", ""), reverse=True):
                date_str = iso_date_aest(m.get("date", ""))
                opp      = m.get("opponent_team_name") or m.get("opponent") or "—"
                ag_m     = re.search(r'U\d{2}', m.get("team_name", ""), re.IGNORECASE)
                age_grp  = ag_m.group(0).upper() if ag_m else "—"
                yc = m.get("yellow_cards", 0)
                rc = m.get("red_cards",    0)
                ym = format_minutes(m.get("yellow_minutes", []))
                rm = format_minutes(m.get("red_minutes",    []))
                rows.append({
                    "Date":      date_str,
                    "Opponent":  opp,
                    "Age Group": age_grp,
                    "🟨":        f"🟨 ({ym})" if yc and ym else ("🟨" if yc else ""),
                    "🟥":        f"🟥 ({rm})" if rc and rm else ("🟥" if rc else ""),
                })
            title = (f"👤 {pname} ({role}) — "
                     f"{stats.get('matches_attended', stats.get('matches_played', 0))} matches, "
                     f"🟨 {stats.get('yellow_cards', 0)}  🟥 {stats.get('red_cards', 0)}")
            return {
                "type":  "table",
                "data":  rows,
                "title": title,
            }
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
                        g   = stats.get("goals", 0)
                        og  = stats.get("own_goals", 0)
                        pen = stats.get("penalties", 0)
                        yc  = stats.get("yellow_cards", 0)
                        rc  = stats.get("red_cards", 0)
                    else:
                        mp, g, yc, rc = "—", "—", "—", "—"

                # Count own goals + penalties per team from match data
                if has_team_in_matches and tm_played:
                    og_reg  = sum(m.get("own_goals", 0) for m in tm_played)
                    pen_reg = sum(
                        sum(1 for e in m.get("events",[]) if e.get("penalty_kick") and not e.get("own_goal"))
                        for m in tm_played
                    )
                elif i == 0:
                    og_reg  = stats.get("own_goals", 0)
                    pen_reg = stats.get("penalties", 0)
                else:
                    og_reg, pen_reg = "—", "—"
                reg_rows.append({
                    "Club":    t,
                    "League":  league,
                    "Jersey":  f"#{jersey}",
                    "Matches": mp,
                    "⚽":      _goal_cell_simple(
                        g   if isinstance(g,   int) else 0,
                        None,
                        og_reg  if isinstance(og_reg,  int) else 0,
                        None, None,
                        pen_reg if isinstance(pen_reg, int) else 0,
                    ),
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
                goals   = m.get("goals",       sum(1 for e in events if _etype(e) in ("goal","goal_scored") and not e.get("own_goal") and _etype(e) != "own_goal"))
                og      = m.get("own_goals",   sum(1 for e in events if _etype(e) == "own_goal" or e.get("own_goal")))
                yellows = m.get("yellow_cards", sum(1 for e in events if _etype(e) == "yellow_card"))
                reds    = m.get("red_cards",    sum(1 for e in events if _etype(e) == "red_card"))

                # Build started/role indicator: ✅ started, 🪑 bench, + captain © and goalie 🧤
                started_icon = "✅" if m.get("started") else "🪑"
                if m.get("captain"):
                    started_icon += " ©"
                if m.get("goalie"):
                    started_icon += " 🧤"

                # Build goals cell inline (no separate OG column)
                _events  = m.get("events", [])
                _pen_m   = [e.get("minute") for e in _events if e.get("penalty_kick") and not e.get("own_goal")]
                _og_m    = [e.get("minute") for e in _events if e.get("own_goal") or e.get("type") == "own_goal"]
                _g_m_raw = [e.get("minute") for e in _events if e.get("type") in ("goal","goal_scored") and not e.get("own_goal")]
                _g_cell  = _goal_cell_simple(goals, _g_m_raw, og, _og_m, _pen_m)
                row = {
                    "Date":     iso_date_aest(m.get("date", "")),
                    "H/A":      "🏠" if m.get("home_or_away") == "home" else "✈️",
                    "Opponent": m.get("opponent_team_name", "—"),
                    "Started":  started_icon,
                    "⚽":       _g_cell,
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
            # Multiple players → clickable player_list
            data = []
            for p in exact_matches[:20]:
                stats  = p.get("stats", {})
                teams  = p.get("teams", []) or ([p.get("team_name")] if p.get("team_name") else [])
                team   = teams[0] if teams else ""
                ag_m2  = re.search(r'U\d{2}', team, re.IGNORECASE)
                age_grp = ag_m2.group(0).upper() if ag_m2 else "—"
                club   = re.sub(r'\s+U\d{2}$', '', team, flags=re.IGNORECASE).strip() or team
                all_m  = p.get("matches", [])
                played = len([m for m in all_m if m.get("available", False) or m.get("started", False)])
                data.append({
                    "Player": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                    "Club":   club,
                    "Div":    age_grp,
                    "M":      played,
                    "⚽":     stats.get("goals", 0),
                    "🟨":     stats.get("yellow_cards", 0),
                    "🟥":     stats.get("red_cards", 0),
                })
            return {
                "type":  "player_list",
                "data":  data,
                "title": f"👤 {len(exact_matches)} players matching '{query}' — click to view profile",
            }
    
    # Fuzzy match fallback
    matched_name = fuzzy_find(q, [n.lower() for n in player_names], threshold=50)
    
    # Single fuzzy match → add to candidates list, show player_list for selection
    if matched_name and matched_name in player_lookup:
        single_p = player_lookup[matched_name]
        stats  = single_p.get("stats", {})
        teams  = single_p.get("teams", []) or ([single_p.get("team_name")] if single_p.get("team_name") else [])
        team   = teams[0] if teams else ""
        ag_m   = re.search(r'U\d{2}', team, re.IGNORECASE)
        age_grp = ag_m.group(0).upper() if ag_m else "—"
        club   = re.sub(r'\s+U\d{2}$', '', team, flags=re.IGNORECASE).strip() or team
        all_m  = single_p.get("matches", [])
        played = len([m for m in all_m if m.get("available", False) or m.get("started", False)])
        return {
            "type":  "player_list",
            "data":  [{
                "Player": f"{single_p.get('first_name', '')} {single_p.get('last_name', '')}".strip(),
                "Club":   club,
                "Div":    age_grp,
                "M":      played,
                "⚽":     stats.get("goals", 0),
                "🟨":     stats.get("yellow_cards", 0),
                "🟥":     stats.get("red_cards", 0),
                "Match":  "Best match",
            }],
            "title": f"🔍 Did you mean: click to view profile",
        }
    
    # Multiple candidates → clickable player_list
    similar = process.extract(q, [n.lower() for n in player_names], scorer=fuzz.WRatio, limit=8)
    if similar:
        data = []
        for name, score, _ in similar:
            if score < 45:
                continue
            p = player_lookup.get(name)
            if not p:
                actual = next((n for n in player_names if n.lower() == name), name)
                p = player_lookup.get(actual.lower())
            if not p:
                continue
            stats  = p.get("stats", {})
            teams  = p.get("teams", []) or ([p.get("team_name")] if p.get("team_name") else [])
            team   = teams[0] if teams else ""
            ag_m   = re.search(r'U\d{2}', team, re.IGNORECASE)
            age_grp = ag_m.group(0).upper() if ag_m else "—"
            club   = re.sub(r'\s+U\d{2}$', '', team, flags=re.IGNORECASE).strip() or team
            all_m  = p.get("matches", [])
            played = len([m for m in all_m if m.get("available", False) or m.get("started", False)])
            data.append({
                "Player": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                "Club":   club,
                "Div":    age_grp,
                "M":      played,
                "⚽":     stats.get("goals", 0),
                "🟨":     stats.get("yellow_cards", 0),
                "🟥":     stats.get("red_cards", 0),
                "Match":  f"{score}%",
            })
        if data:
            return {
                "type":  "player_list",
                "data":  data,
                "title": f"🔍 Did you mean one of these? Click to view profile",
            }
    
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
        row_lc = extract_league_from_league_name(league_name).lower()
        row_cc = extract_league_from_league_name(comp_name).lower()
        if competition_code_lower != row_lc and competition_code_lower != row_cc:
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
            "type":        "ladder",
            "competition": competition_to_use,
            "age_group":   age_group,
            "data":        data,
            "tables": [{"title": f"{age_group} — {competition_to_use.upper()}", "data": data}],
            "title":       f"📊 {competition_to_use.upper()} {age_group} Ladder ({len(data)} teams)"
        }

    # ── No age group → discover every age group in this competition and return all ──
    age_groups_found = set()
    for r in results:
        a = r.get("attributes", {})
        ln = (a.get("league_name") or "").lower()
        cn = (a.get("competition_name") or "").lower()
        row_lc2 = extract_league_from_league_name(ln).lower()
        row_cc2 = extract_league_from_league_name(cn).lower()
        if comp_lower != row_lc2 and comp_lower != row_cc2:
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
        "type":       "ladder",
        "title":      f"📊 {competition_to_use.upper()} — All Age Groups ({len(tables)} divisions)",
        "competition": competition_to_use,
        "tables":     tables,
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

def _goal_cell_simple(g_cnt, g_m, og_cnt, og_m, pen_m, pen_cnt=None):
    """Combine goals + OGs + penalties into one cell.
    g_m / og_m / pen_m may be None (totals only) or lists of minute strings.
    e.g.  2 (30'P, 58') +OG (22')
    """
    parts = []
    if g_cnt:
        pen_set = set(str(m) for m in (pen_m or []) if m)
        if g_m:
            min_strs = []
            for mn in g_m:
                mn_s = str(mn) if mn else ""
                if mn_s in pen_set:
                    min_strs.append(mn_s + "'P")
                    pen_set.discard(mn_s)
                else:
                    min_strs.append(mn_s + "'" if mn_s else "")
            min_strs = [s for s in min_strs if s]
            if min_strs:
                parts.append("⚽×" + str(g_cnt) + " (" + ", ".join(min_strs) + ")")
            else:
                parts.append("⚽×" + str(g_cnt))
        else:
            pc = pen_cnt or 0
            parts.append("⚽×" + str(g_cnt) + (" (" + str(pc) + "P)" if pc else ""))
    if og_cnt:
        if og_m:
            og_mins = [str(mn) + "'" for mn in og_m if mn]
            parts.append("+OG (" + ", ".join(og_mins) + ")" if og_mins else "+OG×" + str(og_cnt))
        else:
            parts.append("+OG×" + str(og_cnt))
    return " ".join(parts)



def tool_match_detail(query: str) -> Any:
    """
    Full match detail: both team lineups split into Players / Staff tabs,
    with goals & cards sourced from match_centre events (attributed by player name)
    and career totals cross-referenced from player_lookup.
    """
    import re as _re
    q = query.strip()
    q_clean = _re.sub(r'\b(match|details?|game|lineups?|for)\b', '', q, flags=_re.IGNORECASE).strip()

    # ── 1. Locate the match ──────────────────────────────────────────────
    matches = find_matches_by_teams_or_hash(match_hash_id=q_clean)

    if not matches:
        date_m    = _re.search(r'(\d{4}-\d{2}-\d{2})', q_clean)
        team_part = _re.sub(r'\d{4}-\d{2}-\d{2}', '', q_clean).strip()
        if date_m and team_part:
            target_date = date_m.group(1)
            # Extract age group from team_part so U16 query never matches U14 game
            ag_m2 = _re.search(r'\b(u\d{2})\b', team_part, _re.IGNORECASE)
            ag_req = ag_m2.group(1).lower() if ag_m2 else None

            def _cn2(s):
                s = s.lower()
                s = _re.sub(r'\bu\d{2}\b', '', s)
                s = _re.sub(r'\b(fc|sc|afc|fk|ac|bfc)\b', '', s)
                return _re.sub(r'\s+', ' ', s).strip()

            # Split on "vs" to get individual team tokens
            vs_parts  = _re.split(r'\s+vs?\s+', team_part, flags=_re.IGNORECASE)
            team_cores = [_cn2(p) for p in vs_parts if p.strip()]

            for mc in match_centre_data:
                ra   = mc.get("result", {}).get("attributes", {})
                # Compare using AEST date (same as display) to avoid UTC boundary mismatch
                d = iso_date_aest(ra.get("date") or "")
                if d != target_date:
                    continue
                h = ra.get("home_team_name", "")
                a = ra.get("away_team_name", "")
                hc = _cn2(h)
                ac = _cn2(a)
                # Must match age group exactly if one was specified
                if ag_req:
                    if ag_req not in h.lower() and ag_req not in a.lower():
                        continue
                # Each query team token must match one of home/away core names
                if all(any(tc in side for side in (hc, ac)) for tc in team_cores if tc):
                    matches.append(mc)

    if not matches:
        parts     = _re.split(r'\s+v(?:s)?\s+', q_clean, flags=_re.IGNORECASE)
        home_like = parts[0].strip() if parts else q_clean
        away_like = parts[1].strip() if len(parts) > 1 else None
        candidates = find_matches_by_teams_or_hash(home_like=home_like, away_like=away_like)
        # Filter by age group if present in query to avoid U14 matching U16 queries
        _ag_fb = _re.search(r'\b(u\d{2})\b', q_clean, _re.IGNORECASE)
        if _ag_fb and candidates:
            _ag_str = _ag_fb.group(1).lower()
            filtered = [m for m in candidates if
                        _ag_str in (m.get("result",{}).get("attributes",{}).get("home_team_name","") or "").lower() or
                        _ag_str in (m.get("result",{}).get("attributes",{}).get("away_team_name","") or "").lower()]
            candidates = filtered or candidates  # fall back if filter removes everything
        matches = candidates

    if not matches:
        return {"type": "error", "message": f"❌ No match found: {query}"}

    mc        = matches[0]
    r_attrs   = mc.get("result", {}).get("attributes", {})
    match_id  = mc.get("match_hash_id", "")
    home_name = r_attrs.get("home_team_name", "")
    away_name = r_attrs.get("away_team_name", "")
    home_score = r_attrs.get("home_score", "—")
    away_score = r_attrs.get("away_score", "—")
    date_str   = format_date_aest(r_attrs.get("date", "")) or r_attrs.get("date", "")[:10]
    league     = extract_league_from_league_name(r_attrs.get("league_name", ""))
    venue      = r_attrs.get("ground_name", "")

    # ── 2. Build card/goal maps keyed by player name ──────────────────────
    # Primary: use player_summary matches (match_hash_id matched) — most reliable
    # Fallback: mc_events player_name field
    from collections import defaultdict
    goal_mins      = defaultdict(list)
    own_goal_mins  = defaultdict(list)
    pen_mins       = defaultdict(list)
    yellow_mins    = defaultdict(list)
    red_mins       = defaultdict(list)

    def _etype(e):
        return (e.get("type") or e.get("event_type") or "").lower()

    # Pass 1: scan player_summary for this match_hash_id
    for p in players_summary:
        pname = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
        for m in p.get("matches", []):
            if m.get("match_hash_id") != match_id:
                continue
            events = m.get("events", [])
            # Own goals
            og_field = m.get("own_goals", 0)
            if isinstance(og_field, list):
                for e in og_field:
                    own_goal_mins[pname].append(str(e.get("minute","")) if isinstance(e,dict) else "")
            else:
                og_n = int(og_field or 0)
                if og_n > 0:
                    og_from_ev = [str(e.get("minute","")) for e in events
                                  if _etype(e) == "own_goal" or e.get("own_goal")]
                    own_goal_mins[pname].extend(og_from_ev or [""] * og_n)
            # Penalty goals (subset of regular goals — add ⚽P marker via pen_mins)
            pen_from_ev = [str(e.get("minute","")) for e in events
                           if e.get("penalty_kick") and not e.get("own_goal")]
            if pen_from_ev:
                pen_mins[pname].extend(pen_from_ev)
            # Goals (regular only)
            g_field = m.get("goals", 0)
            if isinstance(g_field, list):
                for e in g_field:
                    if not e.get("own_goal"):
                        goal_mins[pname].append(str(e.get("minute","")) if isinstance(e,dict) else "")
            elif int(g_field or 0) > 0:
                for e in events:
                    if _etype(e) in ("goal","goal_scored") and not e.get("own_goal"):
                        goal_mins[pname].append(str(e.get("minute","")) if e.get("minute") not in (None,"") else "")
            # Yellow cards
            yc_field = m.get("yellow_cards", 0)
            if isinstance(yc_field, list):
                for e in yc_field:
                    mn = str(e.get("minute","")) if isinstance(e,dict) else ""
                    yellow_mins[pname].append(mn)
            else:
                yc_n = int(yc_field or 0)
                if yc_n > 0:
                    mins_from_events = [str(e.get("minute","")) for e in events
                                        if _etype(e) == "yellow_card" and e.get("minute") not in (None,"")]
                    yellow_mins[pname].extend(mins_from_events or [""] * yc_n)
            # Red cards
            rc_field = m.get("red_cards", 0)
            if isinstance(rc_field, list):
                for e in rc_field:
                    mn = str(e.get("minute","")) if isinstance(e,dict) else ""
                    red_mins[pname].append(mn)
            else:
                rc_n = int(rc_field or 0)
                if rc_n > 0:
                    mins_from_events = [str(e.get("minute","")) for e in events
                                        if _etype(e) == "red_card" and e.get("minute") not in (None,"")]
                    red_mins[pname].extend(mins_from_events or [""] * rc_n)

    # Pass 2: mc_events fallback for any player not found above
    mc_entry  = next((m for m in match_centre_data if m.get("match_hash_id") == match_id), None)
    mc_events = mc_entry.get("events", []) if mc_entry else []
    for e in mc_events:
        pn = (e.get("player_name") or "").strip()
        mn = str(e.get("minute","")) if e.get("minute") not in (None,"") else ""
        et = _etype(e)
        if not pn:
            continue
        if et == "own_goal" or (et in ("goal","goal_scored") and e.get("own_goal")):
            if pn not in own_goal_mins: own_goal_mins[pn].append(mn)
        elif et in ("goal","goal_scored") and pn not in goal_mins:
            goal_mins[pn].append(mn)
            if e.get("penalty_kick"): pen_mins[pn].append(mn)
        elif et == "yellow_card" and pn not in yellow_mins:
            yellow_mins[pn].append(mn)
        elif et == "red_card" and pn not in red_mins:
            red_mins[pn].append(mn)

    # ── 3. Career totals from player_lookup ──────────────────────────────
    def _career(full_name: str):
        """Return (goals, own_goals, penalties, yellows, reds) career totals."""
        p = player_lookup.get(full_name.lower())
        if not p:
            return None
        st = p.get("stats", {})
        return (st.get("goals", 0), st.get("own_goals", 0),
                st.get("penalties", 0), st.get("yellow_cards", 0), st.get("red_cards", 0))

    # ── 4. Format minutes ────────────────────────────────────────────────
    def _mins_str(mins_list):
        clean = [m for m in mins_list if m]
        return ", ".join(f"{m}'" for m in clean) if clean else ""

    def _fmt_cell(count, mins_list, emoji):
        if count == 0:
            return ""
        ms = _mins_str(mins_list)
        return f"{emoji}×{count} ({ms})" if ms else f"{emoji}×{count}"

    def _goal_cell(g_cnt, g_m, og_cnt, og_m, pen_m):
        """Single ⚽ cell: goals with (P) on penalty mins, +OG appended.
        e.g. ⚽×2 (30'P, 58') +OG (22')
        """
        parts = []
        if g_cnt > 0:
            pen_set = set(str(m) for m in pen_m if m)
            min_strs = []
            for mn in g_m:
                if str(mn) in pen_set:
                    min_strs.append(f"{mn}'P")
                    pen_set.discard(str(mn))
                else:
                    min_strs.append(f"{mn}'" if mn else "")
            min_strs = [s for s in min_strs if s]
            sep = ", "
            parts.append(f"⚽×{g_cnt} ({sep.join(min_strs)})" if min_strs else f"⚽×{g_cnt}")
        if og_cnt > 0:
            og_mins = [f"{mn}'" for mn in og_m if mn]
            sep2 = ", "
            parts.append(f"+OG ({sep2.join(og_mins)})" if og_mins else f"+OG×{og_cnt}")
        return " ".join(parts)

    # ── 5. Build rows for one side ───────────────────────────────────────
    def _build_side(lineup_list):
        """
        Returns (player_rows, staff_rows) — separated by whether the entry
        has a jersey number or appears in player_lookup.
        """
        player_rows = []
        staff_rows  = []

        for p in lineup_list:
            fn   = (p.get("first_name") or "").strip()
            ln   = (p.get("last_name")  or "").strip()
            name = f"{fn} {ln}".strip()
            jersey = p.get("jersey_number") or p.get("jersey")

            # Determine if this is a player or non-playing staff
            in_player_lookup = name.lower() in player_lookup
            has_jersey       = bool(jersey)
            is_starting      = bool(p.get("starting"))
            # Heuristic: staff have no jersey AND not in player_lookup AND not starting
            is_staff = (not has_jersey) and (not in_player_lookup) and (not is_starting)

            role = "✅" if is_starting else "🪑"
            if p.get("captain"): role += " ©"
            if p.get("goalie"):  role += " 🧤"

            # Match events for this player
            g_list   = goal_mins.get(name,      [])
            og_list  = own_goal_mins.get(name,  [])
            pen_list = pen_mins.get(name,       [])
            yc_list  = yellow_mins.get(name,    [])
            rc_list  = red_mins.get(name,       [])

            # Fallback: lineup entry may store counts/lists directly
            def _from_field(field_val, fallback_list):
                if isinstance(field_val, list) and len(field_val) > 0:
                    # Non-empty list of event dicts — use directly
                    return len(field_val), [str(e.get("minute","")) for e in field_val if isinstance(e,dict)]
                # Empty list or zero int — prefer mc_events (authoritative)
                if fallback_list:
                    return len(fallback_list), fallback_list
                # Fall back to numeric field
                if isinstance(field_val, (int, float)) and int(field_val) > 0:
                    return int(field_val), []
                return 0, []

            # goals field in raw lineup JSON includes own_goals — strip them out
            _raw_goals = p.get("goals", 0)
            if isinstance(_raw_goals, list):
                _reg_goals = [g for g in _raw_goals if not g.get("own_goal")]
                _og_goals  = [g for g in _raw_goals if g.get("own_goal")]
            else:
                _reg_goals = _raw_goals
                _og_goals  = p.get("own_goals", 0)
            g_cnt,   g_m   = _from_field(_reg_goals, g_list)
            og_cnt,  og_m  = _from_field(_og_goals,  og_list)
            pen_cnt, pen_m = len(pen_list), pen_list
            yc_cnt,  yc_m  = _from_field(p.get("yellow_cards", 0),  yc_list)
            rc_cnt,  rc_m  = _from_field(p.get("red_cards", 0),     rc_list)

            # Career totals
            career = _career(name)
            if career:
                c_g, c_og, c_pen, c_yc, c_rc = career
                g_part = _goal_cell_simple(c_g, None, c_og, None, None, c_pen) if (c_g or c_og) else ""
                card_part = ("🟨" + str(c_yc) + " " if c_yc else "") + ("🟥" + str(c_rc) if c_rc else "")
                career_str = (g_part + " " + card_part).strip() if (g_part or card_part) else ""
            else:
                career_str = ""

            row = {
                "Player":  name,
                "#":       f"#{jersey}" if jersey else "—",
                "Role":    role,
                "⚽":      _goal_cell(g_cnt, g_m, og_cnt, og_m, pen_m),
                "🟨":      _fmt_cell(yc_cnt, yc_m, "🟨") or "",
                "🟥":      _fmt_cell(rc_cnt, rc_m, "🟥") or "",
                "Season":  career_str,
                "_g_cnt":  g_cnt + og_cnt + pen_cnt,   # hidden: total goals this match
                "_yc_cnt": yc_cnt,
                "_rc_cnt": rc_cnt,
            }

            if is_staff:
                staff_rows.append(row)
            else:
                player_rows.append(row)

        # Sort: starters first, then bench, then alpha
        def _sort_key(r):
            return (0 if "✅" in str(r["Role"]) else 1, r["Player"])
        player_rows.sort(key=_sort_key)
        staff_rows.sort(key=lambda r: r["Player"])

        # Totals row — correct counts from hidden fields, inserted at TOP
        if player_rows:
            total_g  = sum(r.get("_g_cnt",  0) for r in player_rows)
            total_yc = sum(r.get("_yc_cnt", 0) for r in player_rows)
            total_rc = sum(r.get("_rc_cnt", 0) for r in player_rows)
            totals_row = {
                "Player": "─── TOTAL ───",
                "#":      "",
                "Role":   "",
                "⚽":     f"⚽ {total_g}"  if total_g  else "",
                "🟨":     f"🟨 {total_yc}" if total_yc else "",
                "🟥":     f"🟥 {total_rc}" if total_rc else "",
                "Season": "",
                "_g_cnt": 0, "_yc_cnt": 0, "_rc_cnt": 0,
            }
            player_rows.insert(0, totals_row)

        return player_rows, staff_rows

    # ── 6. Get lineup ────────────────────────────────────────────────────
    lineup = find_lineup_by_match_hash(match_id)
    home_players, home_staff = _build_side(lineup.get("home_lineup", [])) if lineup else ([], [])
    away_players, away_staff = _build_side(lineup.get("away_lineup", [])) if lineup else ([], [])

    title = f"⚽ {home_name}  {home_score} – {away_score}  {away_name}  |  {date_str}  ·  {league}"
    if venue:
        title += f"  ·  {venue}"

    # ── 7. Build tab list ────────────────────────────────────────────────
    tables = []
    if home_players:
        tables.append({"title": f"🏠 {home_name}", "data": home_players, "clickable": True})
    if away_players:
        tables.append({"title": f"✈️ {away_name}", "data": away_players, "clickable": True})

    if not tables:
        return {"type": "error", "message": "❌ No lineup data for this match"}

    return {
        "type":      "match_detail",
        "title":     title,
        "home_name": home_name,
        "away_name": away_name,
        "tables":    tables,
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
        # Try exact substring first (alias in token)
        for alias in sorted(CLUB_ALIASES.keys(), key=len, reverse=True):
            if alias in token:
                return alias, CLUB_ALIASES[alias]
        # Then try reverse (token in alias) — handles "pascoe" matching "pascoe vale"
        for alias in sorted(CLUB_ALIASES.keys(), key=len, reverse=True):
            if token in alias and len(token) >= 4:
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

        _a_summary = f"{pos_a}/{total_teams} & {pts_a}pts" if pos_a is not None else "\u2014"
        _b_summary = f"{pos_b}/{total_teams} & {pts_b}pts" if pos_b is not None else "\u2014"
        rows.append({
            "League":     comp,
            "Age":        ag,
            "Positions":  edge,
            f"{short_a}": _a_summary,
            f"{short_b}": _b_summary,
        })

    if not rows:
        return {"type": "error",
                "message": f"\u274c Shared competitions found but no ladder data yet for {short_a} vs {short_b}"}

    match_rows = []
    for r in sorted(results, key=lambda x: x.get("attributes", {}).get("date", "")):
        a    = r.get("attributes", {})
        home = a.get("home_team_name", "")
        away = a.get("away_team_name", "")
        hb   = _strip_age_group(home).lower()
        ab   = _strip_age_group(away).lower()
        if not ((alias_a in hb and alias_b in ab) or (alias_b in hb and alias_a in ab)):
            continue
        hs  = a.get("home_score")
        as_ = a.get("away_score")
        score = f"{hs}\u2013{as_}" if hs is not None and as_ is not None else "\u2014"
        ag_m  = re.search(r"U\d{2}", home, re.IGNORECASE)
        ag    = ag_m.group(0).upper() if ag_m else "\u2014"
        lg    = extract_league_from_league_name(a.get("league_name", ""))
        date  = iso_date_aest(a.get("date", "")) or a.get("date", "\u2014")
        result = "\u2014"
        if hs is not None and as_ is not None:
            try:
                hs_i, as_i = int(hs), int(as_)
                a_goals = hs_i if alias_a in hb else as_i
                b_goals = as_i if alias_a in hb else hs_i
                if a_goals > b_goals:   result = f"{short_a} Win"
                elif b_goals > a_goals: result = f"{short_b} Win"
                else:                   result = "Draw"
            except Exception:
                pass
        match_rows.append({"Date": date, "Age": ag, "League": lg,
                           "Home": home, "Score": score, "Away": away, "Result": result})

    return {
        "type":   "multi_table",
        "title":  f"\u2694\ufe0f {short_a} vs {short_b}",
        "tables": [
            {"title": f"\U0001f4ca Ladder Positions ({len(rows)} divisions)", "data": rows},
            {"title": f"\u26bd Matches ({len(match_rows)} played)" if match_rows else "\u26bd Matches (none yet)", "data": match_rows},
        ],
    }


def tool_player_by_jersey(jersey_number: str, club_query: str = "") -> Any:
    """Find a player by jersey number and optionally club/age group.
    e.g. '#30 heidelberg', 'stats for #30 heidelberg u16'
    """
    jersey_clean = jersey_number.lstrip("#").strip()
    if not jersey_clean.isdigit():
        return f"❌ Invalid jersey number: {jersey_number}"

    age_group_f    = extract_age_group(club_query) if club_query else None
    canonical_club = get_canonical_club_name(club_query) if club_query else None
    club_token     = None
    if club_query:
        for alias in sorted(CLUB_ALIASES, key=len, reverse=True):
            if alias in club_query.lower():
                club_token = alias
                break

    matches = []
    for p in players_summary:
        jerseys = p.get("jerseys", {})
        # Check jersey across all teams
        for team, j in jerseys.items():
            if str(j) != jersey_clean:
                continue
            # Apply club filter
            if club_token and club_token not in team.lower():
                continue
            if canonical_club and canonical_club.lower() not in team.lower():
                continue
            if age_group_f and age_group_f.lower() not in team.lower():
                continue
            matches.append((p, team))
            break  # one entry per player

    if not matches:
        hint = f" for #{jersey_clean}"
        if club_query:
            hint += f" at {club_query}"
        return f"❌ No player found wearing #{jersey_clean}" + (f" at {club_query}" if club_query else "")

    if len(matches) == 1:
        p, team = matches[0]
        # Reuse tool_player_profile by full name
        name = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
        return tool_player_profile(name)

    # Multiple matches — show list
    data = []
    for p, team in matches:
        stats = p.get("stats", {})
        data.append({
            "Player": f"{p.get('first_name','')} {p.get('last_name','')}".strip(),
            "Team":   team,
            "#":      f"#{jersey_clean}",
            "M":      stats.get("matches_played", 0),
            "G":      stats.get("goals", 0),
        })
    return {"type": "table", "data": data,
            "title": f"👕 Players wearing #{jersey_clean}"}


def tool_opponent_squad(query: str = "") -> Any:
    """Show the squad for our next opponent.
    If today is Sunday (match day) show this week's opponent,
    otherwise show next week's opponent.
    Usage: 'opponent squad', 'show opponent', 'who do we play', 'next opponent squad'
    """
    import pytz
    melbourne_tz   = pytz.timezone('Australia/Melbourne')
    now_melbourne  = datetime.now(melbourne_tz)

    # Age group from query or fall back to USER_CONFIG
    age_group_f = extract_age_group(query) or USER_CONFIG.get("age_group", "U16")
    my_team     = USER_CONFIG["team"]  # e.g. "Heidelberg United FC U16"

    # Find next fixture for our team
    upcoming = []
    for f in fixtures:
        attrs    = f.get("attributes", {})
        date_str = attrs.get("date", "")
        match_dt = parse_date_utc_to_aest(date_str)
        if not match_dt or match_dt < now_melbourne:
            continue
        home  = attrs.get("home_team_name", "")
        away  = attrs.get("away_team_name", "")
        blob  = f"{home} {away}".lower()
        if "heidelberg" in blob and age_group_f.lower() in blob:
            upcoming.append((match_dt, attrs))

    upcoming.sort(key=lambda x: x[0])

    if not upcoming:
        return f"❌ No upcoming fixtures found for {my_team}"

    match_dt, attrs = upcoming[0]
    home  = attrs.get("home_team_name", "")
    away  = attrs.get("away_team_name", "")

    # Determine opponent
    if "heidelberg" in home.lower():
        opponent = away
    else:
        opponent = home

    date_str = match_dt.strftime("%a %d %b %I:%M %p")
    venue    = attrs.get("ground_name", "")

    result = tool_squad_list(opponent)

    # Prepend match context
    if isinstance(result, dict):
        result["title"] = (f"👥 Opponent Squad: {opponent}\n"
                           f"📅 {date_str}" + (f" @ {venue}" if venue else ""))
    return result

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

    # Filter players — match on team_filter, but also try stripping FC/SC suffix
    # to handle cases where alias canonical name has wrong FC/SC vs actual data
    _team_filter_lower = team_filter.lower()
    _team_filter_bare  = re.sub(r'\b(fc|sc|afc)\b', '', _team_filter_lower).strip()

    def _matches_team(p):
        for t in _person_teams(p):
            t_lower = (t or "").lower()
            if _team_filter_lower in t_lower:
                return True
            # Bare match (strip FC/SC from both sides)
            if _team_filter_bare and _team_filter_bare in re.sub(r'\b(fc|sc|afc)\b', '', t_lower).strip():
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
        "type":  "squad_table",
        "data":  data,
        "title": f"👥 Squad — {title_team}  ·  {len(players)} players{subtitle}"
    }



def tool_club_season(club_query: str = "heidelberg", age_group_filter: str = "") -> dict:
    """
    Combined season view for a club:
      - All completed results (date, opponent, score, W/D/L)
      - All upcoming fixtures
      - Current ladder position per age group
    Returns dict with type="season_summary".
    """
    _refresh_data()
    melbourne_tz = pytz.timezone('Australia/Melbourne')
    now          = datetime.now(melbourne_tz)

    canonical  = get_canonical_club_name(club_query) or club_query
    _raw_token = re.sub(r'\bu\d{2}\b', '', club_query, flags=re.IGNORECASE).strip().lower()
    _raw_token = re.sub(r'\b(fc|sc|afc|united fc|united sc)\s*$', '', _raw_token).strip()
    _canon_token = re.sub(r'\b(fc|sc|afc)\s*$', '', canonical, flags=re.IGNORECASE).strip().lower()
    club_token = _raw_token if len(_raw_token) >= len(_canon_token) else _canon_token

    # Guard: token must be at least 5 chars to avoid false matches on generic words like "city"
    if len(club_token) < 5:
        club_token = canonical.lower()

    age_filter = (age_group_filter or extract_age_group(club_query) or "").lower()

    def _matches_club(home: str, away: str) -> bool:
        blob = f"{home} {away}".lower()
        if club_token not in blob:
            return False
        if age_filter and age_filter not in blob:
            return False
        return True

    # ── Detect ambiguous token — find all distinct club names that match ──────
    matched_clubs = set()
    for r in results:
        a    = r.get("attributes", {})
        home = a.get("home_team_name", "")
        away = a.get("away_team_name", "")
        blob = f"{home} {away}".lower()
        if club_token in blob:
            if club_token in home.lower():
                base = re.sub(r'\s+U\d{2}$', '', home, flags=re.IGNORECASE).strip()
                matched_clubs.add(base)
            if club_token in away.lower():
                base = re.sub(r'\s+U\d{2}$', '', away, flags=re.IGNORECASE).strip()
                matched_clubs.add(base)

    if len(matched_clubs) > 1:
        # Ambiguous — return options for user to pick from
        options = sorted(matched_clubs)
        return {
            "type":    "ambiguous_club",
            "query":   club_query,
            "options": options,
            "age_grp": age_filter.upper() if age_filter else "",
            "message": f"Found {len(options)} clubs matching '{club_query}'. Please select one:",
        }

    # ── Resolve display name from actual data (not raw query) ─────────────────
    display_club = club_query  # fallback
    if matched_clubs:
        display_club = next(iter(matched_clubs))  # actual name from data
    elif canonical and canonical != club_query:
        display_club = re.sub(r'\s+U\d{2}$', '', canonical, flags=re.IGNORECASE).strip()

    # ── Past results ──────────────────────────────────────────────────────────
    past = []
    for r in results:
        a    = r.get("attributes", {})
        home = a.get("home_team_name", "")
        away = a.get("away_team_name", "")
        if not _matches_club(home, away):
            continue
        hs = a.get("home_score")
        as_ = a.get("away_score")
        if hs is None or as_ is None:
            continue
        try:
            hs, as_ = int(hs), int(as_)
        except (ValueError, TypeError):
            continue
        match_dt = parse_date_utc_to_aest(a.get("date", ""))
        if not match_dt:
            continue
        is_home  = club_token in home.lower()
        us       = hs if is_home else as_
        them     = as_ if is_home else hs
        opponent = away if is_home else home
        opponent = re.sub(r'\s+U\d{2}$', '', opponent, flags=re.IGNORECASE).strip()
        if us > them:   outcome, icon = "W", "🟢"
        elif us < them: outcome, icon = "L", "🔴"
        else:           outcome, icon = "D", "🟡"
        league_name = a.get("league_name", "") or a.get("competition_name", "")
        ag_m   = re.search(r'U\d{2}', f"{home} {away} {league_name}", re.IGNORECASE)
        age_grp = ag_m.group(0).upper() if ag_m else "—"
        past.append({
            "dt":       match_dt,
            "date":     match_dt.strftime("%Y-%m-%d"),
            "iso_date": match_dt.strftime("%Y-%m-%d"),
            "age":      age_grp,
            "opponent": opponent,                          # full name, no truncation
            "home":     home,                              # full home team name
            "away":     away,                              # full away team name
            "hash":     a.get("match_hash_id", ""),        # direct lookup key
            "score":    f"{us}–{them}",
            "outcome":  outcome,
            "icon":     icon,
            "venue":    (a.get("ground_name") or "")[:20],
            "league":   league_name,
        })
    past.sort(key=lambda x: x["dt"])

    # ── Upcoming fixtures ─────────────────────────────────────────────────────
    upcoming = []
    for f in fixtures:
        a    = f.get("attributes", {})
        home = a.get("home_team_name", "")
        away = a.get("away_team_name", "")
        if not _matches_club(home, away):
            continue
        match_dt = parse_date_utc_to_aest(a.get("date", ""))
        if not match_dt or match_dt <= now:
            continue
        is_home  = club_token in home.lower()
        opponent = away if is_home else home
        opponent = re.sub(r'\s+U\d{2}$', '', opponent, flags=re.IGNORECASE).strip()
        league_name = a.get("league_name", "") or a.get("competition_name", "")
        ag_m   = re.search(r'U\d{2}', f"{home} {away} {league_name}", re.IGNORECASE)
        age_grp = ag_m.group(0).upper() if ag_m else "—"
        days = (match_dt.date() - now.date()).days
        when = "TODAY" if days == 0 else ("Tomorrow" if days == 1 else f"In {days}d")
        # Raw opponent team name (with age group) for ladder lookup
        opp_full = away if is_home else home
        upcoming.append({
            "dt":      match_dt,
            "Date":    match_dt.strftime("%Y-%m-%d"),
            "Time":    match_dt.strftime("%I:%M %p").lstrip("0") if match_dt.hour or match_dt.minute else "TBC",
            "date":    match_dt.strftime("%Y-%m-%d"),   # kept for backward compat
            "age":     age_grp,
            "opponent": opponent[:18],
            "venue":   (a.get("ground_name") or "TBD")[:20],
            "when":    when,
            "league":  league_name,
            "is_home": is_home,
            "_opp_full": opp_full,
        })
    upcoming.sort(key=lambda x: x["dt"])

    # ── Enrich upcoming with opponent's current ladder position ──────────────
    for fix in upcoming:
        opp_full    = fix.pop("_opp_full", "")
        opp_token   = opp_full.lower()
        league_name = fix["league"]
        comp_code   = extract_league_from_league_name(league_name).lower()
        ag_m        = re.search(r'u\d{2}', league_name.lower())
        age_grp_lc  = ag_m.group(0) if ag_m else ""
        try:
            table = _build_ladder_table(results, comp_code, age_grp_lc if age_grp_lc else None)
            opp_row = next((row for row in table if opp_token in row["Team"].lower()), None)
            if opp_row:
                fix["opp_pos"]   = opp_row["Pos"]
                fix["opp_total"] = len(table)
                fix["opp_pts"]   = opp_row["PTS"]
                fix["opp_w"]     = opp_row["W"]
                fix["opp_d"]     = opp_row["D"]
                fix["opp_l"]     = opp_row["L"]
            else:
                fix["opp_pos"] = None
        except Exception:
            fix["opp_pos"] = None

    # ── Ladder positions ──────────────────────────────────────────────────────
    seen_comps = {}
    for r in results:
        a    = r.get("attributes", {})
        home = a.get("home_team_name", "")
        away = a.get("away_team_name", "")
        if club_token not in f"{home} {away}".lower():
            continue
        league_name = a.get("league_name", "") or a.get("competition_name", "")
        comp_code   = extract_league_from_league_name(league_name).lower()
        ag_m        = re.search(r'u\d{2}', league_name.lower())
        age_grp     = ag_m.group(0) if ag_m else ""
        if age_filter and age_filter != age_grp:
            continue
        key = (comp_code, age_grp)
        if key not in seen_comps:
            seen_comps[key] = league_name

    ladder_sections = []
    for (comp_code, age_grp), league_name in sorted(seen_comps.items(), key=lambda x: x[0][1]):
        table = _build_ladder_table(results, comp_code, age_grp if age_grp else None)
        if not table:
            continue
        our_row = next((row for row in table if club_token in row["Team"].lower()), None)
        if not our_row:
            continue
        ag_label   = age_grp.upper() if age_grp else "Open"
        comp_label = comp_code.upper()
        ladder_sections.append({
            "label": f"{ag_label} — {comp_label}",
            "pos": our_row["Pos"], "total": len(table),
            "pts": our_row["PTS"], "w": our_row["W"],
            "d": our_row["D"],    "l": our_row["L"],
            "gd": our_row["GD"],  "table": table,
        })

    # ── Top scorers & discipline for this club/age ───────────────────────────
    top_scorers = []
    discipline  = []
    for p in players_summary:
        p_teams = _person_teams(p)
        if not any(club_token in (t or "").lower() for t in p_teams):
            continue
        if age_filter and not any(age_filter in (t or "").lower() for t in p_teams):
            continue
        goals   = p.get("stats", {}).get("goals",        0) or 0
        yellows = p.get("stats", {}).get("yellow_cards", 0) or 0
        reds    = p.get("stats", {}).get("red_cards",    0) or 0
        played  = p.get("stats", {}).get("matches_played", 0) or 0
        name    = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
        if goals > 0:
            top_scorers.append({
                "Player":   name,
                "Goals":    goals,
                "Played":   played,
                "Per Game": round(goals / played, 2) if played else 0,
            })
        if yellows + reds > 0:
            discipline.append({
                "Player": name,
                "🟨":     yellows,
                "🟥":     reds,
                "Total":  yellows + reds * 2,
            })
    top_scorers.sort(key=lambda x: (-x["Goals"], -x["Per Game"]))
    discipline.sort(key=lambda x: -x["Total"])

    # ── Latest match detail ───────────────────────────────────────────────────
    latest_match = None
    if past:
        most_recent = past[-1]
        mhash = most_recent.get("hash", "")
        mc = next((m for m in match_centre_data
                   if m.get("match_hash_id") == mhash), None) if mhash else None
        if mc:
            r_attrs = mc.get("result", {}).get("attributes", {})
            events  = mc.get("events", []) or []
            def _etype(e): return (e.get("type") or e.get("event_type") or "").lower()
            latest_match = {
                "home":    r_attrs.get("home_team_name", most_recent["home"]),
                "away":    r_attrs.get("away_team_name", most_recent["away"]),
                "score":   most_recent["score"],
                "date":    most_recent["date"],
                "outcome": most_recent["outcome"],
                "icon":    most_recent["icon"],
                "venue":   most_recent.get("venue", ""),
                "goals":   [{"player": e.get("player_name","?"),
                             "min":    e.get("minute","?"),
                             "team":   e.get("team_name","")}
                            for e in events
                            if "goal" in _etype(e) and "own" not in _etype(e)],
                "cards":   [{"player": e.get("player_name","?"),
                             "type":   _etype(e),
                             "min":    e.get("minute","?"),
                             "team":   e.get("team_name","")}
                            for e in events if "card" in _etype(e)],
                "hash":    mhash,
            }
        else:
            # No match centre data — use what we have from results
            latest_match = {
                "home":    most_recent.get("home", ""),
                "away":    most_recent.get("away", ""),
                "score":   most_recent["score"],
                "date":    most_recent["date"],
                "outcome": most_recent["outcome"],
                "icon":    most_recent["icon"],
                "venue":   most_recent.get("venue", ""),
                "goals":   [],
                "cards":   [],
                "hash":    mhash,
            }

    return {
        "type":         "season_summary",
        "club":         display_club,
        "age_filter":   age_filter.upper() if age_filter else "",
        "past":         past,
        "upcoming":     upcoming,
        "ladder":       ladder_sections,
        "top_scorers":  top_scorers[:10],
        "discipline":   discipline[:10],
        "latest_match": latest_match,
    }


def tool_predict_match(query: str, home_team: str = "") -> dict:
    """
    Predict a scoreline using a tiered model.
    home_team: optional explicit home team name to apply home advantage correctly.
    """
    _refresh_data()

    vs_parts = re.split(r'\s+v(?:s|ersus)?\s+', query.lower())
    if len(vs_parts) < 2:
        return {"type": "error", "message": "❌ Use format: predict Heidelberg vs Brunswick U16"}

    noise = r'\b(predict|prediction|score|match|preview|for|in|the)\b'
    token_a = re.sub(noise, '', vs_parts[0]).strip()
    token_b = re.sub(noise, '', vs_parts[1]).strip()

    def _resolve_token(token):
        token = token.strip()
        for alias in sorted(CLUB_ALIASES.keys(), key=len, reverse=True):
            if alias in token or token in alias:
                return alias, CLUB_ALIASES[alias]
        return token, token.title()

    alias_a, canon_a = _resolve_token(token_a)
    alias_b, canon_b = _resolve_token(token_b)
    age_grp   = extract_age_group(query) or ""
    age_lower = age_grp.lower()

    def _is_relevant(home, away):
        return not age_lower or age_lower in f"{home} {away}".lower()

    # ── Collect ALL results for each club (not just recent) ───────────────────
    def _club_results(alias):
        rows = []
        for r in results:
            a  = r.get("attributes", {})
            h  = a.get("home_team_name", "")
            aw = a.get("away_team_name", "")
            if not _is_relevant(h, aw):
                continue
            hs  = a.get("home_score")
            aws = a.get("away_score")
            if hs is None or aws is None:
                continue
            try:
                hs, aws = int(hs), int(aws)
            except (ValueError, TypeError):
                continue
            h_base = _strip_age_group(h).lower()
            a_base = _strip_age_group(aw).lower()
            if alias in h_base:
                rows.append({"gf": hs, "ga": aws, "home": True,
                             "opp": a_base, "dt": a.get("date", "")})
            elif alias in a_base:
                rows.append({"gf": aws, "ga": hs, "home": False,
                             "opp": h_base, "dt": a.get("date", "")})
        rows.sort(key=lambda x: x["dt"])
        return rows

    res_a = _club_results(alias_a)
    res_b = _club_results(alias_b)

    if not res_a and not res_b:
        return {"type": "error",
                "message": f"❌ No results found for {canon_a} or {canon_b}. Cannot generate prediction."}

    # ── League average (all results in this age group) ────────────────────────
    all_goals = []
    for r in results:
        a  = r.get("attributes", {})
        h  = a.get("home_team_name", "")
        aw = a.get("away_team_name", "")
        if not _is_relevant(h, aw):
            continue
        hs  = a.get("home_score")
        aws = a.get("away_score")
        if hs is None or aws is None:
            continue
        try:
            all_goals.append(int(hs) + int(aws))
        except (ValueError, TypeError):
            pass

    league_avg_total    = (sum(all_goals) / len(all_goals)) if all_goals else 2.5
    league_avg_per_team = league_avg_total / 2.0

    # ── Attack / defence strength — ALL matches ───────────────────────────────
    def _strength(club_res):
        if not club_res:
            return 1.0, 1.0
        avg_gf = sum(r["gf"] for r in club_res) / len(club_res)
        avg_ga = sum(r["ga"] for r in club_res) / len(club_res)
        att    = avg_gf / league_avg_per_team if league_avg_per_team > 0 else 1.0
        defe   = avg_ga / league_avg_per_team if league_avg_per_team > 0 else 1.0
        return round(att, 2), round(defe, 2)

    att_a, def_a = _strength(res_a)
    att_b, def_b = _strength(res_b)

    # ── Tier 1: Direct H2H ────────────────────────────────────────────────────
    h2h_a = [r for r in res_a if alias_b in r["opp"]]   # from A's perspective
    h2h_xg_a = h2h_xg_b = None
    h2h_note = ""
    if h2h_a:
        h2h_xg_a = sum(r["gf"] for r in h2h_a) / len(h2h_a)
        h2h_xg_b = sum(r["ga"] for r in h2h_a) / len(h2h_a)
        wins_a = sum(1 for r in h2h_a if r["gf"] > r["ga"])
        wins_b = sum(1 for r in h2h_a if r["ga"] > r["gf"])
        draws  = len(h2h_a) - wins_a - wins_b
        h2h_note = (
            f"They've met {len(h2h_a)} time{'s' if len(h2h_a)>1 else ''} — "
            f"{canon_a} won {wins_a}, {canon_b} won {wins_b}, {draws} draw{'s' if draws!=1 else ''}. "
            f"Average score in those matches: {round(h2h_xg_a,1)}–{round(h2h_xg_b,1)} from {canon_a}'s perspective."
        )

    # ── Tier 2: Transitive inference via common opponents ─────────────────────
    # For each common opponent C: compare A's gf vs C and B's gf vs C
    # → if A scores more against C than B does, A has an edge
    opp_a = {r["opp"]: r for r in res_a}   # latest result per opponent
    opp_b = {r["opp"]: r for r in res_b}
    # Use all results grouped by opponent (avg)
    def _by_opp(club_res):
        d = {}
        for r in club_res:
            opp = r["opp"]
            if opp not in d:
                d[opp] = {"gf": [], "ga": []}
            d[opp]["gf"].append(r["gf"])
            d[opp]["ga"].append(r["ga"])
        return {opp: {"avg_gf": sum(v["gf"])/len(v["gf"]),
                      "avg_ga": sum(v["ga"])/len(v["ga"]),
                      "n":      len(v["gf"])}
                for opp, v in d.items()}

    by_opp_a = _by_opp(res_a)
    by_opp_b = _by_opp(res_b)
    common_opps = set(by_opp_a.keys()) & set(by_opp_b.keys())
    # Remove direct H2H from common opponents
    common_opps.discard(alias_a)
    common_opps.discard(alias_b)

    transitive_xg_a = transitive_xg_b = None
    transitive_note = ""
    transitive_examples = []
    if common_opps:
        edge_a_list, edge_b_list = [], []
        for opp in common_opps:
            ra = by_opp_a[opp]
            rb = by_opp_b[opp]
            # A scored ra["avg_gf"] against opp; B scored rb["avg_gf"] against opp
            # B conceded rb["avg_ga"] against opp; A conceded ra["avg_ga"] against opp
            # Expected A vs B: A attacks like ra["avg_gf"] / rb["avg_ga"] (normalised)
            ref_gf  = (ra["avg_gf"] + rb["avg_ga"]) / 2   # how opp concedes
            ref_ga  = (ra["avg_ga"] + rb["avg_gf"]) / 2   # how opp scores
            edge_a_list.append(ra["avg_gf"])
            edge_b_list.append(rb["avg_gf"])
            transitive_examples.append(
                f"vs {opp.title()[:16]}: "
                f"{canon_a[:12]} scored {round(ra['avg_gf'],1)}, "
                f"{canon_b[:12]} scored {round(rb['avg_gf'],1)}"
            )
        transitive_xg_a = sum(edge_a_list) / len(edge_a_list)
        transitive_xg_b = sum(edge_b_list) / len(edge_b_list)
        # Normalise to league average scale
        scale = league_avg_per_team / max((transitive_xg_a + transitive_xg_b) / 2, 0.1)
        transitive_xg_a *= scale
        transitive_xg_b *= scale
        top_examples = transitive_examples[:3]
        transitive_note = (
            f"Found {len(common_opps)} common opponent{'s' if len(common_opps)>1 else ''}: "
            + "; ".join(top_examples) + "."
        )

    # ── Determine who has home advantage ─────────────────────────────────────
    # home_team param takes priority; fall back to assuming club_a is home
    # (caller should pass home_team explicitly when known from fixture data)
    if home_team:
        _home_lower = home_team.lower()
        a_is_home = alias_a in _home_lower or _home_lower in alias_a
    else:
        a_is_home = True   # default: first team in query is home

    HOME_ADV = 0.3
    home_adv_a = HOME_ADV if a_is_home else 0.0
    home_adv_b = HOME_ADV if not a_is_home else 0.0

    # ── Combine tiers into final xG ───────────────────────────────────────────
    strength_xg_a = att_a * league_avg_per_team / max(def_b, 0.3)
    strength_xg_b = att_b * league_avg_per_team / max(def_a, 0.3)

    if h2h_a and transitive_xg_a is not None:
        xg_a = (0.50 * h2h_xg_a + 0.20 * transitive_xg_a
              + 0.20 * strength_xg_a + 0.10 * league_avg_per_team + home_adv_a)
        xg_b = (0.50 * h2h_xg_b + 0.20 * transitive_xg_b
              + 0.20 * strength_xg_b + 0.10 * league_avg_per_team + home_adv_b)
        weight_note = "H2H (50%) + common opponents (20%) + season form (20%) + league avg (10%)"
    elif h2h_a:
        xg_a = (0.50 * h2h_xg_a + 0.35 * strength_xg_a
              + 0.15 * league_avg_per_team + home_adv_a)
        xg_b = (0.50 * h2h_xg_b + 0.35 * strength_xg_b
              + 0.15 * league_avg_per_team + home_adv_b)
        weight_note = "H2H (50%) + season form (35%) + league avg (15%)"
    elif transitive_xg_a is not None:
        xg_a = (0.40 * transitive_xg_a + 0.40 * strength_xg_a
              + 0.20 * league_avg_per_team + home_adv_a)
        xg_b = (0.40 * transitive_xg_b + 0.40 * strength_xg_b
              + 0.20 * league_avg_per_team + home_adv_b)
        weight_note = "Common opponents (40%) + season form (40%) + league avg (20%)"
    else:
        xg_a = (0.60 * strength_xg_a + 0.40 * league_avg_per_team + home_adv_a)
        xg_b = (0.60 * strength_xg_b + 0.40 * league_avg_per_team + home_adv_b)
        weight_note = "Season form (60%) + league avg (40%) — no common opponents yet"

    xg_a = max(0.0, round(xg_a, 2))
    xg_b = max(0.0, round(xg_b, 2))
    pred_a = int(round(xg_a))
    pred_b = int(round(xg_b))

    # ── Win probability % (0=loss, 50=draw, 100=win from club_a perspective) ──
    # Simple logistic-style: based on xG gap normalised to 0-100
    xg_diff = xg_a - xg_b
    # Map xg_diff to win%: 0 diff = 50%, +1 goal ~ 70%, +2 goals ~ 85%
    import math as _math
    win_pct_a = round(50 + 50 * (1 - _math.exp(-0.9 * xg_diff)) / (1 + _math.exp(-0.9 * abs(xg_diff))) * (1 if xg_diff >= 0 else -1))
    win_pct_a = max(5, min(95, win_pct_a))

    if pred_a > pred_b:   verdict = f"🏆 {canon_a} to win"
    elif pred_b > pred_a: verdict = f"🏆 {canon_b} to win"
    else:                 verdict = "🤝 Likely a draw"

    # ── Plain-English reasoning note ──────────────────────────────────────────
    reasoning_parts = []
    if h2h_note:
        reasoning_parts.append(f"**Direct H2H:** {h2h_note}")
    if transitive_note:
        reasoning_parts.append(f"**Common opponents:** {transitive_note}")

    # Form comparison
    form_summary_a = f"{canon_a} is scoring {round(att_a * league_avg_per_team, 1)} goals/game and conceding {round(def_a * league_avg_per_team, 1)}"
    form_summary_b = f"{canon_b} is scoring {round(att_b * league_avg_per_team, 1)} and conceding {round(def_b * league_avg_per_team, 1)}"
    reasoning_parts.append(f"**Season form ({len(res_a)} matches for {canon_a}, {len(res_b)} for {canon_b}):** {form_summary_a}. {form_summary_b}.")

    if HOME_ADV > 0:
        home_side = canon_a if a_is_home else canon_b
        reasoning_parts.append(f"**Home advantage:** +{HOME_ADV} goals to {home_side} (home side).")

    reasoning_parts.append(f"**Weights used:** {weight_note}.")
    reasoning = "\n\n".join(reasoning_parts)

    # ── Form strings and rows (all matches) ──────────────────────────────────
    def _form_str(club_res, n=5):
        icons = []
        for r in club_res[-n:]:
            if r["gf"] > r["ga"]:   icons.append("🟢")
            elif r["gf"] < r["ga"]: icons.append("🔴")
            else:                   icons.append("🟡")
        return " ".join(icons) if icons else "—"

    def _form_rows(club_res, n=8):
        rows = []
        for r in club_res[-n:]:
            dt_str = r["dt"][:10] if len(r["dt"]) >= 10 else r["dt"]
            try:
                from datetime import datetime as _dt2
                disp = _dt2.fromisoformat(dt_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
            except Exception:
                disp = dt_str
            icon = "🟢" if r["gf"] > r["ga"] else ("🔴" if r["gf"] < r["ga"] else "🟡")
            rows.append({
                "Date":     disp,
                "Opponent": r["opp"].title()[:20],
                "Score":    f"{icon} {r['gf']}–{r['ga']}",
                "H/A":      "🏠" if r["home"] else "✈️",
            })
        return rows

    data_quality = []
    if len(res_a) < 3:
        data_quality.append(f"limited data for {canon_a} ({len(res_a)} results)")
    if len(res_b) < 3:
        data_quality.append(f"limited data for {canon_b} ({len(res_b)} results)")
    confidence_note = ("⚠️ Low confidence — " + "; ".join(data_quality)) if data_quality else ""

    # ── One-line summary ──────────────────────────────────────────────────────
    if win_pct_a >= 65:
        one_liner = f"{canon_a} likely to win ({win_pct_a}% chance). Predicted {pred_a}–{pred_b}."
    elif win_pct_a <= 35:
        one_liner = f"{canon_b} likely to win ({100-win_pct_a}% chance). Predicted {pred_a}–{pred_b}."
    else:
        one_liner = f"Tight match — close to a draw. Predicted {pred_a}–{pred_b} ({win_pct_a}% for {canon_a})."
    if confidence_note:
        one_liner += f" ⚠️ Limited data."

    title_age = f" {age_grp}" if age_grp else ""
    return {
        "type":              "prediction",
        "title":             f"🔮 Match Prediction{title_age}: {canon_a} vs {canon_b}",
        "club_a":            canon_a,
        "club_b":            canon_b,
        "pred_a":            pred_a,
        "pred_b":            pred_b,
        "xg_a":              xg_a,
        "xg_b":              xg_b,
        "verdict":           verdict,
        "win_pct_a":         win_pct_a,
        "one_liner":         one_liner,
        "form_a":            _form_str(res_a),
        "form_b":            _form_str(res_b),
        "att_a":             att_a,
        "def_a":             def_a,
        "att_b":             att_b,
        "def_b":             def_b,
        "form_rows_a":       _form_rows(res_a),
        "form_rows_b":       _form_rows(res_b),
        "h2h_count":         len(h2h_a),
        "common_opp_count":  len(common_opps),
        "league_avg":        round(league_avg_per_team, 2),
        "confidence_note":   confidence_note,
        "reasoning":         reasoning,
        "weight_note":       weight_note,
        "age_grp":           age_grp,
        "matches_used_a":    len(res_a),
        "matches_used_b":    len(res_b),
        "a_is_home":         a_is_home,
    }


def tool_predict_ladder(club_query: str = "heidelberg",
                        age_group_filter: str = "",
                        after_n_matches: int = 0) -> dict:
    """
    Predict where a club will sit on the ladder after N more fixtures.

    For each remaining fixture:
      - Predict the scoreline using the same model as tool_predict_match
      - Award points (W=3, D=1, L=0) to each team
      - Apply predicted GF/GA to each team
    Returns the full predicted ladder after those N matches (or end of season if N=0).

    Also shows both scenarios:
      - Model prediction (uses match-by-match scoreline predictions)
      - Extrapolated rate (current points-per-game × remaining games)
    """
    _refresh_data()
    melbourne_tz = pytz.timezone('Australia/Melbourne')
    now          = datetime.now(melbourne_tz)

    # ── Resolve club ──────────────────────────────────────────────────────────
    canonical  = get_canonical_club_name(club_query) or club_query
    _raw_token = re.sub(r'\bu\d{2}\b', '', club_query, flags=re.IGNORECASE).strip().lower()
    _raw_token = re.sub(r'\b(fc|sc|afc|united fc|united sc)\s*$', '', _raw_token).strip()
    _canon_token = re.sub(r'\b(fc|sc|afc)\s*$', '', canonical, flags=re.IGNORECASE).strip().lower()
    club_token = _raw_token if len(_raw_token) >= len(_canon_token) else _canon_token
    if len(club_token) < 4:
        club_token = canonical.lower()

    age_filter = (age_group_filter or extract_age_group(club_query) or "").lower()

    # ── Find competition this club plays in ───────────────────────────────────
    comp_code = ""
    for r in results:
        a    = r.get("attributes", {})
        home = a.get("home_team_name", "")
        away = a.get("away_team_name", "")
        blob = f"{home} {away}".lower()
        if club_token not in blob:
            continue
        if age_filter and age_filter not in blob:
            continue
        ln = a.get("league_name", "") or a.get("competition_name", "")
        comp_code = extract_league_from_league_name(ln).lower()
        break

    if not comp_code or comp_code == "other":
        return {"type": "error",
                "message": f"❌ Cannot find competition for {canonical}. Try including the age group, e.g. 'predicted ladder heidelberg u16'."}

    # ── Current ladder ────────────────────────────────────────────────────────
    current_table = _build_ladder_table(results, comp_code, age_filter if age_filter else None)
    if not current_table:
        return {"type": "error", "message": f"❌ No ladder data found for {canonical}."}

    # ── Remaining fixtures for this competition ───────────────────────────────
    remaining = []
    for f in fixtures:
        a    = f.get("attributes", {})
        home = a.get("home_team_name", "")
        away = a.get("away_team_name", "")
        blob = f"{home} {away}".lower()
        if age_filter and age_filter not in blob:
            continue
        ln = a.get("league_name", "") or a.get("competition_name", "")
        if extract_league_from_league_name(ln).lower() != comp_code:
            continue
        match_dt = parse_date_utc_to_aest(a.get("date", ""))
        if not match_dt or match_dt <= now:
            continue
        remaining.append((match_dt, home, away))

    remaining.sort(key=lambda x: x[0])

    # Limit to N fixtures if specified
    if after_n_matches > 0:
        remaining = remaining[:after_n_matches]

    if not remaining:
        return {"type": "error",
                "message": f"❌ No remaining fixtures found for this competition."}

    # ── Build mutable points table from current standings ────────────────────
    from collections import defaultdict
    pred_table = {}
    for row in current_table:
        pred_table[row["Team"]] = {
            "P":   row["P"],
            "W":   row["W"],
            "D":   row["D"],
            "L":   row["L"],
            "GF":  row["GF"],
            "GA":  row["GA"],
            "PTS": row["PTS"],
        }

    # ── League average per team (for prediction model) ────────────────────────
    all_goals = []
    for r in results:
        a  = r.get("attributes", {})
        h  = a.get("home_team_name", "")
        aw = a.get("away_team_name", "")
        if age_filter and age_filter not in f"{h} {aw}".lower():
            continue
        hs  = a.get("home_score")
        aws = a.get("away_score")
        if hs is None or aws is None:
            continue
        try:
            all_goals.append(int(hs) + int(aws))
        except (ValueError, TypeError):
            pass
    league_avg_total    = (sum(all_goals) / len(all_goals)) if all_goals else 2.5
    league_avg_per_team = league_avg_total / 2.0

    def _attack_defence(team_name):
        """Attack/defence strength for a team based on recent results."""
        alias = None
        t_lower = _strip_age_group(team_name).lower()
        for al in sorted(CLUB_ALIASES.keys(), key=len, reverse=True):
            if al in t_lower or t_lower in al:
                alias = al
                break
        if not alias:
            alias = t_lower
        gf_list, ga_list = [], []
        for r in results:
            a  = r.get("attributes", {})
            h  = a.get("home_team_name", "")
            aw = a.get("away_team_name", "")
            if age_filter and age_filter not in f"{h} {aw}".lower():
                continue
            hs  = a.get("home_score")
            aws = a.get("away_score")
            if hs is None or aws is None:
                continue
            try:
                hs, aws = int(hs), int(aws)
            except (ValueError, TypeError):
                continue
            h_base = _strip_age_group(h).lower()
            a_base = _strip_age_group(aw).lower()
            if alias in h_base:
                gf_list.append(hs); ga_list.append(aws)
            elif alias in a_base:
                gf_list.append(aws); ga_list.append(hs)
        if not gf_list:
            return 1.0, 1.0
        n = min(6, len(gf_list))
        avg_gf = sum(gf_list[-n:]) / n
        avg_ga = sum(ga_list[-n:]) / n
        att = avg_gf / league_avg_per_team if league_avg_per_team > 0 else 1.0
        defe = avg_ga / league_avg_per_team if league_avg_per_team > 0 else 1.0
        return round(att, 2), round(defe, 2)

    HOME_ADV = 0.3
    fixture_predictions = []

    for match_dt, home, away in remaining:
        att_h, def_h = _attack_defence(home)
        att_a2, def_a2 = _attack_defence(away)

        xg_h = max(0.0, 0.40 * league_avg_per_team
                       + 0.60 * att_h * league_avg_per_team / max(def_a2, 0.3)
                       + HOME_ADV)
        xg_a2 = max(0.0, 0.40 * league_avg_per_team
                        + 0.60 * att_a2 * league_avg_per_team / max(def_h, 0.3))

        ph = int(round(xg_h))
        pa = int(round(xg_a2))

        # Award points
        for team, gf_pred, ga_pred in [(home, ph, pa), (away, pa, ph)]:
            if team not in pred_table:
                pred_table[team] = {"P": 0, "W": 0, "D": 0, "L": 0, "GF": 0, "GA": 0, "PTS": 0}
            pred_table[team]["P"]  += 1
            pred_table[team]["GF"] += gf_pred
            pred_table[team]["GA"] += ga_pred
            if gf_pred > ga_pred:
                pred_table[team]["W"]   += 1
                pred_table[team]["PTS"] += 3
            elif gf_pred < ga_pred:
                pred_table[team]["L"] += 1
            else:
                pred_table[team]["D"]   += 1
                pred_table[team]["PTS"] += 1

        fixture_predictions.append({
            "Date":  match_dt.strftime("%Y-%m-%d"),
            "Home":  _strip_age_group(home),
            "Score": f"{ph}–{pa}",
            "Away":  _strip_age_group(away),
            "When":  f"In {(match_dt.date() - now.date()).days}d",
        })

    # ── Build sorted predicted ladder ─────────────────────────────────────────
    predicted_ladder = []
    for team, row in pred_table.items():
        gd = row["GF"] - row["GA"]
        predicted_ladder.append({
            "Team": team,
            "P":    row["P"],
            "W":    row["W"],
            "D":    row["D"],
            "L":    row["L"],
            "GF":   row["GF"],
            "GA":   row["GA"],
            "GD":   gd,
            "Pts":  row["PTS"],
        })
    predicted_ladder.sort(key=lambda x: (-x["Pts"], -x["GD"], -x["GF"]))
    for i, row in enumerate(predicted_ladder, 1):
        row["Pos"] = i

    # ── Find our club's predicted position ────────────────────────────────────
    our_pred_row = next(
        (row for row in predicted_ladder if club_token in row["Team"].lower()), None
    )

    # ── Extrapolated rate scenario ────────────────────────────────────────────
    extrap_ladder = []
    for row in current_table:
        games_played = row["P"]
        ppg = row["PTS"] / games_played if games_played > 0 else 0
        n_remaining  = len(remaining)
        extrap_pts   = row["PTS"] + round(ppg * n_remaining)
        extrap_ladder.append({
            "Team":       row["Team"],
            "Current Pts": row["PTS"],
            "Games Left":  n_remaining,
            "PPG":         round(ppg, 2),
            "Projected Pts": extrap_pts,
        })
    extrap_ladder.sort(key=lambda x: -x["Projected Pts"])
    for i, row in enumerate(extrap_ladder, 1):
        row["Proj Pos"] = i

    n_label = f"after {len(remaining)} more match{'es' if len(remaining) != 1 else ''}"
    our_row_current = next((r for r in current_table if club_token in r["Team"].lower()), None)
    our_pos_now     = our_row_current["Pos"] if our_row_current else "?"
    our_pos_pred    = our_pred_row["Pos"] if our_pred_row else "?"
    movement = ""
    if isinstance(our_pos_now, int) and isinstance(our_pos_pred, int):
        diff = our_pos_now - our_pos_pred
        if diff > 0:   movement = f"⬆️ up {diff} place{'s' if diff > 1 else ''}"
        elif diff < 0: movement = f"⬇️ down {abs(diff)} place{'s' if abs(diff) > 1 else ''}"
        else:          movement = "➡️ same position"

    age_label = age_filter.upper() if age_filter else ""
    return {
        "type":                "ladder_prediction",
        "title":               f"📊 Predicted Ladder — {canonical} {age_label} {n_label}",
        "club":                canonical,
        "club_token":          club_token,
        "age_grp":             age_filter.upper(),
        "n_matches":           len(remaining),
        "our_pos_now":         our_pos_now,
        "our_pos_predicted":   our_pos_pred,
        "movement":            movement,
        "predicted_ladder":    predicted_ladder,
        "extrap_ladder":       extrap_ladder,
        "fixture_predictions": fixture_predictions,
        "current_ladder":      current_table,
    }


class FastQueryRouter:
    """Enhanced pattern-based query router with personal team support"""
    def __init__(self):
        pass
        
    def process(self, query: str):
        """Route query to appropriate handler"""
        _refresh_data()  # picks up new JSON files every 30 min via st.cache_data TTL
        q = query.lower().strip()
 
        import fast_agent as _fa_self
        _fa_self._last_debug = {"query": query, "fn": None, "args": {}}
        print(f"\n━━━ QUERY: {query!r}")
        # --- 1. INITIALIZE ALL VARIABLES AT THE START ---
        # This prevents the UnboundLocalError by ensuring they exist immediately
        filter_query = ""
        show_details = False
        is_non_player_query = any(keyword in q for keyword in ['non player', 'non-player', 'coach', 'coaches', 'staff', 'manager'])
        is_personal_query = any(keyword in q for keyword in ['my next', 'when do i play', 'where do i play', 'my schedule', 'when is my', 'where is my', 'our next'])

        # --- 0. SEASON SUMMARY ---
        _season_kw = [
            'season summary', 'season', 'full season',
            'results and fixtures', 'fixtures and results',
            'all matches', 'all results', 'all fixtures',
        ]
        if any(kw in q for kw in _season_kw):
            clean   = re.sub(
                r'\b(season|summary|full|results?|fixtures?|all|matches?|for|show|me|and)\b',
                '', q
            ).strip()
            age_grp = extract_age_group(clean) or ""
            club_q  = re.sub(r'\bu\d{2}\b', '', clean, flags=re.IGNORECASE).strip()
            if not club_q:
                club_q = USER_CONFIG.get("club", "heidelberg")
            import fast_agent as _fa_mod
            _fa_mod._last_debug = {
                'query': query, 'fn': 'tool_club_season',
                'args': f'club_q={club_q!r}, age_grp={age_grp!r}',
            }
            print(f"\n🔧 TOOL: tool_club_season()  query={query!r}")
            return tool_club_season(club_q, age_grp)

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
            import fast_agent as _fa_mod

            _fa_mod._last_debug = {'query': query, 'fn': 'tool_dual_player_detail', 'args': 'clean'}
            print(f"\n🔧 TOOL: tool_dual_player_detail()  args='clean'  query={query!r}")


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
            import fast_agent as _fa_mod

            _fa_mod._last_debug = {'query': query, 'fn': 'tool_dual_registration', 'args': 'filter_query, different_clubs_only=is_diff_club_query'}

            print(f"\n🔧 TOOL: tool_dual_registration()  query={query!r}")
            return tool_dual_registration(filter_query, different_clubs_only=is_diff_club_query)

        # --- 2. MISSING SCORES ---
        missing_keywords = ['missing score', 'missing scores', 'no score', 'scores not entered', 'overdue', 'matches without scores', 'todays missing', 'missing scores today', 'latest missing']
        if any(keyword in q for keyword in missing_keywords):
            # "latest missing" means the most recent match day
            today_only = ('today' in q or 'todays' in q or "today's" in q or 'latest' in q)
            last_week = 'last week' in q or 'previous week' in q

            # Extract round number if present e.g. "round 5" or "r5"
            round_match = re.search(r'\bround\s*(\d+)\b', q)
            round_filter = int(round_match.group(1)) if round_match else None

            # Strip known keywords including round/week words and "latest"
            filter_query = re.sub(
                r'\b(missing|score|scores?|no|not|entered|overdue|matches?|without|for|show|list|today|todays|today\'s|last|previous|week|round|latest|recent|\d+)\b',
                '', q
            ).strip()

            include_all = 'all leagues' in q or 'all league' in q

            import fast_agent as _fa_mod


            _fa_mod._last_debug = {'query': query, 'fn': 'tool_missing_scores', 'args': '\n                filter_query,\n                include_all_leagues=include_all,\n                today_only=today_only,\n                last_week=last_week,\n                round_filter=round_filter\n            '}


            print(f"\n🔧 TOOL: tool_missing_scores()  query={query!r}")
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
            'latest results', 'latest result', 'recent results',
        ]
        is_today_results = any(keyword in q for keyword in todays_results_keywords)

        # Broad results query (no "today" — show all completed results for the filter)
        is_broad_results = (
            not is_today_results and
            q.startswith('results') and len(q) > 7
        )

        if is_today_results:
            filter_query = re.sub(
                r'\b(today|todays|today\'s|results?|for|show|list|me|this|last|week|latest|recent)\b',
                '', q
            ).strip()
            round_m = re.search(r'\bround\s*(\d+)\b', q)
            r_num = int(round_m.group(1)) if round_m else None
            filter_query = re.sub(r'\bround\s*\d+\b', '', filter_query).strip()
            import fast_agent as _fa_mod

            _fa_mod._last_debug = {'query': query, 'fn': 'tool_todays_results', 'args': 'filter_query, round_filter=r_num'}

            print(f"\n🔧 TOOL: tool_todays_results()  query={query!r}")
            return tool_todays_results(filter_query, round_filter=r_num)

        if is_broad_results:
            filter_query = re.sub(
                r'\b(results?|for|show|list|me)\b', '', q
            ).strip()
            round_m = re.search(r'\bround\s*(\d+)\b', q)
            r_num = int(round_m.group(1)) if round_m else None
            filter_query = re.sub(r'\bround\s*\d+\b', '', filter_query).strip()
            import fast_agent as _fa_mod

            _fa_mod._last_debug = {'query': query, 'fn': 'tool_all_results', 'args': 'filter_query, round_filter=r_num'}

            print(f"\n🔧 TOOL: tool_all_results()  query={query!r}")
            return tool_all_results(filter_query, round_filter=r_num)
        # --- 2C. TOP SCORERS TODAY ---
        top_scorers_today_keywords = ['top scorers today', 'goals today', 'who scored today', 'scorers today', "today's scorers", "today's goals"]
        if any(keyword in q for keyword in top_scorers_today_keywords):
            filter_query = re.sub(r'\b(top|scorer|scorers?|goals?|who|scored|today|todays|today\'s|for|show|list|me)\b', '', q).strip()
            import fast_agent as _fa_mod

            _fa_mod._last_debug = {'query': query, 'fn': 'tool_top_scorers_today', 'args': 'filter_query'}

            print(f"\n🔧 TOOL: tool_top_scorers_today()  query={query!r}")
            return tool_top_scorers_today(filter_query)
        
        # --- 2D. TEAMS THAT LOST TODAY ---
        teams_lost_keywords = ['teams that lost today', 'who lost today', 'losses today', 'teams lost today', "today's losses"]
        if any(keyword in q for keyword in teams_lost_keywords):
            filter_query = re.sub(r'\b(teams?|that|who|lost|losses?|today|todays|today\'s|for|show|list|me)\b', '', q).strip()
            import fast_agent as _fa_mod

            _fa_mod._last_debug = {'query': query, 'fn': 'tool_teams_lost_today', 'args': 'filter_query'}

            print(f"\n🔧 TOOL: tool_teams_lost_today()  query={query!r}")
            return tool_teams_lost_today(filter_query)

        # --- 2E. MISSING SCORES TODAY ---
        missing_today_keywords = ['missing scores today', 'missing today', 'scores not entered today', 'todays missing scores']
        if any(keyword in q for keyword in missing_today_keywords):
            filter_query = re.sub(r'\b(missing|today|todays|today\'s|scores?|not|entered|for|show|list|me)\b', '', q).strip()
            import fast_agent as _fa_mod

            _fa_mod._last_debug = {'query': query, 'fn': 'tool_missing_scores', 'args': 'filter_query, include_all_leagues=False, today_only=True'}

            print(f"\n🔧 TOOL: tool_missing_scores()  query={query!r}")
            return tool_missing_scores(filter_query, include_all_leagues=False, today_only=True)
            
        # --- 3. COMPETITION OVERVIEW ---
        comp_overview_keywords = ['competition overview', 'competition standings', 'ypl1 overview', 'ypl2 overview', 'ysl overview', 'vpl overview', 'club rankings', 'overall standings']
        if any(keyword in q for keyword in comp_overview_keywords) or any(comp in q for comp in ['ypl1', 'ypl2', 'ysl nw', 'ysl se', 'vpl']):
            if any(word in q for word in ['overview', 'standings', 'ranking', 'competition']):
                import fast_agent as _fa_mod

                _fa_mod._last_debug = {'query': query, 'fn': 'tool_competition_overview', 'args': 'query'}

                print(f"\n🔧 TOOL: tool_competition_overview()  query={query!r}")
                return tool_competition_overview(query)

        # --- 3B. JERSEY NUMBER SEARCH ---
        # e.g. "stats for #30 heidelberg", "#30 heidelberg u16", "who wears #10"
        jersey_match = re.search(r'#(\d+)', q)
        if jersey_match:
            jersey_num  = jersey_match.group(1)
            club_part   = re.sub(r'#\d+', '', q)
            club_part   = re.sub(r'\b(stats|for|who|wears|wearing|player|show|me|is)\b', '', club_part).strip()
            import fast_agent as _fa_mod
            _fa_mod._last_debug = {'query': query, 'fn': 'tool_player_by_jersey', 'args': f'#{jersey_num}, {club_part}'}
            print(f"\n🔧 TOOL: tool_player_by_jersey()  jersey=#{jersey_num} club={club_part!r}")
            return tool_player_by_jersey(jersey_num, club_part)

        # --- 3C. OPPONENT SQUAD ---
        # e.g. "opponent squad", "show opponent", "who do we play", "next opponent squad"
        opponent_keywords = ['opponent squad', 'show opponent', 'opponent players',
                             'who do we play', 'next opponent', 'playing against',
                             'squad this week', 'squad next week']
        if any(kw in q for kw in opponent_keywords):
            import fast_agent as _fa_mod
            _fa_mod._last_debug = {'query': query, 'fn': 'tool_opponent_squad', 'args': 'query'}
            print(f"\n🔧 TOOL: tool_opponent_squad()  query={query!r}")
            return tool_opponent_squad(query)

        # --- 4. FIXTURES / NEXT MATCH ---
        fixture_keywords = ['next match', 'next game', 'upcoming', 'when do i play', 'where do i play', 'my next', 'schedule', 'fixture', 'fixtures', 'when is my', 'where is my', 'our next']
        if any(keyword in q for keyword in fixture_keywords):
            if is_personal_query:
                import fast_agent as _fa_mod

                _fa_mod._last_debug = {'query': query, 'fn': 'tool_fixtures', 'args': 'query="", limit=5, use_user_team=True'}

                print(f"\n🔧 TOOL: tool_fixtures()  query={query!r}")
                return tool_fixtures(query="", limit=5, use_user_team=True)
            else:
                team_query = re.sub(r'\b(next|match|game|upcoming|when|where|do|i|play|my|schedule|fixtures?|is)\b', '', q).strip()
                limit = 5 if team_query else 10
                import fast_agent as _fa_mod

                _fa_mod._last_debug = {'query': query, 'fn': 'tool_fixtures', 'args': 'team_query, limit, use_user_team=False'}

                print(f"\n🔧 TOOL: tool_fixtures()  query={query!r}")
                return tool_fixtures(team_query, limit, use_user_team=False)

        # --- 4B. ALL CARDS (season, no date filter) ---
        if ("cards" in q or "card" in q) and any(x in q for x in ["all cards", "all season", "season cards", "total cards season"]):
            import fast_agent as _fa_mod
            _fa_mod._last_debug = {'query': query, 'fn': 'tool_all_cards', 'args': query}
            print(f"\n🔧 TOOL: tool_all_cards()  query={query!r}")
            return tool_all_cards(query)

        # --- 4B. CARDS THIS/LAST WEEK (combined yellow + red) ---
        if ("cards" in q or "card" in q) and any(x in q for x in [
                "this week", "this round", "today", "latest", "last week", "previous week", "last round"]):
            import fast_agent as _fa_mod
            _last_week = any(x in q for x in ["last week", "previous week", "last round"])
            _fa_mod._last_debug = {'query': query, 'fn': 'tool_cards_this_week', 'args': query}
            print(f"\n🔧 TOOL: tool_cards_this_week()  query={query!r}  last_week={_last_week}")
            return tool_cards_this_week(query, last_week=_last_week)

        # --- 5. YELLOW CARDS ---
        if "yellow card" in q or "yellows" in q:
            show_details = "detail" in q
            _date_mode   = ("last_week" if any(x in q for x in ["last week", "previous week", "last round"])
                            else ("this_week" if any(x in q for x in ["this week", "today", "this round"]) else ""))
            # staff_only = query is ABOUT staff (not just mentioning them alongside players)
            _staff_only       = is_non_player_query and not any(x in q for x in ["player", "players"])
            _non_player_cards = is_non_player_query and not _staff_only   # mixed mode
            filter_query = re.sub(r'\b(yellow|card|cards|details?|show|list|with|for|me|this|last|week|previous|round|coach|coaches|staff|non|player|players|manager)\b', '', q).strip()
            import fast_agent as _fa_mod

            _fa_mod._last_debug = {'query': query, 'fn': 'tool_yellow_cards', 'args': 'filter_query, show_details,\n                                     include_non_players=_non_player_cards,\n                                     staff_only=_staff_only,\n                                     date_mode=_date_mode'}

            print(f"\n🔧 TOOL: tool_yellow_cards()  query={query!r}")
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
            import fast_agent as _fa_mod

            _fa_mod._last_debug = {'query': query, 'fn': 'tool_red_cards', 'args': 'filter_query, show_details,\n                                  include_non_players=_non_player_cards,\n                                  staff_only=_staff_only,\n                                  date_mode=_date_mode'}

            print(f"\n🔧 TOOL: tool_red_cards()  query={query!r}")
            return tool_red_cards(filter_query, show_details,
                                  include_non_players=_non_player_cards,
                                  staff_only=_staff_only,
                                  date_mode=_date_mode)

        # --- 8A2. CARD SUMMARY BY TEAM/CLUB/AGE (must be before non-player fallback) ---
        if any(kw in q for kw in ["total cards", "card summary", "cards by", "cards per", "cards each"]):
            clean = re.sub(r'\b(total|card|cards?|summary|by|per|each|show|me|list|all)\b', '', q).strip()
            import fast_agent as _fa_mod
            _fa_mod._last_debug = {'query': query, 'fn': 'tool_card_summary', 'args': 'clean'}
            print(f"\n🔧 TOOL: tool_card_summary()  query={query!r}")
            return tool_card_summary(clean)

        # --- 8A2b. CARD + STAFF keyword (e.g. "cards per club staff") ---
        if is_non_player_query and any(kw in q for kw in ["cards", "card"]):
            clean = re.sub(r'\b(card|cards?|show|me|list|all)\b', '', q).strip()
            import fast_agent as _fa_mod
            _fa_mod._last_debug = {'query': query, 'fn': 'tool_card_summary', 'args': 'clean (staff)'}
            print(f"\n🔧 TOOL: tool_card_summary()  query={query!r}")
            return tool_card_summary(clean)

        # --- 7. STANDALONE NON-PLAYER LIST ---
        if is_non_player_query:
            filter_query = re.sub(r'\b(non|player|players?|staff|coach|coaches?|manager|managers|for|all|show|list|with|get|me)\b', '', q).strip()
            import fast_agent as _fa_mod
            _fa_mod._last_debug = {'query': query, 'fn': 'tool_non_players', 'args': 'filter_query'}
            print(f"\n🔧 TOOL: tool_non_players()  query={query!r}")
            return tool_non_players(filter_query)

        # --- 8. TOP SCORERS ---
        if any(word in q for word in ["top scorer","leading scorer", "top scorers", "golden boot"]):
            clean = re.sub(r'\b(top|scorer|scorers?|golden|boot|in|for|show|me|list|all|leagues?|divisions?)\b', '', q).strip()
            result = tool_top_scorers(clean, limit=50)
            if isinstance(result, dict) and result.get("type") == "table":
                if clean:
                    result["title"] = f"🏆 Top scorers — {clean.title()}"
                else:
                    result["title"] = f"🏆 Top Scorers — All Leagues & Divisions"
            return result

        if any(kw in q for kw in ["own goal", "own goals", "og ", "own-goal"]):
            clean = re.sub(r'\b(own.?goal|list|show|me|all|with)\b', '', q).strip()
            import fast_agent as _fa_mod

            _fa_mod._last_debug = {'query': query, 'fn': 'tool_own_goals', 'args': 'clean'}

            print(f"\n🔧 TOOL: tool_own_goals()  query={query!r}")
            return tool_own_goals(clean)

        # --- 8B. MOST APPEARANCES ---
        if any(word in q for word in ["most appearances", "most matches", "most games", "appearances", "games played", "matches played"]):
            clean = re.sub(r'\b(most|appearances?|matches?|games?|played|in|for|show|me|list|all|leagues?|divisions?)\b', '', q).strip()
            result = tool_most_appearances(clean, limit=50)
            if isinstance(result, dict) and result.get("type") == "table":
                if clean:
                    result["title"] = f"👟 Most Appearances — {clean.title()}"
                else:
                    result["title"] = f"👟 Most Appearances — All Leagues & Divisions"
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
            import fast_agent as _fa_mod

            _fa_mod._last_debug = {'query': query, 'fn': 'tool_squad_list', 'args': 'clean'}

            print(f"\n🔧 TOOL: tool_squad_list()  query={query!r}")
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
            import fast_agent as _fa_mod

            _fa_mod._last_debug = {'query': query, 'fn': 'tool_ladder', 'args': 'query'}

            print(f"\n🔧 TOOL: tool_ladder()  query={query!r}")
            return tool_ladder(query)
        if any(kw in q for kw in ["match detail", "match details", "game detail", "lineups for"]):
            import fast_agent as _fa_mod

            _fa_mod._last_debug = {'query': query, 'fn': 'tool_match_detail', 'args': 'query'}

            print(f"\n🔧 TOOL: tool_match_detail()  query={query!r}")
            return tool_match_detail(query)
        if "lineup" in q or "starting" in q:
            import fast_agent as _fa_mod

            _fa_mod._last_debug = {'query': query, 'fn': 'tool_lineups', 'args': 'query'}

            print(f"\n🔧 TOOL: tool_lineups()  query={query!r}")
            return tool_lineups(query)

        # --- PREDICT LADDER ---
        _ladder_pred_kw = ["predicted ladder", "predict ladder", "ladder after",
                           "predicted standings", "end of season ladder",
                           "where will i finish", "final ladder", "projected ladder"]
        if any(kw in q for kw in _ladder_pred_kw):
            clean    = re.sub(
                r'\b(predicted?|ladder|standings?|after|end|of|season|where|will|i|finish|final|projected?)\b',
                '', q).strip()
            club_q   = re.sub(r'\bu\d{2}\b', '', clean, flags=re.IGNORECASE).strip()
            age_q    = extract_age_group(clean) or ""
            # Extract "after N matches"
            n_m      = re.search(r'(\d+)\s*match(?:es)?', q)
            n_games  = int(n_m.group(1)) if n_m else 0
            if not club_q:
                club_q = USER_CONFIG.get("club", "heidelberg")
            import fast_agent as _fa_mod
            _fa_mod._last_debug = {'query': query, 'fn': 'tool_predict_ladder',
                                   'args': f'{club_q!r}, {age_q!r}, {n_games}'}
            print(f"\n🔧 TOOL: tool_predict_ladder()  query={query!r}")
            return tool_predict_ladder(club_q, age_q, n_games)

        # --- PREDICT MATCH ---
        if any(kw in q for kw in ["predict", "prediction", "score prediction", "preview"]):
            # "predict next match" — resolve actual next fixture first
            if "next match" in q or "next game" in q or "next fixture" in q:
                melbourne_tz = pytz.timezone('Australia/Melbourne')
                now_m = datetime.now(melbourne_tz)
                user_club_lc  = USER_CONFIG.get("club", "").lower()
                user_age_lc   = USER_CONFIG.get("age_group", "").lower()
                upcoming_fix  = []
                for f in fixtures:
                    fa   = f.get("attributes", {})
                    fh   = (fa.get("home_team_name") or "").lower()
                    faw  = (fa.get("away_team_name") or "").lower()
                    blob = f"{fh} {faw}"
                    if user_club_lc not in blob:
                        continue
                    if user_age_lc and user_age_lc not in blob:
                        continue
                    fdt = parse_date_utc_to_aest(fa.get("date", ""))
                    if fdt and fdt > now_m:
                        upcoming_fix.append((fdt, fa))
                if upcoming_fix:
                    upcoming_fix.sort(key=lambda x: x[0])
                    _, next_fa = upcoming_fix[0]
                    home_t = next_fa.get("home_team_name", "")
                    away_t = next_fa.get("away_team_name", "")
                    ag_match = re.search(r'u\d{2}', f"{home_t} {away_t}".lower())
                    ag_str = ag_match.group(0) if ag_match else user_age_lc
                    predict_q = f"{home_t} vs {away_t} {ag_str}"
                    home_team_arg = home_t
                else:
                    predict_q = query
                    home_team_arg = ""
            else:
                predict_q = query
                home_team_arg = ""
            import fast_agent as _fa_mod
            _fa_mod._last_debug = {'query': query, 'fn': 'tool_predict_match', 'args': predict_q}
            print(f"\n🔧 TOOL: tool_predict_match()  query={predict_q!r}")
            return tool_predict_match(predict_q, home_team=home_team_arg)

        # Club vs Club comparison (two recognised clubs on either side of vs/v)
        if " vs " in q or " v " in q:
            vs_parts = re.split(r'\s+v(?:s)?\s+', q)
            club_a_token = vs_parts[0].strip() if len(vs_parts) > 0 else ""
            club_b_token = vs_parts[1].strip() if len(vs_parts) > 1 else ""

            _club_words = {"fc", "sc", "afc", "city", "united", "utd", "rangers",
                           "lions", "eagles", "knights", "warriors", "magic", "thunder",
                           "greens", "cannons", "royals", "juventus", "comets", "wanderers"}

            def _token_matches_alias(token):
                """True if token matches any alias — either alias in token OR token in alias."""
                for alias in CLUB_ALIASES:
                    if alias in token or token in alias:
                        return True
                return False

            def _looks_like_club(token):
                """True if token contains a known club word suffix/keyword."""
                words = set(token.lower().split())
                return bool(words & _club_words)

            has_club_a = _token_matches_alias(club_a_token) or _looks_like_club(club_a_token)
            has_club_b = _token_matches_alias(club_b_token) or _looks_like_club(club_b_token)
            if has_club_a and has_club_b:
                import fast_agent as _fa_mod

                _fa_mod._last_debug = {'query': query, 'fn': 'tool_club_vs_club', 'args': 'query'}

                print(f"\n🔧 TOOL: tool_club_vs_club()  query={query!r}")
                return tool_club_vs_club(query)
            # Fall through to match centre for single match lookups
            import fast_agent as _fa_mod

            _fa_mod._last_debug = {'query': query, 'fn': 'tool_match_centre', 'args': 'query'}

            print(f"\n🔧 TOOL: tool_match_centre()  query={query!r}")
            return tool_match_centre(query)

        if "form" in q:
            team = normalize_team(query)
            import fast_agent as _fa_mod

            _fa_mod._last_debug = {'query': query, 'fn': 'tool_form', 'args': 'team if team else query'}

            print(f"\n🔧 TOOL: tool_form()  query={query!r}")
            return tool_form(team if team else query)
        
        # --- 11. DEFAULT FALLBACK ---
        team = normalize_team(query)
        if team:
            import fast_agent as _fa_mod

            _fa_mod._last_debug = {'query': query, 'fn': 'tool_form', 'args': 'team'}

            print(f"\n🔧 TOOL: tool_form()  query={query!r}")
            return tool_form(team)
        import fast_agent as _fa_mod

        _fa_mod._last_debug = {'query': query, 'fn': 'tool_matches', 'args': 'query'}

        print(f"\n🔧 TOOL: tool_matches()  query={query!r}")
        return tool_matches(query)