import streamlit as st
from fast_agent import FastQueryRouter, format_date, format_date_full
import time
import pandas as pd
import json
import os
import re
from collections import defaultdict

# ---------------------------------------------------------
# Page setup
# ---------------------------------------------------------

st.set_page_config(
    page_title="Dribl Football Intelligence",
    page_icon="⚽",
    layout="wide"
)

# ---------------------------------------------------------
# Get base directory (where app.py is located)
# ---------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

print(f"BASE_DIR: {BASE_DIR}")
print(f"DATA_DIR: {DATA_DIR}")
print(f"Current working directory: {os.getcwd()}")

# ---------------------------------------------------------
# Router
# ---------------------------------------------------------

@st.cache_resource
def load_router():
    return FastQueryRouter()

router = load_router()

# ---------------------------------------------------------
# Session state
# ---------------------------------------------------------

if "level" not in st.session_state:
    st.session_state["level"] = "league"

if "selected_league" not in st.session_state:
    st.session_state["selected_league"] = None

if "selected_competition" not in st.session_state:
    st.session_state["selected_competition"] = None

if "selected_club" not in st.session_state:
    st.session_state["selected_club"] = None

if "selected_player" not in st.session_state:
    st.session_state["selected_player"] = None

if "selected_match_id" not in st.session_state:
    st.session_state["selected_match_id"] = None

if "last_search" not in st.session_state:
    st.session_state["last_search"] = ""

# ---------------------------------------------------------
# Data loaders - FIXED PATHS
# ---------------------------------------------------------

@st.cache_resource
def load_master_results():
    """Load master_results.json - handle different file structures"""
    path = os.path.join(DATA_DIR, "master_results.json")
    
    # Debug: Check if file exists
    st.sidebar.write(f"🔍 Looking for results at: {path}")
    st.sidebar.write(f"📁 File exists: {os.path.exists(path)}")
    
    if not os.path.exists(path):
        st.sidebar.error(f"❌ File not found: {path}")
        return []
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Debug: Show data structure
        st.sidebar.write(f"📊 Results data type: {type(data)}")
        if isinstance(data, dict):
            st.sidebar.write(f"📊 Results dict keys: {list(data.keys())}")
        
        # Handle different JSON structures
        if isinstance(data, dict):
            # Try common key names
            if "results" in data:
                st.sidebar.info("✅ Found 'results' key")
                return data["results"]
            elif "data" in data:
                st.sidebar.info("✅ Found 'data' key")
                return data["data"]
            elif "matches" in data:
                st.sidebar.info("✅ Found 'matches' key")
                return data["matches"]
            else:
                # Check if values are lists
                for key, value in data.items():
                    if isinstance(value, list):
                        st.sidebar.info(f"✅ Using list from key: {key}")
                        return value
                # If no list found, return empty
                st.sidebar.warning("⚠️ No list found in dict")
                return []
        
        elif isinstance(data, list):
            st.sidebar.info(f"✅ Direct list with {len(data)} items")
            return data
        
        else:
            st.sidebar.warning(f"⚠️ Unexpected data type: {type(data)}")
            return []
            
    except Exception as e:
        st.sidebar.error(f"❌ Error loading results: {str(e)}")
        import traceback
        st.sidebar.code(traceback.format_exc())
        return []

