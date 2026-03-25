import streamlit as st
from fast_agent import FastQueryRouter, format_date, format_date_full, format_date_aest, format_date_full_aest, iso_date_aest
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
from insights import show_insights_page

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
        try:
            headers = st.context.headers
        except Exception:
            headers = {}
        
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

try:
    from prediction_tracker import (
        get_prediction_for_match, get_predictions_for_club,
        get_all_upcoming_predictions, get_accuracy_stats,
        get_all_scored_predictions, score_predictions,
        generate_all_predictions, run_monday_predictions,
        list_snapshot_dates, get_snapshot_accuracy,
        get_snapshot_predictions, score_and_save_snapshot
    )
    PREDICTION_TRACKER_AVAILABLE = True
except ImportError:
    PREDICTION_TRACKER_AVAILABLE = False

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

    if "device_id" not in st.session_state:
        # Try to read device_id injected by the JS snippet below
        st.session_state["device_id"] = st.query_params.get("_did", "")
    
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
    if "show_season_page" not in st.session_state:
        st.session_state["show_season_page"] = False
    if "season_auto_load" not in st.session_state:
        st.session_state["season_auto_load"] = False
    if "show_predictions_page" not in st.session_state:
        st.session_state["show_predictions_page"] = False
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
    
    if "show_insights_page" not in st.session_state:
        st.session_state["show_insights_page"] = False    

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
    """Logout current user and fully reset session state"""
    try:
        if st.session_state.get("authenticated"):
            log_logout(
                username=st.session_state.get("username", "unknown"),
                full_name=st.session_state.get("full_name", "Unknown"),
                session_id=st.session_state.get("session_id", "")
            )
    except Exception:
        pass
    # Clear everything then re-set only the minimum needed to show login
    st.session_state.clear()
    st.session_state["authenticated"] = False
    st.session_state["session_id"]    = str(uuid.uuid4())
    st.session_state["explicitly_logged_out"] = True  # show login screen

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
                if st.button("Continue as " + saved_selection['name'], type="primary", width='content'):
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
                if st.button("Select Different Profile", width='content'):
                    clear_player_selection(st.session_state["session_id"])
                    st.rerun()
            
            st.markdown("---")
        
 # Quick login - no player selection needed
        st.markdown("### 👋 Quick Login")
        st.caption("Jump straight in — defaults to Heidelberg United U16 / Guest")
        if st.button("⚡ Login Now", type="primary", width='content', key="quick_login"):
            league, competition = get_player_league_info("Guest", "Heidelberg United", "U16")
            st.session_state["authenticated"] = True
            st.session_state["user_type"] = "player"
            st.session_state["username"] = "guest_default"
            st.session_state["full_name"] = "Guest Player"
            st.session_state["player_club"] = "Heidelberg United"
            st.session_state["player_age_group"] = "U16"
            st.session_state["player_role"] = "player"
            st.session_state["role"] = "player"
            st.session_state["last_activity"] = datetime.now()
            st.session_state["player_league"] = league
            st.session_state["player_competition"] = competition
            update_user_config("Heidelberg United", "U16")
            _did = st.session_state.get("device_id", "")
            _guest_id = f"guest_{_did[:8]}" if _did else "guest_unknown"
            st.session_state["username"]  = _guest_id
            st.session_state["full_name"] = f"Guest ({_did[:8]})" if _did else "Guest Player"
            log_login(
                username=_guest_id,
                full_name=st.session_state["full_name"],
                ip_address=get_client_ip(),
                session_id=st.session_state["session_id"]
            )
            st.rerun()

        st.markdown("---")

        # Player/Coach selection (optional)
        st.markdown("### 👤 Or Select a Specific Player/Coach Profile")
        
        # Load all players and coaches
        people = get_players_and_coaches_list(DATA_DIR)
        
        if not people:
            st.error("❌ No player or coach data found. Please ensure data files are loaded.")
            return
        
        # Create dropdown options
        options = [""] + [format_player_display(p) for p in people]
        
        selected_display = st.selectbox(
            "Search your name (optional):",
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
                # Login immediately — no button needed
                st.session_state["authenticated"] = True
                st.session_state["user_type"] = "player"
                st.session_state["username"] = selected_person["player_id"]
                st.session_state["full_name"] = selected_person["name"]
                st.session_state["player_club"] = selected_person["club"]
                st.session_state["player_age_group"] = selected_person.get("age_group", "")
                st.session_state["player_role"] = selected_person["role"]
                st.session_state["role"] = selected_person["role"]
                st.session_state["last_activity"] = datetime.now()
                
                save_player_selection(st.session_state["session_id"], selected_person)
                update_user_config(selected_person["club"], selected_person.get("age_group", ""))
                league, competition = get_player_league_info(
                    selected_person["name"],
                    selected_person["club"],
                    selected_person.get("age_group", "")
                )
                st.session_state["player_league"] = league
                st.session_state["player_competition"] = competition
                log_login(
                    username=selected_person["player_id"],
                    full_name=selected_person["name"],
                    session_id=st.session_state["session_id"]
                )
                st.query_params["uid"] = selected_person["player_id"]
                st.rerun()    
        # Admin login section
        st.markdown("---")
        with st.expander("🔐 Admin Login"):
            st.markdown("### Administrator Access")
            
            with st.form("admin_login_form"):
                admin_username = st.text_input("Admin Username")
                admin_password = st.text_input("Admin Password", type="password")
                admin_submit = st.form_submit_button("Login as Admin", width='content')
                
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
                            # Default player context to Shaurya / Heidelberg United U16
                            st.session_state["player_club"] = "Heidelberg United"
                            st.session_state["player_age_group"] = "U16"
                            st.session_state["player_role"] = "player"
                            admin_league, admin_comp = get_player_league_info("Shaurya", "Heidelberg United", "U16")
                            st.session_state["player_league"] = admin_league
                            st.session_state["player_competition"] = admin_comp
                            
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
    """Get the last data update time from last_updated.json written by pipeline."""
    # Primary: dedicated last_updated.json written at end of each pipeline run
    lu_path = os.path.join(DATA_DIR, "last_updated.json")
    if os.path.exists(lu_path):
        try:
            with open(lu_path, 'r') as f:
                data = json.load(f)
            ts = data.get("last_updated", "")
            if ts:
                update_time = datetime.fromisoformat(ts)
                aest = pytz.timezone("Australia/Melbourne")
                if update_time.tzinfo is None:
                    update_time = pytz.UTC.localize(update_time)
                return update_time.astimezone(aest).strftime("%a, %d %b %Y, %I:%M %p AEST")
        except Exception:
            pass

    # Fallback: use file modification time
    results_path = os.path.join(DATA_DIR, "master_results.json")
    if not os.path.exists(results_path):
        return "Data file not found"
    try:
        mod_time = os.path.getmtime(results_path)
        utc_time = datetime.fromtimestamp(mod_time, tz=pytz.UTC)
        aest = pytz.timezone("Australia/Melbourne")
        aest_time = utc_time.astimezone(aest)
        return aest_time.strftime("%a, %d %b %Y, %I:%M %p AEST") + " (approx)"
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


def get_player_reg_info(player: dict, current_club: str, current_comp: str) -> dict:
    """Classify dual registrations relative to current club/competition."""
    p_teams = player.get("teams", [])
    if not p_teams and player.get("team_name"):
        p_teams = [player["team_name"]]

    current_age = ""
    for t in p_teams:
        if base_club_name(t) == current_club:
            ag = re.search(r'U\d{2}', t, re.IGNORECASE)
            if ag:
                current_age = ag.group(0).upper()
                break
    if not current_age:
        ag = re.search(r'U\d{2}', current_comp or "", re.IGNORECASE)
        if ag:
            current_age = ag.group(0).upper()

    current_team = f"{current_club} {current_age}".strip()
    other_teams  = [t for t in p_teams if t.strip() and t.strip() != current_team]

    same_club_other_ages, diff_clubs = [], []
    for t in other_teams:
        b = base_club_name(t)
        if b == current_club:
            ag = re.search(r'U\d{2}', t, re.IGNORECASE)
            if ag:
                same_club_other_ages.append(ag.group(0).upper())
        elif b:
            diff_clubs.append(b)

    badge_parts = []
    if same_club_other_ages:
        badge_parts.append("🔁 " + "/".join(same_club_other_ages))
    if diff_clubs:
        badge_parts.append("⚡ " + "/".join(c.split()[0] for c in diff_clubs))
    badge = "  " + " · ".join(badge_parts) if badge_parts else ""

    return {"age": current_age, "same_club_other_ages": same_club_other_ages,
            "diff_clubs": diff_clubs, "badge": badge}


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
            roles     = out.get("roles", [])
            role_slug = out.get("role_slug", "")
            out["role"] = (roles[0] if roles else (role_slug or "staff")) if is_staff else "player"
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
 
def style_ladder(df, comp):
    """Apply promotion/relegation zone colours based on competition."""
    n = len(df)
    # Build a list of background colours, one per row, default blank
    colours = [""] * n

    comp_upper = comp.upper()

    if "YPL1" in comp_upper:
        # Bottom 2 = light red
        for i in range(max(0, n - 2), n):
            colours[i] = "background-color: #FFCCCC"

    elif "YPL2" in comp_upper:
        # Top 2 = light green, bottom 2 = light red
        for i in range(min(2, n)):
            colours[i] = "background-color: #CCFFCC"
        for i in range(max(0, n - 2), n):
            colours[i] = "background-color: #FFCCCC"

    elif "YSL" in comp_upper:
        # Top 1 = light green
        if n > 0:
            colours[0] = "background-color: #CCFFCC"

    # Apply same colour to every cell in the row
    return pd.DataFrame(
        [([c] * len(df.columns)) for c in colours],
        index=df.index,
        columns=df.columns,
    )

 
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

def compute_overall_points_ladder(results, league):
    """
    Overall ladder based on actual match POINTS (W=3, D=1, L=0) summed
    across ALL age groups in a league. Uses base club name to merge teams.
    """
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

    for item in results:
        attrs = item.get("attributes", {})
        league_name = attrs.get("league_name", "")
        if not league_name:
            continue
        if extract_league_from_league_name(league_name) != league:
            continue
        if attrs.get("status") != "complete":
            continue

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

        home_base = base_club_name(home)
        away_base = base_club_name(away)

        for team_base in [home_base, away_base]:
            if table[team_base]["club"] == "":
                table[team_base]["club"] = team_base

        table[home_base]["played"] += 1
        table[away_base]["played"] += 1
        table[home_base]["gf"] += hs
        table[home_base]["ga"] += as_
        table[away_base]["gf"] += as_
        table[away_base]["ga"] += hs

        if hs > as_:
            table[home_base]["wins"] += 1
            table[away_base]["losses"] += 1
            table[home_base]["points"] += 3
        elif hs < as_:
            table[away_base]["wins"] += 1
            table[home_base]["losses"] += 1
            table[away_base]["points"] += 3
        else:
            table[home_base]["draws"] += 1
            table[away_base]["draws"] += 1
            table[home_base]["points"] += 1
            table[away_base]["points"] += 1

    for team, row in table.items():
        row["gd"] = row["gf"] - row["ga"]

    ladder = sorted(
        table.values(),
        key=lambda r: (
            -r["points"],
            -r["gd"],
            -r["gf"],
            r["club"].lower(),
        ),
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
        "ypl1", "ypl2", "ysl", "overdue",
        "coach", "coaches", "staff", "manager", "managers",
        "today", "todays", "result", "cards this week", "all cards",
        "latest results", "latest result", "recent results",
        "missing score", "missing scores", "overdue", "no score",
        "latest missing", "scores not entered",
        # Squad / player list queries
        "show me", "players for", "players in", "list players",
        "squad", "who plays", "players at",
        # Dual registration — all variants
        "dual", "cross club", "different club", "multiple club",
        "2 clubs", "2 teams", "two clubs", "two teams",
        "playing for 2", "playing for two", "2 or more",
        "registered in 2", "registered at 2",
        "dual matches", "matches both teams", "matches each team",
        "breakdown", " vs ", " v ",
        # Appearances / scorers
        "most appearances", "most matches", "most games", "appearances",
        "games played", "matches played", "top scorers", "golden boot",
        "leading scorer",
        # Match detail triggers
        "match detail", "match details", "game detail", "lineups for",
        "stats for", "details",
        "total cards", "card summary", "cards by", "cards per", "cards each",
        "cards per club", "card per club",
        "own goal", "own goals",
        # Season summary
        "season summary", "season", "full season",
        "results and fixtures", "fixtures and results",
        "all matches", "all results", "all fixtures",
        # Predicted ladder and match prediction (admin example buttons only, but queries work for all)
        "predicted ladder", "predict ladder", "ladder after",
        "predicted standings", "end of season ladder", "projected ladder",
        "where will i finish", "final ladder",
        "predict", "prediction", "score prediction", "preview",
    ]
    return any(keyword in query.lower() for keyword in keywords)

# ---------------------------------------------------------
# Admin Dashboard
# ---------------------------------------------------------

def show_admin_dashboard():
    """Display admin dashboard with activity analytics"""
    st.markdown("## 📊 Admin Dashboard")

    # ── Force data refresh button ──
    col_r1, col_r2, col_r3 = st.columns([1, 2, 5])
    with col_r1:
        if st.button("🔄 Force Refresh Data", width='content'):
            try:
                from fast_agent import _load_all_data, _refresh_data
                _load_all_data.clear()
                _refresh_data()
                st.success("✅ Data reloaded from disk!")
            except Exception as e:
                st.error(f"Refresh failed: {e}")
    with col_r2:
        try:
            from fast_agent import _load_all_data
            import inspect
            # Show when cache was last populated (approximate)
            st.caption("Cache refreshes every 5 min automatically")
        except Exception:
            pass

    st.markdown("---")
    # Tabs for different views

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📈 Analytics", "👥 Users", "📋 Recent Activity", "🌐 IP Tracking", "🔮 Predictions"])
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
                st.dataframe(df_users, hide_index=True, width='content')
        
        with col2:
            st.markdown("### 🏟️ Most Viewed Clubs")
            if stats.get('top_clubs'):
                df_clubs = pd.DataFrame(
                    list(stats['top_clubs'].items()),
                    columns=['Club', 'Views']
                ).sort_values('Views', ascending=False).head(10)
                st.dataframe(df_clubs, hide_index=True, width='content')
    
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
            
            st.dataframe(df_active, hide_index=True, width='content')
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
                width='content',
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
                    st.dataframe(ip_counts, hide_index=True, width='content')
                
                with col2:
                    st.markdown("#### 🔐 Recent Logins by IP")
                    logins = df[df['action_type'] == 'login'][['timestamp', 'username', 'full_name', 'ip_address']].head(20)
                    st.dataframe(logins, hide_index=True, width='content')
                    
                    st.markdown("#### 🔍 IP to User Mapping")
                    # Show which users use which IPs
                    user_ip_map = df_valid_ip.groupby(['username', 'ip_address']).size().reset_index(name='count')
                    user_ip_map = user_ip_map.sort_values('count', ascending=False).head(20)
                    st.dataframe(user_ip_map, hide_index=True, width='content')
            else:
                st.info("No IP address data available yet. IP tracking will start with the next login.")
        else:
            st.info("No activity data")

    with tab5:
        st.markdown("### 🔮 Match Predictions")

        if not PREDICTION_TRACKER_AVAILABLE:
            st.error("prediction_tracker.py not found. Ensure it is in the same directory as app.py.")
        else:
            # ── Accuracy summary ──────────────────────────────────────────────
            stats = get_accuracy_stats()
            if stats["total"] > 0:
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total scored",      stats["total"])
                col2.metric("Exact score ✅",    stats["correct_score"])
                col3.metric("Right result ✅",   stats["correct_result"])
                col4.metric("Wrong ❌",          stats["wrong"])
                st.metric("Overall accuracy",    f"{stats['accuracy_pct']}%")
                st.markdown("---")
            else:
                st.info("No scored predictions yet — predictions will be scored automatically after matches are played.")

            # ── Admin actions ─────────────────────────────────────────────────
            col_btn1, col_btn2, col_btn3 = st.columns(3)

            with col_btn1:
                if st.button("🔄 Score predictions now", key="score_now_btn"):
                    with st.spinner("Scoring…"):
                        n = score_predictions()
                    st.success(f"Scored {n} prediction{'s' if n != 1 else ''}.")
                    st.rerun()

            with col_btn2:
                if st.button("🔮 Generate missing predictions", key="gen_missing_btn"):
                    with st.spinner("Generating new predictions for unfilled fixtures…"):
                        generate_all_predictions(force=False)
                    st.success("Done — new predictions generated.")
                    st.rerun()

            with col_btn3:
                if st.button("♻️ Regenerate ALL predictions", key="regen_all_btn",
                             help="Force-regenerates every prediction. Takes a minute."):
                    with st.spinner("Regenerating all predictions for all clubs…"):
                        generate_all_predictions(force=True)
                    st.success("All predictions regenerated.")
                    st.rerun()

            st.markdown("---")

            # ── Upcoming predictions browser ──────────────────────────────────
            st.markdown("#### 🗓️ Upcoming Predictions")
            _comps = ["All"] + sorted({"YPL1","YPL2","YSL NW","YSL SE","YSL","VPL Men","VPL Women"})
            _comp_sel = st.selectbox("Filter by competition", _comps, key="pred_comp_filter")
            _comp_arg = "" if _comp_sel == "All" else _comp_sel

            upcoming_preds = get_all_upcoming_predictions(_comp_arg)
            if not upcoming_preds:
                st.info("No upcoming predictions stored. Click 'Generate missing predictions' above.")
            else:
                rows_up = []
                for e in upcoming_preds:
                    rows_up.append({
                        "Date":    e.get("match_date", ""),
                        "Comp":    e.get("comp_code", ""),
                        "Age":     e.get("age_grp", ""),
                        "Home":    e.get("home_short", "")[:20],
                        "Away":    e.get("away_short", "")[:20],
                        "Pred":    f"{e.get('pred_home')}–{e.get('pred_away')}",
                        "Home Win%": f"{e.get('win_pct_home','?')}%",
                        "Confidence": "⚠️ Low" if e.get("confidence") else "✅ OK",
                    })
                df_up = pd.DataFrame(rows_up)
                h = min(600, (len(df_up) + 1) * 35 + 10)
                sel_up = st.dataframe(df_up, hide_index=True, width='content', height=h,
                    selection_mode="single-row", on_select="rerun", key="pred_upcoming_sel")
                _usel = sel_up.selection.get("rows", [])
                if _usel:
                    e = upcoming_preds[_usel[0]]
                    st.info(f"💡 {e.get('one_liner','')}")
                    if st.button("🔮 Full prediction details", key="pred_detail_btn"):
                        _fire_query = lambda q: (
                            st.session_state.update({"clicked_query": q,
                                "show_admin_dashboard": False,
                                "expander_collapse_counter": st.session_state.get("expander_collapse_counter",0)+1})
                            or st.rerun()
                        )
                        st.session_state["clicked_query"] = (
                            f"predict {e.get('home','')} vs {e.get('away','')} {e.get('age_grp','')}")
                        st.session_state["show_admin_dashboard"] = False
                        st.rerun()

            st.markdown("---")

            # ── Scored predictions ────────────────────────────────────────────
            st.markdown("#### 📋 Past Predictions (Scored)")
            scored_preds = get_all_scored_predictions()
            if not scored_preds:
                st.info("No scored predictions yet.")
            else:
                rows_sc = []
                for e in scored_preds:
                    outcome = e.get("outcome", "")
                    label = {"correct_score": "✅ Exact", "correct_result": "✅ Result",
                             "wrong": "❌ Wrong"}.get(outcome, outcome)
                    rows_sc.append({
                        "Match Date":   e.get("match_date",""),
                        "Comp":         e.get("comp_code",""),
                        "Age":          e.get("age_grp",""),
                        "Home":         e.get("home_short","")[:18],
                        "Away":         e.get("away_short","")[:18],
                        "Predicted":    f"{e.get('pred_home')}–{e.get('pred_away')}",
                        "Actual":       f"{e.get('actual_home')}–{e.get('actual_away')}",
                        "Result":       label,
                    })
                df_sc = pd.DataFrame(rows_sc)
                h = min(600, (len(df_sc) + 1) * 35 + 10)
                st.dataframe(df_sc, hide_index=True, width='content', height=h)

            st.markdown("---")

            # ── Historical snapshots ──────────────────────────────────────────
            st.markdown("#### 🗂️ Historical Snapshots")
            snap_dates = list_snapshot_dates()

            if not snap_dates:
                st.info("No historical snapshots yet. They are created each time you run "
                        "prediction_tracker.py.")
            else:
                # Snapshot selector
                st.markdown("**Compare a specific snapshot against actuals**")
                col_snap, col_score_snap = st.columns([3, 1])
                with col_snap:
                    snap_labels = [f"{d} ({get_snapshot_accuracy(d)['total']} scored, "
                                   f"{get_snapshot_accuracy(d)['pending']} pending, "
                                   f"{get_snapshot_accuracy(d)['accuracy_pct']}% acc)"
                                   for d in snap_dates]
                    sel_snap = st.selectbox("Select snapshot", snap_labels,
                                            key="admin_snap_sel")
                    selected_date = snap_dates[snap_labels.index(sel_snap)] if sel_snap else None
                with col_score_snap:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🔄 Score this snapshot", key="score_snap_btn"):
                        if selected_date:
                            with st.spinner("Scoring…"):
                                n = score_and_save_snapshot(selected_date)
                            st.success(f"Scored {n} new predictions.")
                            st.rerun()

                if selected_date:
                    snap_stats = get_snapshot_accuracy(selected_date)
                    snap_preds = get_snapshot_predictions(selected_date)

                    # Accuracy metrics for this snapshot
                    if snap_stats["total"] > 0:
                        c1, c2, c3, c4, c5 = st.columns(5)
                        c1.metric("Scored",        snap_stats["total"])
                        c2.metric("Exact ✅",      snap_stats["correct_score"])
                        c3.metric("Result ✅",     snap_stats["correct_result"])
                        c4.metric("Wrong ❌",      snap_stats["wrong"])
                        c5.metric("Accuracy",      f"{snap_stats['accuracy_pct']}%")

                        # Factor accuracy breakdown
                        fa = snap_stats.get("factor_accuracy", {})
                        if fa:
                            st.markdown("**Which factors predicted best:**")
                            fa_rows = [{"Factors used": k,
                                        "Predictions": v["total"],
                                        "Correct": v["correct"],
                                        "Accuracy %": f"{v['pct']}%"}
                                       for k, v in fa.items()]
                            st.dataframe(pd.DataFrame(fa_rows), hide_index=True, width='content')

                    # Full prediction vs actual table
                    if snap_preds:
                        st.markdown("**Predicted vs Actual**")
                        rows_h = []
                        for e in snap_preds:
                            outcome = e.get("outcome")
                            label   = {"correct_score":  "✅ Exact",
                                       "correct_result": "✅ Result",
                                       "wrong":          "❌ Wrong"}.get(outcome, "⏳ Pending")
                            act_h = e.get("actual_home")
                            act_a = e.get("actual_away")
                            rows_h.append({
                                "Match Date": e.get("match_date",""),
                                "Comp":       e.get("comp_code",""),
                                "Age":        e.get("age_grp",""),
                                "Home":       e.get("home_short","")[:18],
                                "Away":       e.get("away_short","")[:18],
                                "Predicted":  f"{e.get('pred_home')}–{e.get('pred_away')}",
                                "Actual":     f"{act_h}–{act_a}" if act_h is not None else "—",
                                "Home Win%":  f"{e.get('win_pct_home','?')}%",
                                "Result":     label,
                                "Method":     e.get("weight_note","")[:40],
                            })
                        df_h = pd.DataFrame(rows_h)
                        h = min(600, (len(df_h) + 1) * 35 + 10)
                        st.dataframe(df_h, hide_index=True, width='content', height=h)
            
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
                
                return league, competition
        # Not found (expected for Guest/anonymous)
        return '', ''
        
    except Exception as e:
        print(f"Error getting league info: {e}")
        return '', ''     
# ---------------------------------------------------------
# Main Application
# ---------------------------------------------------------

def _inject_device_id_script():
    """
    Inject a tiny JS snippet that:
      1. Reads (or creates) a UUID stored in localStorage under key 'dribl_did'
      2. Writes it into the URL as ?_did=xxxx so Streamlit can read it via st.query_params
    Runs once per page load; harmless on subsequent reruns.
    """
    st.components.v1.html("""
    <script>
    (function() {
        function uuidv4() {
            return ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c =>
                (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16));
        }
        var key = 'dribl_did';
        var did = localStorage.getItem(key);
        if (!did) {
            did = uuidv4();
            localStorage.setItem(key, did);
        }
        // Write into URL query param so Streamlit can read it
        var url = new URL(window.parent.location.href);
        if (url.searchParams.get('_did') !== did) {
            url.searchParams.set('_did', did);
            window.parent.history.replaceState({}, '', url.toString());
        }
    })();
    </script>
    """, height=0)


def _render_ladder_prediction(data: dict):
    """Render a predicted ladder result."""
    title         = data.get("title", "📊 Predicted Ladder")
    club          = data.get("club", "")
    club_token    = data.get("club_token", club.lower())
    n_matches     = data.get("n_matches", 0)
    our_pos_now   = data.get("our_pos_now", "?")
    our_pos_pred  = data.get("our_pos_predicted", "?")
    movement      = data.get("movement", "")
    pred_ladder   = data.get("predicted_ladder", [])
    extrap_ladder = data.get("extrap_ladder", [])
    fix_preds     = data.get("fixture_predictions", [])
    curr_ladder   = data.get("current_ladder", [])

    st.markdown(f"### {title}")

    # ── Summary banner ────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Current Position", f"{our_pos_now}/{len(curr_ladder)}")
    with col2:
        st.metric(f"Predicted (after {n_matches} matches)", f"{our_pos_pred}/{len(pred_ladder)}")
    with col3:
        st.metric("Movement", movement or "—")

    st.markdown("---")

    # ── Tabs: Predicted Ladder | Extrapolated | Fixture Predictions ───────────
    tabs = st.tabs(["🏆 Predicted Ladder", "📈 Extrapolated Rate", "🔮 Fixture Predictions"])

    with tabs[0]:
        st.caption("Based on predicting each remaining match using attack/defence strength model")
        if pred_ladder:
            df = pd.DataFrame(pred_ladder)[["Pos","Team","P","W","D","L","GF","GA","GD","Pts"]]
            df["Team"] = df["Team"].apply(
                lambda t: f"▶ {t}" if club_token in t.lower() else t)
            h = min(600, (len(df) + 1) * 35 + 10)
            st.dataframe(df, hide_index=True, width='content', height=h,
                column_config={
                    "Pos":  st.column_config.NumberColumn("Pos", width="small"),
                    "Team": st.column_config.TextColumn("Team", width="medium"),
                    "P":    st.column_config.NumberColumn("P",   width="small"),
                    "W":    st.column_config.NumberColumn("W",   width="small"),
                    "D":    st.column_config.NumberColumn("D",   width="small"),
                    "L":    st.column_config.NumberColumn("L",   width="small"),
                    "GF":   st.column_config.NumberColumn("GF",  width="small"),
                    "GA":   st.column_config.NumberColumn("GA",  width="small"),
                    "GD":   st.column_config.NumberColumn("GD",  width="small"),
                    "Pts":  st.column_config.NumberColumn("Pts", width="small"),
                })

    with tabs[1]:
        st.caption("Based on each team's current points-per-game rate × games remaining")
        if extrap_ladder:
            df_e = pd.DataFrame(extrap_ladder)[["Proj Pos","Team","Current Pts","PPG","Games Left","Projected Pts"]]
            df_e["Team"] = df_e["Team"].apply(
                lambda t: f"▶ {t}" if club_token in t.lower() else t)
            h = min(600, (len(df_e) + 1) * 35 + 10)
            st.dataframe(df_e, hide_index=True, width='content', height=h,
                column_config={
                    "Proj Pos":      st.column_config.NumberColumn("Pos",           width="small"),
                    "Team":          st.column_config.TextColumn("Team",            width="medium"),
                    "Current Pts":   st.column_config.NumberColumn("Current Pts",   width="small"),
                    "PPG":           st.column_config.NumberColumn("PPG",           width="small"),
                    "Games Left":    st.column_config.NumberColumn("Games Left",    width="small"),
                    "Projected Pts": st.column_config.NumberColumn("Projected Pts", width="small"),
                })

    with tabs[2]:
        st.caption("Predicted scorelines for each remaining fixture used in the model")
        if fix_preds:
            df_f = pd.DataFrame(fix_preds)
            h = min(600, (len(df_f) + 1) * 35 + 10)
            st.dataframe(df_f, hide_index=True, width='content', height=h,
                column_config={
                    "Date":  st.column_config.DateColumn("Date", format="ddd, DD-MMM", width="medium"),
                    "Home":  st.column_config.TextColumn("Home",  width="medium"),
                    "Score": st.column_config.TextColumn("Score", width="small"),
                    "Away":  st.column_config.TextColumn("Away",  width="medium"),
                    "When":  st.column_config.TextColumn("When",  width="small"),
                })
        else:
            st.info("No fixture predictions.")

    st.caption("📌 Statistical model only — not a guarantee. Predictions improve as more results come in.")


def show_predictions_page():
    """
    Standalone predictions page — all upcoming fixtures with predictions,
    grouped by competition and age group. Available to all users.
    """
    st.markdown("### 🔮 Match Predictions")
    st.caption("Predictions are generated every Monday and stored centrally. "
               "Win% is from the home team's perspective.")

    if not PREDICTION_TRACKER_AVAILABLE:
        st.warning("Predictions not available — prediction_tracker.py not found.")
        return

    # ── Filters ───────────────────────────────────────────────────────────────
    col_comp, col_club = st.columns([2, 3])
    with col_comp:
        comp_options = ["All competitions", "YPL1", "YPL2", "YSL NW", "YSL SE",
                        "YSL", "VPL Men", "VPL Women"]
        comp_sel = st.selectbox("Competition", comp_options, key="pred_page_comp")
    with col_club:
        club_filter = st.text_input("Filter by club (optional)",
                                    placeholder="e.g. heidelberg",
                                    key="pred_page_club")

    comp_arg = "" if comp_sel == "All competitions" else comp_sel
    all_preds = get_all_upcoming_predictions(comp_arg)

    if not all_preds:
        st.info("No predictions stored yet. Predictions are generated on Monday "
                "by the pipeline. Ask your admin to run 'Generate missing predictions'.")
        return

    # Apply club filter
    if club_filter.strip():
        cl = club_filter.strip().lower()
        all_preds = [p for p in all_preds
                     if cl in p.get("home", "").lower()
                     or cl in p.get("away", "").lower()]
        if not all_preds:
            st.info(f"No predictions found for '{club_filter}'.")
            return

    # ── Group by comp_code then age_grp ──────────────────────────────────────
    from collections import defaultdict
    grouped = defaultdict(list)
    for p in all_preds:
        key = f"{p.get('comp_code','Other')} — {p.get('age_grp','?')}"
        grouped[key].append(p)

    for group_label in sorted(grouped.keys()):
        matches = grouped[group_label]
        with st.expander(f"**{group_label}** — {len(matches)} fixtures", expanded=True):
            rows = []
            for m in matches:
                win_pct  = m.get("win_pct_home", "?")
                pred_h   = m.get("pred_home", "?")
                pred_a   = m.get("pred_away", "?")
                conf     = "⚠️" if m.get("confidence") else ""
                rows.append({
                    "Date":       m.get("match_date_display", m.get("match_date", "")),
                    "Home":       m.get("home_short", m.get("home", ""))[:22],
                    "Away":       m.get("away_short", m.get("away", ""))[:22],
                    "Pred":       f"{pred_h}–{pred_a}",
                    "Home Win%":  f"{win_pct}%" if win_pct != "?" else "—",
                    "Note":       conf,
                    "_one_liner": m.get("one_liner", ""),
                })

            df = pd.DataFrame(rows)
            _key = f"pred_page_{group_label.replace(' ','_')}_{st.session_state.get('expander_collapse_counter',0)}"
            h = min(500, (len(df) + 1) * 35 + 10)
            sel = st.dataframe(
                df[["Date", "Home", "Away", "Pred", "Home Win%", "Note"]],
                hide_index=True, width='content', height=h,
                selection_mode="single-row", on_select="rerun",
                key=_key,
                column_config={
                    "Date":      st.column_config.DateColumn("Date", format="ddd, DD-MMM", width="medium"),
                    "Home":      st.column_config.TextColumn("Home",      width="medium"),
                    "Away":      st.column_config.TextColumn("Away",      width="medium"),
                    "Pred":      st.column_config.TextColumn("Pred",      width="small"),
                    "Home Win%": st.column_config.TextColumn("Home Win%", width="small"),
                    "Note":      st.column_config.TextColumn("",          width="small"),
                }
            )
            _sel = sel.selection.get("rows", [])
            if _sel:
                _one_liner = rows[_sel[0]].get("_one_liner", "")
                if _one_liner:
                    st.info(f"💡 {_one_liner}")

    # ── Accuracy footer ───────────────────────────────────────────────────────
    stats = get_accuracy_stats()
    if stats["total"] > 0:
        st.markdown("---")
        st.caption(
            f"📊 Prediction accuracy so far: **{stats['accuracy_pct']}%** "
            f"({stats['correct_result']} correct results, "
            f"{stats['correct_score']} exact scores) "
            f"from {stats['total']} scored predictions."
        )


def _render_prediction(data: dict):
    """Render a match prediction: one-liner first, full details in expander."""
    club_a       = data.get("club_a", "")
    club_b       = data.get("club_b", "")
    pred_a       = data.get("pred_a", 0)
    pred_b       = data.get("pred_b", 0)
    xg_a         = data.get("xg_a", 0)
    xg_b         = data.get("xg_b", 0)
    verdict      = data.get("verdict", "")
    win_pct_a    = data.get("win_pct_a", 50)
    one_liner    = data.get("one_liner", "")
    form_a       = data.get("form_a", "")
    form_b       = data.get("form_b", "")
    att_a        = data.get("att_a", 1.0)
    def_a        = data.get("def_a", 1.0)
    att_b        = data.get("att_b", 1.0)
    def_b        = data.get("def_b", 1.0)
    form_rows_a  = data.get("form_rows_a", [])
    form_rows_b  = data.get("form_rows_b", [])
    league_avg   = data.get("league_avg", 0)
    confidence_note = data.get("confidence_note", "")
    reasoning    = data.get("reasoning", "")

    st.markdown(f"### {data.get('title', '🔮 Match Prediction')}")

    # ── One-liner summary ─────────────────────────────────────────────────────
    st.markdown(f"**{one_liner}**")
    if confidence_note:
        st.warning(confidence_note)

    # ── Details expander ──────────────────────────────────────────────────────
    with st.expander("📊 Full details", expanded=False):
        # Score display
        col_a, col_score, col_b = st.columns([3, 2, 3])
        with col_a:
            st.markdown(f"**{club_a}**")
            st.caption(f"xG: {xg_a} | Attack {att_a:.2f}x | Defence {def_a:.2f}x")
        with col_score:
            st.markdown(
                f"<div style='text-align:center;font-size:2rem;font-weight:bold;"
                f"padding:0.3rem 0;'>{pred_a} – {pred_b}</div>",
                unsafe_allow_html=True
            )
            st.markdown(f"<div style='text-align:center'>{verdict}</div>",
                        unsafe_allow_html=True)
        with col_b:
            st.markdown(f"**{club_b}**")
            st.caption(f"xG: {xg_b} | Attack {att_b:.2f}x | Defence {def_b:.2f}x")

        st.caption(f"League avg goals/team: {league_avg} | "
                   f"Based on {data.get('matches_used_a','?')} matches for {club_a}, "
                   f"{data.get('matches_used_b','?')} for {club_b}")

        if reasoning:
            st.markdown("**💡 Why:**")
            st.markdown(reasoning)

        st.markdown("---")
        tabs = st.tabs([f"📋 {club_a[:18]} Form", f"📋 {club_b[:18]} Form"])
        with tabs[0]:
            st.caption(f"Form: {form_a}")
            if form_rows_a:
                st.dataframe(pd.DataFrame(form_rows_a), hide_index=True, width='content',
                    height=(len(form_rows_a) + 1) * 35 + 10,
                    column_config={
                        "Date":     st.column_config.DateColumn("Date", format="ddd, DD-MMM", width="medium"),
                        "H/A":      st.column_config.TextColumn("H/A",      width="small"),
                        "Opponent": st.column_config.TextColumn("Opponent", width="medium"),
                        "Score":    st.column_config.TextColumn("Score",    width="small"),
                    })
        with tabs[1]:
            st.caption(f"Form: {form_b}")
            if form_rows_b:
                st.dataframe(pd.DataFrame(form_rows_b), hide_index=True, width='content',
                    height=(len(form_rows_b) + 1) * 35 + 10,
                    column_config={
                        "Date":     st.column_config.DateColumn("Date", format="ddd, DD-MMM", width="medium"),
                        "H/A":      st.column_config.TextColumn("H/A",      width="small"),
                        "Opponent": st.column_config.TextColumn("Opponent", width="medium"),
                        "Score":    st.column_config.TextColumn("Score",    width="small"),
                    })


def _strip_age_group_display(name: str) -> str:
    """Strip age group suffix for display e.g. 'Heidelberg United FC U16' → 'Heidelberg United FC'."""
    import re as _re
    return _re.sub(r'\s+U\d{2}$', '', (name or ""), flags=_re.IGNORECASE).strip()


def _render_season_summary(data: dict):
    """Render tool_club_season() output inside app.py."""
    club         = data.get("club", "")
    age_filter   = data.get("age_filter", "")
    past         = data.get("past", [])
    upcoming     = data.get("upcoming", [])
    ladder       = data.get("ladder", [])
    top_scorers  = data.get("top_scorers", [])
    discipline   = data.get("discipline", [])
    latest_match = data.get("latest_match")

    title_suffix = f" {age_filter}" if age_filter else " — All Age Groups"
    st.markdown(f"### 📋 Season Summary: **{club}**{title_suffix}")

    if not past and not upcoming and not ladder:
        st.warning(f"No season data found for {club}{title_suffix}.")
        return

    # ── Top summary row: standings ────────────────────────────────────────────
    if ladder:
        st.markdown("#### 📊 Standings")
        for s in ladder:
            medal = "🥇" if s["pos"] == 1 else ("🥈" if s["pos"] == 2 else ("🥉" if s["pos"] == 3 else "  "))
            st.markdown(
                f"{medal} **{s['label']}** — "
                f"Position **{s['pos']}/{s['total']}** &nbsp;|&nbsp; "
                f"**{s['pts']} pts** &nbsp;|&nbsp; "
                f"W{s['w']} D{s['d']} L{s['l']} &nbsp;|&nbsp; GD {s['gd']}"
            )

    # ── Summary: top scorers + discipline + latest match ─────────────────────
    sum_col1, sum_col2, sum_col3 = st.columns(3)

    with sum_col1:
        st.markdown("**⚽ Top Scorers**")
        if top_scorers:
            for i, p in enumerate(top_scorers[:5], 1):
                st.caption(f"{i}. {p['Player']} — {p['Goals']} goals ({p['Per Game']}/game)")
        else:
            st.caption("No scorer data yet.")

    with sum_col2:
        st.markdown("**🟨 Discipline**")
        if discipline:
            for p in discipline[:5]:
                st.caption(f"{p['Player']} — 🟨{p['🟨']} 🟥{p['🟥']}")
        else:
            st.caption("No cards yet.")

    with sum_col3:
        st.markdown("**📅 Latest Match**")
        if not age_filter and len(set(m["age"] for m in past)) > 1:
            # Multiple age groups — show one latest per age group
            age_groups_past = sorted(set(m["age"] for m in past))
            for ag in age_groups_past:
                ag_past = [m for m in past if m["age"] == ag]
                if ag_past:
                    latest = ag_past[-1]
                    st.caption(
                        f"**{ag}** {latest['icon']} {latest['date']}  "
                        f"{_strip_age_group_display(latest.get('home',''))} "
                        f"{latest['score']} "
                        f"{_strip_age_group_display(latest.get('away',''))}"
                    )
                    if latest.get("hash"):
                        if st.button(f"📋 {ag} details", key=f"latest_match_btn_{club}_{ag}"):
                            st.session_state["clicked_query"] = f"match details {latest['hash']}"
                            st.session_state["show_season_page"] = False
                            st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
                            st.rerun()
        elif latest_match:
            # Single age group — show full detail
            st.caption(
                f"{latest_match['icon']} {latest_match['date']}  "
                f"{_strip_age_group_display(latest_match['home'])} "
                f"{latest_match['score']} "
                f"{_strip_age_group_display(latest_match['away'])}"
            )
            if latest_match.get("goals"):
                for g in latest_match["goals"]:
                    st.caption(f"⚽ {g['player']} {g['min']}'")
            if latest_match.get("cards"):
                for c in latest_match["cards"]:
                    icon = "🟥" if "red" in (c["type"] or "").lower() else "🟨"
                    st.caption(f"{icon} {c['player']} {c['min']}'")
            if latest_match.get("hash"):
                if st.button("📋 Full match details", key=f"latest_match_btn_{club}"):
                    st.session_state["clicked_query"] = f"match details {latest_match['hash']}"
                    st.session_state["show_season_page"] = False
                    st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
                    st.rerun()
        else:
            st.caption("No matches played yet.")

    st.markdown("---")

    # ── One tab per age group ─────────────────────────────────────────────────
    age_groups = sorted(set([m["age"] for m in past] + [m["age"] for m in upcoming]))
    if not age_groups:
        return

    # When no age filter and multiple age groups — prepend an "All Matches" tab
    show_all_tab = (not age_filter) and len(age_groups) > 1
    tab_labels   = (["📋 All Matches"] if show_all_tab else []) + [f"⚽ {ag}" for ag in age_groups]
    tabs         = st.tabs(tab_labels)
    tab_offset   = 1 if show_all_tab else 0

    # ── All Matches tab ───────────────────────────────────────────────────────
    if show_all_tab:
        with tabs[0]:
            # Combined results — all age groups, sorted by date desc
            all_res_rows = []
            for m in sorted(past, key=lambda x: x.get("iso_date",""), reverse=True):
                all_res_rows.append({
                    "Date":     m.get("iso_date", m.get("date", "")),
                    "Age":      m["age"],
                    "Opponent": m["opponent"],
                    "Score":    f"{m['icon']} {m['score']}",
                    "Venue":    m.get("venue", ""),
                    "_hash":    m.get("hash", ""),
                    "_home":    m.get("home", ""),
                    "_away":    m.get("away", ""),
                    "_iso":     m.get("iso_date", ""),
                })

            if all_res_rows:
                st.markdown(f"**📋 All Results — {len(all_res_rows)} matches across {len(age_groups)} age groups**")
                st.caption("👇 Click a match row to view full match details")
                df_all = pd.DataFrame(all_res_rows)
                _all_key = f"season_all_{st.session_state.get('expander_collapse_counter',0)}"
                h = min(600, (len(df_all) + 1) * 35 + 10)
                sel_all = st.dataframe(
                    df_all[["Date","Age","Opponent","Score","Venue"]],
                    hide_index=True, width='content', height=h,
                    selection_mode="single-row", on_select="rerun",
                    key=_all_key,
                    column_config={
                        "Date":     st.column_config.DateColumn("Date", format="ddd, DD-MMM", width="medium"),
                        "Age":      st.column_config.TextColumn("Age",      width="small"),
                        "Opponent": st.column_config.TextColumn("Opponent", width="medium"),
                        "Score":    st.column_config.TextColumn("Score",    width="small"),
                        "Venue":    st.column_config.TextColumn("Venue",    width="medium"),
                    }
                )
                _ar = sel_all.selection.get("rows", [])
                if _ar:
                    _row  = all_res_rows[_ar[0]]
                    _hash = _row.get("_hash", "")
                    if _hash:
                        st.session_state["clicked_query"] = f"match details {_hash}"
                    else:
                        st.session_state["clicked_query"] = (
                            f"match details {_row['_home']} vs {_row['_away']} {_row['_iso']}"
                        )
                    st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
                    st.session_state["show_season_page"] = False
                    st.rerun()
            else:
                st.info("No results yet.")

            # Combined upcoming — all age groups
            all_fix_rows = []
            for m in sorted(upcoming, key=lambda x: x.get("dt", "")):
                opp_pos = m.get("opp_pos")
                pos_str = (f"{opp_pos}/{m.get('opp_total','?')} · {m.get('opp_pts','?')}pts · "
                           f"W{m.get('opp_w',0)} D{m.get('opp_d',0)} L{m.get('opp_l',0)}"
                           if opp_pos else "—")
                all_fix_rows.append({
                    "Date":         m.get("Date", m.get("date", "")),
                    "Time":         m.get("Time", ""),
                    "Age":          m["age"],
                    "H/A":          "🏠" if m.get("is_home") else "✈️",
                    "Opponent":     m["opponent"],
                    "Opp Standing": pos_str,
                    "Venue":        m["venue"],
                    "When":         m["when"],
                })

            if all_fix_rows:
                st.markdown(f"**🗓️ All Upcoming Fixtures — {len(all_fix_rows)}**")
                df_af = pd.DataFrame(all_fix_rows)
                h = min(400, (len(df_af) + 1) * 35 + 10)
                st.dataframe(
                    df_af[["Date","Time","Age","H/A","Opponent","Opp Standing","Venue","When"]],
                    hide_index=True, width='content', height=h,
                    key=f"season_all_fix_{st.session_state.get('expander_collapse_counter',0)}",
                    column_config={
                        "Date":         st.column_config.DateColumn("Date", format="ddd, DD-MMM", width="medium"),
                        "Time":         st.column_config.TextColumn("Time",          width="small"),
                        "Age":          st.column_config.TextColumn("Age",          width="small"),
                        "H/A":          st.column_config.TextColumn("H/A",          width="small"),
                        "Opponent":     st.column_config.TextColumn("Opponent",     width="medium"),
                        "Opp Standing": st.column_config.TextColumn("Opp Standing", width="medium"),
                        "Venue":        st.column_config.TextColumn("Venue",        width="medium"),
                        "When":         st.column_config.TextColumn("When",         width="small"),
                    }
                )

    for tab, age_grp in zip(tabs[tab_offset:], age_groups):
        with tab:
            age_past     = [m for m in past     if m["age"] == age_grp]
            age_upcoming = [m for m in upcoming if m["age"] == age_grp]

            # Find this age group's ladder section
            ladder_section = next((s for s in ladder if age_grp.lower() in s["label"].lower()), None)

            # ── Full ladder — clickable to fire team season query ─────────────
            if ladder_section:
                with st.expander(f"📊 Full {age_grp} Ladder", expanded=False):
                    club_lower = club.lower()
                    df_lad = pd.DataFrame(ladder_section["table"])
                    df_lad = df_lad.rename(columns={"PTS": "Pts"})
                    df_lad["Team"] = df_lad["Team"].apply(
                        lambda t: f"▶ {t}" if club_lower in t.lower() else t)
                    h = min(500, (len(df_lad) + 1) * 35 + 10)
                    st.caption("👇 Click a team to see their season summary")
                    _lad_key = f"season_lad_{age_grp}_{st.session_state.get('expander_collapse_counter',0)}"
                    sel_lad = st.dataframe(
                        df_lad, hide_index=True, width='content', height=h,
                        selection_mode="single-row", on_select="rerun",
                        key=_lad_key,
                        column_config={
                            "Pos":  st.column_config.NumberColumn("Pos", width="small"),
                            "Team": st.column_config.TextColumn("Team", width="medium"),
                            "P":    st.column_config.NumberColumn("P",   width="small"),
                            "W":    st.column_config.NumberColumn("W",   width="small"),
                            "D":    st.column_config.NumberColumn("D",   width="small"),
                            "L":    st.column_config.NumberColumn("L",   width="small"),
                            "GF":   st.column_config.NumberColumn("GF",  width="small"),
                            "GA":   st.column_config.NumberColumn("GA",  width="small"),
                            "GD":   st.column_config.NumberColumn("GD",  width="small"),
                            "Pts":  st.column_config.NumberColumn("Pts", width="small"),
                        }
                    )
                    _lr = sel_lad.selection.get("rows", [])
                    if _lr:
                        _team_name = df_lad.iloc[_lr[0]]["Team"].lstrip("▶ ").strip()
                        st.session_state["clicked_query"] = f"season {_team_name} {age_grp}"
                        st.session_state["show_season_page"] = False
                        st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
                        st.rerun()

            st.markdown("---")

            # ── Results ───────────────────────────────────────────────────────
            if age_past:
                w = sum(1 for m in age_past if m["outcome"] == "W")
                d = sum(1 for m in age_past if m["outcome"] == "D")
                l = sum(1 for m in age_past if m["outcome"] == "L")
                st.markdown(f"**📋 Results** — {len(age_past)} played &nbsp; 🟢{w} 🟡{d} 🔴{l}")
                st.caption("👇 Click a match row to view full match details")

                res_rows = []
                for m in age_past:
                    res_rows.append({
                        "Date":     m["date"],
                        "Opponent": m["opponent"],
                        "Score":    f"{m['icon']} {m['score']}",
                        "Venue":    m.get("venue", ""),
                        "_hash":    m.get("hash", ""),
                        "_home":    m.get("home", ""),
                        "_away":    m.get("away", ""),
                        "_iso":     m.get("iso_date", ""),
                    })

                df_r = pd.DataFrame(res_rows)
                _res_key = f"season_res_{age_grp}_{st.session_state.get('expander_collapse_counter',0)}"
                h = min(400, (len(df_r) + 1) * 35 + 10)
                sel_r = st.dataframe(
                    df_r[["Date", "Opponent", "Score", "Venue"]],
                    hide_index=True, width='content', height=h,
                    selection_mode="single-row", on_select="rerun",
                    key=_res_key,
                    column_config={
                        "Date":     st.column_config.DateColumn("Date", format="ddd, DD-MMM", width="medium"),
                        "Opponent": st.column_config.TextColumn("Opponent", width="medium"),
                        "Score":    st.column_config.TextColumn("Score",    width="small"),
                        "Venue":    st.column_config.TextColumn("Venue",    width="medium"),
                    }
                )
                _rr = sel_r.selection.get("rows", [])
                if _rr:
                    _row  = res_rows[_rr[0]]
                    _hash = _row.get("_hash", "")
                    if _hash:
                        st.session_state["clicked_query"] = f"match details {_hash}"
                    else:
                        st.session_state["clicked_query"] = (
                            f"match details {_row['_home']} vs {_row['_away']} {_row['_iso']}"
                        )
                    st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
                    st.session_state["show_season_page"] = False
                    st.rerun()
            else:
                st.info("No results yet.")

            st.markdown("---")

            # ── Upcoming fixtures ─────────────────────────────────────────────
            if age_upcoming:
                st.markdown(f"**🗓️ Upcoming Fixtures** — {len(age_upcoming)}")
                fix_rows = []
                for m in age_upcoming:
                    opp_pos = m.get("opp_pos")
                    pos_str = (f"{opp_pos}/{m.get('opp_total','?')} · {m.get('opp_pts','?')}pts · "
                               f"W{m.get('opp_w',0)} D{m.get('opp_d',0)} L{m.get('opp_l',0)}"
                               if opp_pos else "—")
                    fix_rows.append({
                        "Date":         m.get("Date", m.get("date", "")),
                        "Time":         m.get("Time", ""),
                        "H/A":          "🏠" if m.get("is_home") else "✈️",
                        "Opponent":     m["opponent"],
                        "Opp Standing": pos_str,
                        "Venue":        m["venue"],
                        "When":         m["when"],
                    })
                df_f = pd.DataFrame(fix_rows)
                h = min(400, (len(df_f) + 1) * 35 + 10)
                st.dataframe(
                    df_f[["Date","Time","H/A","Opponent","Opp Standing","Venue","When"]],
                    hide_index=True, width='content', height=h,
                    key=f"season_fix_{age_grp}_{st.session_state.get('expander_collapse_counter',0)}",
                    column_config={
                        "Date":         st.column_config.DateColumn("Date", format="ddd, DD-MMM", width="medium"),
                        "Time":         st.column_config.TextColumn("Time",          width="small"),
                        "H/A":          st.column_config.TextColumn("H/A",          width="small"),
                        "Opponent":     st.column_config.TextColumn("Opponent",     width="medium"),
                        "Opp Standing": st.column_config.TextColumn("Opp Standing", width="medium"),
                        "Venue":        st.column_config.TextColumn("Venue",        width="medium"),
                        "When":         st.column_config.TextColumn("When",         width="small"),
                    }
                )
            else:
                st.info("No upcoming fixtures.")


def show_season_page():
    """Dedicated Season Summary page triggered by sidebar button."""
    st.markdown("### 📋 Season Summary")

    # Always default to the logged-in user's own club
    default_club = st.session_state.get("player_club") or "Heidelberg United FC"
    default_age  = st.session_state.get("player_age_group") or ""

    col_club, col_age, col_go = st.columns([3, 1, 1])
    with col_club:
        club_input = st.text_input("Club", value=default_club, key="season_club_input")
    with col_age:
        age_input = st.text_input("Age group (optional)", value=default_age,
                                  placeholder="U16", key="season_age_input")
    with col_go:
        st.markdown("<br>", unsafe_allow_html=True)
        go = st.button("🔍 Go", key="season_go_btn", type="primary", width='content')

    # Auto-load on first open using the user's own club, or when Go is clicked
    if go or st.session_state.get("season_auto_load"):
        st.session_state["season_auto_load"] = False
        with st.spinner("Loading season data…"):
            try:
                from fast_agent import tool_club_season
                data = tool_club_season(club_input.strip(), age_input.strip())
                _render_season_summary(data)
            except Exception as e:
                st.error(f"Error loading season data: {e}")
    else:
        # Trigger auto-load immediately on first open
        st.session_state["season_auto_load"] = True
        st.rerun()


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
        if st.button("🚪 Logout", key="logout_button", width='content'):
            logout_user()
            st.session_state.clear()
            st.rerun()
    # Sidebar — admin only
    if st.session_state.get("role") == "admin":
        with st.sidebar:
            st.markdown("---")
            st.markdown("### 🔄 Admin Controls")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Refresh Data", width='content', help="Reload all data from files"):
                    force_reload_all_data()
                    st.success("✅ All data refreshed!")
                    st.rerun()
            
            with col2:
                last_update = get_last_updated_time()
                st.caption(f"📅 Updated:\n{last_update.split(',')[1] if ',' in last_update else last_update}")
            
            st.markdown("---")

    # Check for admin dashboard
    if st.session_state["role"] == "admin":
        with st.sidebar:
            st.markdown("### Admin Controls")
            if st.button("📊 View Dashboard", width='content'):
                st.session_state["show_admin_dashboard"] = True
    
    # Show admin dashboard if requested
    if st.session_state.get("show_admin_dashboard", False) and st.session_state["role"] == "admin":
        if st.button("⬅️ Back to App"):
            st.session_state["show_admin_dashboard"] = False
            st.rerun()
        show_admin_dashboard()
        return

    # ── Season Summary and Predictions page shortcuts (admin only) ──────────────
    if st.session_state.get("role") == "admin":
        with st.sidebar:
            st.markdown("---")
            if st.button("📋 Season Summary", key="sidebar_season_btn", width='content'):
                st.session_state["show_season_page"]      = True
                st.session_state["show_predictions_page"] = False
                st.session_state["season_auto_load"]      = True
                st.rerun()
            if st.button("🔮 Predictions", key="sidebar_predictions_btn", width='content'):
                st.session_state["show_predictions_page"] = True
                st.session_state["show_season_page"]      = False
                st.rerun()
            if st.button("📊 Insights", key="sidebar_insights_btn", width='content'):
                st.session_state["show_insights_page"]    = True
                st.session_state["show_season_page"]      = False
                st.session_state["show_predictions_page"] = False
                st.rerun()    

    if st.session_state.get("show_insights_page"):
        if st.button("⬅️ Back to App", key="insights_back_btn"):
            st.session_state["show_insights_page"] = False
            st.rerun()
        show_insights_page()
        return

    if st.session_state.get("show_predictions_page"):
        if st.button("⬅️ Back to App", key="pred_page_back_btn"):
            st.session_state["show_predictions_page"] = False
            st.rerun()
        show_predictions_page()
        return

    if st.session_state.get("show_season_page"):
        if st.button("⬅️ Back to App", key="season_back_btn"):
            st.session_state["show_season_page"] = False
            st.rerun()
        show_season_page()
        return
    


    # Search bar
    st.markdown("### 💬 Ask Me Anything")
    
    # ── Search state init ──────────────────────────────────────────────
    for _k, _v in [
        ("search_input",           ""),
        ("search_version",         0),
        ("last_processed_version", -1),
        ("search_answer",          None),
        ("search_answer_time",     0.0),
    ]:
        if _k not in st.session_state:
            st.session_state[_k] = _v

    # Consume a pending clear (set by league nav buttons AFTER widget renders)
    if st.session_state.pop("_pending_search_clear", False):
        st.session_state["search_input"]   = ""
        st.session_state["search_answer"]  = None
        st.session_state["search_version"] = 0
        st.session_state["last_processed_version"] = -1

    # Initialise history stack
    if "search_history" not in st.session_state:
        st.session_state["search_history"] = []

    # Consume _restore_search BEFORE widget renders (back-button restore)
    if "_restore_search" in st.session_state:
        _rs = st.session_state.pop("_restore_search")
        st.session_state["search_input"]       = _rs["query"]
        st.session_state["search_answer"]      = _rs["answer"]
        st.session_state["search_answer_time"] = _rs["answer_time"]
        st.session_state["search_version"]    += 1
        st.session_state["last_processed_version"] = st.session_state["search_version"]

    # Consume clicked_query BEFORE the widget renders so key= update is honoured
    if st.session_state.get("clicked_query"):
        _cq_prev_q   = st.session_state.get("search_input", "")
        _cq_prev_ans = st.session_state.get("search_answer")
        _cq_prev_t   = st.session_state.get("search_answer_time", 0.0)
        if _cq_prev_ans is not None and _cq_prev_q:
            _hist = st.session_state.get("search_history", [])
            _hist.append({"query": _cq_prev_q, "answer": _cq_prev_ans, "answer_time": _cq_prev_t})
            st.session_state["search_history"] = _hist[-20:]
        st.session_state["search_input"]   = st.session_state.pop("clicked_query")
        st.session_state["search_version"] += 1

    # key= lets Streamlit use session_state["search_input"] as the live value.
    # label must be non-empty; hidden with label_visibility.
    search = st.text_input(
        "Search",
        key="search_input",
        placeholder="Try: 'Stats for Shaurya', 'top scorers U16', 'cards this week', 'yellow cards U16', 'todays results'...",
        label_visibility="collapsed"
    )
    # Bump version when user types a new query (Enter key)
    if search and search != st.session_state.get("_last_typed", ""):
        st.session_state["_last_typed"]    = search
        st.session_state["search_version"] += 1
    # 1. Define dynamic labels based on session state
    user_club = st.session_state.get("player_club") or "Heidelberg United"
    user_age = st.session_state.get("player_age_group") or "U16"
    user_name = st.session_state.get("full_name") or "Guest"
    user_league = st.session_state.get("player_league") or "YPL2"
    user_competition = st.session_state.get("player_competition") or "YPL2"

    # ── Find next opponent for the user's team from fixtures ──
    def _get_next_opponent():
        """Return (opponent_base_name, is_home) for user's next upcoming fixture."""
        try:
            import pytz as _pytz
            from fast_agent import fixtures as _fixtures, USER_CONFIG as _UC, \
                parse_date_utc_to_aest as _parse, _strip_age_group as _strip
            melbourne_tz = _pytz.timezone('Australia/Melbourne')
            now = datetime.now(melbourne_tz)
            # Match on club name + age group independently (more robust than full team string)
            user_club_lower = (_UC.get("club") or "").lower()
            user_age_lower  = (_UC.get("age_group") or "").lower()
            upcoming = []
            for f in _fixtures:
                a = f.get("attributes", {})
                home = (a.get("home_team_name") or "")
                away = (a.get("away_team_name") or "")
                blob = f"{home} {away}".lower()
                if not user_club_lower or user_club_lower not in blob:
                    continue
                if user_age_lower and user_age_lower not in blob:
                    continue
                dt = _parse(a.get("date", ""))
                if dt and dt > now:
                    is_home = user_club_lower in home.lower()
                    opp_raw = a.get("away_team_name") if is_home else a.get("home_team_name")
                    opp_stripped = _strip(opp_raw or "").strip()
                    if opp_stripped:
                        upcoming.append((dt, opp_stripped, is_home))
            if not upcoming:
                return None, None
            upcoming.sort(key=lambda x: x[0])
            _, opp, is_home = upcoming[0]
            return opp, is_home
        except Exception:
            return None, None

    _next_opp, _next_is_home = _get_next_opponent()
    # Build the vs example: always "user_club vs Opponent"
    if _next_opp:
        _vs_query = f"{user_club} vs {_next_opp}"
        _vs_label = f"{'🏠' if _next_is_home else '✈️'} {_vs_query}"
    else:
        _vs_query = f"{user_club} vs Altona Magic"
        _vs_label = f"⚔️ {_vs_query}"

    # Example queries - collapse after click/search by changing label so Streamlit treats it as new widget
    _collapse = st.session_state.get("expander_collapse_counter", 0)
    _expander_label = "💡 Example Queries" + "\u200b" * (_collapse % 50)  # invisible chars force new widget when we want collapsed
    with st.expander(_expander_label, expanded=False):
        st.markdown("*Click any example to try it:*")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**📊 Player Stats**")

            q1 = f"top scorers in {user_club}"
            if st.button(q1, key="ex1", width='content'):
                st.session_state["clicked_query"] = q1
                st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
                st.rerun()

            q1b = f"most appearances in {user_club}"
            if st.button(q1b, key="ex1b", width='content'):
                st.session_state["clicked_query"] = q1b
                st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
                st.rerun()


            q3 = f"stats for {user_name}"
            if st.button(f"my stats ({user_name})", key="ex3", width='content'):
                st.session_state["clicked_query"] = q3
                st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
                st.rerun()

            st.markdown("**📅 Fixtures & Season**")
            if st.button("my next match", key="ex5", width='content'):
                st.session_state["clicked_query"] = "my next match"
                st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
                st.rerun()

            q_season = f"season {user_club} {user_age}"
            if st.button(f"📋 {user_club} {user_age} season", key="ex_season", width='content'):
                st.session_state["clicked_query"] = q_season
                st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
                st.rerun()

            if _next_opp:
                q_opp_season = f"season {_next_opp} {user_age}"
                if st.button(f"📋 {_next_opp} {user_age} season", key="ex_opp_season", width='content'):
                    st.session_state["clicked_query"] = q_opp_season
                    st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
                    st.rerun()

            q6 = f"upcoming fixtures {user_club}"
            if st.button(q6, key="ex6", width='content'):
                st.session_state["clicked_query"] = q6
                st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
                st.rerun()

        with col2:
            st.markdown("**👥 Squad & Dual Reg**")

            q_squad = f"squad for {user_club} {user_age}"
            if st.button(q_squad, key="ex_squad", width='content'):
                st.session_state["clicked_query"] = q_squad
                st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
                st.rerun()

            if _next_opp:
                q_squadOp = f"squad for {_next_opp} {user_age}"
                if st.button(f"opponent squad ({_next_opp})", key="ex_squadOp", width='content'):
                    st.session_state["clicked_query"] = q_squadOp
                    st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
                    st.rerun()

            q_dual = "2 clubs"
            if st.button("2 clubs", key="ex_dual", width='content'):
                st.session_state["clicked_query"] = q_dual
                st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
                st.rerun()

            q_dual2 = f"dual registration {user_club}"
            if st.button(q_dual2, key="ex_dual2", width='content'):
                st.session_state["clicked_query"] = q_dual2
                st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
                st.rerun()

            st.markdown("**⚔️ Club Comparison & Prediction**")
            if st.button(_vs_label, key="ex_vs", width='content'):
                st.session_state["clicked_query"] = _vs_query
                st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
                st.rerun()

            q_pred_ladder = f"predicted ladder {user_club} {user_age}"
            if st.session_state.get("role") == "admin":
                if st.button(f"📊 predicted ladder {user_age}", key="ex_pred_ladder", width='content'):
                    st.session_state["clicked_query"] = q_pred_ladder
                    st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
                    st.rerun()

            q_pred_ladder1 = f"predicted ladder {user_club} {user_age} after 1 match"
            if st.session_state.get("role") == "admin":
                if st.button(f"📊 ladder after 1 match", key="ex_pred_ladder1", width='content'):
                    st.session_state["clicked_query"] = q_pred_ladder1
                    st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
                    st.rerun()

            st.markdown("**🏆 Competitions**")
            q_ypl2 = "YPL2 ladder"
            if st.button("YPL2 ladder", key="ex_ypl2", width='content'):
                st.session_state["clicked_query"] = q_ypl2
                st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
                st.rerun()

            st.markdown("**👔 Coaches & Staff**")
            q16 = f"coaches for {user_club}"
            if st.button(q16, key="ex16", width='content'):
                st.session_state["clicked_query"] = q16
                st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
                st.rerun()

            q_staff_cards = f"red card staff {user_club}"
            if st.button(q_staff_cards, key="ex_staff_rc", width='content'):
                st.session_state["clicked_query"] = q_staff_cards
                st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
                st.rerun()

        with col3:
            st.markdown("**🟨🟥 Discipline & Results**")

            q10b = f"cards this week {user_competition} {user_age}"
            if st.button(f"cards this week {user_competition} {user_age}", key="ex10b", width='content'):
                st.session_state["clicked_query"] = q10b
                st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
                st.rerun()

            q10b_all = f"all cards {user_competition} {user_age}"
            if st.button(f"all cards {user_competition} {user_age}", key="ex10b_all", width='content'):
                st.session_state["clicked_query"] = q10b_all
                st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
                st.rerun()

            q10c = "cards per club"
            if st.button(q10c, key="ex10c", width='content'):
                st.session_state["clicked_query"] = q10c
                st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
                st.rerun()

            q10d = "own goals"
            if st.button(q10d, key="ex10d", width='content'):
                st.session_state["clicked_query"] = q10d
                st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
                st.rerun()

            q14 = "latest results"
            if st.button("Latest Results", key="q14", width='content'):
                st.session_state["clicked_query"] = q14
                st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
                st.rerun()

            q15 = "latest missing scores"
            if st.button("Latest Missing Scores", key="q15", width='content'):
                st.session_state["clicked_query"] = q15
                st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
                st.rerun()
    # ── Process: fires when version advances (typed Enter or button click) ──
    _cur_v = st.session_state["search_version"]
    if search and _cur_v != st.session_state["last_processed_version"]:
        st.session_state["last_processed_version"] = _cur_v
        st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
        st.session_state["level"] = "league"
        st.session_state["selected_league"] = None
        st.session_state["selected_competition"] = None
        st.session_state["selected_club"] = None
        st.session_state["selected_player"] = None
        st.session_state["selected_match_id"] = None
        # Always clear the previous answer first so stale results never show
        st.session_state["search_answer"]      = None
        st.session_state["search_answer_time"] = 0.0
        if is_natural_language_query(search):
            log_search(
                username=st.session_state["username"],
                full_name=st.session_state["full_name"],
                query=search,
                session_id=st.session_state["session_id"]
            )
            with st.spinner("🧠 Analyzing..."):
                _t0 = time.time()
                _ans = router.process(search)
                _t1 = time.time()
            st.session_state["search_answer"]      = _ans
            st.session_state["search_answer_time"] = round(_t1 - _t0, 3)

    # ── Render: always show stored answer (persists across reruns) ──────────
    def _fire_query(q):
        st.session_state["clicked_query"] = q
        st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
        st.rerun()

    def _render_answer(answer):
        st.markdown("---")
        if isinstance(answer, dict):
            if answer.get("type") == "player_profile":
                pname    = answer.get("name", "")
                is_dual  = answer.get("is_dual", False)
                reg_rows = answer.get("registrations", [])
                m_rows   = answer.get("matches", [])
                detailed = answer.get("detailed", False)
                note     = answer.get("note", "")
                st.markdown(f"### 👤 {pname}")
                if is_dual:
                    st.caption("🔄 Dual Registration")
                if reg_rows:
                    df_reg = pd.DataFrame(reg_rows)
                    st.caption("👇 Click a club row to view their squad")
                    sel_reg = st.dataframe(
                        df_reg, hide_index=True, width='content',
                        height=(len(reg_rows) + 1) * 35 + 10,
                        selection_mode="single-row", on_select="rerun",
                        key="prof_reg_sel",
                    )
                    _reg_sel = sel_reg.selection.get("rows", [])
                    if _reg_sel:
                        _fire_query(f"squad for {df_reg.iloc[_reg_sel[0]]['Club']}")
                if m_rows:
                    label = "📅 Match-by-Match" if detailed else f"📅 Recent Matches (last {len(m_rows)})"
                    st.markdown(f"**{label}**")
                    st.caption("👇 Click a match row to view full match detail (lineups, goals, cards)")
                    df_m = pd.DataFrame(m_rows)
                    _cfg = {}
                    if "Date" in df_m.columns:
                        df_m["Date"] = pd.to_datetime(df_m["Date"], errors="coerce").dt.date
                        _cfg["Date"] = st.column_config.DateColumn("Date", format="ddd, DD-MMM", width="medium")
                    h = min(600, (len(m_rows) + 1) * 35 + 10)
                    sel_match = st.dataframe(
                        df_m, hide_index=True, width='content',
                        height=h, column_config=_cfg,
                        selection_mode="single-row", on_select="rerun",
                        key="prof_match_sel",
                    )
                    _match_sel = sel_match.selection.get("rows", [])
                    if _match_sel:
                        _mrow = df_m.iloc[_match_sel[0]]
                        _opp  = str(_mrow.get("Opponent", "") or "")
                        _date = str(_mrow.get("Date", "") or "")
                        if _opp and _opp != "\u2014":
                            _fire_query(f"match details {_opp} {_date}")
                    if not detailed:
                        st.caption(f"💡 Say 'details for {pname}' for full match-by-match breakdown")
                if note:
                    st.caption(f"ℹ️ {note}")

            elif answer.get("type") == "squad_table":
                st.info(answer.get("title", "Squad"))
                data = answer.get("data", [])
                if data:
                    df = pd.DataFrame(data)
                    num_rows = len(df)
                    h = 600 if num_rows > 16 else (num_rows + 1) * 35 + 10
                    st.caption("👇 Click a player row to view their stats")
                    sel = st.dataframe(
                        df, hide_index=True, width='content', height=h,
                        selection_mode="single-row", on_select="rerun",
                        key="squad_row_sel",
                    )
                    _sel_rows = sel.selection.get("rows", [])
                    if _sel_rows:
                        _fire_query(f"stats for {df.iloc[_sel_rows[0]]['Player']}")

            elif answer.get("type") == "player_list":
                st.info(answer.get("title", "Players"))
                data = answer.get("data", [])
                if data:
                    df = pd.DataFrame(data)
                    num_rows = len(df)
                    h = 600 if num_rows > 16 else (num_rows + 1) * 35 + 10
                    st.caption("👇 Click a player row to view their full profile")
                    sel = st.dataframe(
                        df, hide_index=True, width='content', height=h,
                        selection_mode="single-row", on_select="rerun",
                        key="player_list_sel",
                    )
                    _pl_sel = sel.selection.get("rows", [])
                    if _pl_sel:
                        _fire_query(f"stats for {df.iloc[_pl_sel[0]]['Player']}")

            elif answer.get("type") == "team_stats":
                st.markdown(answer.get("summary", ""))
                results_data = answer.get("results", [])
                if results_data:
                    st.markdown("**📅 Recent Results**")
                    df_res = pd.DataFrame(results_data)
                    h = min(400, (len(df_res) + 1) * 35 + 10)
                    st.dataframe(df_res, hide_index=True, width='content', height=h,
                                 column_config={
                                     "Date":     st.column_config.DateColumn("Date", format="ddd, DD-MMM", width="medium"),
                                     "H/A":      st.column_config.TextColumn("",         width="small"),
                                     "Opponent": st.column_config.TextColumn("Opponent", width="medium"),
                                     "Score":    st.column_config.TextColumn("Score",    width="small"),
                                     "Result":   st.column_config.TextColumn("Result",   width="small"),
                                 })
                upcoming_data = answer.get("upcoming", [])
                if upcoming_data:
                    st.markdown("**📆 Upcoming Fixtures**")
                    df_up = pd.DataFrame(upcoming_data)
                    h = min(400, (len(df_up) + 1) * 35 + 10)
                    cols = ["Date","Time","H/A","Opponent","Venue","When","Opp Standing"]
                    cols = [c for c in cols if c in df_up.columns]
                    st.dataframe(df_up[cols], hide_index=True, width='content', height=h,
                                 column_config={
                                     "Date":         st.column_config.DateColumn("Date", format="ddd, DD-MMM", width="medium"),
                                     "Time":         st.column_config.TextColumn("Time",         width="small"),
                                     "H/A":          st.column_config.TextColumn("",             width="small"),
                                     "Opponent":     st.column_config.TextColumn("Opponent",     width="medium"),
                                     "Venue":        st.column_config.TextColumn("Venue",        width="medium"),
                                     "When":         st.column_config.TextColumn("When",         width="small"),
                                     "Opp Standing": st.column_config.TextColumn("Opp Standing", width="medium"),
                                 })
            elif answer.get("type") == "cards_this_week":
                st.markdown(f"### {answer.get('title','🟨🟥 Cards This Week')}")
                yellow_rows = answer.get("yellow_rows", [])
                red_rows    = answer.get("red_rows", [])

                col_y, col_r = st.columns(2)

                with col_y:
                    st.markdown(f"**🟨 Yellow Cards — {len(yellow_rows)} player{'s' if len(yellow_rows) != 1 else ''}**")
                    if yellow_rows:
                        df_y = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")}
                                             for r in yellow_rows])
                        _yk = f"cards_week_y_{st.session_state.get('expander_collapse_counter',0)}"
                        h = min(500, (len(df_y) + 1) * 35 + 10)
                        st.caption("👇 Click a row to view player details")
                        sel_y = st.dataframe(df_y, hide_index=True, width='content', height=h,
                            selection_mode="single-row", on_select="rerun", key=_yk,
                            column_config={
                                "Date":     st.column_config.DateColumn("Date", format="ddd, DD-MMM", width="medium"),
                                "Player":   st.column_config.TextColumn("Player",   width="medium"),
                                "Team":     st.column_config.TextColumn("Team",     width="medium"),
                                "Age":      st.column_config.TextColumn("Age",      width="small"),
                                "Opponent": st.column_config.TextColumn("Opponent", width="medium"),
                                "Min":      st.column_config.TextColumn("Min",      width="small"),
                                "Role":     st.column_config.TextColumn("Role",     width="small"),
                            })
                        _ysel = sel_y.selection.get("rows", [])
                        if _ysel:
                            _pname = yellow_rows[_ysel[0]].get("_pname", "")
                            if _pname:
                                _fire_query(f"stats for {_pname}")
                    else:
                        st.info("No yellow cards this week.")

                with col_r:
                    st.markdown(f"**🟥 Red Cards — {len(red_rows)} player{'s' if len(red_rows) != 1 else ''}**")
                    if red_rows:
                        df_r = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")}
                                             for r in red_rows])
                        _rk = f"cards_week_r_{st.session_state.get('expander_collapse_counter',0)}"
                        h = min(500, (len(df_r) + 1) * 35 + 10)
                        st.caption("👇 Click a row to view player details")
                        sel_r = st.dataframe(df_r, hide_index=True, width='content', height=h,
                            selection_mode="single-row", on_select="rerun", key=_rk,
                            column_config={
                                "Date":     st.column_config.DateColumn("Date", format="ddd, DD-MMM", width="medium"),
                                "Player":   st.column_config.TextColumn("Player",   width="medium"),
                                "Team":     st.column_config.TextColumn("Team",     width="medium"),
                                "Age":      st.column_config.TextColumn("Age",      width="small"),
                                "Opponent": st.column_config.TextColumn("Opponent", width="medium"),
                                "Min":      st.column_config.TextColumn("Min",      width="small"),
                                "Role":     st.column_config.TextColumn("Role",     width="small"),
                            })
                        _rsel = sel_r.selection.get("rows", [])
                        if _rsel:
                            _pname = red_rows[_rsel[0]].get("_pname", "")
                            if _pname:
                                _fire_query(f"stats for {_pname}")
                    else:
                        st.info("No red cards this week. 🎉")

            elif answer.get("type") == "card_summary":
                st.info(answer.get("title", "Card Summary"))
                data       = answer.get("data", [])
                mode       = answer.get("mode", "club")
                col_key    = answer.get("col_key", "Club")
                base_club  = answer.get("base_club", "")
                age_group  = answer.get("age_group", "")
                staff_only = answer.get("staff_only", False)
                _sf        = " staff" if staff_only else ""
                if data:
                    df = pd.DataFrame(data)
                    h  = min(600, (len(df) + 1) * 35 + 10)
                    _cs_key = f"card_sum_{mode}_{st.session_state.get('expander_collapse_counter', 0)}"
                    if mode == "players":
                        _lbl = "staff member" if staff_only else "player"
                        st.caption(f"👇 Click a {_lbl} to view their profile")
                        sel = st.dataframe(df, hide_index=True, width='content',
                            height=h, selection_mode="single-row", on_select="rerun",
                            key=_cs_key)
                        _cs = sel.selection.get("rows", [])
                        if _cs:
                            import re as _re
                            _raw = str(df.iloc[_cs[0]][col_key])
                            _clean = _re.sub(r'\s*\(.*?\)\s*$', '', _raw).strip()
                            _fire_query(f"stats for {_clean}")
                    elif mode == "age":
                        _lbl = "age group" if not staff_only else "age group (staff)"
                        st.caption(f"👇 Click an age group to see cards")
                        sel = st.dataframe(df, hide_index=True, width='content',
                            height=h, selection_mode="single-row", on_select="rerun",
                            key=_cs_key)
                        _cs = sel.selection.get("rows", [])
                        if _cs:
                            _ag = df.iloc[_cs[0]][col_key]
                            if staff_only:
                                _fire_query(f"card summary {base_club} {_ag} staff")
                            else:
                                _fire_query(f"card summary {base_club} {_ag}")
                    else:  # club mode
                        st.caption("👇 Click a club to see breakdown by age group")
                        sel = st.dataframe(df, hide_index=True, width='content',
                            height=h, selection_mode="single-row", on_select="rerun",
                            key=_cs_key)
                        _cs = sel.selection.get("rows", [])
                        if _cs:
                            _club = df.iloc[_cs[0]][col_key]
                            _fire_query(f"cards per club {_club}{_sf}")

            elif answer.get("type") == "match_detail":
                st.markdown(f"### {answer.get('title', 'Match Detail')}")
                tables = answer.get("tables", [])
                if tables:
                    tab_labels = [t["title"] for t in tables]
                    tabs = st.tabs(tab_labels)
                    for _ti, (tab, tbl) in enumerate(zip(tabs, tables)):
                        with tab:
                            data = tbl.get("data", [])
                            if data:
                                df = pd.DataFrame(data)
                                # Drop hidden count columns before display
                                display_cols = [c for c in df.columns if not c.startswith("_")]
                                df = df[display_cols]
                                num_rows = len(df)
                                h = 600 if num_rows > 16 else (num_rows + 1) * 35 + 10
                                is_clickable = tbl.get("clickable", False)
                                # Totals row is first (row 0) — guard against clicking it
                                if is_clickable:
                                    st.caption("👇 Click a player to view their full profile")
                                    _md_sel = st.dataframe(
                                        df, hide_index=True, width='content', height=h,
                                        selection_mode="single-row", on_select="rerun",
                                        key=f"match_detail_sel_{_ti}",
                                    )
                                    _md_rows = _md_sel.selection.get("rows", [])
                                    if _md_rows:
                                        _md_name = df.iloc[_md_rows[0]]["Player"]
                                        if not str(_md_name).startswith("─"):
                                            _fire_query(f"stats for {_md_name}")
                                else:
                                    st.dataframe(df, hide_index=True, width='content', height=h)
                            else:
                                st.info("No lineup data available.")

            elif answer.get("type") == "ladder":
                st.info(answer.get("title", "Ladder"))
                tables = answer.get("tables", [])
                competition = answer.get("competition", "")
                if tables:
                    tab_labels = [t["title"] for t in tables]
                    tabs = st.tabs(tab_labels)
                    for _ti, (tab, tbl) in enumerate(zip(tabs, tables)):
                        with tab:
                            data = tbl.get("data", [])
                            if data:
                                df = pd.DataFrame(data)
                                h = min(600, (len(df) + 1) * 35 + 10)
                                st.caption("👇 Click a club to see their matches")
                                sel = st.dataframe(df, hide_index=True, width='content',
                                    height=h, selection_mode="single-row", on_select="rerun",
                                    key=f"ladder_sel_{_ti}_{st.session_state.get('expander_collapse_counter',0)}")
                                _lr = sel.selection.get("rows", [])
                                if _lr:
                                    _team = df.iloc[_lr[0]]["Team"]
                                    _fire_query(f"Season {_team}")
                            else:
                                st.info("No data available.")
            elif answer.get("type") == "multi_table":
                st.info(answer.get("title", "Results"))
                tables = answer.get("tables", [])
                if tables:
                    tab_labels = [t["title"] for t in tables]
                    tabs = st.tabs(tab_labels)
                    for _ti, (tab, tbl) in enumerate(zip(tabs, tables)):
                        with tab:
                            data = tbl.get("data", [])
                            if not data:
                                st.info("No data available.")
                                continue
                            df = pd.DataFrame(data)
                            num_rows = len(df)
                            h = 600 if num_rows > 16 else (num_rows + 1) * 35 + 10
                            _mt_key = f"multi_tbl_{_ti}_{st.session_state.get('expander_collapse_counter',0)}"
                            # Ladder table — click row to view season for that age group
                            if "Age" in df.columns and "League" in df.columns:
                                st.caption("👇 Click a row to view season summary for that age group")
                                sel = st.dataframe(df, hide_index=True, width='content',
                                    height=h, selection_mode="single-row", on_select="rerun",
                                    key=_mt_key)
                                _lr = sel.selection.get("rows", [])
                                if _lr:
                                    _row     = df.iloc[_lr[0]]
                                    _age     = str(_row.get("Age", "")).strip()
                                    _club_cols = [c for c in df.columns if c not in ("League", "Age", "Positions")]
                                    _club_name = _club_cols[0] if _club_cols else ""
                                    if _club_name and _age:
                                        _fire_query(f"season {_club_name} {_age}")
                            # Matches table — click row to view match detail
                            elif "Home" in df.columns and "Away" in df.columns:
                                st.caption("👇 Click a match to view full details")
                                sel = st.dataframe(df, hide_index=True, width='content',
                                    height=h, selection_mode="single-row", on_select="rerun",
                                    key=_mt_key)
                                _mr = sel.selection.get("rows", [])
                                if _mr:
                                    _mrow  = df.iloc[_mr[0]]
                                    _home  = str(_mrow.get("Home", "")).strip()
                                    _away  = str(_mrow.get("Away", "")).strip()
                                    _mdate = str(_mrow.get("Date", "")).strip()
                                    _fire_query(f"match details {_home} vs {_away} {_mdate}")
                            else:
                                st.dataframe(df, hide_index=True, width='content', height=h)


                with st.expander("⚔️ Compare upcoming fixture", expanded=False):
                    try:
                        import pytz as _pytz
                        import datetime as _dt_mod
                        from fast_agent import (
                            fixtures as _fa_fix,
                            _strip_age_group as _sag
                        )
                        _mel_tz = _pytz.timezone('Australia/Melbourne')
                        _now    = _dt_mod.datetime.now(_mel_tz)

                        # Key = frozenset of the two stripped club names → keep earliest dt only
                        _earliest: dict = {}   # key → (fh, faw, fdt_full)

                        for _f in _fa_fix:
                            _fa = _f.get("attributes", {})

                            # Parse date — prefer datetime_aest, fall back to date_aest / raw date
                            _raw = _fa.get("datetime_aest") or _fa.get("date_aest") or _fa.get("date", "")
                            if not _raw:
                                continue
                            try:
                                # datetime_aest / date_aest are already local — parse directly
                                # raw UTC "2026-02-08 06:30:00" needs conversion
                                if " " in _raw and "T" not in _raw and _raw.endswith(":00") and len(_raw) > 10:
                                    # space-separated UTC format — convert to Melbourne
                                    import pytz as _pz2
                                    _utc_dt = _dt_mod.datetime.strptime(_raw[:19], "%Y-%m-%d %H:%M:%S")
                                    _utc_dt = _pz2.utc.localize(_utc_dt)
                                    _fdt_full = _utc_dt.astimezone(_mel_tz)
                                else:
                                    _fdt_full = _dt_mod.datetime.fromisoformat(_raw[:19])
                                    if _fdt_full.tzinfo is None:
                                        _fdt_full = _mel_tz.localize(_fdt_full)
                            except Exception:
                                continue

                            if _fdt_full.date() < _now.date():
                                continue

                            _fh  = _sag(_fa.get("home_team_name", ""))
                            _faw = _sag(_fa.get("away_team_name", ""))
                            if not _fh or not _faw:
                                continue

                            # Deduplicate: one entry per club-pair, earliest date wins
                            _pair_key = frozenset([_fh.lower(), _faw.lower()])
                            if _pair_key not in _earliest or _fdt_full < _earliest[_pair_key][2]:
                                _earliest[_pair_key] = (_fh, _faw, _fdt_full)

                        # Build label → (fh, faw, fdt) dict, sorted by date then label
                        _fix_opts = {}
                        for _fh, _faw, _fdt_full in sorted(_earliest.values(), key=lambda x: x[2]):
                            _date_label = _fdt_full.strftime("%a %d %b")
                            _label = f"{_fh} vs {_faw}  ({_date_label})"
                            _fix_opts[_label] = (_fh, _faw, _fdt_full)

                        _fix_list = [""] + list(_fix_opts.keys())
                        _sel_fix = st.selectbox(
                            "Pick a fixture to compare",
                            _fix_list,
                            key=f"vs_fixture_pick_{st.session_state.get('expander_collapse_counter',0)}",
                            label_visibility="collapsed",
                            placeholder="🔍 Type club name to filter fixtures..."
                        )
                        if _sel_fix and _sel_fix in _fix_opts:
                            _fh, _faw, _fdt_full = _fix_opts[_sel_fix]
                            _fire_query(f"{_fh} vs {_faw}")
                    except Exception as _fe:
                        st.caption(f"Could not load fixtures: {_fe}")
            elif answer.get("type") == "own_goal_list":
                st.info(answer.get("title", "Own Goals"))
                data   = answer.get("data", [])
                hashes = answer.get("hashes", [])
                if data:
                    df = pd.DataFrame(data)
                    h  = min(600, (len(df) + 1) * 35 + 10)
                    st.caption("👇 Click a row to view the full match detail")
                    _og_key = f"og_sel_{st.session_state.get('expander_collapse_counter', 0)}"
                    sel = st.dataframe(df, hide_index=True, width='content',
                        height=h, selection_mode="single-row", on_select="rerun",
                        key=_og_key)
                    _ogr = sel.selection.get("rows", [])
                    if _ogr:
                        _row  = df.iloc[_ogr[0]]
                        # Use human-readable Team vs Opponent + Date
                        _team_og = str(_row.get("Team", "")).strip()
                        _opp_og  = str(_row.get("Opponent", "")).strip()
                        _date_og = str(_row.get("Date", "")).strip()
                        if _team_og and _opp_og and _date_og:
                            _fire_query(f"match details {_team_og} vs {_opp_og} {_date_og}")
                        elif _opp_og and _date_og:
                            _fire_query(f"match details {_opp_og} {_date_og}")

            elif answer.get("type") == "match_list":
                st.info(answer.get("title", "Matches"))
                data = answer.get("data", [])
                if data:
                    df = pd.DataFrame(data)
                    h  = min(600, (len(df) + 1) * 35 + 10)
                    st.caption("👇 Click a match to view full details & squad")
                    _ml_key = f"match_list_{st.session_state.get('expander_collapse_counter', 0)}"
                    sel = st.dataframe(df, hide_index=True, width='content',
                        height=h, selection_mode="single-row", on_select="rerun",
                        key=_ml_key)
                    _mr = sel.selection.get("rows", [])
                    if _mr:
                        _row = df.iloc[_mr[0]]
                        _home = _row.get("Home", "")
                        _away = _row.get("Away", "")
                        _date = str(_row.get("Date", "")).strip()
                        _fire_query(f"match details {_home} vs {_away} {_date}")

            elif answer.get("type") == "table":
                st.info(answer.get("title", "Results"))
                data = answer.get("data", [])
                if data:
                    df = pd.DataFrame(data)
                    _cfg = {}
                    if "Date" in df.columns:
                        df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date
                        _cfg["Date"] = st.column_config.DateColumn("Date", format="ddd, DD-MMM", width="medium")
                    if "First @ To" in df.columns:
                        df["First @ To"] = pd.to_datetime(df["First @ To"], errors="coerce").dt.date
                        _cfg["First @ To"] = st.column_config.DateColumn("First @ To", format="ddd, DD-MMM", width="medium")
                    num_rows = len(df)
                    final_height = 600 if num_rows > 16 else (num_rows + 1) * 35
                    # Determine name column and whether table is clickable
                    _name_col = None
                    if "Player" in df.columns:
                        _name_col = "Player"
                    elif "Name" in df.columns:
                        _name_col = "Name"
                    _has_stats = any(c in df.columns for c in ["\u26bd", "\U0001f7e8", "\U0001f7e5", "Total \U0001f7e8"])
                    if _name_col and _has_stats:
                        st.caption("👇 Click a player row to view their profile")
                        sel = st.dataframe(
                            df, hide_index=True, width='content',
                            height=final_height, column_config=_cfg,
                            selection_mode="single-row", on_select="rerun",
                            key="top_scorers_sel",
                        )
                        _ts_sel = sel.selection.get("rows", [])
                        if _ts_sel:
                            _fire_query(f"stats for {df.iloc[_ts_sel[0]][_name_col]}")
                    else:
                        st.dataframe(df, hide_index=True, width='content',
                                     height=final_height, column_config=_cfg)
            elif answer.get("type") == "ladder_prediction":
                if st.session_state.get("role") == "admin":
                    _render_ladder_prediction(answer)
                else:
                    st.info("📊 Predicted ladder is available to admins only.")

            elif answer.get("type") == "prediction":
                # Match predictions are admin-only
                if st.session_state.get("role") == "admin":
                    _render_prediction(answer)
                else:
                    st.info("🔮 Match predictions are available to admins. Ask your admin to check the prediction dashboard.")

            elif answer.get("type") == "ambiguous_club":
                st.warning(answer.get("message", "Multiple clubs found."))
                options = answer.get("options", [])
                age_q   = answer.get("age_grp", "")
                st.markdown("**Select a club:**")
                for opt in options:
                    btn_label = f"📋 {opt}"
                    if st.button(btn_label, key=f"amb_{opt.replace(' ','_')}"):
                        q = f"season {opt} {age_q}".strip()
                        st.session_state["clicked_query"] = q
                        st.session_state["expander_collapse_counter"] = st.session_state.get("expander_collapse_counter", 0) + 1
                        st.rerun()

            elif answer.get("type") == "season_summary":
                _render_season_summary(answer)

            elif answer.get("type") == "error":
                st.error(answer.get("message", "An error occurred"))


        else:
            st.chat_message("assistant").write(answer)
        st.caption(f"⏱️ {st.session_state['search_answer_time']:.3f}s")
        st.markdown("---")

    if st.session_state.get("search_answer") is not None and search:
        _render_answer(st.session_state["search_answer"])

    # ── Back button ──
    _hist = st.session_state.get("search_history", [])
    if _hist:
        if st.button(f"\u2b05\ufe0f Back  ({_hist[-1]['query']})", key='search_back_btn'):
            _entry = _hist.pop()
            st.session_state["search_history"] = _hist
            st.session_state["_restore_search"] = _entry
            st.rerun()

    # Navigation buttons
    if st.session_state["level"] != "league":
        col1, col2, _ = st.columns([1, 1, 6])
        if col1.button("⬅️ Back", width='content'):
            back_one_level()
            st.rerun()
        if col2.button("🔄 Restart", width='content'):
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
                if st.button(league_name, key=f"league_btn_{idx}", width='stretch'):
                    st.session_state["selected_league"] = league_name
                    st.session_state["level"] = "competition"
                    st.session_state["_pending_search_clear"] = True   # cleared before widget next run
                    
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

        # Always show leagues so user can switch without hitting Back
        st.markdown("### 🏆 Leagues")
        all_leagues = get_all_leagues(results, fixtures)
        league_cols = st.columns(min(len(all_leagues), 4))
        for idx, league_name in enumerate(all_leagues):
            col_idx = idx % 4
            with league_cols[col_idx]:
                btn_type = "primary" if league_name == league else "secondary"
                if st.button(league_name, key=f"league_btn2_{idx}", width='stretch', type=btn_type):
                    st.session_state["selected_league"] = league_name
                    st.session_state["level"] = "competition"
                    st.session_state["selected_competition"] = None
                    st.session_state["selected_club"] = None
                    st.rerun()

        st.markdown("---")
        st.markdown(f"### 📘 Age Groups in **{league}**")

        comps = get_competitions_for_league(results, fixtures, league)

        if search and not is_natural_language_query(search):
            comps = [c for c in comps if search.lower() in c.lower()]

        if not comps:
            st.info("No competitions found.")
            return
        
        # Add clickable competition buttons
        st.markdown("**Click a competition name to open:**")
        cols = st.columns(min(len(comps), 5))  # Max 4 columns
        for idx, comp_name in enumerate(comps):
            col_idx = idx % 5
            with cols[col_idx]:
                if st.button(comp_name, key=f"comp_btn_{idx}", width='content'):
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
# Overall club rankings - tabbed: Old (position-based) vs New (points-based)
        st.markdown("---")
        st.markdown(f"### 📈 Overall Club Rankings - {league}")

        tab_old, tab_new = st.tabs(["🏅 Old Ladder (by Position)", "⚡ Overall Points Ladder"])

        with tab_new:
            st.caption("Rankings based on total match points (W=3, D=1, L=0) earned across all age groups in this league.")
            overall_ladder = compute_overall_points_ladder(results, league)
            if overall_ladder:
                overall_ladder_df = pd.DataFrame(overall_ladder)
                overall_ladder_df.insert(0, "Rank", range(1, len(overall_ladder_df) + 1))
                overall_display_df = overall_ladder_df[["Rank", "club", "played", "wins", "draws", "losses", "gf", "ga", "gd", "points"]].copy()
                overall_display_df.columns = ["Rank", "Club", "P", "W", "D", "L", "GF", "GA", "GD", "Pts"]
                st.dataframe(
                    overall_display_df,
                    hide_index=True,
                    width='content',
                    height=598,
                    column_config={
                        "Rank": st.column_config.NumberColumn("Rank", width="small"),
                        "Club": st.column_config.TextColumn("Club", width="large"),
                        "P": st.column_config.NumberColumn("P", width="small"),
                        "W": st.column_config.NumberColumn("W", width="small"),
                        "D": st.column_config.NumberColumn("D", width="small"),
                        "L": st.column_config.NumberColumn("L", width="small"),
                        "GF": st.column_config.NumberColumn("GF", width="small"),
                        "GA": st.column_config.NumberColumn("GA", width="small"),
                        "GD": st.column_config.NumberColumn("GD", width="small"),
                        "Pts": st.column_config.NumberColumn("Pts", width="small"),
                    },
                )
            else:
                st.info("No results data found to build the points ladder for this league.")
                
        with tab_old:
            if league in comp_overview:
                data = comp_overview[league]
                age_groups = data.get("age_groups", [])
                rows = []
                for club in data.get("clubs", []):
                    row = {
                        "Rank": club.get("overall_rank", 0),
                        "Club": base_club_name(club.get("club", "")),
                        "Points": club.get("total_position_points", 0),
                    }
                    for age in age_groups:
                        pos = club.get("age_groups", {}).get(age, {}).get("position")
                        row[age] = pos if pos else "-"
                    row["GF"] = club.get("total_gf", 0)
                    row["GA"] = club.get("total_ga", 0)
                    row["GD"] = club.get("total_gf", 0) - club.get("total_ga", 0)
                    rows.append(row)
                df_overview = pd.DataFrame(rows)
                configs = {
                    "Rank": st.column_config.NumberColumn("Rank", width="small"),
                    "Club": st.column_config.TextColumn("Club", width="large"),
                    "Points": st.column_config.NumberColumn("Pts", width="small"),
                    "GF": st.column_config.NumberColumn("GF", width="small"),
                    "GA": st.column_config.NumberColumn("GA", width="small"),
                    "GD": st.column_config.NumberColumn("GD", width="small"),
                }
                for age in age_groups:
                    configs[age] = st.column_config.TextColumn(age, width="small")
                st.dataframe(df_overview, hide_index=True, width='content', height=598, column_config=configs)
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

        # Build display dataframe (no Select column needed)
        display_df = ladder_df[["Pos", "ClubDisplay", "played", "wins", "draws", "losses",
                                 "gf", "ga", "gd", "points"]].copy()
        display_df.columns = ["Pos", "Club", "P", "W", "D", "L", "GF", "GA", "GD", "Pts"]

        # Apply zone colours
      #  styled = display_df.style.apply(style_ladder, comp=comp, axis=None)

        st.dataframe(
            display_df,
            hide_index=True,
            width='content',
            height=590,
        )

        # Club selector below the table
        club_options = [""] + list(ladder_df["ClubDisplay"])
        currently_selected = st.session_state.get("selected_club")
        default_idx = club_options.index(currently_selected) if currently_selected in club_options else 0

        chosen_club = st.selectbox(
            "🏟️ Select a club to view squad & matches:",
            options=club_options,
            index=default_idx,
            format_func=lambda x: "— pick a club —" if x == "" else x,
            key="club_selector"
        )

        if chosen_club and chosen_club != currently_selected:
            st.session_state["selected_club"] = chosen_club
            st.session_state["selected_match_id"] = None
            log_view(
                username=st.session_state["username"],
                full_name=st.session_state["full_name"],
                view_type="club",
                league=league,
                competition=comp,
                club=chosen_club,
                session_id=st.session_state["session_id"]
            )
            st.rerun()
        elif not chosen_club and currently_selected:
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
# Score shown from club's perspective with W/D/L indicator
                        if hs is not None and as_ is not None:
                            our = int(hs) if is_home else int(as_)
                            opp = int(as_) if is_home else int(hs)
                            icon = "🟢" if our > opp else ("🔴" if our < opp else "🟡")
                            score = f"{icon} {our}-{opp}"
                        else:
                            score = ""

                        match_rows.append({
                            "Select": False,
                            "Date": format_date(attrs.get("date", "")),
                            "H/A": home_away,
                            "Opponent": base_club_name(opponent),
                            "Score": score,
                            "_match_hash_id": attrs.get("match_hash_id"),
                        })

                    df_matches = pd.DataFrame(match_rows)
                    df_matches["Select"] = df_matches["Select"].astype(bool)

                    # Pre-tick the currently selected match
                    current_id = st.session_state.get("selected_match_id")
                    if current_id:
                        df_matches["Select"] = df_matches["_match_hash_id"] == current_id

                    edited_matches = st.data_editor(
                        df_matches[["Select", "Date", "H/A", "Opponent", "Score"]],
                        hide_index=True,
                        column_config={
                            "Select": st.column_config.CheckboxColumn("", default=False, width="small"),
                            "Date": st.column_config.DateColumn("Date", format="ddd, DD-MMM", width="medium"),
                            "H/A": st.column_config.TextColumn("", width="small"),
                            "Opponent": st.column_config.TextColumn("Opponent", width="medium"),
                            "Score": st.column_config.TextColumn("Score", width="small")
                        },
                        disabled=["Date", "H/A", "Opponent", "Score"],
                        width='content',
                        key="club_matches_editor"
                    )

                    # Single clean selection block — no duplicates
                    selected_rows = edited_matches[edited_matches["Select"] == True]
                    if not selected_rows.empty:
                        new_match_id = df_matches.iloc[selected_rows.index[0]]["_match_hash_id"]
                        if st.session_state.get("selected_match_id") != new_match_id:
                            st.session_state["selected_match_id"] = new_match_id
                            st.rerun()
                    elif st.session_state.get("selected_match_id") is not None:
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
                        st.info(f"**{format_date_full_aest(attrs.get('date', ''))}** vs {base_club_name(opponent)} - **{our_score}-{opp_score}**")
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
                    if any(len(p.get("teams", [])) > 1 for p in players):
                        st.caption("🔁 = also plays another age group at this club · ⚡ = also registered at a different club")
                    rows = []
                    for p in players:
                        full_name   = f"{p.get('first_name','')} {p.get('last_name','')}"
                        reg         = get_player_reg_info(p, club, comp)
                        player_age  = reg["age"]
                        dual_badge  = reg["badge"]
                        jerseys_map = p.get("jerseys", {})
                        jersey      = jerseys_map.get(
                            next((t for t in p.get("teams", []) if base_club_name(t) == club), ""),
                            p.get("jersey", "")
                        )

                        if selected_match_id:
                            match_data = get_player_match_stats(p, selected_match_id)
                            if match_data:
                                indicators = []
                                if match_data.get("captain"): indicators.append("(C)")
                                if match_data.get("goalie"):  indicators.append("🥅")
                                if indicators:
                                    full_name = f"{full_name} {' '.join(indicators)}"
                                events = match_data.get("events", [])
                                def _etype(e): return (e.get("type") or e.get("event_type") or "").lower()
                                goals_m   = sum(1 for e in events if _etype(e) == "goal")
                                yellows_m = sum(1 for e in events if _etype(e) == "yellow_card")
                                reds_m    = sum(1 for e in events if _etype(e) == "red_card")
                                is_captain = (
                                    match_data.get("captain") or
                                    match_data.get("role_in_match", "").lower() == "captain" or
                                    p.get("stats", {}).get("matches_captained", 0) > 0
                                )
                                if is_captain and "(C)" not in full_name:
                                    full_name = f"{full_name} (C)"
                                rows.append({
                                    "Select": False, "Age": player_age,
                                    "Player": f"{full_name}{dual_badge}", "#": jersey,
                                    "M": 1, "G": goals_m, "🟨": yellows_m, "🟥": reds_m,
                                })
                        else:
                            rows.append({
                                "Select": False, "Age": player_age,
                                "Player": f"{full_name}{dual_badge}", "#": jersey,
                                "M": len([m for m in p.get("matches", [])
                                          if m.get("available", False) or m.get("started", False)]),
                                "G": p.get("stats", {}).get("goals", 0),
                                "🟨": p.get("stats", {}).get("yellow_cards", 0),
                                "🟥": p.get("stats", {}).get("red_cards", 0),
                            })

                    df_players = pd.DataFrame(rows)
                    df_players["Select"] = df_players["Select"].astype(bool)
                    edited_players = st.data_editor(
                        df_players, hide_index=True,
                        column_config={
                            "Select": st.column_config.CheckboxColumn("", help="View details", default=False),
                            "Age":    st.column_config.TextColumn("Age", width="small"),
                            "Player": st.column_config.TextColumn("Player", width="medium"),
                            "#":      st.column_config.TextColumn("#", width="small"),
                            "M":      st.column_config.NumberColumn("M", width="small", help="Matches"),
                            "G":      st.column_config.NumberColumn("G", width="small", help="Goals"),
                            "🟨":     st.column_config.NumberColumn("🟨", width="small"),
                            "🟥":     st.column_config.NumberColumn("🟥", width="small"),
                        },
                        disabled=["Age", "Player", "#", "M", "G", "🟨", "🟥"],
                        width='content', height=730, key="players_editor"
                    )

                    selected_player_rows = edited_players[edited_players["Select"] == True]
                    if not selected_player_rows.empty:
                        idx = selected_player_rows.index[0]
                        selected_player = players[idx]
                        # Stay on ladder_clubs — show details below instead of navigating away
                        if st.session_state.get("selected_player") != selected_player:
                            st.session_state["selected_player"] = selected_player
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
                        if st.session_state.get("selected_player") is not None:
                            st.session_state["selected_player"] = None
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
                        width='content',
                    )
