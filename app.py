import streamlit as st
from fast_agent import FastQueryRouter, format_date, format_date_full
import time
import pandas as pd
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta
import pytz
import uuid
import plotly.graph_objects as go
import io

# Import authentication and tracking modules
from config import authenticate_user, ENABLE_GUEST_ACCESS, SESSION_TIMEOUT_MINUTES
from activity_tracker import (
    log_login, log_logout, log_search, log_view,
    get_recent_activity, get_user_stats, get_active_users_today
)

# ---------------------------------------------------------
# Page setup with enhanced styling
# ---------------------------------------------------------

st.set_page_config(
    page_title="VJ Football Intelligence",
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
    
    /* Login container */
    .login-container {
        max-width: 400px;
        margin: 5rem auto;
        padding: 2rem;
        background: white;
        border-radius: 10px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
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
    
    /* User info badge */
    .user-badge {
        background: #E8F5E9;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        display: inline-block;
        margin: 0.5rem 0;
        border: 1px solid #4CAF50;
    }

</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# Get base directory
# ---------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# ---------------------------------------------------------
# Session Management
# ---------------------------------------------------------

def init_session_state():
    """Initialize session state variables"""
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    
    if "username" not in st.session_state:
        st.session_state["username"] = None
    
    if "full_name" not in st.session_state:
        st.session_state["full_name"] = None
    
    if "role" not in st.session_state:
        st.session_state["role"] = None
    
    if "session_id" not in st.session_state:
        st.session_state["session_id"] = str(uuid.uuid4())
    
    if "last_activity" not in st.session_state:
        st.session_state["last_activity"] = datetime.now()
    
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

def check_session_timeout():
    """Check if session has timed out"""
    if st.session_state["authenticated"]:
        time_diff = datetime.now() - st.session_state["last_activity"]
        if time_diff.total_seconds() > (SESSION_TIMEOUT_MINUTES * 60):
            logout_user()
            st.warning(f"Session timed out after {SESSION_TIMEOUT_MINUTES} minutes of inactivity")
            return False
        
        # Update last activity
        st.session_state["last_activity"] = datetime.now()
    return True

def login_user(username: str, password: str):
    """Authenticate and login user"""
    user = authenticate_user(username, password)
    
    if user:
        st.session_state["authenticated"] = True
        st.session_state["username"] = user["username"]
        st.session_state["full_name"] = user["full_name"]
        st.session_state["role"] = user["role"]
        st.session_state["last_activity"] = datetime.now()
        
        # Log the login
        log_login(
            username=user["username"],
            full_name=user["full_name"],
            session_id=st.session_state["session_id"]
        )
        
        return True
    return False
    
def search_link(label, query):
    """Generates an HTML link that reloads the page with a search parameter"""
    # URL encode the query for the link
    encoded_query = query.replace(" ", "+")
    link = f'<a href="/?search={encoded_query}" target="_self" style="text-decoration: none;">{label}</a>'
    return link
    
def logout_user():
    """Logout current user"""
    if st.session_state["authenticated"]:
        # Log the logout
        log_logout(
            username=st.session_state["username"],
            full_name=st.session_state["full_name"],
            session_id=st.session_state["session_id"]
        )
    
    st.session_state["authenticated"] = False
    st.session_state["username"] = None
    st.session_state["full_name"] = None
    st.session_state["role"] = None
    st.session_state["session_id"] = str(uuid.uuid4())

# ---------------------------------------------------------
# Login Page
# ---------------------------------------------------------

def show_login_page():
    """Display login page"""
    st.markdown("""
        <div class="main-header">
            <h1 style='margin:0; padding:0;'>⚽ VJ Football Intelligence</h1>
            <p style='margin:0.5rem 0 0 0; font-size:16px; opacity:0.9;'>
                Please login to continue
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("### 🔐 Login")
        
        # 1. Wrap inputs and the Login button in a form
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            
            # 2. Change the button to a form_submit_button
            # Note: use_container_width is supported here to keep your layout
            submit_button = st.form_submit_button("Login", type="primary", use_container_width=True)
            
            if submit_button:
                if username and password:
                    if login_user(username, password):
                        st.success("✅ Login successful!")
                        st.rerun()
                    else:
                        st.error("❌ Invalid username or password")
                else:
                    st.warning("⚠️ Please enter username and password")
        
        # 3. Guest Access stays outside the form to remain independent
        if ENABLE_GUEST_ACCESS:
            if st.button("Guest Access", use_container_width=True):
                st.session_state["authenticated"] = True
                st.session_state["username"] = "guest"
                st.session_state["full_name"] = "Guest User"
                st.session_state["role"] = "guest"
                log_login("guest", "Guest User", st.session_state["session_id"])
                st.rerun()

# ---------------------------------------------------------
# Get last updated timestamp in AEST
# ---------------------------------------------------------

def get_last_updated_time():
    """Get the last modified time of master_results.json in AEST"""
    results_path = os.path.join(DATA_DIR, "master_results.json")
    if os.path.exists(results_path):
        mod_time = os.path.getmtime(results_path)
        utc_time = datetime.fromtimestamp(mod_time, tz=pytz.UTC)
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
# Data loaders
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
# Helper functions (same as before)
# ---------------------------------------------------------

def base_club_name(team_name: str) -> str:
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

def get_matches_for_club_in_comp(results, club_name, competition):
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

def get_players_for_club(players_data, club_name, competition=None):
    """
    Get players for a specific club, optionally filtered by competition
    """
    players = []
    for p in players_data.get("players", []):
        team = p.get("team_name", "")
        
        # Check club name match
        if base_club_name(team) != club_name:
            continue
        
        # If competition specified, filter by it
        if competition:
            # Extract competition from team's league name
            team_comp = extract_competition_from_league_name(p.get("league_name", ""))
            if team_comp != competition:
                continue
        
        players.append(p)
    return players

def get_matches_for_player(player):
    return player.get("matches", [])

def player_played_in_match(player, match_hash_id):
    for m in player.get("matches", []):
        if m.get("match_hash_id") == match_hash_id:
            return True
    return False

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
# Header with user info
# ---------------------------------------------------------

def header():
    col1, col2 = st.columns([4, 1])
    
    with col1:
        st.markdown("""
            <div class="main-header">
                <h1 style='margin:0; padding:0;'>⚽ VJ Football Intelligence</h1>
                <p style='margin:0.5rem 0 0 0; font-size:16px; opacity:0.9;'>
                    League → Competition → Ladder → Club → Players
                </p>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
            <div class="user-badge">
                👤 {st.session_state['full_name']}
                {' 🛡️' if st.session_state['role'] == 'admin' else ''}
            </div>
        """, unsafe_allow_html=True)
        
        if st.button("🚪 Logout", use_container_width=True):
            logout_user()
            st.rerun()
    
    # Show last updated time
    last_updated = get_last_updated_time()
    st.markdown(f"""
        <div class="last-updated">
            📅 Last updated: {last_updated}
        </div>
    """, unsafe_allow_html=True)

def is_natural_language_query(query):
    keywords = [
        "stats for", "when", "where", "how many", "what", "who",
        "next match", "last match", "results for", "goals", "cards",
        "when do i play", "my next", "upcoming", "schedule", "fixture",
        "details for", "top scorer", "ladder", "table", "form",
        "yellow card", "red card", "lineup", "vs", " v ",
        "team", "overview", "competition", "standings", "rankings",
        "ypl1", "ypl2", "ysl", "missing score", "no score", "overdue"
    ]
    return any(keyword in query.lower() for keyword in keywords)

# ---------------------------------------------------------
# Admin Dashboard
# ---------------------------------------------------------

def show_admin_dashboard():
    """Display admin dashboard with activity analytics"""
    st.markdown("## 📊 Admin Dashboard")
    
    # Tabs for different views
    tab1, tab2, tab3 = st.tabs(["📈 Analytics", "👥 Users", "📋 Recent Activity"])
    
    with tab1:
        # Get overall stats
        stats = get_user_stats()
        
        # Show metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Activities", stats.get('total_activities', 0))
        with col2:
            st.metric("Unique Users", stats.get('unique_users', 0))
        with col3:
            active_today = get_active_users_today()
            st.metric("Active Today", len(active_today))
        with col4:
            search_count = stats.get('activities_by_type', {}).get('search_query', 0)
            st.metric("Total Searches", search_count)
        
        # Activities by type
        st.markdown("### Activity Breakdown")
        if stats.get('activities_by_type'):
            df_types = pd.DataFrame(
                list(stats['activities_by_type'].items()),
                columns=['Action Type', 'Count']
            ).sort_values('Count', ascending=False)
            st.bar_chart(df_types.set_index('Action Type'))
        
        # Most active users
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 👥 Most Active Users")
            if stats.get('most_active_users'):
                df_users = pd.DataFrame(stats['most_active_users'])
                st.dataframe(df_users, hide_index=True, use_container_width=True)
        
        with col2:
            st.markdown("### 🏟️ Most Viewed Clubs")
            if stats.get('top_clubs'):
                df_clubs = pd.DataFrame(
                    list(stats['top_clubs'].items()),
                    columns=['Club', 'Views']
                ).sort_values('Views', ascending=False).head(10)
                st.dataframe(df_clubs, hide_index=True, use_container_width=True)
    
    with tab2:
        # Active users today
        st.markdown("### Active Users Today")
        active_today = get_active_users_today()
        if active_today:
            df_active = pd.DataFrame(active_today)
            st.dataframe(df_active, hide_index=True, use_container_width=True)
        else:
            st.info("No active users today")
    
    with tab3:
        # Recent activity
        st.markdown("### Recent Activity (Last 50)")
        recent = get_recent_activity(limit=50)
        if recent:
            df_recent = pd.DataFrame(recent)
            # Select relevant columns
            display_cols = ['timestamp', 'username', 'full_name', 'action_type', 'league', 'competition', 'club', 'player', 'search_query']
            available_cols = [col for col in display_cols if col in df_recent.columns]
            st.dataframe(df_recent[available_cols], hide_index=True, use_container_width=True)
        else:
            st.info("No recent activity")

# ---------------------------------------------------------
# Main Application
# ---------------------------------------------------------

def main_app():
    """Main application logic"""
    header()
    
    # Check for admin dashboard
    if st.session_state["role"] == "admin":
        # Add admin dashboard option in sidebar
        with st.sidebar:
            st.markdown("### Admin Controls")
            if st.button("📊 View Dashboard", use_container_width=True):
                st.session_state["show_admin_dashboard"] = True
    
    # Show admin dashboard if requested
    if st.session_state.get("show_admin_dashboard", False) and st.session_state["role"] == "admin":
        if st.button("⬅️ Back to App"):
            st.session_state["show_admin_dashboard"] = False
            st.rerun()
        show_admin_dashboard()
        return
    
    # Load data
    results = load_master_results()
    fixtures = load_fixtures()
    players_data = load_players_summary()
    comp_overview = load_competition_overview()

    # Search bar
    st.markdown("### 💬 Ask Me Anything")
    
    # Initialize search input in session state if not present
    if "search_query" not in st.session_state:
        st.session_state["search_query"] = ""
    
    # Check if a button was clicked and update the query
    if "clicked_query" in st.session_state and st.session_state["clicked_query"]:
        st.session_state["search_query"] = st.session_state["clicked_query"]
        st.session_state["clicked_query"] = None  # Clear after use
    
    search = st.text_input(
        "",
        value=st.session_state["search_query"],
        placeholder="Try: 'Stats for Shaurya','top scorers in U16', 'yellow cards Heidelberg', 'missing scores'...",
        label_visibility="collapsed"
    )
    
    # Update session state when user types
    if search != st.session_state["search_query"]:
        st.session_state["search_query"] = search
    
    # Example queries
    with st.expander("💡 Example Queries", expanded=False):
        st.markdown("*Click any example to try it:*")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**📊 Statistics**")
            if st.button("top scorers in Heidelberg United", key="ex1", use_container_width=True):
                st.session_state["clicked_query"] = "top scorers in Heidelberg United"
                st.rerun()
            if st.button("yellow cards Heidelberg United U16", key="ex2", use_container_width=True):
                st.session_state["clicked_query"] = "yellow cards Heidelberg United U16"
                st.rerun()
            if st.button("stats for Shaurya", key="ex3", use_container_width=True):
                st.session_state["clicked_query"] = "stats for Shaurya"
                st.rerun()
            if st.button("team stats for Heidelberg U16", key="ex4", use_container_width=True):
                st.session_state["clicked_query"] = "team stats for Heidelberg U16"
                st.rerun()
            
            st.markdown("**📅 Fixtures**")
            if st.button("when is my next match", key="ex5", use_container_width=True):
                st.session_state["clicked_query"] = "when is my next match"
                st.rerun()
            if st.button("upcoming fixtures Heidelberg United", key="ex6", use_container_width=True):
                st.session_state["clicked_query"] = "upcoming fixtures Heidelberg United"
                st.rerun()
            
        with col2:
            st.markdown("**🏆 Competitions**")
            if st.button("YPL2 overview", key="ex7", use_container_width=True):
                st.session_state["clicked_query"] = "YPL2 overview"
                st.rerun()
            if st.button("U16 YPL2 ladder", key="ex8", use_container_width=True):
                st.session_state["clicked_query"] = "U16 YPL2 ladder"
                st.rerun()
            
            st.markdown("**🟨🟥 Discipline**")
            if st.button("yellow cards details", key="ex9", use_container_width=True):
                st.session_state["clicked_query"] = "yellow cards details"
                st.rerun()
            if st.button("red cards in U16", key="ex10", use_container_width=True):
                st.session_state["clicked_query"] = "red cards in U16"
                st.rerun()
            if st.button("coaches yellow cards", key="ex11", use_container_width=True):
                st.session_state["clicked_query"] = "coaches yellow cards"
                st.rerun()
            
        with col3:
            st.markdown("**⚠️ Missing Scores**")
            if st.button("missing scores", key="ex12", use_container_width=True):
                st.session_state["clicked_query"] = "missing scores"
                st.rerun()
            if st.button("missing scores Heidelberg", key="ex13", use_container_width=True):
                st.session_state["clicked_query"] = "missing scores Heidelberg"
                st.rerun()
            if st.button("missing scores YPL2", key="ex14", use_container_width=True):
                st.session_state["clicked_query"] = "missing scores YPL2"
                st.rerun()
    
    # Process search queries
    if search and search != st.session_state["last_search"]:
        st.session_state["last_search"] = search

        if is_natural_language_query(search):
            # Log the search
            log_search(
                username=st.session_state["username"],
                full_name=st.session_state["full_name"],
                query=search,
                session_id=st.session_state["session_id"]
            )
            
            with st.spinner("🧠 Analyzing..."):
                start = time.time()
                answer = router.process(search)
                end = time.time()

            st.markdown("---")
            if isinstance(answer, dict):
                if answer.get("type") == "table":
                    title = answer.get('title', "Results")
                    st.info(title) 
                    
                    data = answer.get('data', [])
                    if data:
                        df = pd.DataFrame(data)
                        
                        # --- Dynamic Height Logic ---
                        num_rows = len(df)
                        # (Rows + Header) * Row Height (35px). Cap at 600px if > 16 rows.
                        final_height = 600 if num_rows > 16 else (num_rows + 1) * 35
                        
                        st.dataframe(df, hide_index=True, use_container_width=True, height=final_height)
                        
                        # --- Download Section ---
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            csv = df.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                label="📥 Download CSV",
                                data=csv,
                                file_name=f"data_export.csv",
                                mime='text/csv'
                            )
                            
                        with col2:
                            # We import here so the app doesn't crash on startup if installation failed
                            try:
                                import plotly.graph_objects as go
                                
                                fig = go.Figure(data=[go.Table(
                                    header=dict(values=list(df.columns), fill_color='#F0F2F6', align='left'),
                                    cells=dict(values=[df[col] for col in df.columns], fill_color='white', align='left')
                                )])
                                fig.update_layout(margin=dict(l=5, r=5, t=5, b=5))
                                
                                # Convert to PNG
                                img_bytes = fig.to_image(format="png", engine="kaleido")
                                
                                st.download_button(
                                    label="🖼️ Download as Image",
                                    data=img_bytes,
                                    file_name=f"table_export.png",
                                    mime="image/png"
                                )
                            except (ImportError, ModuleNotFoundError):
                                st.button("🖼️ Image Export (Install Plotly)", disabled=True, help="Run 'pip install plotly kaleido' in your terminal.")

                elif answer.get("type") == "error":
                    st.error(answer.get("message", "An error occurred"))

            else:
                st.chat_message("assistant").write(answer)

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

    # LEVEL 1: LEAGUES
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
            selected_league = selected_rows.iloc[0]["League"]
            st.session_state["selected_league"] = selected_league
            st.session_state["level"] = "competition"
            
            # Log the view
            log_view(
                username=st.session_state["username"],
                full_name=st.session_state["full_name"],
                view_type="league",
                league=selected_league,
                session_id=st.session_state["session_id"]
            )
            
            st.rerun()

    # LEVEL 2: COMPETITIONS (same structure, with logging)
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
            selected_comp = selected_rows.iloc[0]["Competition"]
            st.session_state["selected_competition"] = selected_comp
            st.session_state["level"] = "ladder_clubs"
            st.session_state["selected_club"] = None
            st.session_state["selected_match_id"] = None
            
            # Log the view
            log_view(
                username=st.session_state["username"],
                full_name=st.session_state["full_name"],
                view_type="competition",
                league=league,
                competition=selected_comp,
                session_id=st.session_state["session_id"]
            )
            
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
                }
                # Add age group positions
                for age in age_groups:
                    pos = club.get("age_groups", {}).get(age, {}).get("position")
                    row[age] = pos if pos else "-"
                # Add GF, GA, GD as last 3 columns
                row["GF"] = club.get("total_gf", 0)
                row["GA"] = club.get("total_ga", 0)
                row["GD"] = club.get("total_gf", 0) - club.get("total_ga", 0)
                rows.append(row)
            df_overview = pd.DataFrame(rows)
            st.dataframe(df_overview, hide_index=True, use_container_width=True, height=600)
        else:
            st.info("No competition overview data available for this league.")

    # LEVEL 3: LADDER + CLUB (with logging when club selected)
    elif level == "ladder_clubs":
        comp = st.session_state["selected_competition"]
        league = st.session_state["selected_league"]
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
            height=600,  # Increased height to show ~18 rows
            key="ladder_editor"
        )

        selected_rows = edited[edited["Select"] == True]
        if not selected_rows.empty:
            idx = selected_rows.index[0]
            new_club = ladder_df.iloc[idx]["ClubDisplay"]
            
            if st.session_state.get("selected_club") != new_club:
                st.session_state["selected_club"] = new_club
                st.session_state["selected_match_id"] = None
                
                # Log the view
                log_view(
                    username=st.session_state["username"],
                    full_name=st.session_state["full_name"],
                    view_type="club",
                    league=league,
                    competition=comp,
                    club=new_club,
                    session_id=st.session_state["session_id"]
                )
                
                st.rerun()
        elif currently_selected:
            st.session_state["selected_club"] = None
            st.session_state["selected_match_id"] = None
            st.rerun()

        # Show club details (same as before)
        club = st.session_state.get("selected_club")
        if club:
            st.markdown("---")
            st.markdown(f"## 🏟️ {club}")
            
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
                st.markdown(f"### 👤 Squad")
                
                # Get all people (players + non-players) for this club in this competition
                all_people = get_players_for_club(players_data, club, comp)

                if search and not is_natural_language_query(search):
                    all_people = [
                        p for p in all_people
                        if search.lower() in f"{p.get('first_name','')} {p.get('last_name','')}".lower()
                    ]

                selected_match_id = st.session_state.get("selected_match_id")
                if selected_match_id:
                    st.info(f"🎯 Filtered by selected match")
                    all_people = [p for p in all_people if player_played_in_match(p, selected_match_id)]

                # Separate players and non-players
                players = [p for p in all_people if not p.get("role") or p.get("role") == "player"]
                non_players = [p for p in all_people if p.get("role") and p.get("role") != "player"]

                # PLAYERS TABLE
                if players:
                    st.markdown("**Players**")
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
                        selected_player = players[idx]
                        st.session_state["selected_player"] = selected_player
                        st.session_state["level"] = "matches"
                        
                        # Log the view
                        player_name = f"{selected_player.get('first_name','')} {selected_player.get('last_name','')}"
                        log_view(
                            username=st.session_state["username"],
                            full_name=st.session_state["full_name"],
                            view_type="player",
                            league=league,
                            competition=comp,
                            club=club,
                            player=player_name,
                            session_id=st.session_state["session_id"]
                        )
                        
                        st.rerun()
                else:
                    if selected_match_id:
                        st.info("No players in selected match")
                    else:
                        st.info("No players found")
                
                # NON-PLAYERS TABLE (STAFF/COACHES)
                if non_players:
                    st.markdown("**Staff & Coaches**")
                    staff_rows = []
                    for p in non_players:
                        full_name = f"{p.get('first_name','')} {p.get('last_name','')}"
                        role = p.get("role", "staff").title()
                        staff_rows.append({
                            "Name": full_name,
                            "Role": role,
                            "🟨": p.get("stats", {}).get("yellow_cards", 0),
                            "🟥": p.get("stats", {}).get("red_cards", 0),
                        })

                    df_staff = pd.DataFrame(staff_rows)
                    st.dataframe(
                        df_staff,
                        hide_index=True,
                        column_config={
                            "Name": st.column_config.TextColumn("Name", width="medium"),
                            "Role": st.column_config.TextColumn("Role", width="small"),
                            "🟨": st.column_config.NumberColumn("🟨", width="small"),
                            "🟥": st.column_config.NumberColumn("🟥", width="small")
                        },
                        use_container_width=True,
                    )

    # LEVEL 4: PLAYER MATCHES (same as before)
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
# Main Entry Point
# ---------------------------------------------------------

def main():
    """Main entry point"""
    init_session_state()
    
    # Check if authenticated
    if not st.session_state["authenticated"]:
        show_login_page()
    else:
        # User is logged in, now handle the URL search parameter
        params = st.query_params
        if "search" in params:
            # Update the search input state from the URL
            st.session_state["search_input_value"] = params["search"].replace("+", " ")
        # Check session timeout
        if not check_session_timeout():
            show_login_page()
        else:
            main_app()
# app.py


        
if __name__ == "__main__":
    main()