@st.cache_resource
def load_fixtures():
    """Load fixtures.json - handle different file structures"""
    path = os.path.join(DATA_DIR, "fixtures.json")
    
    st.sidebar.write(f"🔍 Looking for fixtures at: {path}")
    st.sidebar.write(f"📁 File exists: {os.path.exists(path)}")
    
    if not os.path.exists(path):
        st.sidebar.error(f"❌ File not found: {path}")
        return []
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        st.sidebar.write(f"📊 Fixtures data type: {type(data)}")
        if isinstance(data, dict):
            st.sidebar.write(f"📊 Fixtures dict keys: {list(data.keys())}")
        
        if isinstance(data, dict):
            if "fixtures" in data:
                st.sidebar.info("✅ Found 'fixtures' key")
                return data["fixtures"]
            elif "data" in data:
                st.sidebar.info("✅ Found 'data' key")
                return data["data"]
            elif "matches" in data:
                st.sidebar.info("✅ Found 'matches' key")
                return data["matches"]
            else:
                for key, value in data.items():
                    if isinstance(value, list):
                        st.sidebar.info(f"✅ Using list from key: {key}")
                        return value
                st.sidebar.warning("⚠️ No list found in dict")
                return []
        
        elif isinstance(data, list):
            st.sidebar.info(f"✅ Direct list with {len(data)} items")
            return data
        
        else:
            st.sidebar.warning(f"⚠️ Unexpected data type: {type(data)}")
            return []
            
    except Exception as e:
        st.sidebar.error(f"❌ Error loading fixtures: {str(e)}")
        import traceback
        st.sidebar.code(traceback.format_exc())
        return []

@st.cache_resource
def load_players_summary():
    """Load players_summary.json"""
    path = os.path.join(DATA_DIR, "players_summary.json")
    
    st.sidebar.write(f"🔍 Looking for players at: {path}")
    st.sidebar.write(f"📁 File exists: {os.path.exists(path)}")
    
    if not os.path.exists(path):
        st.sidebar.error(f"❌ File not found: {path}")
        return {"players": []}
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        st.sidebar.write(f"📊 Players data type: {type(data)}")
        
        if isinstance(data, dict):
            if "players" in data:
                st.sidebar.info(f"✅ Found 'players' key with {len(data['players'])} players")
                return data
            else:
                # Maybe it's already the players list?
                for key, value in data.items():
                    if isinstance(value, list):
                        st.sidebar.info(f"✅ Found list in key: {key}")
                        return {"players": value}
                st.sidebar.warning("⚠️ No players list found")
                return {"players": []}
        
        elif isinstance(data, list):
            st.sidebar.info(f"✅ Direct list with {len(data)} players")
            return {"players": data}
        
        else:
            st.sidebar.warning(f"⚠️ Unexpected data type: {type(data)}")
            return {"players": []}
            
    except Exception as e:
        st.sidebar.error(f"❌ Error loading players: {str(e)}")
        import traceback
        st.sidebar.code(traceback.format_exc())
        return {"players": []}

@st.cache_resource
def load_competition_overview():
    """Load competition_overview.json"""
    path = os.path.join(DATA_DIR, "competition_overview.json")
    
    st.sidebar.write(f"🔍 Looking for competition overview at: {path}")
    st.sidebar.write(f"📁 File exists: {os.path.exists(path)}")
    
    if not os.path.exists(path):
        st.sidebar.error(f"❌ File not found: {path}")
        return {}
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        st.sidebar.write(f"📊 Competition overview data type: {type(data)}")
        
        if isinstance(data, dict):
            st.sidebar.info(f"✅ Loaded competition overview")
            return data
        else:
            st.sidebar.warning(f"⚠️ Unexpected data type: {type(data)}")
            return {}
            
    except Exception as e:
        st.sidebar.error(f"❌ Error loading competition overview: {str(e)}")
        import traceback
        st.sidebar.code(traceback.format_exc())
        return {}

# ---------------------------------------------------------
# Helpers: club name normalization and extraction
# ---------------------------------------------------------

def base_club_name(team_name: str) -> str:
    """Return the base club name without age suffix like ' U18'."""
    if not team_name:
        return ""
    
    # Remove age group suffixes: U13, U14, U15, U16, U17, U18, U19, U20, U21
    # Pattern: space followed by U and 2 digits at the end of string
    pattern = r'\s+U\d{2}$'
    cleaned = re.sub(pattern, '', team_name).strip()
    return cleaned