# PLAYER DETAIL PANEL — inline below squad
                selected_player = st.session_state.get("selected_player")
                if selected_player:
                    pname = f"{selected_player.get('first_name','')} {selected_player.get('last_name','')}"
                    st.markdown("---")
                    col_ph, col_px = st.columns([6, 1])
                    with col_ph:
                        stats       = selected_player.get("stats", {})
                        detail_reg  = get_player_reg_info(selected_player, club, comp)
                        age_label   = f"  ·  🎂 {detail_reg['age']}" if detail_reg["age"] else ""
                        dual_parts  = []
                        if detail_reg["same_club_other_ages"]:
                            dual_parts.append(f"🔁 Also plays {' & '.join(detail_reg['same_club_other_ages'])} at {club}")
                        if detail_reg["diff_clubs"]:
                            dual_parts.append(f"⚡ Also at {', '.join(detail_reg['diff_clubs'])}")
                        dual_label  = "  ·  " + "  ·  ".join(dual_parts) if dual_parts else ""
                        jerseys_map = selected_player.get("jerseys", {})
                        jersey      = jerseys_map.get(
                            next((t for t in selected_player.get("teams", []) if base_club_name(t) == club), ""),
                            selected_player.get("jersey", "—")
                        )
                        st.markdown(f"### 👤 {pname}")
                        # Recalculate matches from match-level data (available or started = counts)
                        _all_pm = selected_player.get("matches", [])
                        _matches_played_calc = len([m for m in _all_pm
                                                    if m.get("available", False) or m.get("started", False)])
                        st.caption(
                            f"Jersey #{jersey}{age_label}  |  "
                            f"⚽ {stats.get('goals', 0)} goals  |  "
                            f"🎮 {_matches_played_calc} matches  |  "
                            f"🟨 {stats.get('yellow_cards', 0)}  🟥 {stats.get('red_cards', 0)}"
                            f"{dual_label}"
                        )
                    with col_px:
                        if st.button("✖ Close", key="close_player_detail"):
                            st.session_state["selected_player"] = None
                            st.rerun()

                    player_matches = sorted(
                        selected_player.get("matches", []),
                        key=lambda m: m.get("date", ""),
                        reverse=True
                    )
                    if player_matches:
                        is_dual = len(selected_player.get("teams", [])) > 1
                        match_rows = []
                        for m in player_matches:
                            # Only show matches where player was actually available or started
                            if not (m.get("available", False) or m.get("started", False)):
                                continue
                            opponent = base_club_name(m.get("opponent_team_name") or m.get("opponent") or "—")
                            events   = m.get("events", [])
                            def _etype(e): return (e.get("type") or e.get("event_type") or "").lower()
                            goals    = m.get("goals",       sum(1 for e in events if _etype(e) == "goal"))
                            yellows  = m.get("yellow_cards", sum(1 for e in events if _etype(e) == "yellow_card"))
                            reds     = m.get("red_cards",    sum(1 for e in events if _etype(e) == "red_card"))

                            # Collect card minutes for display (e.g. "45'" or "45', 78'")
                            yc_mins = [str(e.get("minute")) for e in events
                                       if _etype(e) == "yellow_card" and e.get("minute")]
                            rc_mins = [str(e.get("minute")) for e in events
                                       if _etype(e) == "red_card" and e.get("minute")]
                            yc_str = ("🟨 " + ", ".join(f"{m2}'" for m2 in yc_mins)) if yc_mins else ("🟨" if yellows else "")
                            rc_str = ("🟥 " + ", ".join(f"{m2}'" for m2 in rc_mins)) if rc_mins else ("🟥" if reds else "")
                            cards_str = "  ".join(filter(None, [yc_str, rc_str])) or "—" if (yellows or reds) else ""

                            # Age group from league_name or team_name on the match entry
                            _ag_src = m.get("league_name") or m.get("team_name") or ""
                            _ag_m = re.search(r'U\d{2}', _ag_src, re.IGNORECASE)
                            age_grp = _ag_m.group(0).upper() if _ag_m else ""

                            # Started/bench + captain/goalie indicators
                            started_icon = "✅" if m.get("started") else "🪑"
                            if m.get("captain"):
                                started_icon += " ©"
                            if m.get("goalie"):
                                started_icon += " 🧤"

                            row = {
                                "Date":     format_date_aest(m.get("date", "")),
                                "Age":      age_grp,
                                "Started":  started_icon,
                                "Opponent": opponent,
                                "G": goals,
                                "Cards":    cards_str,
                            }
                            if is_dual and m.get("team_name"):
                                row["Club"] = base_club_name(m["team_name"])
                            match_rows.append(row)
                        df_player = pd.DataFrame(match_rows)
                        col_cfg = {
                            "Date":     st.column_config.DateColumn("Date", format="ddd, DD-MMM", width="medium"),
                            "Age":      st.column_config.TextColumn("Age", width="small"),
                            "Started":  st.column_config.TextColumn("", width="small"),
                            "Opponent": st.column_config.TextColumn("Opponent", width="medium"),
                            "G":        st.column_config.NumberColumn("G", width="small"),
                            "Cards":    st.column_config.TextColumn("Cards", width="small"),
                        }
                        if is_dual:
                            col_cfg["Club"] = st.column_config.TextColumn("Club", width="medium")
                        h = min(600, (len(match_rows) + 1) * 35 + 10)
                        st.dataframe(df_player, hide_index=True, width='content',
                                     column_config=col_cfg, height=h)
                    else:
                        st.info("No match history found.")

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
                "Date": format_date_aest(m.get("date", "")),
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
            width='content',
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
    _inject_device_id_script()
    # Refresh device_id from query_params on every run (JS may have just set it)
    _did = st.query_params.get("_did", "")
    if _did:
        st.session_state["device_id"] = _did

    params = st.query_params

    # Handle URL search param (always, regardless of auth state)
    if "search" in params:
        st.session_state["search_input_value"] = params["search"].replace("+", " ")

    # ✅ Auto-login if uid is in the URL and not yet authenticated
    if not st.session_state["authenticated"] and "uid" in params:
        uid = params["uid"]
        people = get_players_and_coaches_list(DATA_DIR)
        matched = next((p for p in people if p.get("player_id") == uid), None)
        if matched:
            league, competition = get_player_league_info(
                matched["name"],
                matched["club"],
                matched.get("age_group", "")
            )
            st.session_state["authenticated"] = True
            st.session_state["user_type"] = "player"
            st.session_state["username"] = matched["player_id"]
            st.session_state["full_name"] = matched["name"]
            st.session_state["player_club"] = matched["club"]
            st.session_state["player_age_group"] = matched.get("age_group", "")
            st.session_state["player_role"] = matched["role"]
            st.session_state["role"] = matched["role"]
            st.session_state["last_activity"] = datetime.now()
            st.session_state["player_league"] = league
            st.session_state["player_competition"] = competition
            update_user_config(matched["club"], matched.get("age_group", ""))
            log_login(
                username=matched["player_id"],
                full_name=matched["name"],
                session_id=st.session_state["session_id"]
            )
            st.rerun()

    # Show login page ONLY if user explicitly logged out
    if not st.session_state["authenticated"]:
        if st.session_state.get("explicitly_logged_out", False):
            show_login_page()
            return
        else:
            # Session was reset (tab reload, browser back etc) — auto-create guest session
            st.session_state["authenticated"]    = True
            st.session_state["user_type"]        = "guest"
            st.session_state["username"]         = "guest"
            st.session_state["full_name"]        = "Guest"
            st.session_state["player_club"]      = "Heidelberg United FC"
            st.session_state["player_age_group"] = "U16"
            st.session_state["player_role"]      = "player"
            st.session_state["role"]             = "player"
            st.session_state["last_activity"]    = datetime.now()
            st.session_state["player_league"]    = "YPL2"
            st.session_state["player_competition"] = "YPL2"
            update_user_config("Heidelberg United FC", "U16")

    # Authenticated — check timeout then show app
    if not check_session_timeout():
        # Timeout: restore guest session rather than force login
        st.session_state["authenticated"]    = True
        st.session_state["user_type"]        = "guest"
        st.session_state["username"]         = "guest"
        st.session_state["full_name"]        = "Guest"
        st.session_state["player_club"]      = "Heidelberg United FC"
        st.session_state["player_age_group"] = "U16"
        st.session_state["player_role"]      = "player"
        st.session_state["role"]             = "player"
        st.session_state["last_activity"]    = datetime.now()
        st.session_state["player_league"]    = "YPL2"
        st.session_state["player_competition"] = "YPL2"
        update_user_config("Heidelberg United FC", "U16")

    main_app()


        
