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
import random


# Import authentication and tracking modules
from player_config import (
    get_players_and_coaches_list,
    format_player_display,
    save_player_selection,
    get_player_selection,
    clear_player_selection,
    verify_admin,
    get_player_selection_stats
)
# ADD after imports:
SESSION_TIMEOUT_MINUTES = 240  # 4 hours

def get_client_ip():
    """Get client IP address from Streamlit request headers"""
    try:
        # Try to get from Streamlit headers
        from streamlit.web.server.websocket_headers import _get_websocket_headers
        headers = _get_websocket_headers()
        
        # Check common proxy headers first
        if headers:
            # X-Forwarded-For is used by proxies/load balancers
            if 'x-forwarded-for' in headers:
                # Get first IP in chain (original client)
                return headers['x-forwarded-for'].split(',')[0].strip()
            
            # X-Real-IP is used by some proxies
            if 'x-real-ip' in headers:
                return headers['x-real-ip']
        
        # Fallback: try to get from context
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        ctx = get_script_run_ctx()
        if ctx:
            session_info = ctx.session_info
            if hasattr(session_info, 'client_ip'):
                return session_info.client_ip
        
        return "Unknown"
    except:
        return "Unknown"
        
from activity_tracker import (
    log_login, log_logout, log_search, log_view,
    get_recent_activity, get_user_stats, get_active_users_today
)

# ---------------------------------------------------------
# Page setup with enhanced styling
# ---------------------------------------------------------