def extract_league_from_league_name(league_name: str) -> str:
    if not league_name:
        return "Other"
    
    league_name_lower = str(league_name).lower()
    
    # Check for patterns
    if "ypl1" in league_name_lower:
        return "YPL1"
    if "ypl2" in league_name_lower:
        return "YPL2"
    if "ysl" in league_name_lower and ("north-west" in league_name_lower or "nw" in league_name_lower):
        return "YSL NW"
    if "ysl" in league_name_lower and ("south-east" in league_name_lower or "se" in league_name_lower):
        return "YSL SE"
    if "vpl men" in league_name_lower:
        return "VPL Men"
    if "vpl women" in league_name_lower:
        return "VPL Women"
    
    # Also check for YSL without region
    if "ysl" in league_name_lower:
        return "YSL"
    
    return "Other"

def extract_competition_from_league_name(league_name: str) -> str:
    if not league_name:
        return league_name
    parts = league_name.split()
    if len(parts) < 2:
        return league_name
    age = parts[0]
    if "YPL1" in league_name:
        return f"{age} YPL1"
    if "YPL2" in league_name:
        return f"{age} YPL2"
    if "YSL Boys - North-West" in league_name:
        return f"{age} YSL NW"
    if "YSL Boys - South-East" in league_name:
        return f"{age} YSL SE"
    return league_name

def get_all_leagues(results, fixtures):
    leagues = set()

    print(f"DEBUG: Processing {len(results)} results and {len(fixtures)} fixtures")
    
    for item in results:
        if not isinstance(item, dict):
            continue
            
        # Try to get league name from different possible locations
        league_name = None
        
        # Case 1: Nested in attributes
        if "attributes" in item:
            attrs = item.get("attributes", {})
            league_name = attrs.get("league_name")
            # Also check other possible keys
            if not league_name:
                league_name = attrs.get("competition_name") or attrs.get("league")
        
        # Case 2: Direct key
        if not league_name:
            league_name = item.get("league_name") or item.get("competition_name") or item.get("league")
        
        if league_name:
            extracted = extract_league_from_league_name(str(league_name))
            print(f"DEBUG: Found league '{league_name}' -> extracted '{extracted}'")
            if extracted != "Other":
                leagues.add(extracted)

    for item in fixtures:
        if not isinstance(item, dict):
            continue
            
        league_name = None
        
        if "attributes" in item:
            attrs = item.get("attributes", {})
            league_name = attrs.get("league_name")
            if not league_name:
                league_name = attrs.get("competition_name") or attrs.get("league")
        
        if not league_name:
            league_name = item.get("league_name") or item.get("competition_name") or item.get("league")
        
        if league_name:
            extracted = extract_league_from_league_name(str(league_name))
            if extracted != "Other":
                leagues.add(extracted)

    leagues = sorted(list(leagues))
    print(f"DEBUG: Final leagues list: {leagues}")
    return leagues

def get_competitions_for_league(results, fixtures, league):
    comps = set()

    for item in results:
        attrs = item.get("attributes", {})
        league_name = attrs.get("league_name")
        if league_name and extract_league_from_league_name(league_name) == league:
            comps.add(extract_competition_from_league_name(league_name))

    for item in fixtures:
        attrs = item.get("attributes", {})
        league_name = attrs.get("league_name")
        if league_name and extract_league_from_league_name(league_name) == league:
            comps.add(extract_competition_from_league_name(league_name))

    return sorted(list(comps))

def get_results_for_competition(results, competition):
    matches = []
    for item in results:
        attrs = item.get("attributes", {})
        league_name = attrs.get("league_name")
        status = attrs.get("status")
        if league_name and status == "complete":
            if extract_competition_from_league_name(league_name) == competition:
                matches.append(item)
    return matches

# ---------------------------------------------------------
# Matches and players helpers
# ---------------------------------------------------------