if __name__ == "__main__":
    main()
# Last auto-update: 2026-03-02 10:00:32 AEDT
<<<<<<< HEAD
# Last auto-update: Sun 22 Mar 07:04:00 AEDT 2026
# Last auto-update: Sun 22 Mar 08:04:06 AEDT 2026
# Last auto-update: Sun 22 Mar 09:04:05 AEDT 2026
# Last auto-update: Sun 22 Mar 10:04:08 AEDT 2026
# Last auto-update: Sun 22 Mar 11:25:51 AEDT 2026
# Last auto-update: Sun 22 Mar 12:04:50 AEDT 2026
# Last auto-update: Sun 22 Mar 13:05:06 AEDT 2026
# Last auto-update: Sun 22 Mar 14:05:17 AEDT 2026
# Last auto-update: Sun 22 Mar 14:55:04 AEDT 2026
# Last auto-update: Sun 22 Mar 15:05:37 AEDT 2026
# Last auto-update: Sun 22 Mar 15:30:05 AEDT 2026
# Last auto-update: Sun 22 Mar 15:43:51 AEDT 2026
# Last auto-update: Sun 22 Mar 18:30:58 AEDT 2026
# Last auto-update: Sun 22 Mar 20:06:08 AEDT 2026
# Last auto-update: Sun 22 Mar 21:06:09 AEDT 2026
# Last auto-update: Sun 22 Mar 21:31:07 AEDT 2026
# Last auto-update: Mon 23 Mar 04:05:14 AEDT 2026
# Last auto-update: Mon 23 Mar 06:05:30 AEDT 2026
# Last auto-update: Mon 23 Mar 08:05:46 AEDT 2026
# Last auto-update: Mon 23 Mar 10:05:24 AEDT 2026
# Last auto-update: Mon 23 Mar 12:05:01 AEDT 2026
# Last auto-update: Mon 23 Mar 14:04:41 AEDT 2026
# Last auto-update: Mon 23 Mar 16:04:37 AEDT 2026
=======

