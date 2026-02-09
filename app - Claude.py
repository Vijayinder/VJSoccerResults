import streamlit as st
from fast_agent import FastQueryRouter, format_date, format_date_full
import time
import pandas as pd
import json
import os
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

if "last_search" not in st.session_state:
    st.session_state["last_search"] = ""

# ---------------------------------------------------------
# Data loaders
# ---------------------------------------------------------

@st.cache_resource
def load_master_results():
    path = os.path.join("data", "master_results.json")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

@st.cache_resource
def load_fixtures():
    path = os.path.join("data", "fixtures.json")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

@st.cache_resource
def load_players_summary():
    path = os.path.join("data", "players_summary.json")
    if not os.path.exists(path):
        return {"players": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# ---------------------------------------------------------
# Helpers: league / competition extraction
# ---------------------------------------------------------

def extract_league_from_league_name(league_name: str) -> str:
    if "YPL1" in league_name:
        return "YPL1"
    if "YPL2" in league_name:
        return "YPL2"
    if "YSL Boys - North-West" in league_name:
        return "YSL NW"
    if "YSL Boys - South-East" in league_name:
        return "YSL SE"
    if "VPL Men" in league_name:
        return "VPL Men"
    if "VPL Women" in league_name:
        return "VPL Women"
    return "Other"

def extract_competition_from_league_name(league_name: str) -> str:
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
        attrs = item.get("attributes", {})
        league_name = attrs.get("league_name")
        if league_name:
            leagues.add(extract_league_from_league_name(league_name))

    for item in fixtures:
        attrs = item.get("attributes", {})
        league_name = attrs.get("league_name")
        if league_name:
            leagues.add(extract_league_from_league_name(league_name))

    leagues = sorted([l for l in leagues if l != "Other"])
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
# Ladder + clubs
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

        hs = int(hs)
        as_ = int(as_)

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
# Players + matches
# ---------------------------------------------------------

def get_players_for_club(players_data, club_name):
    return [p for p in players_data.get("players", []) if p.get("team_name") == club_name]

def get_matches_for_player(player):
    return player.get("matches", [])

# ---------------------------------------------------------
# Navigation helpers
# ---------------------------------------------------------

def restart_to_top():
    st.session_state["level"] = "league"
    st.session_state["selected_league"] = None
    st.session_state["selected_competition"] = None
    st.session_state["selected_club"] = None
    st.session_state["selected_player"] = None

def back_one_level():
    lvl = st.session_state["level"]
    if lvl == "competition":
        st.session_state["level"] = "league"
        st.session_state["selected_league"] = None
    elif lvl == "ladder_clubs":
        st.session_state["level"] = "competition"
        st.session_state["selected_competition"] = None
    elif lvl == "players":
        st.session_state["level"] = "ladder_clubs"
        st.session_state["selected_club"] = None
    elif lvl == "matches":
        st.session_state["level"] = "players"
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
            League → Competition → Ladder & Clubs → Players → Matches
        </p>
        <hr>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# Check if query is natural language
# ---------------------------------------------------------

def is_natural_language_query(query):
    """Check if the search query is a natural language question"""
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
            
            # Check if answer is a dict (table response)
            if isinstance(answer, dict):
                if answer.get("type") == "table":
                    st.markdown(f"**{answer.get('title')}**")
                    df = pd.DataFrame(answer.get('data', []))
                    st.dataframe(df, hide_index=True)
                elif answer.get("type") == "error":
                    st.error(answer.get("message", "An error occurred"))
            else:
                # Regular text response
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

        # Simple text filtering (not natural language)
        if search and not is_natural_language_query(search):
            leagues = [l for l in leagues if search.lower() in l.lower()]

        if not leagues:
            st.info("No leagues found.")
            return

        # Create DataFrame with explicit boolean type
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

        # Check if any row was selected
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
            st.rerun()

    # ---------------- LEVEL 3: LADDER + CLUBS ----------------
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
        ladder_df.insert(1, "Select", pd.Series([False] * len(ladder_df), dtype=bool))

        edited = st.data_editor(
            ladder_df[["Select", "Pos", "club", "played", "wins", "draws", "losses",
                       "gf", "ga", "gd", "points"]],
            hide_index=True,
            column_config={
                "Select": st.column_config.CheckboxColumn("Select", help="Select to open", default=False),
                "club": st.column_config.TextColumn("Club")
            },
            disabled=["Pos", "club", "played", "wins", "draws", "losses",
                      "gf", "ga", "gd", "points"],
            key="ladder_editor"
        )

        selected_rows = edited[edited["Select"] == True]
        if not selected_rows.empty:
            st.session_state["selected_club"] = selected_rows.iloc[0]["club"]
            st.session_state["level"] = "players"
            st.rerun()

    # ---------------- LEVEL 4: PLAYERS ----------------
    elif level == "players":
        club = st.session_state["selected_club"]
        st.subheader(f"👤 Players — {club}")

        players = get_players_for_club(players_data, club)

        if search and not is_natural_language_query(search):
            players = [
                p for p in players
                if search.lower() in f"{p.get('first_name','')} {p.get('last_name','')}".lower()
            ]

        if not players:
            st.info("No players found.")
            return

        rows = []
        for p in players:
            full_name = f"{p.get('first_name','')} {p.get('last_name','')}"
            rows.append({
                "Select": False,
                "Player": full_name,
                "Team": p.get("team_name"),
                "Goals": p.get("stats", {}).get("goals", 0),
                "Yellow Cards": p.get("stats", {}).get("yellow_cards", 0),
                "Red Cards": p.get("stats", {}).get("red_cards", 0),
            })

        df = pd.DataFrame(rows)
        df["Select"] = df["Select"].astype(bool)

        edited = st.data_editor(
            df,
            hide_index=True,
            column_config={
                "Select": st.column_config.CheckboxColumn("Select", help="Select to open", default=False),
            },
            disabled=["Player", "Team", "Goals", "Yellow Cards", "Red Cards"],
            key="players_editor"
        )

        selected_rows = edited[edited["Select"] == True]
        if not selected_rows.empty:
            idx = selected_rows.index[0]
            st.session_state["selected_player"] = players[idx]
            st.session_state["level"] = "matches"
            st.rerun()

    # ---------------- LEVEL 5: MATCHES ----------------
    elif level == "matches":
        player = st.session_state["selected_player"]
        full_name = f"{player.get('first_name','')} {player.get('last_name','')}"
        st.subheader(f"📅 Matches — {full_name}")

        matches = get_matches_for_player(player)

        rows = []
        for m in matches:
            rows.append({
                "Date": format_date(m.get("date", "")),
                "Competition": m.get("competition_name"),
                "League": m.get("league_name"),
                "Opponent": m.get("opponent_team_name"),
                "Home/Away": m.get("home_or_away"),
                "Goals": m.get("goals"),
                "Yellow Cards": m.get("yellow_cards"),
                "Red Cards": m.get("red_cards"),
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, hide_index=True)

# ---------------------------------------------------------
# Run
# ---------------------------------------------------------

if __name__ == "__main__":
    main()