def get_matches_for_club_in_comp(results, club_name, competition):
    """Return completed matches in the competition where either team base name equals club_name."""
    matches = []
    for item in results:
        attrs = item.get("attributes", {})
        league_name = attrs.get("league_name")
        status = attrs.get("status")
        if status != "complete":
            continue
        if extract_competition_from_league_name(league_name) != competition:
            continue
        home = attrs.get("home_team_name")
        away = attrs.get("away_team_name")
        home_base = base_club_name(home)
        away_base = base_club_name(away)
        if home_base == club_name or away_base == club_name:
            matches.append(item)
    return matches

def get_players_for_club(players_data, club_name):
    """Return players whose team base name matches club_name."""
    players = []
    for p in players_data.get("players", []):
        team = p.get("team_name", "")
        if base_club_name(team) == club_name:
            players.append(p)
    return players

def get_matches_for_player(player):
    return player.get("matches", [])

def player_played_in_match(player, match_hash_id):
    for m in player.get("matches", []):
        if m.get("match_hash_id") == match_hash_id:
            return True
    return False

# ---------------------------------------------------------
# Ladder computation
# ---------------------------------------------------------

def compute_ladder_from_results(results_for_comp):
    table = defaultdict(lambda: {
        "club": "",
        "played": 0,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "gf": 0,
        "ga": 0,
        "gd": 0,
        "points": 0,
    })

    for item in results_for_comp:
        attrs = item.get("attributes", {})
        home = attrs.get("home_team_name")
        away = attrs.get("away_team_name")
        hs = attrs.get("home_score")
        as_ = attrs.get("away_score")

        if home is None or away is None or hs is None or as_ is None:
            continue

        try:
            hs = int(hs)
            as_ = int(as_)
        except Exception:
            continue

        for team in [home, away]:
            if table[team]["club"] == "":
                table[team]["club"] = team

        table[home]["played"] += 1
        table[away]["played"] += 1

        table[home]["gf"] += hs
        table[home]["ga"] += as_
        table[away]["gf"] += as_
        table[away]["ga"] += hs

        if hs > as_:
            table[home]["wins"] += 1
            table[away]["losses"] += 1
            table[home]["points"] += 3
        elif hs < as_:
            table[away]["wins"] += 1
            table[home]["losses"] += 1
            table[away]["points"] += 3
        else:
            table[home]["draws"] += 1
            table[away]["draws"] += 1
            table[home]["points"] += 1
            table[away]["points"] += 1

    for team, row in table.items():
        row["gd"] = row["gf"] - row["ga"]

    ladder = sorted(
        table.values(),
        key=lambda r: (
            -r["points"],
            -r["gd"],
            -r["gf"],
            r["ga"],
            r["club"].lower(),
        )
    )

    return ladder

# ---------------------------------------------------------
# Navigation helpers
# ---------------------------------------------------------

def restart_to_top():
    st.session_state["level"] = "league"
    st.session_state["selected_league"] = None
    st.session_state["selected_competition"] = None
    st.session_state["selected_club"] = None
    st.session_state["selected_player"] = None
    st.session_state["selected_match_id"] = None

def back_one_level():
    lvl = st.session_state["level"]
    if lvl == "competition":
        st.session_state["level"] = "league"
        st.session_state["selected_league"] = None
    elif lvl == "ladder_clubs":
        st.session_state["level"] = "competition"
        st.session_state["selected_competition"] = None
        st.session_state["selected_club"] = None
        st.session_state["selected_match_id"] = None
    elif lvl == "matches":
        st.session_state["level"] = "ladder_clubs"
        st.session_state["selected_player"] = None

# ---------------------------------------------------------
# Header
# ---------------------------------------------------------