# Last auto-update: 2026-03-09 20:00:32 AEDT
# Last auto-update: 2026-03-09 23:00:32 AEDT
# Last auto-update: 2026-03-10 00:00:33 AEDT
# Last auto-update: 2026-03-10 04:00:35 AEDT
# Last auto-update: 2026-03-10 08:00:33 AEDT
# Last auto-update: 2026-03-10 12:00:32 AEDT
# Last auto-update: 2026-03-10 16:00:36 AEDT
# Last auto-update: 2026-03-10 20:00:33 AEDT
# Last auto-update: 2026-03-11 00:00:33 AEDT
# Last auto-update: 2026-03-11 04:00:32 AEDT
# Last auto-update: 2026-03-11 08:00:33 AEDT
# Last auto-update: 2026-03-11 12:00:32 AEDT
# Last auto-update: 2026-03-11 16:00:36 AEDT
# Last auto-update: 2026-03-11 20:00:32 AEDT
# Last auto-update: 2026-03-12 00:00:32 AEDT
>>>>>>> 2b4dc2403554a40c8ee77f52a53dc9946053db3f
# Last auto-update: Mon 23 Mar 18:05:26 AEDT 2026
# Last auto-update: Mon 23 Mar 20:04:21 AEDT 2026
# Last auto-update: Mon 23 Mar 22:04:22 AEDT 2026
# Last auto-update: Tue 24 Mar 00:04:02 AEDT 2026
# Last auto-update: Tue 24 Mar 04:03:50 AEDT 2026
# Last auto-update: Tue 24 Mar 08:04:11 AEDT 2026
# Last auto-update: Tue 24 Mar 12:04:26 AEDT 2026
# Last auto-update: Tue 24 Mar 13:25:23 AEDT 2026
# Last auto-update: Tue 24 Mar 16:04:35 AEDT 2026
# Last auto-update: Tue 24 Mar 16:44:20 AEDT 2026
# Last auto-update: Tue 24 Mar 20:04:25 AEDT 2026
# Last auto-update: Wed 25 Mar 00:04:06 AEDT 2026
# Last auto-update: Wed 25 Mar 04:03:51 AEDT 2026
# Last auto-update: Wed 25 Mar 08:04:05 AEDT 2026
# Last auto-update: Wed 25 Mar 12:04:21 AEDT 2026
# Last auto-update: Wed 25 Mar 13:04:54 AEDT 2026
# Last auto-update: Wed 25 Mar 13:16:49 AEDT 2026
# Last auto-update: Wed 25 Mar 16:04:55 AEDT 2026
