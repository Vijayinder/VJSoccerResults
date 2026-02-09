import streamlit as st
from fast_agent import FastQueryRouter, format_date, format_date_full
import time
import pandas as pd
import json
import os
import re
from collections import defaultdict
from datetime import datetime
import pytz

# ---------------------------------------------------------
# Page setup with enhanced styling
# ---------------------------------------------------------

st.set_page_config(
    page_title="Dribl Football Intelligence",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for better visuals
st.markdown("""
<style>
    /* Main header styling */
    .main-header {
        text-align: center;
        padding: 1rem 0;
        background: linear-gradient(135deg, #1E88E5 0%, #1565C0 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 1rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* Metrics cards */
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #1E88E5;
    }
    
    /* Data editor styling */
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
    }
    
    /* Button styling */
    .stButton > button {
        border-radius: 5px;
        font-weight: 500;
    }
    
    /* Info box */
    .info-box {
        background: #E3F2FD;
        padding: 0.8rem;
        border-radius: 8px;
        border-left: 4px solid #2196F3;
        margin: 0.5rem 0;
    }
    
    /* Last updated text */
    .last-updated {
        text-align: center;
        color: #666;
        font-size: 0.9rem;
        font-style: italic;
        padding: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# Get base directory
# ---------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# ---------------------------------------------------------
# Get last updated timestamp in AEST
# ---------------------------------------------------------

def get_last_updated_time():
    """Get the last modified time of master_results.json in AEST"""
    results_path = os.path.join(DATA_DIR, "master_results.json")
    if os.path.exists(results_path):
        # Get file modification time
        mod_time = os.path.getmtime(results_path)
        # Convert to datetime
        utc_time = datetime.fromtimestamp(mod_time, tz=pytz.UTC)
        # Convert to AEST (Australian Eastern Standard Time)
        aest = pytz.timezone('Australia/Melbourne')
        aest_time = utc_time.astimezone(aest)
        return aest_time.strftime("%d %b %Y, %I:%M %p AEST")
    return "Unknown"

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
# Data loaders - CLEAN VERSION
# ---------------------------------------------------------

@st.cache_resource
def load_master_results():
    """Load master_results.json"""
    path = os.path.join(DATA_DIR, "master_results.json")
    
    if not os.path.exists(path):
        return []
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Handle different JSON structures
        if isinstance(data, dict):
            if "results" in data:
                return data["results"]
            elif "data" in data:
                return data["data"]
            elif "matches" in data:
                return data["matches"]
            else:
                for key, value in data.items():
                    if isinstance(value, list):
                        return value
                return []
        
        elif isinstance(data, list):
            return data
        
        else:
            return []
            
    except Exception as e:
        st.error(f"Error loading results: {str(e)}")
        return []

@st.cache_resource
def load_fixtures():
    """Load fixtures.json"""
    path = os.path.join(DATA_DIR, "fixtures.json")
    
    if not os.path.exists(path):
        return []
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if isinstance(data, dict):
            if "fixtures" in data:
                return data["fixtures"]
            elif "data" in data:
                return data["data"]
            elif "matches" in data:
                return data["matches"]
            else:
                for key, value in data.items():
                    if isinstance(value, list):
                        return value
                return []
        
        elif isinstance(data, list):
            return data
        
        else:
            return []
            
    except Exception as e:
        st.error(f"Error loading fixtures: {str(e)}")
        return []

@st.cache_resource
def load_players_summary():
    """Load players_summary.json"""
    path = os.path.join(DATA_DIR, "players_summary.json")
    
    if not os.path.exists(path):
        return {"players": []}
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if isinstance(data, dict):
            if "players" in data:
                return data
            else:
                for key, value in data.items():
                    if isinstance(value, list):
                        return {"players": value}
                return {"players": []}
        
        elif isinstance(data, list):
            return {"players": data}
        
        else:
            return {"players": []}
            
    except Exception as e:
        st.error(f"Error loading players: {str(e)}")
        return {"players": []}

@st.cache_resource
def load_competition_overview():
    """Load competition_overview.json"""
    path = os.path.join(DATA_DIR, "competition_overview.json")
    
    if not os.path.exists(path):
        return {}
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if isinstance(data, dict):
            return data
        else:
            return {}
            
    except Exception as e:
        st.error(f"Error loading competition overview: {str(e)}")
        return {}

# ---------------------------------------------------------
# Helpers: club name normalization and extraction
# ---------------------------------------------------------

def base_club_name(team_name: str) -> str:
    """Return the base club name without age suffix like ' U18'."""
    if not team_name:
        return ""
    pattern = r'\s+U\d{2}$'
    cleaned = re.sub(pattern, '', team_name).strip()
    return cleaned

def extract_league_from_league_name(league_name: str) -> str:
    if not league_name:
        return "Other"
    
    league_name_lower = str(league_name).lower()
    
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
    
    for item in results:
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

    return sorted(list(leagues))

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
        <div class="main-header">
            <h1 style='margin:0; padding:0;'>⚽ Dribl Football Intelligence</h1>
            <p style='margin:0.5rem 0 0 0; font-size:16px; opacity:0.9;'>
                League → Competition → Ladder → Club → Players
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    # Show last updated time
    last_updated = get_last_updated_time()
    st.markdown(f"""
        <div class="last-updated">
            📅 Last updated: {last_updated}
        </div>
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
    
    results = load_master_results()
    fixtures = load_fixtures()
    players_data = load_players_summary()
    comp_overview = load_competition_overview()

    # Search bar with enhanced styling
    st.markdown("### 💬 Ask Me Anything")
    search = st.text_input(
        "",
        key="global_search",
        placeholder="Try: 'top scorers in U16', 'yellow cards Heidelberg', 'when is my next match'...",
        label_visibility="collapsed"
    )
    
    # Example queries in an expander
    with st.expander("💡 Example Queries", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**📊 Statistics**")
            st.markdown("• top scorers in U16")
            st.markdown("• yellow cards Heidelberg United")
            st.markdown("• stats for [player name]")
            st.markdown("• team stats for Heidelberg U16")
            
            st.markdown("\n**📅 Fixtures**")
            st.markdown("• when is my next match")
            st.markdown("• upcoming fixtures Essendon")
            
        with col2:
            st.markdown("**🏆 Competitions**")
            st.markdown("• YPL1 overview")
            st.markdown("• U16 YPL1 ladder")
            
            st.markdown("\n**🟨🟥 Discipline**")
            st.markdown("• yellow cards details")
            st.markdown("• red cards in U15")

    # Process natural language queries
    if search and search != st.session_state["last_search"]:
        st.session_state["last_search"] = search

        if is_natural_language_query(search):
            with st.spinner("🧠 Analyzing..."):
                start = time.time()
                answer = router.process(search)
                end = time.time()

            st.markdown("---")

            if isinstance(answer, dict):
                if answer.get("type") == "table":
                    st.markdown(f"### {answer.get('title')}")
                    df = pd.DataFrame(answer.get('data', []))
                    st.dataframe(df, hide_index=True, use_container_width=True)
                elif answer.get("type") == "error":
                    st.error(answer.get("message", "An error occurred"))
            else:
                st.markdown(answer)

            st.caption(f"⏱️ Response time: {end - start:.3f}s")
            st.markdown("---")

    # Navigation buttons
    if st.session_state["level"] != "league":
        col1, col2, _ = st.columns([1, 1, 6])
        if col1.button("⬅️ Back", use_container_width=True):
            back_one_level()
            st.rerun()
        if col2.button("🔄 Restart", use_container_width=True):
            restart_to_top()
            st.rerun()

    level = st.session_state["level"]

    # ---------------- LEVEL 1: LEAGUES ----------------
    if level == "league":
        st.markdown("### 🏆 Select a League")

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
                "Select": st.column_config.CheckboxColumn("Select", help="Click to open", default=False),
                "League": st.column_config.TextColumn("League", width="large")
            },
            disabled=["League"],
            use_container_width=True,
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
        st.markdown(f"### 📘 Competitions in {league}")

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
                "Select": st.column_config.CheckboxColumn("Select", help="Click to open", default=False),
                "Competition": st.column_config.TextColumn("Competition", width="large")
            },
            disabled=["Competition"],
            use_container_width=True,
            key="competition_editor"
        )

        selected_rows = edited[edited["Select"] == True]
        if not selected_rows.empty:
            st.session_state["selected_competition"] = selected_rows.iloc[0]["Competition"]
            st.session_state["level"] = "ladder_clubs"
            st.session_state["selected_club"] = None
            st.session_state["selected_match_id"] = None
            st.rerun()

        # Overall club rankings
        st.markdown("---")
        st.markdown(f"### 📈 Overall Club Rankings - {league}")
        if league in comp_overview:
            data = comp_overview[league]
            age_groups = data.get("age_groups", [])
            rows = []
            for club in data.get("clubs", []):
                row = {
                    "Rank": club.get("overall_rank", 0),
                    "Club": base_club_name(club.get("club", "")),
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
            st.dataframe(df_overview, hide_index=True, use_container_width=True)
        else:
            st.info("No competition overview data available for this league.")

    # ---------------- LEVEL 3: LADDER + CLUB PAGE ----------------
    elif level == "ladder_clubs":
        comp = st.session_state["selected_competition"]
        st.markdown(f"### 📊 Ladder — {comp}")

        results_for_comp = get_results_for_competition(results, comp)
        ladder = compute_ladder_from_results(results_for_comp)

        if not ladder:
            st.warning("No completed results found for this competition.")
            return

        ladder_df = pd.DataFrame(ladder)
        ladder_df.insert(0, "Pos", range(1, len(ladder_df) + 1))
        ladder_df["ClubDisplay"] = ladder_df["club"].apply(base_club_name)
        
        currently_selected = st.session_state.get("selected_club")
        ladder_df["Select"] = ladder_df["ClubDisplay"].apply(lambda x: x == currently_selected)

        edited = st.data_editor(
            ladder_df[["Select", "Pos", "ClubDisplay", "played", "wins", "draws", "losses",
                       "gf", "ga", "gd", "points"]],
            hide_index=True,
            column_config={
                "Select": st.column_config.CheckboxColumn("Select", help="Select club", default=False),
                "ClubDisplay": st.column_config.TextColumn("Club", width="medium"),
                "Pos": st.column_config.NumberColumn("Pos", width="small"),
                "played": st.column_config.NumberColumn("P", width="small"),
                "wins": st.column_config.NumberColumn("W", width="small"),
                "draws": st.column_config.NumberColumn("D", width="small"),
                "losses": st.column_config.NumberColumn("L", width="small"),
                "gf": st.column_config.NumberColumn("GF", width="small"),
                "ga": st.column_config.NumberColumn("GA", width="small"),
                "gd": st.column_config.NumberColumn("GD", width="small"),
                "points": st.column_config.NumberColumn("Pts", width="small")
            },
            disabled=["Pos", "ClubDisplay", "played", "wins", "draws", "losses",
                      "gf", "ga", "gd", "points"],
            use_container_width=True,
            key="ladder_editor"
        )

        selected_rows = edited[edited["Select"] == True]
        if not selected_rows.empty:
            idx = selected_rows.index[0]
            new_club = ladder_df.iloc[idx]["ClubDisplay"]
            
            if st.session_state.get("selected_club") != new_club:
                st.session_state["selected_club"] = new_club
                st.session_state["selected_match_id"] = None
                st.rerun()
        elif currently_selected:
            st.session_state["selected_club"] = None
            st.session_state["selected_match_id"] = None
            st.rerun()

        # Show club details if selected
        club = st.session_state.get("selected_club")
        if club:
            st.markdown("---")
            st.markdown(f"## 🏟️ {club}")
            
            # Create two columns for matches and players
            col_matches, col_players = st.columns([1, 1])
            
            with col_matches:
                st.markdown(f"### 📅 Matches")

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
                        home_away = "🏠" if is_home else "✈️"
                        score = f"{hs}-{as_}" if hs is not None and as_ is not None else ""
                        match_rows.append({
                            "Select": False,
                            "Date": format_date(attrs.get("date", "")),
                            "Opponent": base_club_name(opponent),
                            "H/A": home_away,
                            "Score": score,
                            "_match_hash_id": attrs.get("match_hash_id"),
                        })

                    df_matches = pd.DataFrame(match_rows)
                    df_matches["Select"] = df_matches["Select"].astype(bool)

                    edited_matches = st.data_editor(
                        df_matches[["Select", "Date", "H/A", "Opponent", "Score"]],
                        hide_index=True,
                        column_config={
                            "Select": st.column_config.CheckboxColumn("Select", help="Filter players by match", default=False),
                            "Date": st.column_config.TextColumn("Date", width="small"),
                            "H/A": st.column_config.TextColumn("", width="small"),
                            "Opponent": st.column_config.TextColumn("Opponent", width="medium"),
                            "Score": st.column_config.TextColumn("Score", width="small")
                        },
                        disabled=["Date", "H/A", "Opponent", "Score"],
                        use_container_width=True,
                        key="club_matches_editor"
                    )

                    selected_match_rows = edited_matches[edited_matches["Select"] == True]
                    if not selected_match_rows.empty:
                        idx = selected_match_rows.index[0]
                        st.session_state["selected_match_id"] = df_matches.iloc[idx]["_match_hash_id"]
                        st.rerun()
                else:
                    st.info(f"No matches found")

            with col_players:
                st.markdown(f"### 👤 Players")

                players = get_players_for_club(players_data, club)

                if search and not is_natural_language_query(search):
                    players = [
                        p for p in players
                        if search.lower() in f"{p.get('first_name','')} {p.get('last_name','')}".lower()
                    ]

                selected_match_id = st.session_state.get("selected_match_id")
                if selected_match_id:
                    st.info(f"🎯 Filtered by selected match")
                    players = [p for p in players if player_played_in_match(p, selected_match_id)]

                if players:
                    rows = []
                    for p in players:
                        full_name = f"{p.get('first_name','')} {p.get('last_name','')}"
                        rows.append({
                            "Select": False,
                            "Player": full_name,
                            "#": p.get("jersey", ""),
                            "M": p.get("stats", {}).get("matches_played", 0),
                            "G": p.get("stats", {}).get("goals", 0),
                            "🟨": p.get("stats", {}).get("yellow_cards", 0),
                            "🟥": p.get("stats", {}).get("red_cards", 0),
                        })

                    df_players = pd.DataFrame(rows)
                    df_players["Select"] = df_players["Select"].astype(bool)

                    edited_players = st.data_editor(
                        df_players,
                        hide_index=True,
                        column_config={
                            "Select": st.column_config.CheckboxColumn("", help="View details", default=False),
                            "Player": st.column_config.TextColumn("Player", width="medium"),
                            "#": st.column_config.TextColumn("#", width="small"),
                            "M": st.column_config.NumberColumn("M", width="small", help="Matches"),
                            "G": st.column_config.NumberColumn("G", width="small", help="Goals"),
                            "🟨": st.column_config.NumberColumn("🟨", width="small"),
                            "🟥": st.column_config.NumberColumn("🟥", width="small")
                        },
                        disabled=["Player", "#", "M", "G", "🟨", "🟥"],
                        use_container_width=True,
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
                        st.info("No players in selected match")
                    else:
                        st.info("No players found")

    # ---------------- LEVEL 4: PLAYER MATCHES ----------------
    elif level == "matches":
        player = st.session_state["selected_player"]
        if not player:
            st.info("No player selected.")
            return

        full_name = f"{player.get('first_name','')} {player.get('last_name','')}"
        st.markdown(f"### 📅 Matches — {full_name}")

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
                "H/A": "🏠" if m.get("home_or_away") == "home" else "✈️",
                "Goals": m.get("goals", 0),
                "🟨": m.get("yellow_cards", 0),
                "🟥": m.get("red_cards", 0),
            })

        df = pd.DataFrame(rows)
        st.dataframe(
            df, 
            hide_index=True, 
            use_container_width=True,
            column_config={
                "H/A": st.column_config.TextColumn("", width="small"),
                "Goals": st.column_config.NumberColumn("G", width="small"),
                "🟨": st.column_config.NumberColumn("🟨", width="small"),
                "🟥": st.column_config.NumberColumn("🟥", width="small")
            }
        )

# ---------------------------------------------------------
# Run
# ---------------------------------------------------------

if __name__ == "__main__":
    main()