def header():
    st.markdown("""
        <h1 style='text-align:center; color:#1E88E5;'>
            ⚽ Dribl Football Intelligence
        </h1>
        <p style='text-align:center; font-size:18px;'>
            League → Competition → Ladder → Club Page (Matches + Players) → Player Matches
        </p>
        <hr>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# Natural language detection
# ---------------------------------------------------------

def is_natural_language_query(query):
    keywords = [
        "stats for", "when", "where", "how many", "what", "who",
        "next match", "last match", "results for", "goals", "cards",
        "when do i play", "my next", "upcoming", "schedule", "fixture",
        "details for", "top scorer", "ladder", "table", "form",
        "yellow card", "red card", "lineup", "vs", " v ",
        "team", "overview", "competition", "standings", "rankings",
        "ypl1", "ypl2", "ysl"
    ]
    return any(keyword in query.lower() for keyword in keywords)

# ---------------------------------------------------------
# Main view
# ---------------------------------------------------------

def main():
    header()
   # ======= FILE EXPLORER DEBUG =======
    with st.sidebar.expander("📁 FILE EXPLORER", expanded=True):
        st.write("**Current working directory:**")
        st.code(os.getcwd())
        
        st.write("**BASE_DIR (where app.py is):**")
        st.code(BASE_DIR)
        
        st.write("**DATA_DIR:**")
        st.code(DATA_DIR)
        
        st.write("**Files in BASE_DIR:**")
        if os.path.exists(BASE_DIR):
            files = os.listdir(BASE_DIR)
            for f in files:
                full_path = os.path.join(BASE_DIR, f)
                if os.path.isdir(full_path):
                    st.write(f"📁 {f}/")
                else:
                    size = os.path.getsize(full_path) if os.path.isfile(full_path) else 0
                    st.write(f"📄 {f} ({size} bytes)")
        
        if os.path.exists(DATA_DIR):
            st.write("**Files in DATA_DIR:**")
            data_files = os.listdir(DATA_DIR)
            for f in data_files:
                full_path = os.path.join(DATA_DIR, f)
                if os.path.isfile(full_path):
                    size = os.path.getsize(full_path)
                    st.write(f"📄 {f} ({size} bytes)")
                else:
                    st.write(f"📁 {f}/")
        else:
            st.error("❌ 'data' directory not found!")
            
        # Check for all required files
        st.write("**Required files check:**")
        required_files = [
            "master_results.json",
            "fixtures.json",
            "players_summary.json",
            "competition_overview.json",
            "master_match_centre.json",
            "master_lineups.json"
        ]
        
        for req_file in required_files:
            full_path = os.path.join(DATA_DIR, req_file)
            exists = os.path.exists(full_path)
            if exists:
                size = os.path.getsize(full_path)
                st.success(f"✅ {req_file} ({size} bytes)")
            else:
                st.error(f"❌ {req_file} NOT FOUND")
    # ======= END FILE EXPLORER =======
    
    results = load_master_results()
    fixtures = load_fixtures()
    players_data = load_players_summary()
    comp_overview = load_competition_overview()

    # ======= ADD DEBUG SECTION HERE (AFTER LOADING DATA) =======
    with st.sidebar.expander("🐛 DEBUG INFO", expanded=False):
        st.write(f"**Results loaded:** {len(results)} items")
        st.write(f"**Fixtures loaded:** {len(fixtures)} items")
        st.write(f"**Players loaded:** {len(players_data.get('players', []))}")
        
        if results:
            st.write("**Sample Result Item:**")
            sample = results[0] if len(results) > 0 else {}
            st.json(sample)
            
            # Check if it has attributes
            if "attributes" in sample:
                attrs = sample.get("attributes", {})
                st.write("**League name in sample:**", attrs.get("league_name", "NOT FOUND"))
            else:
                st.write("⚠️ No 'attributes' key found in sample")
                
        # Test league extraction
        if results:
            st.write("**Raw league names found in first 20 results:**")
            league_names = []
            for item in results[:20]:
                if isinstance(item, dict):
                    if "attributes" in item:
                        league = item.get("attributes", {}).get("league_name")
                    else:
                        league = item.get("league_name")
                    if league:
                        league_names.append(league)
            
            for name in league_names[:10]:  # Show first 10
                st.write(f"- `{name}`")
            
            if league_names:
                st.write("**Extracted leagues:**")
                for name in league_names[:10]:
                    extracted = extract_league_from_league_name(name)
                    st.write(f"- `{name}` → `{extracted}`")
    # ======= END DEBUG SECTION =======

    # Search bar
    search = st.text_input(
        "💬 Ask me anything! (e.g., 'when is my next match', 'stats for Shaurya', 'top scorers'):",
        key="global_search",
        placeholder="Try: when do i play next, stats for [player name], top scorers..."
    )

    # Process natural language queries
    if search and search != st.session_state["last_search"]:
        st.session_state["last_search"] = search

        if is_natural_language_query(search):
            with st.spinner("🧠 Thinking..."):
                start = time.time()
                answer = router.process(search)
                end = time.time()

            st.markdown("---")
            st.markdown("### 💬 Answer")

            if isinstance(answer, dict):
                if answer.get("type") == "table":
                    st.markdown(f"**{answer.get('title')}**")
                    df = pd.DataFrame(answer.get('data', []))
                    st.dataframe(df, hide_index=True)
                elif answer.get("type") == "error":
                    st.error(answer.get("message", "An error occurred"))
            else:
                st.markdown(answer)

            st.markdown(f"⏱️ *Response time: {end - start:.3f}s*")
            st.markdown("---")

    # Navigation buttons
    if st.session_state["level"] != "league":
        col1, col2, _ = st.columns([1, 1, 6])
        if col1.button("⬅️ Back"):
            back_one_level()
            st.rerun()
        if col2.button("🔄 Restart"):
            restart_to_top()
            st.rerun()

    level = st.session_state["level"]

    # ---------------- LEVEL 1: LEAGUES ----------------
    if level == "league":
        st.subheader("🏆 Leagues")

        leagues = get_all_leagues(results, fixtures)

        if search and not is_natural_language_query(search):
            leagues = [l for l in leagues if search.lower() in l.lower()]

        if not leagues:
            st.info("No leagues found.")
            return

        df = pd.DataFrame({
            "Select": pd.Series([False] * len(leagues), dtype=bool),
            "League": leagues,
        })

        edited = st.data_editor(
            df,
            hide_index=True,
            column_config={
                "Select": st.column_config.CheckboxColumn("Select", help="Select to open", default=False),
                "League": st.column_config.TextColumn("League")
            },
            disabled=["League"],
            key="league_editor"
        )

        selected_rows = edited[edited["Select"] == True]
        if not selected_rows.empty:
            st.session_state["selected_league"] = selected_rows.iloc[0]["League"]
            st.session_state["level"] = "competition"
            st.rerun()

    # ---------------- LEVEL 2: COMPETITIONS ----------------
    elif level == "competition":
        league = st.session_state["selected_league"]
        st.subheader(f"📘 Competitions in {league}")

        comps = get_competitions_for_league(results, fixtures, league)

        if search and not is_natural_language_query(search):
            comps = [c for c in comps if search.lower() in c.lower()]

        if not comps:
            st.info("No competitions found.")
            return

        df = pd.DataFrame({
            "Select": pd.Series([False] * len(comps), dtype=bool),
            "Competition": comps,
        })

        edited = st.data_editor(
            df,
            hide_index=True,
            column_config={
                "Select": st.column_config.CheckboxColumn("Select", help="Select to open", default=False),
                "Competition": st.column_config.TextColumn("Competition")
            },
            disabled=["Competition"],
            key="competition_editor"
        )

        selected_rows = edited[edited["Select"] == True]
        if not selected_rows.empty:
            st.session_state["selected_competition"] = selected_rows.iloc[0]["Competition"]
            st.session_state["level"] = "ladder_clubs"
            st.session_state["selected_club"] = None
            st.session_state["selected_match_id"] = None
            st.rerun()

        # Overall club rankings for this league (YPL1, YPL2, etc.)
        st.markdown("---")
        st.subheader(f"📈 Overall Club Rankings - {league}")
        if league in comp_overview:
            data = comp_overview[league]
            age_groups = data.get("age_groups", [])
            rows = []
            for club in data.get("clubs", []):
                row = {
                    "Rank": club.get("overall_rank", 0),
                    "Club": base_club_name(club.get("club", "")),  # Remove age suffix
                    "Total Pos": club.get("total_position_points", 0),
                    "Teams": club.get("age_group_count", 0),
                    "GF": club.get("total_gf", 0),
                    "GA": club.get("total_ga", 0),
                    "GD": club.get("total_gf", 0) - club.get("total_ga", 0),
                }
                for age in age_groups:
                    pos = club.get("age_groups", {}).get(age, {}).get("position")
                    row[age] = pos if pos else "-"
                rows.append(row)
            df_overview = pd.DataFrame(rows)
            st.dataframe(df_overview, hide_index=True)
        else:
            st.info("No competition overview data found for this league. Run generate_competition_overview.py first.")

    # ---------------- LEVEL 3: LADDER + CLUB PAGE ----------------
    elif level == "ladder_clubs":
        comp = st.session_state["selected_competition"]
        st.subheader(f"📊 Ladder — {comp}")

        results_for_comp = get_results_for_competition(results, comp)
        ladder = compute_ladder_from_results(results_for_comp)

        if not ladder:
            st.warning("No completed results found for this competition.")
            return

        ladder_df = pd.DataFrame(ladder)
        ladder_df.insert(0, "Pos", range(1, len(ladder_df) + 1))
        
        # Add base club display column
        ladder_df["ClubDisplay"] = ladder_df["club"].apply(base_club_name)
        
        # Set checkbox state based on currently selected club
        currently_selected = st.session_state.get("selected_club")
        ladder_df["Select"] = ladder_df["ClubDisplay"].apply(lambda x: x == currently_selected)

        edited = st.data_editor(
            ladder_df[["Select", "Pos", "ClubDisplay", "played", "wins", "draws", "losses",
                       "gf", "ga", "gd", "points"]],
            hide_index=True,
            column_config={
                "Select": st.column_config.CheckboxColumn("Select", help="Select club", default=False),
                "ClubDisplay": st.column_config.TextColumn("Club")
            },
            disabled=["Pos", "ClubDisplay", "played", "wins", "draws", "losses",
                      "gf", "ga", "gd", "points"],
            key="ladder_editor"
        )

        # Check if selection changed
        selected_rows = edited[edited["Select"] == True]
        if not selected_rows.empty:
            idx = selected_rows.index[0]
            new_club = ladder_df.iloc[idx]["ClubDisplay"]
            
            # Only update if it's a different club (or first selection)
            if st.session_state.get("selected_club") != new_club:
                st.session_state["selected_club"] = new_club
                st.session_state["selected_match_id"] = None
                st.rerun()
        elif currently_selected:
            # User unchecked the box - clear selection
            st.session_state["selected_club"] = None
            st.session_state["selected_match_id"] = None
            st.rerun()

        # Show club details if a club is selected
        club = st.session_state.get("selected_club")
        if club:
            st.markdown("---")
            st.subheader(f"🏟️ Club: {club}")
            
            # MATCHES SECTION
            st.markdown(f"### 📅 Matches in {comp}")

            matches = get_matches_for_club_in_comp(results, club, comp)

            if matches:
                match_rows = []
                for m in matches:
                    attrs = m.get("attributes", {})
                    home = attrs.get("home_team_name")
                    away = attrs.get("away_team_name")
                    hs = attrs.get("home_score")
                    as_ = attrs.get("away_score")
                    is_home = (base_club_name(home) == club)
                    opponent = away if is_home else home
                    home_away = "Home" if is_home else "Away"
                    score = f"{hs}-{as_}" if hs is not None and as_ is not None else ""
                    match_rows.append({
                        "Select": False,
                        "Date": format_date(attrs.get("date", "")),
                        "Opponent": base_club_name(opponent),
                        "Home/Away": home_away,
                        "Score": score,
                        "_match_hash_id": attrs.get("match_hash_id"),
                    })

                df_matches = pd.DataFrame(match_rows)
                df_matches["Select"] = df_matches["Select"].astype(bool)

                edited_matches = st.data_editor(
                    df_matches[["Select", "Date", "Opponent", "Home/Away", "Score"]],
                    hide_index=True,
                    column_config={
                        "Select": st.column_config.CheckboxColumn("Select match to filter players", help="Select match", default=False),
                    },
                    disabled=["Date", "Opponent", "Home/Away", "Score"],
                    key="club_matches_editor"
                )

                selected_match_rows = edited_matches[edited_matches["Select"] == True]
                if not selected_match_rows.empty:
                    idx = selected_match_rows.index[0]
                    st.session_state["selected_match_id"] = df_matches.iloc[idx]["_match_hash_id"]
                    st.rerun()
            else:
                st.info(f"No matches found for {club} in {comp}.")

            # PLAYERS SECTION
            st.markdown(f"### 👤 Players")

            players = get_players_for_club(players_data, club)

            if search and not is_natural_language_query(search):
                players = [
                    p for p in players
                    if search.lower() in f"{p.get('first_name','')} {p.get('last_name','')}".lower()
                ]

            # Filter by selected match if applicable
            selected_match_id = st.session_state.get("selected_match_id")
            if selected_match_id:
                st.info(f"🎯 Showing players who played in the selected match")
                players = [p for p in players if player_played_in_match(p, selected_match_id)]

            if players:
                rows = []
                for p in players:
                    full_name = f"{p.get('first_name','')} {p.get('last_name','')}"
                    rows.append({
                        "Select": False,
                        "Player": full_name,
                        "Jersey": p.get("jersey", ""),
                        "Matches": p.get("stats", {}).get("matches_played", 0),
                        "Goals": p.get("stats", {}).get("goals", 0),
                        "Yellow": p.get("stats", {}).get("yellow_cards", 0),
                        "Red": p.get("stats", {}).get("red_cards", 0),
                    })

                df_players = pd.DataFrame(rows)
                df_players["Select"] = df_players["Select"].astype(bool)

                edited_players = st.data_editor(
                    df_players,
                    hide_index=True,
                    column_config={
                        "Select": st.column_config.CheckboxColumn("Select to view matches", help="Select player", default=False),
                    },
                    disabled=["Player", "Jersey", "Matches", "Goals", "Yellow", "Red"],
                    key="players_editor"
                )

                selected_player_rows = edited_players[edited_players["Select"] == True]
                if not selected_player_rows.empty:
                    idx = selected_player_rows.index[0]
                    st.session_state["selected_player"] = players[idx]
                    st.session_state["level"] = "matches"
                    st.rerun()
            else:
                if selected_match_id:
                    st.info(f"No players from {club} played in the selected match.")
                else:
                    st.info(f"No players found for {club}.")

    # ---------------- LEVEL 4: PLAYER MATCHES ----------------
    elif level == "matches":
        player = st.session_state["selected_player"]
        if not player:
            st.info("No player selected.")
            return

        full_name = f"{player.get('first_name','')} {player.get('last_name','')}"
        st.subheader(f"📅 Matches — {full_name}")

        matches = get_matches_for_player(player)

        if not matches:
            st.info("No matches found for this player.")
            return

        rows = []
        for m in matches:
            rows.append({
                "Date": format_date(m.get("date", "")),
                "Competition": m.get("competition_name"),
                "Opponent": base_club_name(m.get("opponent_team_name", "")),
                "Home/Away": m.get("home_or_away"),
                "Goals": m.get("goals", 0),
                "Yellow": m.get("yellow_cards", 0),
                "Red": m.get("red_cards", 0),
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, hide_index=True)

# ---------------------------------------------------------
# Run
# ---------------------------------------------------------

if __name__ == "__main__":
    main()