st.set_page_config(
    page_title="Junior Pro Football Intelligence",
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
    /* Targeted styling for buttons inside expanders only */
    [data-testid="stExpander"] .stButton > button {
        padding: 2px 8px !important;
        min-height: 28px !important;
        height: 28px !important;
        font-size: 13px !important;
        margin-bottom: 2px !important;
    }

    /* Optional: remove the gap between buttons */
    [data-testid="stExpander"] div[data-testid="stVerticalBlock"] > div {
        gap: 0.2rem !important;
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
        
    if "expander_state" not in st.session_state:
        st.session_state["expander_state"] = False
    if "expander_collapse_counter" not in st.session_state:
        st.session_state["expander_collapse_counter"] = 0
    if "user_type" not in st.session_state:
        st.session_state["user_type"] = None  # 'player' or 'admin'
    
    if "player_club" not in st.session_state:
        st.session_state["player_club"] = None
    
    if "player_age_group" not in st.session_state:
        st.session_state["player_age_group"] = None
    
    if "player_role" not in st.session_state:
        st.session_state["player_role"] = None
    
    if "player_league" not in st.session_state:
        st.session_state["player_league"] = None

def check_session_timeout():
    """Check if session has timed out"""
    if st.session_state["authenticated"]:
        time_diff = datetime.now() - st.session_state["last_activity"]
        if time_diff.total_seconds() > (SESSION_TIMEOUT_MINUTES * 260):
            logout_user()
            st.warning(f"Session timed out after {SESSION_TIMEOUT_MINUTES} minutes of inactivity")
            return False
        
        # Update last activity
        st.session_state["last_activity"] = datetime.now()
    return True

   
def search_link(label, query):
    """Generates an HTML link that reloads the page with a search parameter"""
    # URL encode the query for the link
    encoded_query = query.replace(" ", "+")
    link = f'<a href="/?search={encoded_query}" target="_self" style="text-decoration: none;">{label}</a>'
    return link
    
def logout_user():
    """Logout current user"""
    if st.session_state["authenticated"]:
        log_logout(
            username=st.session_state.get("username", "unknown"),
            full_name=st.session_state.get("full_name", "Unknown"),
            session_id=st.session_state["session_id"]
        )
    
    st.session_state["authenticated"] = False
    st.session_state["user_type"] = None  # ADD
    st.session_state["username"] = None
    st.session_state["full_name"] = None
    st.session_state["role"] = None
    st.session_state["player_club"] = None  # ADD
    st.session_state["player_age_group"] = None  # ADD
    st.session_state["player_role"] = None  # ADD
    st.session_state["session_id"] = str(uuid.uuid4())
    st.session_state["player_league"] = None  # ADD THIS
    st.session_state["player_competition"] = None  # ADD THIS

# ---------------------------------------------------------
# Login Page
# ---------------------------------------------------------


def show_login_page():
    """Display player selection page"""
    st.markdown("""
        <div class="main-header">
            <h2 style='margin:0; padding:0;'>⚽ Junior Pro Football Intelligence</h2>
            <p style='margin:0.5rem 0 0 0; font-size:16px; opacity:0.9;'>
                Welcome! Please select your profile to continue
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # Check for saved selection
        saved_selection = get_player_selection(st.session_state["session_id"])
        
        if saved_selection:
            st.success(f"👋 Welcome back, {saved_selection['name']}!")
            club_display = saved_selection['club']
            if saved_selection.get('age_group'):
                club_display += f" ({saved_selection['age_group']})"
            st.info(f"**Club:** {club_display}")
            
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Continue as " + saved_selection['name'], type="primary", use_container_width=True):
                    # Login with saved selection
                    st.session_state["authenticated"] = True
                    st.session_state["user_type"] = "player"
                    st.session_state["username"] = saved_selection["player_id"]
                    st.session_state["full_name"] = saved_selection["name"]
                    st.session_state["player_club"] = saved_selection["club"]
                    st.session_state["player_age_group"] = saved_selection.get("age_group", "")
                    st.session_state["player_role"] = saved_selection["role"]
                    st.session_state["role"] = saved_selection["role"]
                    st.session_state["last_activity"] = datetime.now()
                    st.session_state["player_league"] = selected_person.get("league", "")
                    st.session_state["player_competition"] = selected_person.get("competition", "")
                    # Update USER_CONFIG in fast_agent
                    update_user_config(saved_selection["club"], saved_selection.get("age_group", ""))
                    # Look up league and competition from player data
                    league, competition = get_player_league_info(
                        saved_selection["name"],
                        saved_selection["club"],
                        saved_selection.get("age_group", "")
                    )
                    st.session_state["player_league"] = league
                    st.session_state["player_competition"] = competition
                    # Log the login
                    log_login(
                        username=saved_selection["player_id"],
                        full_name=saved_selection["name"],
                        session_id=st.session_state["session_id"]
                    )
                    st.rerun()
            with col_b:
                if st.button("Select Different Profile", use_container_width=True):
                    clear_player_selection(st.session_state["session_id"])
                    st.rerun()
            
            st.markdown("---")
        
        # Player/Coach selection
        st.markdown("### 👤 Select Player/Coach Profile")
        
        # Load all players and coaches
        people = get_players_and_coaches_list(DATA_DIR)
        
        if not people:
            st.error("❌ No player or coach data found. Please ensure data files are loaded.")
            return
        
        # Create dropdown options
        options = [""] + [format_player_display(p) for p in people]
        
        selected_display = st.selectbox(
            "Who brought you here?",
            options=options,
            format_func=lambda x: "Select your name..." if x == "" else x,
            help="Start typing to search for your name"
        )
        
        if selected_display and selected_display != "":
            # Find the person data
            selected_person = None
            for person in people:
                if format_player_display(person) == selected_display:
                    selected_person = person
                    break
            
            if selected_person:
                # 1. Extract data for clarity
                name = selected_person['name']
                role = selected_person['role']
                club = selected_person['club']
                age = selected_person.get('age_group', 'N/A')

                # 2. Display the success message outside the form for styling
                st.success(f"✅ Selected: {role} **{name}** from **{club}** in age group **{age}**")

                # 3. Use a form to capture the "Enter" keypress
                with st.form("confirmation_form", border=False):
                    # We need a submit button for the Enter key to trigger
                    submit = st.form_submit_button("Continue", type="primary", use_container_width=True)
                    
                    if submit:
                        # Login logic
                        st.session_state["authenticated"] = True
                        st.session_state["user_type"] = "player"
                        st.session_state["username"] = selected_person["player_id"]
                        st.session_state["full_name"] = selected_person["name"]
                        st.session_state["player_club"] = selected_person["club"]
                        st.session_state["player_age_group"] = selected_person.get("age_group", "")
                        st.session_state["player_role"] = selected_person["role"]
                        st.session_state["role"] = selected_person["role"]
                        st.session_state["last_activity"] = datetime.now()
                        
                        # Save selection
                        save_player_selection(st.session_state["session_id"], selected_person)
                        
                        # Update USER_CONFIG
                        update_user_config(selected_person["club"], selected_person.get("age_group", ""))
                        # Look up league and competition from player data
                        league, competition = get_player_league_info(
                            selected_person["name"],
                            selected_person["club"],
                            selected_person.get("age_group", "")
                        )
                        st.session_state["player_league"] = league
                        st.session_state["player_competition"] = competition
                        # Log the login
                        log_login(
                            username=selected_person["player_id"],
                            full_name=selected_person["name"],
                            session_id=st.session_state["session_id"]
                        )
                        st.rerun()
        
        # Admin login section
        st.markdown("---")
        with st.expander("🔐 Admin Login"):
            st.markdown("### Administrator Access")
            
            with st.form("admin_login_form"):
                admin_username = st.text_input("Admin Username")
                admin_password = st.text_input("Admin Password", type="password")
                admin_submit = st.form_submit_button("Login as Admin", use_container_width=True)
                
                if admin_submit:
                    if admin_username and admin_password:
                        admin = verify_admin(admin_username, admin_password)
                        if admin:
                            st.session_state["authenticated"] = True
                            st.session_state["user_type"] = "admin"
                            st.session_state["username"] = admin["username"]
                            st.session_state["full_name"] = admin["full_name"]
                            st.session_state["role"] = "admin"
                            st.session_state["last_activity"] = datetime.now()
                            
                            # Log the login
                            log_login(
                                username=admin["username"],
                                full_name=admin["full_name"],
                                session_id=st.session_state["session_id"]
                            )
                            
                            st.success("✅ Admin login successful!")
                            st.rerun()
                        else:
                            st.error("❌ Invalid admin credentials")
                    else:
                        st.warning("⚠️ Please enter username and password")

# ---------------------------------------------------------
# Get last updated timestamp in AEST
# ---------------------------------------------------------

def get_last_updated_time():
    """Get the last data update time from JSON (not file timestamp)"""
    results_path = os.path.join(DATA_DIR, "master_results.json")
    
    if not os.path.exists(results_path):
        return "Data file not found"
    
    try:
        # Try to get from JSON first
        with open(results_path, 'r') as f:
            data = json.load(f)
        
        if '_last_updated' in data:
            update_time = datetime.fromisoformat(data['_last_updated'])
            aest = pytz.timezone('Australia/Melbourne')
            
            if update_time.tzinfo is None:
                utc = pytz.UTC
                update_time = utc.localize(update_time)
            
            aest_time = update_time.astimezone(aest)
            return aest_time.strftime("%a, %d %b %Y, %I:%M %p AEST")
        
        # Fallback: use file timestamp (for local testing with old files)
        mod_time = os.path.getmtime(results_path)
        utc_time = datetime.fromtimestamp(mod_time, tz=pytz.UTC)
        aest = pytz.timezone('Australia/Melbourne')
        aest_time = utc_time.astimezone(aest)
        return aest_time.strftime("%a, %d %b %Y, %I:%M %p AEST") + " (file time)"
        
    except Exception as e:
        return f"Error reading timestamp: {str(e)}"

# ---------------------------------------------------------
# Router
# ---------------------------------------------------------

@st.cache_resource
def load_router():
    """Load the query router (cached per session)"""
    return FastQueryRouter()

router = load_router()

# ---------------------------------------------------------
# Data loaders
# ---------------------------------------------------------

@st.cache_data(ttl=900)  # Auto-refresh every 5 minutes
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

@st.cache_data(ttl=900)  # Auto-refresh every 5 minutes
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

@st.cache_data(ttl=900)  # Auto-refresh every 5 minutes
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


@st.cache_data(ttl=900)  # Auto-refresh every 5 minutes
def load_staff_summary():
    """Load staff_summary.json"""
    path = os.path.join(DATA_DIR, "staff_summary.json")
    
    if not os.path.exists(path):
        return {"staff": []}
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if isinstance(data, dict):
            if "staff" in data:
                return data
            else:
                for key, value in data.items():
                    if isinstance(value, list):
                        return {"staff": value}
                return {"staff": []}
        elif isinstance(data, list):
            return {"staff": data}
        else:
            return {"staff": []}
    except Exception as e:
        st.error(f"Error loading staff: {str(e)}")
        return {"staff": []}

@st.cache_data(ttl=900)  # Auto-refresh every 5 minutes
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

def force_reload_all_data():
    """Force reload of all data including fast_agent module data"""
    import importlib
    import sys
    
    # Clear Streamlit caches
    st.cache_data.clear()
    st.cache_resource.clear()
    
    # Force reimport of fast_agent to reload its module-level data
    if 'fast_agent' in sys.modules:
        importlib.reload(sys.modules['fast_agent'])
    
    # Reinitialize router with fresh data
    global router
    from fast_agent import FastQueryRouter
    router = FastQueryRouter()

# ---------------------------------------------------------
# Helper functions (same as before)
# ---------------------------------------------------------

def base_club_name(team_name: str) -> str:
    if not team_name:
        return ""
    pattern = r'\s+U\d{2}$'
    cleaned = re.sub(pattern, '', team_name).strip()
    return cleaned

def extract_competition_from_league_name(league_name: str) -> str:
    """
    Extract competition with age group from league name.
    E.g., "U16 Boys Victorian Youth Premier League 1" → "U16 YPL1"
    """
    if not league_name:
        return league_name
    
    parts = league_name.split()
    if len(parts) < 2:
        return league_name
    
    # First part is usually the age group (U13, U14, U15, U16, U18)
    age = parts[0]
    
    # Determine which league it belongs to
    if "YPL1" in league_name or "Youth Premier League 1" in league_name:
        return f"{age} YPL1"
    if "YPL2" in league_name or "Youth Premier League 2" in league_name:
        return f"{age} YPL2"
    if "YSL" in league_name and ("North-West" in league_name or "NW" in league_name):
        return f"{age} YSL NW"
    if "YSL" in league_name and ("South-East" in league_name or "SE" in league_name):
        return f"{age} YSL SE"
    if "VPL Men" in league_name:
        return f"{age} VPL Men"
    if "VPL Women" in league_name:
        return f"{age} VPL Women"
    if "YSL" in league_name:
        return f"{age} YSL"
    
    # Fallback: return original
    return league_name
    
def extract_competition_from_league(league_name: str) -> str:
    """Extract competition code from full league name"""
    if not league_name:
        return ""
    
    league_lower = league_name.lower()
    
    # Check for each competition type
    if "ypl1" in league_lower or "ypl 1" in league_lower:
        return "YPL1"
    elif "ypl2" in league_lower or "ypl 2" in league_lower:
        return "YPL2"
    elif "ysl" in league_lower and ("north-west" in league_lower or "nw" in league_lower or "north west" in league_lower):
        return "YSL NW"
    elif "ysl" in league_lower and ("south-east" in league_lower or "se" in league_lower or "south east" in league_lower):
        return "YSL SE"
    elif "vpl men" in league_lower:
        return "VPL Men"
    elif "vpl women" in league_lower:
        return "VPL Women"
    elif "ysl" in league_lower:
        return "YSL"
    elif "vpl" in league_lower:
        return "VPL"
    
    # If no match, return original
    return league_name

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
            extracted = extract_competition_from_league(str(league_name))
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
            extracted = extract_competition_from_league(str(league_name))
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

def _person_teams_and_leagues(p):
    """Get (team, league) pairs for a person. Handles both team_name/league_name and teams/leagues arrays."""
    teams = p.get("teams", [])
    leagues = p.get("leagues", [])
    if teams or leagues:
        if len(teams) == len(leagues):
            return list(zip(teams, leagues))
        if teams:
            league = leagues[0] if leagues else ""
            return [(t, league) for t in teams]
        team = teams[0] if teams else ""
        return [(team, lg) for lg in leagues]
    tn = p.get("team_name", "")
    ln = p.get("league_name", "")
    return [(tn, ln)] if tn or ln else []


def get_players_for_club(players_data, club_name, competition=None, staff_data=None):
    """
    Get players and staff for a specific club, optionally filtered by competition.
    Merges players_summary.json and staff_summary.json for the structured club view.
    """
    def normalize(p, is_staff=False):
        out = dict(p)
        if not out.get("team_name") and out.get("teams"):
            out["team_name"] = out["teams"][0] if out["teams"] else ""
        if not out.get("league_name") and out.get("leagues"):
            out["league_name"] = out["leagues"][0] if out["leagues"] else ""
        if not out.get("role"):
            if is_staff:
                roles = out.get("roles", [])
                out["role"] = (roles[0] if roles else "staff")
            else:
                out["role"] = "player"
        if is_staff and "jersey" not in out:
            out["jersey"] = ""
        return out

    result = []
    seen_ids = set()

    for p in players_data.get("players", []):
        pn = normalize(p, False)
        for team, league in _person_teams_and_leagues(pn):
            if not team:
                continue
            if base_club_name(team) != club_name:
                continue
            if competition and extract_competition_from_league_name(league or pn.get("league_name", "")) != competition:
                continue
            pid = pn.get("person_id") or f"{pn.get('first_name','')}_{pn.get('last_name','')}"
            if pid not in seen_ids:
                seen_ids.add(pid)
                result.append(pn)
            break

    if staff_data:
        for p in staff_data.get("staff", []):
            pn = normalize(p, True)
            for team, league in _person_teams_and_leagues(pn):
                if not team:
                    continue
                if base_club_name(team) != club_name:
                    continue
                if competition and extract_competition_from_league_name(league or pn.get("league_name", "")) != competition:
                    continue
                pid = pn.get("person_id") or f"{pn.get('first_name','')}_{pn.get('last_name','')}"
                if pid not in seen_ids:
                    seen_ids.add(pid)
                    result.append(pn)
                break

    return result

def get_matches_for_player(player):
    return player.get("matches", [])

def player_played_in_match(player, match_hash_id):
    for m in player.get("matches", []):
        if m.get("match_hash_id") == match_hash_id:
            return True
    return False
    
def get_player_match_stats(player, match_hash_id):
    """Get stats for a specific match"""
    for m in player.get("matches", []):
        if m.get("match_hash_id") == match_hash_id:
            return m
    return None
    
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
    """Renders the full-width app header and last updated timestamp"""
    last_updated = get_last_updated_time()
    # Main Title and Subtitle
    st.markdown(f"""
        <div class="main-header" style="text-align: center;">
        <h3 style='margin:0; padding:0;'>⚽ Junior Pro Football Intelligence</h3>
        <p style='margin:0.5rem 0 0 0; font-size:16px; opacity:0.9;'>
            {st.session_state.get('player_club') or 'League'} 
            → {st.session_state.get('player_age_group') or 'Competition'} 
            → Players
        </p>
        <span style="font-size: 12px; color: #000000; text-transform: uppercase; letter-spacing: 1px;">
                📅 Data Updated: {last_updated}
            </span>
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
        "ypl1", "ypl2", "ysl", "missing score", "no score", "overdue",
        "coach", "coaches", "staff", "manager", "managers",
        # ✅ NEW: Today's matches keywords
        "today", "todays", "result"  # Catches "todays results", "results today", "today's results"
    ]
    return any(keyword in query.lower() for keyword in keywords)

# ---------------------------------------------------------
# Admin Dashboard
# ---------------------------------------------------------

def show_admin_dashboard():
    """Display admin dashboard with activity analytics"""
    st.markdown("## 📊 Admin Dashboard")
    
    # Tabs for different views

    ab1, tab2, tab3, tab4 = st.tabs(["📈 Analytics", "👥 Users", "📋 Recent Activity", "🌐 IP Tracking"])
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
            
            # --- Convert last_activity column to AEST ---
            if 'last_activity' in df_active.columns:
                try:
                    aest = pytz.timezone('Australia/Melbourne')
                    # Convert strings to datetime objects (assuming UTC)
                    df_active['last_activity'] = pd.to_datetime(df_active['last_activity'], utc=True)
                    # Convert to Melbourne time
                    df_active['last_activity'] = df_active['last_activity'].dt.tz_convert(aest)
                    # Format: Mon, 16-Feb 14:30:05
                    df_active['last_activity'] = df_active['last_activity'].dt.strftime("%a, %d-%b %H:%M:%S")
                except Exception as e:
                    st.error(f"Error formatting last_activity: {e}")
            
            st.dataframe(df_active, hide_index=True, use_container_width=True)
        else:
            st.info("No active users today")
    
        with tab3:
            # Recent activity
            st.markdown("### Recent Activity (Last 50)")
            recent = get_recent_activity(limit=50)
            if recent:
                df_recent = pd.DataFrame(recent)
                
                # Select relevant columns INCLUDING IP address
                display_cols = ['timestamp', 'username', 'full_name', 'ip_address', 'action_type', 'league', 'competition', 'club', 'search_query']
                available_cols = [col for col in display_cols if col in df_recent.columns]
                
                st.dataframe(
                    df_recent[available_cols], 
                    hide_index=True, 
                    use_container_width=True,
                    column_config={
                        "timestamp": st.column_config.TextColumn("Time", width="medium"),
                        "username": st.column_config.TextColumn("User", width="small"),
                        "ip_address": st.column_config.TextColumn("IP Address", width="medium"),
                        "action_type": st.column_config.TextColumn("Action", width="small")
                    }
                )
            else:
                st.info("No recent activity")
        with tab4:
            st.markdown("### 🌐 IP Address Analytics")
            
            recent = get_recent_activity(limit=1000)
            if recent:
                df = pd.DataFrame(recent)
                
                if 'ip_address' in df.columns and not df['ip_address'].isna().all():
                    # Filter out Unknown/None IPs
                    df_valid_ip = df[df['ip_address'].notna() & (df['ip_address'] != 'Unknown')]
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("#### 📊 IP Statistics")
                        unique_ips = df_valid_ip['ip_address'].nunique()
                        st.metric("Unique IP Addresses", unique_ips)
                        
                        # Top IPs by activity
                        st.markdown("**Most Active IPs**")
                        ip_counts = df_valid_ip['ip_address'].value_counts().head(10).reset_index()
                        ip_counts.columns = ['IP Address', 'Activities']
                        st.dataframe(ip_counts, hide_index=True, use_container_width=True)
                    
                    with col2:
                        st.markdown("#### 🔐 Recent Logins by IP")
                        logins = df[df['action_type'] == 'login'][['timestamp', 'username', 'full_name', 'ip_address']].head(20)
                        st.dataframe(logins, hide_index=True, use_container_width=True)
                        
                        st.markdown("#### 🔍 IP to User Mapping")
                        # Show which users use which IPs
                        user_ip_map = df_valid_ip.groupby(['username', 'ip_address']).size().reset_index(name='count')
                        user_ip_map = user_ip_map.sort_values('count', ascending=False).head(20)
                        st.dataframe(user_ip_map, hide_index=True, use_container_width=True)
                else:
                    st.info("No IP address data available yet. IP tracking will start with the next login.")
            else:
                st.info("No activity data")
            
def update_user_config(club_name: str, age_group: str):
    """Update USER_CONFIG in fast_agent module with player's club and age group"""
    try:
        import fast_agent
        
        # Build team name
        team_name = club_name
        if age_group:
            team_name = f"{club_name} {age_group}"
        
        # Update the USER_CONFIG dictionary
        fast_agent.USER_CONFIG["team"] = team_name
        fast_agent.USER_CONFIG["club"] = club_name
        fast_agent.USER_CONFIG["age_group"] = age_group if age_group else ""
        
    except Exception as e:
        print(f"Error updating USER_CONFIG: {e}")
def get_player_league_info(player_name: str, club: str, age_group: str):
    """Look up player's league and competition from loaded data"""
    try:
        # Load player data
        players_data = load_players_summary()
        players = players_data.get("players", [])
        
        # Split name
        name_parts = player_name.split()
        if len(name_parts) >= 2:
            first_name = name_parts[0]
            last_name = " ".join(name_parts[1:])
        else:
            first_name = player_name
            last_name = ""
        
        # Find matching player
        for p in players:
            if (p.get('first_name', '').lower() == first_name.lower() and 
                p.get('last_name', '').lower() == last_name.lower()):
                
                # Get full league name - try multiple fields
                league = (p.get('league_name') or 
                         (p.get('leagues', [None])[0] if p.get('leagues') else None) or
                         p.get('competition_name') or
                         '')
                
                # Extract just the competition part (YPL1, YPL2, etc.)
                competition = extract_competition_from_league(league)
                
                print(f"DEBUG: Found player {player_name}")
                print(f"  Full league: {league}")
                print(f"  Competition: {competition}")
                
                return league, competition
        
        # If not found in players, try staff
        staff_data = load_staff_summary()
        staff = staff_data.get("staff", [])
        
        for s in staff:
            if (s.get('first_name', '').lower() == first_name.lower() and 
                s.get('last_name', '').lower() == last_name.lower()):
                
                league = (s.get('league_name') or 
                         (s.get('leagues', [None])[0] if s.get('leagues') else None) or
                         s.get('competition_name') or
                         '')
                
                competition = extract_competition_from_league(league)
                
                print(f"DEBUG: Found staff {player_name}")
                print(f"  Full league: {league}")
                print(f"  Competition: {competition}")
                
                return league, competition
        
        # If player not found, return empty - NO GUESSING!
        print(f"WARNING: Could not find league info for {player_name}")
        return '', ''
        
    except Exception as e:
        print(f"Error getting league info: {e}")
        return '', ''     
# ---------------------------------------------------------
# Main Application
# ---------------------------------------------------------

def main_app():
    """Main application logic"""
    header()
    # Load data
    results = load_master_results()
    fixtures = load_fixtures()
    players_data = load_players_summary()
    staff_data = load_staff_summary()
    comp_overview = load_competition_overview()
    
    # 4. Extract names and club info safely
    first_name = st.session_state.get('full_name', 'Champ').split()[0]
    club = st.session_state.get('player_club', 'The League')
    age = st.session_state.get('player_age_group', '')
    league = st.session_state.get('player_league', '')
    Comp = st.session_state.get('player_competition', '')
    
    
    
    col_left, col_mid, col_right = st.columns([2, 6, 2])
    
    with col_left:
        if st.session_state.get("user_type") == "admin":
            st.markdown(f"""
                <div class="user-badge">
                    🔑 Admin: {st.session_state['full_name']}
                </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="padding: 10px 0;">
                <div style=" display: inline-block;box-shadow: 0 2px 4px rgba(0,0,0,0.1)">
                    <span style="font-size: 18px;  font-weight: 500;">👤 {st.session_state.get('full_name')}</span>
                    <p><span style="font-size: 15px; ">⚽ {club} {age}</span></p>
                </div>
            </div>
            """, unsafe_allow_html=True)
    with col_right:
        if st.button("🚪 Logout", key="logout_button", use_container_width=True):
            st.session_state.clear()
            st.rerun()
    # In your sidebar (after logout button or admin controls)
    with st.sidebar:
        st.markdown("---")
        
        # ✅ Admin-Only Manual Data Refresh Section
        if st.session_state.get("role") == "admin":
            st.markdown("### 🔄 Admin Controls")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Refresh Data", use_container_width=True, help="Reload all data from files"):
                    force_reload_all_data()
                    st.success("✅ All data refreshed!")
                    st.rerun()
            
            with col2:
                # Show last update time
                last_update = get_last_updated_time()
                st.caption(f"📅 Updated:\n{last_update.split(',')[1] if ',' in last_update else last_update}")
            
            st.markdown("---")
        
        # Contact form (available to everyone)
        with st.expander("📧 Contact Us"):
            with st.form("contact_form", clear_on_submit=True):
                st.markdown("**Get in touch with us**")
                
                name = st.text_input("Name*", key="contact_name")
                email = st.text_input("Email*", key="contact_email")
                subject = st.selectbox("Subject*", [
                    "General Inquiry",
                    "Technical Support",
                    "Feature Request",
                    "Report an Issue",
                    "Data Question",
                    "Other"
                ])
                message = st.text_area("Message*", height=100, key="contact_message")
                
                submitted = st.form_submit_button("Send Message", use_container_width=True)
                
                if submitted:
                    if name and email and message:
                        # Create mailto link
                        import urllib.parse
                        email_body = f"From: {name} ({email})\n\nSubject: {subject}\n\nMessage:\n{message}"
                        mailto = f"mailto:juniorprofootball@gmail.com?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(email_body)}"
                        
                        st.markdown(f"[📧 Click here to send email]({mailto})")
                        st.info("Your email client should open. If not, click the link above!")
                    else:
                        st.error("Please fill in all fields")
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
    # 1. Define dynamic labels based on session state
    user_club = st.session_state.get("player_club") or "Heidelberg United"
    user_age = st.session_state.get("player_age_group") or "U16"
    user_name = st.session_state.get("full_name") or "John Doe"
    user_league = st.session_state.get("player_league") or "YPL2"  # ADD THIS
    user_competition = st.session_state.get("player_competition") or "YPL2"  

    # Example queries - collapse after click/search by changing label so Streamlit treats it as new widget
    _collapse = st.session_state.get("expander_collapse_counter", 0)
    _expander_label = "💡 Example Queries" + "\u200b" * (_collapse % 50)  # invisible chars force new widget when we want collapsed
    with st.expander(_expander_label, expanded=False):
        st.markdown("*Click any example to try it:*")
        col1, col2, col3 = st.columns(3)
        
    with col1:
        st.markdown("**📊 Player Stats**")
        
        # Dynamic top scorers
        q1 = f"top scorers in {user_club}"
        if st.button(q1, key="ex1", use_container_width=False):
            st.session_state["clicked_query"] = q1
            st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
            st.rerun()
        
        # Dynamic yellow cards
        q2 = f"yellow cards {user_club} {user_age}"
        if st.button(q2, key="ex2", use_container_width=False):
            st.session_state["clicked_query"] = q2
            st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
            st.rerun()
        
        # Dynamic personal stats
        q3 = f"stats for {user_name}"
        if st.button(f"my stats ({user_name})", key="ex3", use_container_width=False):
            st.session_state["clicked_query"] = q3
            st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
            st.rerun()

        # Dynamic team stats
        q4 = f"team stats for {user_club} {user_age}"
        if st.button(q4, key="ex4", use_container_width=False):
            st.session_state["clicked_query"] = q4
            st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
            st.rerun()
        
        st.markdown("**📅 Fixtures**")
        if st.button("my next match", key="ex5", use_container_width=False):
            # The agent logic should handle "my next match" based on session user info
            st.session_state["clicked_query"] = "my next match"
            st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
            st.rerun()
        
        q6 = f"upcoming fixtures {user_club}"
        if st.button(q6, key="ex6", use_container_width=False):
            st.session_state["clicked_query"] = q6
            st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
            st.rerun()

    with col2:
        st.markdown("**🏆 Competitions**")
        # You can keep these generic or tie them to the competition the age group plays in
        q7 = f"{user_league} ladder"  # Instead of f"{user_age} YPL2 ladder"
        if st.button(q7, key="ex7", use_container_width=False):
            st.session_state["clicked_query"] = q7
            st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
            st.rerun()
        
        q8 = f"{user_competition} ladder"  # Instead of f"{user_age} YPL2 ladder"
        if st.button(q8, key="ex8", use_container_width=False):
            st.session_state["clicked_query"] = q8
            st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
            st.rerun()
        
        st.markdown("**👔 Coaches & Staff**")
        q16 = f"coaches for {user_club}"
        if st.button(q16, key="ex16", use_container_width=False):
            st.session_state["clicked_query"] = q16
            st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
            st.rerun()

    with col3:
        st.markdown("**🟨🟥 Discipline**")
        # ... previous red cards logic ...
        q10 = f"red cards in {user_age}"
        if st.button(q10, key="ex10", use_container_width=False):
            st.session_state["clicked_query"] = q10
            st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
            st.rerun()
            
        st.markdown("**⚠️ Missing Scores**")
        q13 = f"missing scores {user_club}"
        if st.button(q13, key="ex13", use_container_width=False):
            st.session_state["clicked_query"] = q13
            st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
            st.rerun()
        st.markdown("**📊 Today's Games**")
        
        q14 = "todays results"
        if st.button("Today's Results", key="q14", use_container_width=False):  # ← Nice label
            st.session_state["clicked_query"] = q14
            st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
            st.rerun()
            
        q15 = "missing scores today"
        if st.button(q15, key="q15", use_container_width=False):
            st.session_state["clicked_query"] = q15
            st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
            st.rerun()
    # Process search queries
    if search and search != st.session_state["last_search"]:
        st.session_state["last_search"] = search
        st.session_state["expander_state"] = False  # Collapse expander after search
        st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1

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
        
        # Add clickable league buttons
        st.markdown("**Click a league name to open:**")
        cols = st.columns(min(len(leagues), 4))  # Max 4 columns
        for idx, league_name in enumerate(leagues):
            col_idx = idx % 4
            with cols[col_idx]:
                if st.button(league_name, key=f"league_btn_{idx}", use_container_width=True):
                    st.session_state["selected_league"] = league_name
                    st.session_state["level"] = "competition"
                    
                    # Log the view
                    log_view(
                        username=st.session_state["username"],
                        full_name=st.session_state["full_name"],
                        view_type="league",
                        league=league_name,
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
        
        # Add clickable competition buttons
        st.markdown("**Click a competition name to open:**")
        cols = st.columns(min(len(comps), 4))  # Max 4 columns
        for idx, comp_name in enumerate(comps):
            col_idx = idx % 4
            with cols[col_idx]:
                if st.button(comp_name, key=f"comp_btn_{idx}", use_container_width=True):
                    st.session_state["selected_competition"] = comp_name
                    st.session_state["level"] = "ladder_clubs"
                    st.session_state["selected_club"] = None
                    st.session_state["selected_match_id"] = None
                    
                    # Log the view
                    log_view(
                        username=st.session_state["username"],
                        full_name=st.session_state["full_name"],
                        view_type="competition",
                        league=league,
                        competition=comp_name,
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
                    "Points": club.get("total_position_points", 0),
 #                   "Teams": club.get("age_group_count", 0),
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
            # --- START OF COLUMN CONFIGURATION ---
            # 1. Define fixed columns first
            configs = {
                "Rank": st.column_config.NumberColumn("Rank", width="small"),
                "Club": st.column_config.TextColumn("Club", width="large"), # <--- Increased width
                "Points": st.column_config.NumberColumn("Pts", width="small"),
                "GF": st.column_config.NumberColumn("GF", width="small"),
                "GA": st.column_config.NumberColumn("GA", width="small"),
                "GD": st.column_config.NumberColumn("GD", width="small"),
            }
            
            # 2. Add dynamic age group columns to the config as "small"
            for age in age_groups:
                configs[age] = st.column_config.TextColumn(age, width="small")
            # --- END OF COLUMN CONFIGURATION ---
            st.dataframe(df_overview, hide_index=True, use_container_width=False, height=598)
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
        
        st.markdown("---")
        st.markdown("**Select from ladder table below:**")
        
        currently_selected = st.session_state.get("selected_club")
        ladder_df["Select"] = ladder_df["ClubDisplay"].apply(lambda x: x == currently_selected)

        edited = st.data_editor(
            ladder_df[["Select", "Pos", "ClubDisplay", "played", "wins", "draws", "losses",
                       "gf", "ga", "gd", "points"]],
            hide_index=True,
            column_config={
                "Select": st.column_config.CheckboxColumn("Select", help="Select club",width="small", default=False),
                "ClubDisplay": st.column_config.TextColumn("Club", width="medium"),
                "Pos": st.column_config.NumberColumn("Pos", width="small"),
                "points": st.column_config.NumberColumn("Pts", width="small"),
                "played": st.column_config.NumberColumn("P", width="small"),
                "wins": st.column_config.NumberColumn("W", width="small"),
                "draws": st.column_config.NumberColumn("D", width="small"),
                "losses": st.column_config.NumberColumn("L", width="small"),
                "gf": st.column_config.NumberColumn("GF", width="small"),
                "ga": st.column_config.NumberColumn("GA", width="small"),
                "gd": st.column_config.NumberColumn("GD", width="small")

            },
            disabled=["Pos", "ClubDisplay", "points", "played", "wins", "draws", "losses",
                      "gf", "ga", "gd"],
            use_container_width=False,
            height=590,  # Increased height to show ~18 rows
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
                        use_container_width=False,
                        key="club_matches_editor"
                    )

                    selected_match_rows = edited_matches[edited_matches["Select"] == True]
                    current_selection_ids = list(df_matches.iloc[selected_match_rows.index]["_match_hash_id"])
                    # If more than one is selected, we want the "newest" one (the last in the list)
                    if len(current_selection_ids) > 0:
                        new_match_id = current_selection_ids[-1] # Take the most recent click
                        if st.session_state.get("selected_match_id") != new_match_id:
                            st.session_state["selected_match_id"] = new_match_id
                            st.rerun()
                    elif st.session_state.get("selected_match_id") is not None:
                        # If everything was unselected, clear the state
                        st.session_state["selected_match_id"] = None
                        st.rerun()
                    if not selected_match_rows.empty:
                        idx = selected_match_rows.index[0]
                        new_match_id = df_matches.iloc[idx]["_match_hash_id"]
                        # Only rerun if we're selecting a different match
                        if st.session_state.get("selected_match_id") != new_match_id:
                            st.session_state["selected_match_id"] = new_match_id
                            st.rerun()
                    elif st.session_state.get("selected_match_id"):
                        # Deselect if checkbox was unchecked
                        st.session_state["selected_match_id"] = None
                        st.rerun()
                else:
                    st.info(f"No matches found")

            with col_players:
                st.markdown(f"### 👤 Squad")
                
                # Get all people (players + staff) for this club in this competition
                all_people = get_players_for_club(players_data, club, comp, staff_data)

                if search and not is_natural_language_query(search):
                    all_people = [
                        p for p in all_people
                        if search.lower() in f"{p.get('first_name','')} {p.get('last_name','')}".lower()
                    ]

                selected_match_id = st.session_state.get("selected_match_id")
                if selected_match_id:
                    st.info(f"🎯 Filtered by selected match")
                                    # Get the selected match details
                    selected_match = None
                    for m in matches:
                        if m.get("attributes", {}).get("match_hash_id") == selected_match_id:
                            selected_match = m
                            break
                    if selected_match:
                        attrs = selected_match.get("attributes", {})
                        home = attrs.get("home_team_name")
                        away = attrs.get("away_team_name")
                        hs = attrs.get("home_score")
                        as_ = attrs.get("away_score")
                        is_home = (base_club_name(home) == club)
                        opponent = away if is_home else home
                        our_score = hs if is_home else as_
                        opp_score = as_ if is_home else hs
                        
                        # Match summary box
                        st.info(f"**{format_date_full(attrs.get('date', ''))}** vs {base_club_name(opponent)} - **{our_score}-{opp_score}**")
                    # Filter players who played in this match
                    all_people = [p for p in all_people if player_played_in_match(p, selected_match_id)]

                # Separate players and non-players
#                players = [p for p in all_people if not p.get("role") or p.get("role") == "player"]
#                non_players = [p for p in all_people if p.get("role") and p.get("role") != "player"]
                players = [
                    p for p in all_people 
                    if not p.get("role") or p.get("role").lower() == "player"
                ]

                non_players = [
                    p for p in all_people 
                    if p.get("role") and p.get("role").lower() != "player"
                ]
                # PLAYERS TABLE
                if players:
                    st.markdown("**Players**")
                    rows = []
                    for p in players:
                        full_name = f"{p.get('first_name','')} {p.get('last_name','')}"
                        
                        # ✅ NEW: Check if match selected for match-specific stats
                        if selected_match_id:
                            # Get match-specific data
                            match_data = get_player_match_stats(p, selected_match_id)
                            
                            if match_data:
                                # Add captain/goalie indicators to name
                                indicators = []
                                if match_data.get("captain"):
                                    indicators.append("(C)")
                                if match_data.get("goalie"):
                                    indicators.append("🥅")
                                
                                if indicators:
                                    full_name = f"{full_name} {' '.join(indicators)}"
                                
                                # Count events in this match for goals/cards
                                goals_in_match = 0
                                yellows_in_match = 0
                                reds_in_match = 0
                                
                                for event in match_data.get("events", []):
                                    event_type = event.get("event_type", "")
                                    if event_type == "goal":
                                        goals_in_match += 1
                                    elif event_type == "yellow_card":
                                        yellows_in_match += 1
                                    elif event_type == "red_card":
                                        reds_in_match += 1
                                
                                # Use match-specific stats
                                rows.append({
                                    "Select": False,
                                    "Player": full_name,
                                    "#": p.get("jersey", ""),
                                    "M": 1,  # This match
                                    "G": goals_in_match,
                                    "🟨": yellows_in_match,
                                    "🟥": reds_in_match,
                                })
                        else:
                            # No match selected - use season totals
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
                        use_container_width=False,
                        height=730,
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
                        use_container_width=False,
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
            use_container_width=False,
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
# Last auto-update: 2026-02-19 18:46:53 AEDT
# Last auto-update: 2026-02-19 19:29:21 AEDT
# Last auto-update: 2026-02-19 19:37:42 AEDT
# Last auto-update: 2026-02-19 20:00:16 AEDT
# Last auto-update: 2026-02-20 00:00:17 AEDT
# Last auto-update: 2026-02-20 04:00:18 AEDT
# Last auto-update: 2026-02-20 08:00:17 AEDT
# Last auto-update: 2026-02-20 12:00:17 AEDT
# Last auto-update: 2026-02-20 16:00:17 AEDT
# Last auto-update: 2026-02-20 20:00:17 AEDT
# Last auto-update: 2026-02-21 00:00:16 AEDT
# Last auto-update: 2026-02-21 04:00:17 AEDT
# Last auto-update: 2026-02-21 08:00:16 AEDT
# Last auto-update: 2026-02-21 12:00:16 AEDT
# Last auto-update: 2026-02-21 13:25:33 AEDT
# Last auto-update: 2026-02-21 16:00:16 AEDT
# Last auto-update: 2026-02-21 20:00:16 AEDT
# Last auto-update: 2026-02-22 00:00:16 AEDT
# Last auto-update: 2026-02-22 01:00:17 AEDT
# Last auto-update: 2026-02-22 02:00:18 AEDT
# Last auto-update: 2026-02-22 03:00:17 AEDT
# Last auto-update: 2026-02-22 04:00:17 AEDT
# Last auto-update: 2026-02-22 05:00:18 AEDT
# Last auto-update: 2026-02-22 06:00:16 AEDT
# Last auto-update: 2026-02-22 07:00:16 AEDT
# Last auto-update: 2026-02-22 08:00:17 AEDT
# Last auto-update: 2026-02-22 09:00:16 AEDT
# Last auto-update: 2026-02-22 09:57:30 AEDT
# Last auto-update: 2026-02-22 10:00:17 AEDT
