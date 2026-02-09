# fast_agent.py - ENHANCED VERSION WITH PERSONAL CONFIGURATION
"""
Dribl Soccer Stats Fast Agent - Enhanced Edition
=================================================
Features:
- Personal team configuration (Heidelberg United FC U16)
- Yellow/Red card queries
- Detailed player match-by-match stats
- Enhanced player profile with jersey, cards, etc.
- Date format: dd-mmm (e.g., 09-Feb)
"""

# fast_agent.py - FIXED VERSION
import os
import json
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
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
# 1. Load JSON data files - FIXED PATHS
# ---------------------------------------------------------

# Get the directory where this file is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

def load_json(name: str):
    """Load and parse JSON file from data directory"""
    # Try multiple possible paths
    possible_paths = [
        os.path.join(DATA_DIR, name),  # Relative to fast_agent.py
        os.path.join("data", name),    # Relative to working directory
        name                           # Absolute or in working directory
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            print(f"  📂 Loading from: {path}")
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    
    # If file doesn't exist, return empty/default data
    print(f"  ⚠️  File not found: {name}")
    
    # Return appropriate empty data structure based on filename
    if "players_summary" in name:
        return {"players": []}
    elif "competition_overview" in name:
        return {}
    elif "fixtures" in name or "results" in name or "match_centre" in name or "lineups" in name:
        return []
    else:
        return {}

print("\n" + "="*60)
print("📂 LOADING DATA FILES")
print("="*60)

# Load data with fallbacks
results = load_json("master_results.json")
print(f"  {'✅' if results else '⚠️ '} master_results.json: {len(results) if isinstance(results, list) else 0} completed matches\n")

fixtures = load_json("fixtures.json")
print(f"  {'✅' if fixtures else '⚠️ '} fixtures.json: {len(fixtures) if isinstance(fixtures, list) else 0} upcoming fixtures\n")

players_data = load_json("players_summary.json")
players_summary = players_data.get("players", [])
print(f"  {'✅' if players_summary else '⚠️ '} players_summary.json: {len(players_summary)} players indexed")

if players_summary:
    sample = players_summary[0]
    print(f"     Sample: {sample.get('first_name')} {sample.get('last_name')} ({sample.get('team_name')})\n")

match_centre_data = load_json("master_match_centre.json")
print(f"  {'✅' if match_centre_data else '⚠️ '} master_match_centre.json: {len(match_centre_data) if isinstance(match_centre_data, list) else 0} matches with events\n")

lineups_data = load_json("master_lineups.json")
print(f"  {'✅' if lineups_data else '⚠️ '} master_lineups.json: {len(lineups_data) if isinstance(lineups_data, list) else 0} match lineups\n")

competition_overview = load_json("competition_overview.json")
print(f"  {'✅' if competition_overview else '⚠️ '} competition_overview.json: {len(competition_overview)} competitions\n")

print("="*60)
print("✅ DATA LOADING COMPLETE")
print("="*60 + "\n")


# ---------------------------------------------------------
# 2. Date formatting helper
# ---------------------------------------------------------

def format_date(date_str: str) -> str:
    """Convert date string to dd-mmm format (e.g., 09-Feb)"""
    if not date_str:
        return "TBD"
    try:
        # Handle ISO format or date-only
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

# ---------------------------------------------------------
# 3. Build search indices
# ---------------------------------------------------------

print("="*60)
print("🔨 BUILDING SEARCH INDICES")
print("="*60)

def fuzzy_find(query: str, choices: List[str], threshold: int = 60) -> Optional[str]:
    if not choices:
        return None
    res = process.extractOne(query, choices, scorer=fuzz.WRatio)
    if not res:
        return None
    match, score, _ = res
    print(f"  🔍 Fuzzy: '{query}' → '{match}' ({score}%)")
    return match if score >= threshold else None

print("  🔨 Building player index...")
player_names = []
player_lookup = {}

for p in players_summary:
    first = p.get("first_name", "")
    last = p.get("last_name", "")
    full_name = f"{first} {last}".strip()
    
    if full_name:
        player_names.append(full_name)
        player_lookup[full_name.lower()] = p

print(f"  ✅ Player index: {len(player_names)} players")
print(f"     Examples: {', '.join(player_names[:3])}\n")

print("  🔨 Building team index...")
team_names = sorted({
    p.get("team_name", "")
    for p in players_summary
    if p.get("team_name")
})
print(f"  ✅ Team index: {len(team_names)} teams\n")

print("  🔨 Building league index...")
league_names = sorted({
    p.get("league_name", "")
    for p in players_summary
    if p.get("league_name")
})
print(f"  ✅ League index: {len(league_names)} leagues\n")

print("  🔨 Building competition index...")
competition_names = sorted({
    p.get("competition_name", "")
    for p in players_summary
    if p.get("competition_name")
})
print(f"  ✅ Competition index: {len(competition_names)} competitions\n")

print("="*60)
print("✅ ALL INDICES BUILT")
print("="*60 + "\n")

def fuzzy_team(q: str) -> Optional[str]:
    return fuzzy_find(q.lower(), [t.lower() for t in team_names], threshold=60)

def normalize_team(q: str) -> Optional[str]:
    best = fuzzy_team(q)
    if not best:
        return None
    return next((t for t in team_names if t.lower() == best), best)

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
# 5. FIXTURES TOOL
# ---------------------------------------------------------

def tool_fixtures(query: str = "", limit: int = 10, use_user_team: bool = False) -> str:
    """
    Show upcoming fixtures
    
    Args:
        query: Optional team name filter
        limit: Maximum number of fixtures to show
        use_user_team: If True and no query provided, use user's team from config
    """
    # Use user's team if no query provided and use_user_team is True
    if use_user_team and not query:
        query = USER_CONFIG["team"]
        print(f"  👤 Using your team: '{query}'")
    
    print(f"  📅 Searching fixtures: '{query}' (limit: {limit})")
    
    # Parse today's date
    today = datetime.now().date()
    
    # Filter upcoming fixtures
    upcoming = []
    for f in fixtures:
        attrs = f.get("attributes", {})
        date_str = attrs.get("date", "")
        
        # Parse fixture date
        fixture_date = parse_date(date_str)
        if fixture_date >= today:
            upcoming.append((fixture_date, attrs))
    
    # Sort by date
    upcoming.sort(key=lambda x: x[0])
    
    # Filter by team if query provided
    if query:
        team = normalize_team(query) or query
        filtered = []
        for date, attrs in upcoming:
            home = attrs.get("home_team_name", "")
            away = attrs.get("away_team_name", "")
            
            # Match team name
            if team.lower() in home.lower() or team.lower() in away.lower():
                filtered.append((date, attrs))
        
        upcoming = filtered
    
    if not upcoming:
        team_name = query if query else "any team"
        return f"❌ No upcoming fixtures found for {team_name}"
    
    # Limit results
    upcoming = upcoming[:limit]
    
    # Format output - make it personal if using user team
    if use_user_team and query == USER_CONFIG["team"]:
        lines = [f"📅 **Your Upcoming Matches** ({len(upcoming)} matches)\n"]
    else:
        team_display = query if query else "All Teams"
        lines = [f"📅 **Upcoming Fixtures - {team_display}** ({len(upcoming)} matches)\n"]
    
    for i, (fixture_date, attrs) in enumerate(upcoming, 1):
        home = attrs.get("home_team_name", "Unknown")
        away = attrs.get("away_team_name", "Unknown")
        venue = attrs.get("venue", "TBD")
        time = attrs.get("time", "TBD")
        competition = attrs.get("competition_name", "")
        
        # Format date
        date_display = fixture_date.strftime("%d-%b-%Y (%a)")
        
        # Calculate days until match
        days_until = (fixture_date - today).days
        if days_until == 0:
            days_str = "🔴 TODAY!"
        elif days_until == 1:
            days_str = "⚠️ Tomorrow"
        elif days_until <= 7:
            days_str = f"🟡 In {days_until} days"
        else:
            days_str = f"🟢 In {days_until} days"
        
        # Determine home/away for user's team
        if use_user_team and query == USER_CONFIG["team"]:
            if USER_CONFIG["club"].lower() in home.lower():
                match_type = "🏠 HOME"
                opponent = away
            else:
                match_type = "✈️ AWAY"
                opponent = home
            
            lines.append(f"**Match {i}:** {days_str}")
            lines.append(f"   📅 {date_display} at {time}")
            lines.append(f"   {match_type} vs {opponent}")
            lines.append(f"   🏟️ {venue}")
            if competition:
                lines.append(f"   🏆 {competition}")
            lines.append("")
        else:
            lines.append(f"🗓️  **{date_display}** {days_str}")
            lines.append(f"   ⏰ {time}")
            lines.append(f"   🏟️ {venue}")
            lines.append(f"   ⚽ {home} vs {away}")
            if competition:
                lines.append(f"   🏆 {competition}")
            lines.append("")
    
    return "\n".join(lines)

# ---------------------------------------------------------
# 6. CARD QUERIES
# ---------------------------------------------------------

def tool_yellow_cards(query: str = "", show_details: bool = False) -> str:
    """List all players with yellow cards"""
    print(f"  🟨 Searching yellow cards: '{query}'")
    
    players_with_yellows = [
        p for p in players_summary 
        if p.get("stats", {}).get("yellow_cards", 0) > 0
    ]
    
    if query:
        q = query.lower()
        players_with_yellows = [
            p for p in players_with_yellows
            if (q in p.get("team_name", "").lower() or
                q in p.get("league_name", "").lower() or
                q in p.get("competition_name", "").lower())
        ]
    
    if not players_with_yellows:
        return "❌ No players with yellow cards found"
    
    players_with_yellows.sort(key=lambda x: x.get("stats", {}).get("yellow_cards", 0), reverse=True)
    
    if show_details:
        lines = [f"🟨 **Players with Yellow Cards** ({len(players_with_yellows)} total)\n"]
        
        for p in players_with_yellows[:50]:
            stats = p.get("stats", {})
            yellows = stats.get("yellow_cards", 0)
            
            lines.append(
                f"👤 **{p.get('first_name')} {p.get('last_name')}** (#{p.get('jersey')})\n"
                f"   {p.get('team_name')} | 🟨 {yellows} card(s)"
            )
            
            matches = p.get("matches", [])
            for m in matches:
                if m.get("yellow_cards", 0) > 0:
                    venue = "🏠" if m.get('home_or_away') == 'home' else "✈️"
                    date_str = format_date(m.get('date', ''))
                    lines.append(
                        f"   {venue} vs {m.get('opponent_team_name')} - {date_str} - 🟨 {m.get('yellow_cards')}"
                    )
            lines.append("")
        
        return "\n".join(lines)
    else:
        lines = [f"🟨 **Yellow Cards Summary** ({len(players_with_yellows)} players)\n"]
        lines.append("Player | Team | Cards")
        lines.append("-" * 60)
        
        for p in players_with_yellows[:30]:
            stats = p.get("stats", {})
            yellows = stats.get("yellow_cards", 0)
            name = f"{p.get('first_name')} {p.get('last_name')}"
            team = p.get('team_name', '')[:30]
            lines.append(f"{name[:25]:<25} | {team:<30} | 🟨 {yellows}")
        
        if len(players_with_yellows) > 30:
            lines.append(f"\n... and {len(players_with_yellows) - 30} more")
        
        lines.append(f"\n💡 Use 'yellow cards details' to see match-by-match breakdown")
        
        return "\n".join(lines)


def tool_red_cards(query: str = "", show_details: bool = False) -> str:
    """List all players with red cards"""
    print(f"  🟥 Searching red cards: '{query}'")
    
    players_with_reds = [
        p for p in players_summary 
        if p.get("stats", {}).get("red_cards", 0) > 0
    ]
    
    if query:
        q = query.lower()
        players_with_reds = [
            p for p in players_with_reds
            if (q in p.get("team_name", "").lower() or
                q in p.get("league_name", "").lower() or
                q in p.get("competition_name", "").lower())
        ]
    
    if not players_with_reds:
        return "❌ No players with red cards found"
    
    players_with_reds.sort(key=lambda x: x.get("stats", {}).get("red_cards", 0), reverse=True)
    
    if show_details:
        lines = [f"🟥 **Players with Red Cards** ({len(players_with_reds)} total)\n"]
        
        for p in players_with_reds:
            stats = p.get("stats", {})
            reds = stats.get("red_cards", 0)
            
            lines.append(
                f"👤 **{p.get('first_name')} {p.get('last_name')}** (#{p.get('jersey')})\n"
                f"   {p.get('team_name')} | 🟥 {reds} card(s)"
            )
            
            matches = p.get("matches", [])
            for m in matches:
                if m.get("red_cards", 0) > 0:
                    venue = "🏠" if m.get('home_or_away') == 'home' else "✈️"
                    date_str = format_date(m.get('date', ''))
                    lines.append(
                        f"   {venue} vs {m.get('opponent_team_name')} - {date_str} - 🟥 RED CARD"
                    )
            lines.append("")
        
        return "\n".join(lines)
    else:
        lines = [f"🟥 **Red Cards Summary** ({len(players_with_reds)} players)\n"]
        lines.append("Player | Team | Cards")
        lines.append("-" * 60)
        
        for p in players_with_reds:
            stats = p.get("stats", {})
            reds = stats.get("red_cards", 0)
            name = f"{p.get('first_name')} {p.get('last_name')}"
            team = p.get('team_name', '')[:30]
            lines.append(f"{name[:25]:<25} | {team:<30} | 🟥 {reds}")
        
        return "\n".join(lines)


def tool_top_scorers(query: str = "", limit: int = 20):
    """List top goal scorers - returns data for table display"""
    print(f"  ⚽ Top scorers: '{query}' (limit: {limit})")
    
    scorers = [
        p for p in players_summary 
        if p.get("stats", {}).get("goals", 0) > 0
    ]
    
    if query:
        q = query.lower()
        scorers = [
            p for p in scorers
            if (q in p.get("team_name", "").lower() or
                q in p.get("league_name", "").lower() or
                q in p.get("competition_name", "").lower())
        ]
    
    if not scorers:
        return {"type": "error", "message": "❌ No goal scorers found"}
    
    scorers.sort(key=lambda x: x.get("stats", {}).get("goals", 0), reverse=True)
    
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
    
    return {"type": "table", "data": data, "title": f"⚽ Top Scorers ({len(scorers)} players with goals)"}


def tool_team_stats(query: str = "") -> str:
    """Get team statistics including squad overview and top performers"""
    print(f"  📊 Team stats: '{query}'")
    
    # If query is just an age group, use user's club
    age_groups = ['u13', 'u14', 'u15', 'u16', 'u17', 'u18']
    query_lower = query.lower().strip()
    
    # Check if query is just an age group
    if query_lower in age_groups:
        team_query = f"{USER_CONFIG['club']} {query.upper()}"
        print(f"  👤 Using your club: '{team_query}'")
    else:
        team_query = query
    
    # Find matching team
    team = normalize_team(team_query) or team_query
    
    players = [p for p in players_summary if team.lower() in p.get("team_name", "").lower()]
    
    if not players:
        return f"❌ No players found for team: {query}"
    
    lines = [f"📊 **Team Statistics: {players[0].get('team_name', team)}**\n"]
    
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
            if i >= 5:  # Show top 5
                break
    
    # Most disciplined (most cards)
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
    for r in results:
        a = r.get("attributes", {})
        home = a.get("home_team_name", "")
        away = a.get("away_team_name", "")
        if team.lower() in home.lower() or team.lower() in away.lower():
            team_results.append(a)

    team_results.sort(key=lambda x: x.get("date", ""), reverse=True)
    if team_results:
        lines.append(f"\n**📅 Recent Results:**")
        for a in team_results[:5]:
            date_str = format_date(a.get('date', ''))
            hs = a.get('home_score')
            as_ = a.get('away_score')
            
            # Determine if win/loss/draw
            is_home = team.lower() in a.get('home_team_name', '').lower()
            if is_home:
                result = "🟢 W" if int(hs) > int(as_) else ("🔴 L" if int(hs) < int(as_) else "🟡 D")
            else:
                result = "🟢 W" if int(as_) > int(hs) else ("🔴 L" if int(as_) < int(hs) else "🟡 D")
            
            lines.append(f"  {result} {date_str}: {a.get('home_team_name')} {hs}-{as_} {a.get('away_team_name')}")

    return "\n".join(lines)


def tool_competition_overview(query: str = ""):
    """Display competition overview showing club rankings across all age groups"""
    print(f"  🏆 Competition overview: '{query}'")
    
    # Normalize query to match competition names
    q = query.upper().strip()
    
    # Map common queries to competition keys
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
    
    # Find matching competition
    competition_key = None
    for key, value in comp_mapping.items():
        if key in q or value in q:
            competition_key = value
            break
    
    # If no query provided or not found, list all competitions
    if not competition_key or competition_key not in competition_overview:
        # Return list of available competitions
        lines = ["🏆 **Available Competitions:**\n"]
        for comp in sorted(competition_overview.keys()):
            club_count = len(competition_overview[comp]["clubs"])
            age_groups = competition_overview[comp]["age_groups"]
            lines.append(f"**{comp}**: {club_count} clubs, {len(age_groups)} age groups ({', '.join(age_groups)})")
        lines.append("\n💡 Try: 'YPL1 overview', 'YPL2 standings', 'competition overview YSL NW'")
        return "\n".join(lines)
    
    # Get competition data
    comp_data = competition_overview[competition_key]
    age_groups = sorted(comp_data["age_groups"])
    clubs = comp_data["clubs"]
    
    # Build table data
    table_data = []
    
    for club_data in clubs:
        row = {
            "Rank": club_data["overall_rank"],
            "Club": club_data["club"]
        }
        
        # Add position for each age group
        for age in age_groups:
            if age in club_data["age_groups"]:
                row[age] = club_data["age_groups"][age]["position"]
            else:
                row[age] = "-"
        
        # Add summary columns
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
# 7. ENHANCED PLAYER STATS
# ---------------------------------------------------------

def tool_players(query: str, detailed: bool = False) -> str:
    """Search for player and show stats"""
    print(f"  🔍 Searching player: '{query}' (detailed={detailed})")
    
    q = query.lower().strip()
    
    # Exact substring match
    exact_matches = []
    for full_name, player_data in player_lookup.items():
        if q in full_name:
            exact_matches.append(player_data)
    
    if exact_matches:
        print(f"  ✅ Found {len(exact_matches)} matches")
        
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
                        performance.append(f"⚽ {m.get('goals')} goal(s)")
                    if m.get('yellow_cards', 0) > 0:
                        performance.append(f"🟨 Yellow")
                    if m.get('red_cards', 0) > 0:
                        performance.append(f"🟥 Red")
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
                    goals_str = f"⚽×{m.get('goals')}" if m.get('goals', 0) > 0 else ""
                    cards_str = ""
                    if m.get('yellow_cards', 0) > 0:
                        cards_str += "🟨"
                    if m.get('red_cards', 0) > 0:
                        cards_str += "🟥"
                    
                    lines.append(
                        f"   {venue} vs {m.get('opponent_team_name')} - {date_str} {goals_str} {cards_str}"
                    )
                
                lines.append(f"\n💡 Use 'details for {p.get('first_name')} {p.get('last_name')}' for match-by-match breakdown")
            
            return "\n".join(lines)
        else:
            lines = [f"Found {len(exact_matches)} players:\n"]
            for p in exact_matches[:10]:
                stats = p.get("stats", {})
                lines.append(
                    f"👤 **{p.get('first_name')} {p.get('last_name')}** (#{p.get('jersey')})\n"
                    f"   {p.get('team_name')}\n"
                    f"   ⚽ {stats.get('goals', 0)} goals | 🎮 {stats.get('matches_played', 0)} matches | "
                    f"🟨 {stats.get('yellow_cards', 0)} | 🟥 {stats.get('red_cards', 0)}\n"
                )
            return "\n".join(lines)
    
    # Fuzzy match fallback
    print(f"  🔍 Trying fuzzy search...")
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
# 8. Other tools
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
    team = normalize_team(query) or query
    lines = [f"🏟️ **{team}**\n"]

    players = [p for p in players_summary if team.lower() in p.get("team_name", "").lower()]
    
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
    
    team_results = []
    for r in results:
        a = r.get("attributes", {})
        home = a.get("home_team_name", "")
        away = a.get("away_team_name", "")
        if team.lower() in home.lower() or team.lower() in away.lower():
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
# 9. ENHANCED Smart Query Router
# ---------------------------------------------------------

class FastQueryRouter:
    """Enhanced pattern-based query router with personal team support"""
    
    def __init__(self):
        print(f"✅ Router ready! {len(team_names)} teams, {len(player_names)} players\n")
        
    def process(self, query: str):
        """Route query to appropriate handler"""
        q = query.lower().strip()
        
        print(f"🔍 Query: '{query}'")
        
        # COMPETITION OVERVIEW (HIGH PRIORITY - before other routes)
        comp_overview_keywords = ['competition overview', 'competition standings', 'ypl1 overview', 'ypl2 overview', 
                                   'ysl overview', 'vpl overview', 'club rankings', 'overall standings']
        if any(keyword in q for keyword in comp_overview_keywords) or any(comp in q for comp in ['ypl1', 'ypl2', 'ysl nw', 'ysl se', 'vpl']):
            # Check if it's specifically asking for overview/standings
            if 'overview' in q or 'standings' in q or 'ranking' in q or 'competition' in q:
                print("✅ Route: COMPETITION OVERVIEW")
                return tool_competition_overview(query)
        
        # PERSONAL FIXTURES (detect "my", "i", "our")
        personal_keywords = ['my next', 'when do i play', 'where do i play', 'my schedule', 'when is my', 'where is my', 'our next']
        is_personal_query = any(keyword in q for keyword in personal_keywords)
        
        # FIXTURES / NEXT MATCH (HIGH PRIORITY)
        fixture_keywords = [
            'next match', 'next game', 'upcoming', 'when do i play',
            'where do i play', 'my next', 'schedule', 'fixture', 'fixtures',
            'when is my', 'where is my', 'our next'
        ]
        if any(keyword in q for keyword in fixture_keywords):
            print("✅ Route: FIXTURES" + (" (PERSONAL)" if is_personal_query else ""))
            
            if is_personal_query:
                return tool_fixtures(query="", limit=5, use_user_team=True)
            else:
                team_query = re.sub(r'\b(next|match|game|upcoming|when|where|do|i|play|my|schedule|fixtures?|is)\b', '', q).strip()
                limit = 5 if team_query else 10
                return tool_fixtures(team_query, limit, use_user_team=False)
        
        # YELLOW CARDS
        if "yellow card" in q or "yellows" in q:
            print("✅ Route: YELLOW CARDS")
            show_details = "detail" in q
            filter_query = re.sub(r'\b(yellow|card|cards|details?|show|list|with)\b', '', q).strip()
            return tool_yellow_cards(filter_query, show_details)
        
        # RED CARDS
        if "red card" in q or "reds" in q:
            print("✅ Route: RED CARDS")
            show_details = "detail" in q
            filter_query = re.sub(r'\b(red|card|cards|details?|show|list|with)\b', '', q).strip()
            return tool_red_cards(filter_query, show_details)
        
        # TOP SCORERS
        if "top scorer" in q or "leading scorer" in q or "goal scorer" in q:
            print("✅ Route: TOP SCORERS")
            limit_match = re.search(r'top (\d+)', q)
            limit = int(limit_match.group(1)) if limit_match else 20
            filter_query = re.sub(r'\b(top|scorer|scorers?|leading|goal|goals?|\d+)\b', '', q).strip()
            return tool_top_scorers(filter_query, limit)
        
        # TEAM STATS (detect "stats for U13" or "stats for [team] U13")
        if "stats for" in q:
            clean = re.sub(r'\b(stats?|for)\b', '', q).strip()
            
            # Check if it's just an age group (u13, u14, etc.)
            age_groups = ['u13', 'u14', 'u15', 'u16', 'u17', 'u18']
            if clean.lower() in age_groups:
                print("✅ Route: TEAM STATS (personal)")
                return tool_team_stats(clean)
            
            # Check if it looks like a team query (contains team name)
            # If it has a team name, it's a team stats query
            team_keywords = ['fc', 'sc', 'united', 'city', 'rovers', 'wanderers']
            if any(keyword in clean.lower() for keyword in team_keywords) or any(age in clean.lower() for age in age_groups):
                print("✅ Route: TEAM STATS")
                return tool_team_stats(clean)
            
            # Otherwise, it's a player stats query
            print("✅ Route: PLAYER STATS")
            return tool_players(clean, detailed=False)
        
        # PLAYER STATS (with details mode)
        if any(word in q for word in ["player", "show me"]) or "details for" in q:
            print("✅ Route: PLAYER STATS")
            detailed = "detail" in q
            clean = re.sub(r'\b(stats?|for|player|show|me|get|find|tell|about|details?)\b', '', q).strip()
            return tool_players(clean, detailed)
        
        # LADDER
        if any(word in q for word in ["ladder", "table", "standings"]):
            print("✅ Route: LADDER")
            return tool_ladder(query)
        
        # LINEUP
        if "lineup" in q or "starting" in q:
            print("✅ Route: LINEUP")
            return tool_lineups(query)
        
        # MATCH RESULT
        if " vs " in q or " v " in q:
            print("✅ Route: MATCH RESULT")
            return tool_match_centre(query)
        
        # TEAM FORM
        if "form" in q:
            print("✅ Route: TEAM FORM")
            team = normalize_team(query)
            return tool_form(team if team else query)
        
        # TEAM OVERVIEW
        if "team" in q or "overview" in q:
            print("✅ Route: TEAM OVERVIEW")
            team = normalize_team(query)
            return tool_team_overview(team if team else query)
        
        # DEFAULT
        print("✅ Route: DEFAULT (team search)")
        team = normalize_team(query)
        if team:
            return tool_form(team)
        return tool_matches(query)

# ---------------------------------------------------------
# 10. Interactive CLI
# ---------------------------------------------------------

def main():
    """Main interactive loop"""
    print("\n" + "="*60)
    print("🚀 DRIBL BOT - PERSONALIZED EDITION!")
    print("="*60 + "\n")
    
    router = FastQueryRouter()
    
    print("📝 Try these queries:\n")
    
    print("🏆 Competition Overview:")
    print("  - YPL1 overview")
    print("  - YPL2 standings")
    print("  - competition overview")
    print("  - YSL NW overview")
    
    print("\n📅 Personal Fixtures (auto-uses your team):")
    print("  - when is my next match")
    print("  - where do i play next")
    print("  - my schedule")
    
    print("\n📅 Other Fixtures:")
    print("  - upcoming fixtures")
    print("  - next match for Essendon Royals")
    
    print("\n🟨 Yellow Cards:")
    print("  - list players with yellow cards")
    print("  - yellow cards details")
    print("  - yellow cards for Essendon Royals")
    
    print("\n🟥 Red Cards:")
    print("  - list players with red cards")
    print("  - red cards details")
    
    print("\n⚽ Top Scorers:")
    print("  - top scorers")
    print("  - top 10 scorers")
    print("  - top scorers U16 YPL1")
    
    print("\n📊 Team Stats:")
    print("  - stats for U13  (your Heidelberg U13 team)")
    print("  - stats for Avondale U13  (Avondale's team)")
    print("  - stats for Essendon Royals U16")
    
    print("\n👤 Enhanced Player Stats:")
    print("  - stats for Shaurya jaswal")
    print("  - details for Shaurya jaswal")
    
    print("\n🏟️ Team & Other:")
    print("  - Essendon Royals SC U16 form")
    print("  - U16 YPL1 Boys ladder")
    print("  - Essendon vs South Melbourne")
    
    print("\nType 'exit' to quit\n")
    print("="*60 + "\n")
    
    while True:
        try:
            q = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        
        if not q or q.lower() in {"exit", "quit", "q"}:
            print("\n👋 Thanks for using Dribl Bot!")
            break
        
        start = datetime.now()
        try:
            response = router.process(q)
            elapsed = (datetime.now() - start).total_seconds()
            
            # Handle different response types
            if isinstance(response, dict):
                if response.get("type") == "table":
                    print(f"\n{response.get('title')}\n")
                    data = response.get('data', [])
                    if data:
                        # Print as formatted table
                        import pandas as pd
                        df = pd.DataFrame(data)
                        print(df.to_string(index=False))
                elif response.get("type") == "error":
                    print(f"\n{response.get('message')}")
            else:
                # Regular text response
                print(f"\n{response}\n")
            
            print(f"⚡ {elapsed:.3f}s\n" + "-"*60 + "\n")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
