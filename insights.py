<<<<<<< HEAD
"""
insights.py  —  Junior Pro Football Intelligence
=================================================
Standalone analytics module.  Import into app.py and call show_insights_page().

Data sources (read directly from fast_agent globals after _refresh_data()):
  players_summary   — list of player dicts, each with matches[] and events[]
  staff_summary     — same shape, for coaches / staff
  match_centre_data — raw match-centre JSON (events with player_name + minute)
  results           — completed match attributes

All analysis is done purely from what is in the JSON files.
No numbers are invented — if a field is absent the insight is skipped or labelled
"insufficient data".

Insights produced
─────────────────
1.  Goal-minute distribution      — which 15-min band goals fall in
2.  Card-minute distribution      — same for yellow + red cards
3.  Comeback analysis             — how often teams recover from being behind
4.  Starting-XI vs bench impact   — goals/cards split by started vs sub
5.  Clean-sheet rate              — per club / per age group
6.  Player form streaks           — longest W/D/L streaks for your club
7.  First-scorer win rate         — does scoring first predict winning?
8.  Home vs Away scoring          — average goals home / away per team
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List, Optional, Any

# ── lazy imports (Streamlit only available when running the app) ──────────────
try:
    import streamlit as st
    import pandas as pd
    _HAS_ST = True
except ImportError:
    _HAS_ST = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_int(v) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _etype(e: dict) -> str:
    return (e.get("type") or e.get("event_type") or "").lower()


def _strip_age(name: str) -> str:
    return re.sub(r"\s+U\d{2}$", "", (name or ""), flags=re.IGNORECASE).strip()


def _band(minute) -> Optional[str]:
    """Map a goal/card minute to a 15-minute period bucket."""
    m = _safe_int(minute)
    if m is None:
        return None
    if m <= 15:   return "1–15"
    if m <= 30:   return "16–30"
    if m <= 45:   return "31–45"
    if m <= 60:   return "46–60"
    if m <= 75:   return "61–75"
    return "76–90+"


BANDS = ["1–15", "16–30", "31–45", "46–60", "61–75", "76–90+"]
HALVES = {"1H": ["1–15", "16–30", "31–45"],
           "2H": ["46–60", "61–75", "76–90+"]}


# ---------------------------------------------------------------------------
# 1. Goal-minute distribution (from players_summary events)
# ---------------------------------------------------------------------------

def goal_minute_distribution(
    players_summary: list,
    club_filter: str = "",
    age_filter: str = "",
    league_filter: str = "",
) -> dict:
    """
    Returns:
      bands       — {band: count}
      total       — int
      narrative   — plain-English string (or "" if no data)
      half_split  — {"1H": n, "2H": n}
      has_data    — bool
    """
    counts: Dict[str, int] = {b: 0 for b in BANDS}
    total = 0

    for p in players_summary:
        for m in p.get("matches", []):
            if not (m.get("available") or m.get("started")):
                continue
            m_team = m.get("team_name", "")
            if club_filter and club_filter.lower() not in m_team.lower():
                continue
            if age_filter and age_filter.lower() not in m_team.lower():
                continue
            if league_filter:
                m_lg = m.get("league_name", "") or m.get("competition_name", "")
                if league_filter.lower() not in m_lg.lower():
                    continue

            # goal_minutes field (populated by _normalize_person)
            for minute in m.get("goal_minutes", []):
                b = _band(minute)
                if b:
                    counts[b] += 1
                    total += 1

            # fallback: scan raw events
            if not m.get("goal_minutes"):
                for e in m.get("events", []):
                    if _etype(e) in ("goal", "goal_scored") and not e.get("own_goal"):
                        b = _band(e.get("minute"))
                        if b:
                            counts[b] += 1
                            total += 1

    if total == 0:
        return {"bands": counts, "total": 0, "narrative": "", "half_split": {}, "has_data": False}

    # Peak band
    peak_band = max(counts, key=counts.get)
    peak_pct  = round(counts[peak_band] / total * 100)
    first_h   = sum(counts[b] for b in HALVES["1H"])
    second_h  = sum(counts[b] for b in HALVES["2H"])
    first_pct = round(first_h / total * 100)

    # Narrative
    if peak_band in HALVES["1H"]:
        tempo = "early-pressure style"
    elif peak_band == "31–45":
        tempo = "late first-half burst (just before the break)"
    elif peak_band in ("46–60",):
        tempo = "strong second-half start"
    else:
        tempo = "late-game intensity"

    if first_pct >= 60:
        half_note = f"Most goals come in the first half ({first_pct}%)."
    elif first_pct <= 40:
        half_note = f"Most goals come in the second half ({100 - first_pct}%)."
    else:
        half_note = f"Goals are fairly evenly split across both halves ({first_pct}% first half)."

    narrative = (
        f"⚽ **Goal timing:** The most productive 15-minute window is **{peak_band}** "
        f"({counts[peak_band]} goals, {peak_pct}% of the total {total}). "
        f"{half_note} "
        f"This suggests a **{tempo}**."
    )

    return {
        "bands":      counts,
        "total":      total,
        "narrative":  narrative,
        "half_split": {"1H": first_h, "2H": second_h},
        "has_data":   True,
    }


# ---------------------------------------------------------------------------
# 2. Card-minute distribution
# ---------------------------------------------------------------------------

def card_minute_distribution(
    players_summary: list,
    staff_summary: list,
    club_filter: str = "",
    age_filter: str = "",
) -> dict:
    yc: Dict[str, int] = {b: 0 for b in BANDS}
    rc: Dict[str, int] = {b: 0 for b in BANDS}
    yc_total = rc_total = 0

    for pool in (players_summary, staff_summary):
        for p in pool:
            for m in p.get("matches", []):
                m_team = m.get("team_name", "")
                if club_filter and club_filter.lower() not in m_team.lower():
                    continue
                if age_filter and age_filter.lower() not in m_team.lower():
                    continue

                for minute in m.get("yellow_minutes", []):
                    b = _band(minute)
                    if b:
                        yc[b] += 1; yc_total += 1

                for minute in m.get("red_minutes", []):
                    b = _band(minute)
                    if b:
                        rc[b] += 1; rc_total += 1

    # Narratives
    narratives = []
    if yc_total > 0:
        peak_yc = max(yc, key=yc.get)
        pct_yc  = round(yc[peak_yc] / yc_total * 100)
        late_yc = sum(yc[b] for b in ["61–75", "76–90+"])
        late_pct = round(late_yc / yc_total * 100)
        if late_pct >= 50:
            yc_note = f"Over half of yellow cards come in the last 30 minutes ({late_pct}%) — frustration/fatigue likely."
        else:
            yc_note = f"Yellow cards peak in **{peak_yc}** ({pct_yc}% of {yc_total} total)."
        narratives.append(f"🟨 **Discipline:** {yc_note}")

    if rc_total > 0:
        peak_rc = max(rc, key=rc.get)
        pct_rc  = round(rc[peak_rc] / rc_total * 100)
        narratives.append(
            f"🟥 **Red cards** most common in **{peak_rc}** ({rc[peak_rc]}/{rc_total}, {pct_rc}%)."
        )

    return {
        "yellow": yc, "red": rc,
        "yc_total": yc_total, "rc_total": rc_total,
        "narratives": narratives,
        "has_data": (yc_total + rc_total) > 0,
    }


# ---------------------------------------------------------------------------
# 3. Comeback / come-from-behind analysis  (match_centre_data events)
# ---------------------------------------------------------------------------

def comeback_analysis(match_centre_data: list, club_filter: str = "", age_filter: str = "") -> dict:
    """
    Scans in-match goal events (ordered by minute) per match.
    Returns how often a team that went behind first came back to draw or win.
    """
    went_behind = 0
    came_back   = 0
    still_lost  = 0

    for mc in match_centre_data:
        r_attrs = mc.get("result", {}).get("attributes", {})
        home = r_attrs.get("home_team_name", "")
        away = r_attrs.get("away_team_name", "")
        if club_filter:
            if club_filter.lower() not in home.lower() and club_filter.lower() not in away.lower():
                continue
        if age_filter:
            if age_filter.lower() not in home.lower() and age_filter.lower() not in away.lower():
                continue

        hs_final = _safe_int(r_attrs.get("home_score"))
        as_final = _safe_int(r_attrs.get("away_score"))
        if hs_final is None or as_final is None:
            continue

        events = sorted(mc.get("events", []), key=lambda e: _safe_int(e.get("minute")) or 999)
        home_g = away_g = 0
        went_behind_flag = False

        for e in events:
            if _etype(e) not in ("goal", "goal_scored"):
                continue
            is_og  = e.get("own_goal", False)
            t_name = (e.get("team_name") or "").lower()

            if not is_og:
                if home.lower() in t_name or (t_name and home.lower()[:6] in t_name):
                    home_g += 1
                else:
                    away_g += 1
            else:
                if home.lower() in t_name:
                    away_g += 1
                else:
                    home_g += 1

            # check if either tracked side went behind at any point
            if club_filter:
                our_g  = home_g if club_filter.lower() in home.lower() else away_g
                opp_g  = away_g if club_filter.lower() in home.lower() else home_g
            else:
                our_g, opp_g = home_g, away_g

            if opp_g > our_g and not went_behind_flag:
                went_behind_flag = True

        if went_behind_flag:
            went_behind += 1
            if club_filter:
                our_final  = hs_final if club_filter.lower() in home.lower() else as_final
                opp_final  = as_final if club_filter.lower() in home.lower() else hs_final
            else:
                our_final, opp_final = hs_final, as_final
            if our_final >= opp_final:
                came_back += 1
            else:
                still_lost += 1

    if went_behind == 0:
        return {"has_data": False, "narrative": ""}

    rate = round(came_back / went_behind * 100)
    narrative = (
        f"🔁 **Comeback rate:** {went_behind} times a deficit was conceded; "
        f"the team recovered {came_back} of those ({rate}%). "
    )
    if rate >= 60:
        narrative += "That's a **very resilient squad** — rarely gives up when behind."
    elif rate >= 40:
        narrative += "Decent resilience — comes back from behind fairly often."
    else:
        narrative += "**Fragile when behind** — once a goal is conceded it usually becomes a loss."

    return {
        "has_data":    True,
        "went_behind": went_behind,
        "came_back":   came_back,
        "still_lost":  still_lost,
        "rate_pct":    rate,
        "narrative":   narrative,
    }


# ---------------------------------------------------------------------------
# 4. Starter vs sub impact
# ---------------------------------------------------------------------------

def starter_vs_sub_impact(
    players_summary: list,
    club_filter: str = "",
    age_filter: str = "",
) -> dict:
    starter_goals = starter_matches = 0
    sub_goals = sub_matches = 0
    starter_yc = sub_yc = 0

    for p in players_summary:
        for m in p.get("matches", []):
            if not (m.get("available") or m.get("started")):
                continue
            m_team = m.get("team_name", "")
            if club_filter and club_filter.lower() not in m_team.lower():
                continue
            if age_filter and age_filter.lower() not in m_team.lower():
                continue

            g  = m.get("goals", 0) or 0
            yc = m.get("yellow_cards", 0) or 0

            if m.get("started"):
                starter_matches += 1
                starter_goals   += g
                starter_yc      += yc
            else:
                sub_matches += 1
                sub_goals   += g
                sub_yc      += yc

    if starter_matches == 0:
        return {"has_data": False, "narrative": ""}

    starter_gpg = round(starter_goals / starter_matches, 3)
    sub_gpg     = round(sub_goals     / sub_matches, 3)     if sub_matches else None
    starter_ycpm = round(starter_yc   / starter_matches, 3)
    sub_ycpm     = round(sub_yc       / sub_matches, 3)     if sub_matches else None

    narrative_parts = [
        f"🎽 **Starters:** {starter_matches} appearances, "
        f"{starter_goals} goals ({starter_gpg:.2f}/match), "
        f"{starter_yc} yellow cards ({starter_ycpm:.2f}/match)."
    ]

    if sub_gpg is not None:
        narrative_parts.append(
            f"🪑 **Bench:** {sub_matches} appearances, "
            f"{sub_goals} goals ({sub_gpg:.2f}/match), "
            f"{sub_yc} yellow cards ({sub_ycpm:.2f}/match)."
        )
        if starter_gpg > sub_gpg * 1.2:
            narrative_parts.append("Starters are significantly more productive in front of goal.")
        elif sub_gpg and sub_gpg > starter_gpg * 1.2:
            narrative_parts.append("Substitutes are outscoring starters per match — good impact from the bench!")
        else:
            narrative_parts.append("Goal output is similar between starters and subs.")

    return {
        "has_data":        True,
        "starter_matches": starter_matches,
        "starter_goals":   starter_goals,
        "starter_gpg":     starter_gpg,
        "sub_matches":     sub_matches,
        "sub_goals":       sub_goals,
        "sub_gpg":         sub_gpg,
        "narrative":       "\n\n".join(narrative_parts),
    }


# ---------------------------------------------------------------------------
# 5. Clean-sheet rate
# ---------------------------------------------------------------------------

def clean_sheet_rate(results: list, club_filter: str = "", age_filter: str = "") -> dict:
    played = clean_sheets = 0

    for r in results:
        a  = r.get("attributes", {})
        if (a.get("status") or "").lower() != "complete":
            continue
        home = a.get("home_team_name", "")
        away = a.get("away_team_name", "")
        blob = f"{home} {away}".lower()
        if club_filter and club_filter.lower() not in blob:
            continue
        if age_filter and age_filter.lower() not in blob:
            continue

        hs = _safe_int(a.get("home_score"))
        as_ = _safe_int(a.get("away_score"))
        if hs is None or as_ is None:
            continue

        is_home = (not club_filter) or club_filter.lower() in home.lower()
        ga      = as_ if is_home else hs
        played += 1
        if ga == 0:
            clean_sheets += 1

    if played == 0:
        return {"has_data": False, "narrative": ""}

    rate = round(clean_sheets / played * 100)
    narrative = (
        f"🧤 **Clean sheets:** {clean_sheets} in {played} matches ({rate}%). "
    )
    if rate >= 50:
        narrative += "Exceptional defensive record — keeping a clean sheet in more than half of games."
    elif rate >= 30:
        narrative += "Solid defensive base."
    else:
        narrative += "Conceding in most games — an area to focus on."

    return {
        "has_data":     True,
        "played":       played,
        "clean_sheets": clean_sheets,
        "rate_pct":     rate,
        "narrative":    narrative,
    }


# ---------------------------------------------------------------------------
# 6. First-scorer advantage
# ---------------------------------------------------------------------------

def first_scorer_advantage(match_centre_data: list, club_filter: str = "", age_filter: str = "") -> dict:
    """Does the team that scores first win more often?"""
    total = first_scored_then_won = first_scored_then_drew = first_scored_then_lost = 0
    we_scored_first = 0
    we_scored_first_then_won = 0

    for mc in match_centre_data:
        r_attrs = mc.get("result", {}).get("attributes", {})
        home = r_attrs.get("home_team_name", "")
        away = r_attrs.get("away_team_name", "")
        if club_filter:
            if club_filter.lower() not in home.lower() and club_filter.lower() not in away.lower():
                continue
        if age_filter:
            if age_filter.lower() not in home.lower() and age_filter.lower() not in away.lower():
                continue

        hs = _safe_int(r_attrs.get("home_score"))
        as_ = _safe_int(r_attrs.get("away_score"))
        if hs is None or as_ is None:
            continue

        events = sorted(mc.get("events", []), key=lambda e: _safe_int(e.get("minute")) or 999)
        first_scorer_team = None

        for e in events:
            if _etype(e) not in ("goal", "goal_scored"):
                continue
            t = e.get("team_name", "")
            is_og = e.get("own_goal", False)
            if is_og:
                # own goal credited to conceding team
                if home.lower()[:8] in t.lower():
                    first_scorer_team = "away"
                else:
                    first_scorer_team = "home"
            else:
                if home.lower()[:8] in t.lower() or (t and t.lower() in home.lower()[:8]):
                    first_scorer_team = "home"
                else:
                    first_scorer_team = "away"
            break

        if not first_scorer_team:
            continue  # 0-0

        total += 1
        if hs > as_:   result = "home_win"
        elif as_ > hs: result = "away_win"
        else:          result = "draw"

        fs_won = (first_scorer_team == "home" and result == "home_win") or \
                 (first_scorer_team == "away" and result == "away_win")
        fs_drew = result == "draw"

        if fs_won:   first_scored_then_won  += 1
        elif fs_drew: first_scored_then_drew += 1
        else:        first_scored_then_lost  += 1

        # Club-specific tracking
        if club_filter:
            we_home = club_filter.lower() in home.lower()
            we_first = (first_scorer_team == "home" and we_home) or \
                       (first_scorer_team == "away" and not we_home)
            if we_first:
                we_scored_first += 1
                our_result = ("win" if (we_home and result == "home_win") or
                              (not we_home and result == "away_win") else
                              "draw" if result == "draw" else "loss")
                if our_result == "win":
                    we_scored_first_then_won += 1

    if total == 0:
        return {"has_data": False, "narrative": ""}

    win_pct  = round(first_scored_then_won  / total * 100)
    draw_pct = round(first_scored_then_drew / total * 100)
    loss_pct = round(first_scored_then_lost / total * 100)

    narrative = (
        f"🥅 **First-scorer advantage:** Across {total} matches, the team that "
        f"scored first went on to win **{win_pct}%** of the time, "
        f"drew {draw_pct}%, lost {loss_pct}%. "
    )
    if win_pct >= 70:
        narrative += "Scoring first is almost decisive in this competition."
    elif win_pct >= 55:
        narrative += "A strong indicator — scoring first gives a clear edge."
    else:
        narrative += "Leads are not always held — matches remain open after the first goal."

    if club_filter and we_scored_first > 0:
        club_rate = round(we_scored_first_then_won / we_scored_first * 100)
        narrative += (
            f"\n\nFor **{club_filter}**: scored first in {we_scored_first} matches "
            f"and won {we_scored_first_then_won} of them ({club_rate}%)."
        )

    return {
        "has_data":   True,
        "total":      total,
        "win_pct":    win_pct,
        "draw_pct":   draw_pct,
        "loss_pct":   loss_pct,
        "narrative":  narrative,
    }


# ---------------------------------------------------------------------------
# 7. Home vs Away scoring
# ---------------------------------------------------------------------------

def home_away_split(results: list, club_filter: str = "", age_filter: str = "") -> dict:
    home_goals = home_matches = 0
    away_goals = away_matches = 0

    for r in results:
        a = r.get("attributes", {})
        if (a.get("status") or "").lower() != "complete":
            continue
        home = a.get("home_team_name", "")
        away = a.get("away_team_name", "")
        blob = f"{home} {away}".lower()
        if club_filter and club_filter.lower() not in blob:
            continue
        if age_filter and age_filter.lower() not in blob:
            continue

        hs = _safe_int(a.get("home_score"))
        as_ = _safe_int(a.get("away_score"))
        if hs is None or as_ is None:
            continue

        if club_filter:
            # track from our perspective
            if club_filter.lower() in home.lower():
                home_goals   += hs;  home_matches   += 1
            elif club_filter.lower() in away.lower():
                away_goals   += as_; away_matches   += 1
        else:
            home_goals  += hs;  home_matches  += 1
            away_goals  += as_; away_matches  += 1

    if home_matches + away_matches == 0:
        return {"has_data": False, "narrative": ""}

    hgpg = round(home_goals / home_matches, 2) if home_matches else 0
    agpg = round(away_goals / away_matches, 2) if away_matches else 0

    narrative = (
        f"🏠 **Home:** {home_matches} matches, avg {hgpg} goals/game.   "
        f"✈️ **Away:** {away_matches} matches, avg {agpg} goals/game. "
    )
    if hgpg > agpg + 0.3:
        narrative += "Clear home advantage in attack — significantly more productive at home."
    elif agpg > hgpg + 0.3:
        narrative += "Interestingly, more goals come in away games."
    else:
        narrative += "Home and away output are consistent — a well-balanced side."

    return {
        "has_data":      True,
        "home_matches":  home_matches,
        "home_goals":    home_goals,
        "home_gpg":      hgpg,
        "away_matches":  away_matches,
        "away_goals":    away_goals,
        "away_gpg":      agpg,
        "narrative":     narrative,
    }


# ---------------------------------------------------------------------------
# 8. Player form streaks
# ---------------------------------------------------------------------------

def player_form_streaks(
    players_summary: list,
    club_filter: str = "",
    age_filter: str = "",
    top_n: int = 5,
) -> dict:
    """
    Returns players with longest current scoring streak and longest goalless drought.
    """
    streaks = []
    droughts = []

    for p in players_summary:
        name = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
        played = [
            m for m in sorted(p.get("matches", []), key=lambda x: x.get("date", ""))
            if (m.get("available") or m.get("started"))
            and (not club_filter or club_filter.lower() in (m.get("team_name", "") or "").lower())
            and (not age_filter  or age_filter.lower()  in (m.get("team_name", "") or "").lower())
        ]
        if len(played) < 3:
            continue

        # Current scoring streak (games with ≥1 goal from most recent backwards)
        scoring_streak = 0
        for m in reversed(played):
            if (m.get("goals") or 0) > 0:
                scoring_streak += 1
            else:
                break

        # Current goalless drought
        drought = 0
        for m in reversed(played):
            if (m.get("goals") or 0) == 0:
                drought += 1
            else:
                break

        team = _strip_age(played[-1].get("team_name", ""))
        total_goals = sum(m.get("goals", 0) or 0 for m in played)

        if scoring_streak >= 2:
            streaks.append({
                "Player":  name,
                "Team":    team,
                "Streak":  scoring_streak,
                "Total G": total_goals,
                "Matches": len(played),
            })

        if drought >= 3 and total_goals > 0:
            droughts.append({
                "Player":   name,
                "Team":     team,
                "Drought":  drought,
                "Total G":  total_goals,
                "Matches":  len(played),
            })

    streaks.sort(key=lambda x: -x["Streak"])
    droughts.sort(key=lambda x: -x["Drought"])

    return {
        "has_data":  bool(streaks or droughts),
        "streaks":   streaks[:top_n],
        "droughts":  droughts[:top_n],
    }


# ===========================================================================
# Streamlit page  —  call from app.py
# ===========================================================================

def show_insights_page():
    """
    Main entry point.  Call this from app.py after authentication.
    Reads data directly from fast_agent globals.
    """
    if not _HAS_ST:
        print("Streamlit not available — cannot render insights page.")
        return

    try:
        import fast_agent as fa
        fa._refresh_data()
        players_summary   = fa.players_summary
        staff_summary     = fa.staff_summary
        match_centre_data = fa.match_centre_data
        results           = fa.results
        USER_CONFIG       = fa.USER_CONFIG
    except ImportError:
        st.error("fast_agent.py not found in the same directory.")
        return

    # ── Page title ─────────────────────────────────────────────────────────
    st.markdown("### 📊 Match & Player Insights")
    st.caption(
        "All insights are derived from your existing JSON data files. "
        "Only metrics that have enough data are shown."
    )

    # ── Filters ────────────────────────────────────────────────────────────
    col_club, col_age = st.columns([3, 1])
    with col_club:
        default_club = USER_CONFIG.get("club", "")
        club_filter  = st.text_input("Club filter (leave blank for all clubs)",
                                     value=default_club,
                                     key="insights_club_filter")
    with col_age:
        default_age = USER_CONFIG.get("age_group", "")
        age_filter  = st.text_input("Age group (e.g. U16)",
                                    value=default_age,
                                    key="insights_age_filter")

    st.markdown("---")

    # ── Run all analyses ───────────────────────────────────────────────────
    goal_dist  = goal_minute_distribution(players_summary, club_filter, age_filter)
    card_dist  = card_minute_distribution(players_summary, staff_summary, club_filter, age_filter)
    comeback   = comeback_analysis(match_centre_data, club_filter, age_filter)
    starter    = starter_vs_sub_impact(players_summary, club_filter, age_filter)
    cs_rate    = clean_sheet_rate(results, club_filter, age_filter)
    fs_adv     = first_scorer_advantage(match_centre_data, club_filter, age_filter)
    ha_split   = home_away_split(results, club_filter, age_filter)
    streaks    = player_form_streaks(players_summary, club_filter, age_filter)

    any_data = any([
        goal_dist["has_data"], card_dist["has_data"], comeback["has_data"],
        starter["has_data"],   cs_rate["has_data"],   fs_adv["has_data"],
        ha_split["has_data"],  streaks["has_data"],
    ])

    if not any_data:
        st.warning(
            "No data found for the selected filters. "
            "Try clearing the club / age group filter to see all clubs, "
            "or check that your JSON files are loaded."
        )
        return

    # ─────────────────────────────────────────────────────────────────────
    # Section 1 — Goal timing
    # ─────────────────────────────────────────────────────────────────────
    with st.expander("⚽ Goal Timing — When do goals happen?", expanded=True):
        if goal_dist["has_data"]:
            st.markdown(goal_dist["narrative"])
            df_goals = pd.DataFrame({
                "Period":     list(goal_dist["bands"].keys()),
                "Goals":      list(goal_dist["bands"].values()),
            })
            # percentage column
            df_goals["%"] = (df_goals["Goals"] / goal_dist["total"] * 100).round(1)

            col_tbl, col_txt = st.columns([2, 1])
            with col_tbl:
                st.dataframe(
                    df_goals,
                    hide_index=True,
                    column_config={
                        "Period": st.column_config.TextColumn("Period",  width="small"),
                        "Goals":  st.column_config.NumberColumn("Goals", width="small"),
                        "%":      st.column_config.NumberColumn("%",     width="small"),
                    },
                    height=(len(df_goals) + 1) * 35 + 10,
                )
            with col_txt:
                h1 = goal_dist["half_split"].get("1H", 0)
                h2 = goal_dist["half_split"].get("2H", 0)
                st.metric("1st Half Goals", h1)
                st.metric("2nd Half Goals", h2)
                st.metric("Total Goals (with minute)", goal_dist["total"])
        else:
            st.info("No goal-minute data found. Events may not carry a `minute` field in your JSON.")

    # ─────────────────────────────────────────────────────────────────────
    # Section 2 — Card timing
    # ─────────────────────────────────────────────────────────────────────
    with st.expander("🟨🟥 Discipline — When do cards happen?", expanded=True):
        if card_dist["has_data"]:
            for n in card_dist["narratives"]:
                st.markdown(n)

            col_y, col_r = st.columns(2)
            with col_y:
                st.markdown("**Yellow Card Distribution**")
                yc_df = pd.DataFrame({
                    "Period":  BANDS,
                    "Yellow":  [card_dist["yellow"][b] for b in BANDS],
                })
                st.dataframe(yc_df, hide_index=True, height=(len(yc_df)+1)*35+10)
            with col_r:
                st.markdown("**Red Card Distribution**")
                rc_df = pd.DataFrame({
                    "Period": BANDS,
                    "Red":    [card_dist["red"][b] for b in BANDS],
                })
                st.dataframe(rc_df, hide_index=True, height=(len(rc_df)+1)*35+10)
        else:
            st.info("No card-minute data found.")

    # ─────────────────────────────────────────────────────────────────────
    # Section 3 — First scorer, Home/Away, Clean sheets, Comebacks
    # ─────────────────────────────────────────────────────────────────────
    with st.expander("📈 Match Patterns", expanded=True):
        sections = [
            (fs_adv,  "First scorer wins"),
            (ha_split, "Home vs Away"),
            (cs_rate,  "Clean sheets"),
            (comeback, "Comeback rate"),
        ]
        for data, _label in sections:
            if data.get("has_data"):
                st.markdown(data["narrative"])
                st.markdown("---")

        if not any(d.get("has_data") for d, _ in sections):
            st.info("Insufficient match-centre data for pattern analysis.")

    # ─────────────────────────────────────────────────────────────────────
    # Section 4 — Starters vs Subs
    # ─────────────────────────────────────────────────────────────────────
    with st.expander("🎽 Starters vs Substitutes", expanded=False):
        if starter["has_data"]:
            st.markdown(starter["narrative"])
            rows = [
                {"Role": "Starter", "Matches": starter["starter_matches"],
                 "Goals": starter["starter_goals"], "Goals/Match": starter["starter_gpg"]},
            ]
            if starter["sub_matches"]:
                rows.append(
                    {"Role": "Sub/Bench", "Matches": starter["sub_matches"],
                     "Goals": starter["sub_goals"],   "Goals/Match": starter["sub_gpg"]},
                )
            st.dataframe(pd.DataFrame(rows), hide_index=True,
                         height=(len(rows)+1)*35+10)
        else:
            st.info("No starter/sub data available.")

    # ─────────────────────────────────────────────────────────────────────
    # Section 5 — Form streaks
    # ─────────────────────────────────────────────────────────────────────
    with st.expander("🔥 Player Form — Streaks & Droughts", expanded=False):
        if streaks["has_data"]:
            col_s, col_d = st.columns(2)
            with col_s:
                st.markdown("**🔥 Current Scoring Streaks** (consecutive games with a goal)")
                if streaks["streaks"]:
                    st.dataframe(pd.DataFrame(streaks["streaks"]),
                                 hide_index=True,
                                 height=(len(streaks["streaks"])+1)*35+10)
                else:
                    st.caption("No active streaks of 2+ games.")
            with col_d:
                st.markdown("**❄️ Goalless Droughts** (games without scoring, minimum 3)")
                if streaks["droughts"]:
                    st.dataframe(pd.DataFrame(streaks["droughts"]),
                                 hide_index=True,
                                 height=(len(streaks["droughts"])+1)*35+10)
                else:
                    st.caption("No significant goalless runs found.")
        else:
            st.info("Not enough match data to compute streaks (minimum 3 matches per player).")
=======
"""
insights.py  —  Junior Pro Football Intelligence
=================================================
Standalone analytics module.  Import into app.py and call show_insights_page().

Data sources (read directly from fast_agent globals after _refresh_data()):
  players_summary   — list of player dicts, each with matches[] and events[]
  staff_summary     — same shape, for coaches / staff
  match_centre_data — raw match-centre JSON (events with player_name + minute)
  results           — completed match attributes

All analysis is done purely from what is in the JSON files.
No numbers are invented — if a field is absent the insight is skipped or labelled
"insufficient data".

Insights produced
─────────────────
1.  Goal-minute distribution      — which 15-min band goals fall in
2.  Card-minute distribution      — same for yellow + red cards
3.  Comeback analysis             — how often teams recover from being behind
4.  Starting-XI vs bench impact   — goals/cards split by started vs sub
5.  Clean-sheet rate              — per club / per age group
6.  Player form streaks           — longest W/D/L streaks for your club
7.  First-scorer win rate         — does scoring first predict winning?
8.  Home vs Away scoring          — average goals home / away per team
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List, Optional, Any

# ── lazy imports (Streamlit only available when running the app) ──────────────
try:
    import streamlit as st
    import pandas as pd
    _HAS_ST = True
except ImportError:
    _HAS_ST = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_int(v) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _etype(e: dict) -> str:
    return (e.get("type") or e.get("event_type") or "").lower()


def _strip_age(name: str) -> str:
    return re.sub(r"\s+U\d{2}$", "", (name or ""), flags=re.IGNORECASE).strip()


def _band(minute) -> Optional[str]:
    """Map a goal/card minute to a 15-minute period bucket."""
    m = _safe_int(minute)
    if m is None:
        return None
    if m <= 15:   return "1–15"
    if m <= 30:   return "16–30"
    if m <= 45:   return "31–45"
    if m <= 60:   return "46–60"
    if m <= 75:   return "61–75"
    return "76–90+"


BANDS = ["1–15", "16–30", "31–45", "46–60", "61–75", "76–90+"]
HALVES = {"1H": ["1–15", "16–30", "31–45"],
           "2H": ["46–60", "61–75", "76–90+"]}


# ---------------------------------------------------------------------------
# 1. Goal-minute distribution (from players_summary events)
# ---------------------------------------------------------------------------

def goal_minute_distribution(
    players_summary: list,
    club_filter: str = "",
    age_filter: str = "",
    league_filter: str = "",
) -> dict:
    """
    Returns:
      bands       — {band: count}
      total       — int
      narrative   — plain-English string (or "" if no data)
      half_split  — {"1H": n, "2H": n}
      has_data    — bool
    """
    counts: Dict[str, int] = {b: 0 for b in BANDS}
    total = 0

    for p in players_summary:
        for m in p.get("matches", []):
            if not (m.get("available") or m.get("started")):
                continue
            m_team = m.get("team_name") or ""
            if club_filter and club_filter.lower() not in m_team.lower():
                continue
            if age_filter and age_filter.lower() not in m_team.lower():
                continue
            if league_filter:
                m_lg = m.get("league_name", "") or m.get("competition_name", "")
                if league_filter.lower() not in m_lg.lower():
                    continue

            # goal_minutes field (populated by _normalize_person)
            for minute in m.get("goal_minutes", []):
                b = _band(minute)
                if b:
                    counts[b] += 1
                    total += 1

            # fallback: scan raw events
            if not m.get("goal_minutes"):
                for e in m.get("events", []):
                    if _etype(e) in ("goal", "goal_scored") and not e.get("own_goal"):
                        b = _band(e.get("minute"))
                        if b:
                            counts[b] += 1
                            total += 1

    if total == 0:
        return {"bands": counts, "total": 0, "narrative": "", "half_split": {}, "has_data": False}

    # Peak band
    peak_band = max(counts, key=counts.get)
    peak_pct  = round(counts[peak_band] / total * 100)
    first_h   = sum(counts[b] for b in HALVES["1H"])
    second_h  = sum(counts[b] for b in HALVES["2H"])
    first_pct = round(first_h / total * 100)

    # Narrative
    if peak_band in HALVES["1H"]:
        tempo = "early-pressure style"
    elif peak_band == "31–45":
        tempo = "late first-half burst (just before the break)"
    elif peak_band in ("46–60",):
        tempo = "strong second-half start"
    else:
        tempo = "late-game intensity"

    if first_pct >= 60:
        half_note = f"Most goals come in the first half ({first_pct}%)."
    elif first_pct <= 40:
        half_note = f"Most goals come in the second half ({100 - first_pct}%)."
    else:
        half_note = f"Goals are fairly evenly split across both halves ({first_pct}% first half)."

    narrative = (
        f"⚽ **Goal timing:** The most productive 15-minute window is **{peak_band}** "
        f"({counts[peak_band]} goals, {peak_pct}% of the total {total}). "
        f"{half_note} "
        f"This suggests a **{tempo}**."
    )

    return {
        "bands":      counts,
        "total":      total,
        "narrative":  narrative,
        "half_split": {"1H": first_h, "2H": second_h},
        "has_data":   True,
    }


# ---------------------------------------------------------------------------
# 2. Card-minute distribution
# ---------------------------------------------------------------------------

def card_minute_distribution(
    players_summary: list,
    staff_summary: list,
    club_filter: str = "",
    age_filter: str = "",
) -> dict:
    yc: Dict[str, int] = {b: 0 for b in BANDS}
    rc: Dict[str, int] = {b: 0 for b in BANDS}
    yc_total = rc_total = 0

    for pool in (players_summary, staff_summary):
        for p in pool:
            for m in p.get("matches", []):
                m_team = m.get("team_name") or ""
                if club_filter and club_filter.lower() not in m_team.lower():
                    continue
                if age_filter and age_filter.lower() not in m_team.lower():
                    continue

                for minute in m.get("yellow_minutes", []):
                    b = _band(minute)
                    if b:
                        yc[b] += 1; yc_total += 1

                for minute in m.get("red_minutes", []):
                    b = _band(minute)
                    if b:
                        rc[b] += 1; rc_total += 1

    # Narratives
    narratives = []
    if yc_total > 0:
        peak_yc = max(yc, key=yc.get)
        pct_yc  = round(yc[peak_yc] / yc_total * 100)
        late_yc = sum(yc[b] for b in ["61–75", "76–90+"])
        late_pct = round(late_yc / yc_total * 100)
        if late_pct >= 50:
            yc_note = f"Over half of yellow cards come in the last 30 minutes ({late_pct}%) — frustration/fatigue likely."
        else:
            yc_note = f"Yellow cards peak in **{peak_yc}** ({pct_yc}% of {yc_total} total)."
        narratives.append(f"🟨 **Discipline:** {yc_note}")

    if rc_total > 0:
        peak_rc = max(rc, key=rc.get)
        pct_rc  = round(rc[peak_rc] / rc_total * 100)
        narratives.append(
            f"🟥 **Red cards** most common in **{peak_rc}** ({rc[peak_rc]}/{rc_total}, {pct_rc}%)."
        )

    return {
        "yellow": yc, "red": rc,
        "yc_total": yc_total, "rc_total": rc_total,
        "narratives": narratives,
        "has_data": (yc_total + rc_total) > 0,
    }


# ---------------------------------------------------------------------------
# 3. Comeback / come-from-behind analysis  (match_centre_data events)
# ---------------------------------------------------------------------------

def comeback_analysis(match_centre_data: list, club_filter: str = "", age_filter: str = "") -> dict:
    """
    Scans in-match goal events (ordered by minute) per match.
    Returns how often a team that went behind first came back to draw or win.
    """
    went_behind = 0
    came_back   = 0
    still_lost  = 0

    for mc in match_centre_data:
        r_attrs = mc.get("result", {}).get("attributes", {})
        home = r_attrs.get("home_team_name") or ""
        away = r_attrs.get("away_team_name") or ""
        if club_filter:
            if club_filter.lower() not in home.lower() and club_filter.lower() not in away.lower():
                continue
        if age_filter:
            if age_filter.lower() not in home.lower() and age_filter.lower() not in away.lower():
                continue

        hs_final = _safe_int(r_attrs.get("home_score"))
        as_final = _safe_int(r_attrs.get("away_score"))
        if hs_final is None or as_final is None:
            continue

        events = sorted(mc.get("events", []), key=lambda e: _safe_int(e.get("minute")) or 999)
        home_g = away_g = 0
        went_behind_flag = False

        for e in events:
            if _etype(e) not in ("goal", "goal_scored"):
                continue
            is_og  = e.get("own_goal", False)
            t_name = (e.get("team_name") or "").lower()

            if not is_og:
                if home.lower() in t_name or (t_name and home.lower()[:6] in t_name):
                    home_g += 1
                else:
                    away_g += 1
            else:
                if home.lower() in t_name:
                    away_g += 1
                else:
                    home_g += 1

            # check if either tracked side went behind at any point
            if club_filter:
                our_g  = home_g if club_filter.lower() in home.lower() else away_g
                opp_g  = away_g if club_filter.lower() in home.lower() else home_g
            else:
                our_g, opp_g = home_g, away_g

            if opp_g > our_g and not went_behind_flag:
                went_behind_flag = True

        if went_behind_flag:
            went_behind += 1
            if club_filter:
                our_final  = hs_final if club_filter.lower() in home.lower() else as_final
                opp_final  = as_final if club_filter.lower() in home.lower() else hs_final
            else:
                our_final, opp_final = hs_final, as_final
            if our_final >= opp_final:
                came_back += 1
            else:
                still_lost += 1

    if went_behind == 0:
        return {"has_data": False, "narrative": ""}

    rate = round(came_back / went_behind * 100)
    narrative = (
        f"🔁 **Comeback rate:** {went_behind} times a deficit was conceded; "
        f"the team recovered {came_back} of those ({rate}%). "
    )
    if rate >= 60:
        narrative += "That's a **very resilient squad** — rarely gives up when behind."
    elif rate >= 40:
        narrative += "Decent resilience — comes back from behind fairly often."
    else:
        narrative += "**Fragile when behind** — once a goal is conceded it usually becomes a loss."

    return {
        "has_data":    True,
        "went_behind": went_behind,
        "came_back":   came_back,
        "still_lost":  still_lost,
        "rate_pct":    rate,
        "narrative":   narrative,
    }


# ---------------------------------------------------------------------------
# 4. Starter vs sub impact
# ---------------------------------------------------------------------------

def starter_vs_sub_impact(
    players_summary: list,
    club_filter: str = "",
    age_filter: str = "",
) -> dict:
    starter_goals = starter_matches = 0
    sub_goals = sub_matches = 0
    starter_yc = sub_yc = 0

    for p in players_summary:
        for m in p.get("matches", []):
            if not (m.get("available") or m.get("started")):
                continue
            m_team = m.get("team_name") or ""
            if club_filter and club_filter.lower() not in m_team.lower():
                continue
            if age_filter and age_filter.lower() not in m_team.lower():
                continue

            g  = m.get("goals", 0) or 0
            yc = m.get("yellow_cards", 0) or 0

            if m.get("started"):
                starter_matches += 1
                starter_goals   += g
                starter_yc      += yc
            else:
                sub_matches += 1
                sub_goals   += g
                sub_yc      += yc

    if starter_matches == 0:
        return {"has_data": False, "narrative": ""}

    starter_gpg = round(starter_goals / starter_matches, 3)
    sub_gpg     = round(sub_goals     / sub_matches, 3)     if sub_matches else None
    starter_ycpm = round(starter_yc   / starter_matches, 3)
    sub_ycpm     = round(sub_yc       / sub_matches, 3)     if sub_matches else None

    narrative_parts = [
        f"🎽 **Starters:** {starter_matches} appearances, "
        f"{starter_goals} goals ({starter_gpg:.2f}/match), "
        f"{starter_yc} yellow cards ({starter_ycpm:.2f}/match)."
    ]

    if sub_gpg is not None:
        narrative_parts.append(
            f"🪑 **Bench:** {sub_matches} appearances, "
            f"{sub_goals} goals ({sub_gpg:.2f}/match), "
            f"{sub_yc} yellow cards ({sub_ycpm:.2f}/match)."
        )
        if starter_gpg > sub_gpg * 1.2:
            narrative_parts.append("Starters are significantly more productive in front of goal.")
        elif sub_gpg and sub_gpg > starter_gpg * 1.2:
            narrative_parts.append("Substitutes are outscoring starters per match — good impact from the bench!")
        else:
            narrative_parts.append("Goal output is similar between starters and subs.")

    return {
        "has_data":        True,
        "starter_matches": starter_matches,
        "starter_goals":   starter_goals,
        "starter_gpg":     starter_gpg,
        "sub_matches":     sub_matches,
        "sub_goals":       sub_goals,
        "sub_gpg":         sub_gpg,
        "narrative":       "\n\n".join(narrative_parts),
    }


# ---------------------------------------------------------------------------
# 5. Clean-sheet rate
# ---------------------------------------------------------------------------

def clean_sheet_rate(results: list, club_filter: str = "", age_filter: str = "") -> dict:
    played = clean_sheets = 0

    for r in results:
        a  = r.get("attributes", {})
        if (a.get("status") or "").lower() != "complete":
            continue
        home = a.get("home_team_name") or ""
        away = a.get("away_team_name") or ""
        blob = f"{home} {away}".lower()
        if club_filter and club_filter.lower() not in blob:
            continue
        if age_filter and age_filter.lower() not in blob:
            continue

        hs = _safe_int(a.get("home_score"))
        as_ = _safe_int(a.get("away_score"))
        if hs is None or as_ is None:
            continue

        is_home = (not club_filter) or club_filter.lower() in home.lower()
        ga      = as_ if is_home else hs
        played += 1
        if ga == 0:
            clean_sheets += 1

    if played == 0:
        return {"has_data": False, "narrative": ""}

    rate = round(clean_sheets / played * 100)
    narrative = (
        f"🧤 **Clean sheets:** {clean_sheets} in {played} matches ({rate}%). "
    )
    if rate >= 50:
        narrative += "Exceptional defensive record — keeping a clean sheet in more than half of games."
    elif rate >= 30:
        narrative += "Solid defensive base."
    else:
        narrative += "Conceding in most games — an area to focus on."

    return {
        "has_data":     True,
        "played":       played,
        "clean_sheets": clean_sheets,
        "rate_pct":     rate,
        "narrative":    narrative,
    }


# ---------------------------------------------------------------------------
# 6. First-scorer advantage
# ---------------------------------------------------------------------------

def first_scorer_advantage(match_centre_data: list, club_filter: str = "", age_filter: str = "") -> dict:
    """Does the team that scores first win more often?"""
    total = first_scored_then_won = first_scored_then_drew = first_scored_then_lost = 0
    we_scored_first = 0
    we_scored_first_then_won = 0

    for mc in match_centre_data:
        r_attrs = mc.get("result", {}).get("attributes", {})
        home = r_attrs.get("home_team_name") or ""
        away = r_attrs.get("away_team_name") or ""
        if club_filter:
            if club_filter.lower() not in home.lower() and club_filter.lower() not in away.lower():
                continue
        if age_filter:
            if age_filter.lower() not in home.lower() and age_filter.lower() not in away.lower():
                continue

        hs = _safe_int(r_attrs.get("home_score"))
        as_ = _safe_int(r_attrs.get("away_score"))
        if hs is None or as_ is None:
            continue

        events = sorted(mc.get("events", []), key=lambda e: _safe_int(e.get("minute")) or 999)
        first_scorer_team = None

        for e in events:
            if _etype(e) not in ("goal", "goal_scored"):
                continue
            t = e.get("team_name", "")
            is_og = e.get("own_goal", False)
            if is_og:
                # own goal credited to conceding team
                if home.lower()[:8] in t.lower():
                    first_scorer_team = "away"
                else:
                    first_scorer_team = "home"
            else:
                if home.lower()[:8] in t.lower() or (t and t.lower() in home.lower()[:8]):
                    first_scorer_team = "home"
                else:
                    first_scorer_team = "away"
            break

        if not first_scorer_team:
            continue  # 0-0

        total += 1
        if hs > as_:   result = "home_win"
        elif as_ > hs: result = "away_win"
        else:          result = "draw"

        fs_won = (first_scorer_team == "home" and result == "home_win") or \
                 (first_scorer_team == "away" and result == "away_win")
        fs_drew = result == "draw"

        if fs_won:   first_scored_then_won  += 1
        elif fs_drew: first_scored_then_drew += 1
        else:        first_scored_then_lost  += 1

        # Club-specific tracking
        if club_filter:
            we_home = club_filter.lower() in home.lower()
            we_first = (first_scorer_team == "home" and we_home) or \
                       (first_scorer_team == "away" and not we_home)
            if we_first:
                we_scored_first += 1
                our_result = ("win" if (we_home and result == "home_win") or
                              (not we_home and result == "away_win") else
                              "draw" if result == "draw" else "loss")
                if our_result == "win":
                    we_scored_first_then_won += 1

    if total == 0:
        return {"has_data": False, "narrative": ""}

    win_pct  = round(first_scored_then_won  / total * 100)
    draw_pct = round(first_scored_then_drew / total * 100)
    loss_pct = round(first_scored_then_lost / total * 100)

    narrative = (
        f"🥅 **First-scorer advantage:** Across {total} matches, the team that "
        f"scored first went on to win **{win_pct}%** of the time, "
        f"drew {draw_pct}%, lost {loss_pct}%. "
    )
    if win_pct >= 70:
        narrative += "Scoring first is almost decisive in this competition."
    elif win_pct >= 55:
        narrative += "A strong indicator — scoring first gives a clear edge."
    else:
        narrative += "Leads are not always held — matches remain open after the first goal."

    if club_filter and we_scored_first > 0:
        club_rate = round(we_scored_first_then_won / we_scored_first * 100)
        narrative += (
            f"\n\nFor **{club_filter}**: scored first in {we_scored_first} matches "
            f"and won {we_scored_first_then_won} of them ({club_rate}%)."
        )

    return {
        "has_data":   True,
        "total":      total,
        "win_pct":    win_pct,
        "draw_pct":   draw_pct,
        "loss_pct":   loss_pct,
        "narrative":  narrative,
    }


# ---------------------------------------------------------------------------
# 7. Home vs Away scoring
# ---------------------------------------------------------------------------

def home_away_split(results: list, club_filter: str = "", age_filter: str = "") -> dict:
    home_goals = home_matches = 0
    away_goals = away_matches = 0

    for r in results:
        a = r.get("attributes", {})
        if (a.get("status") or "").lower() != "complete":
            continue
        home = a.get("home_team_name") or ""
        away = a.get("away_team_name") or ""
        blob = f"{home} {away}".lower()
        if club_filter and club_filter.lower() not in blob:
            continue
        if age_filter and age_filter.lower() not in blob:
            continue

        hs = _safe_int(a.get("home_score"))
        as_ = _safe_int(a.get("away_score"))
        if hs is None or as_ is None:
            continue

        if club_filter:
            # track from our perspective
            if club_filter.lower() in home.lower():
                home_goals   += hs;  home_matches   += 1
            elif club_filter.lower() in away.lower():
                away_goals   += as_; away_matches   += 1
        else:
            home_goals  += hs;  home_matches  += 1
            away_goals  += as_; away_matches  += 1

    if home_matches + away_matches == 0:
        return {"has_data": False, "narrative": ""}

    hgpg = round(home_goals / home_matches, 2) if home_matches else 0
    agpg = round(away_goals / away_matches, 2) if away_matches else 0

    narrative = (
        f"🏠 **Home:** {home_matches} matches, avg {hgpg} goals/game.   "
        f"✈️ **Away:** {away_matches} matches, avg {agpg} goals/game. "
    )
    if hgpg > agpg + 0.3:
        narrative += "Clear home advantage in attack — significantly more productive at home."
    elif agpg > hgpg + 0.3:
        narrative += "Interestingly, more goals come in away games."
    else:
        narrative += "Home and away output are consistent — a well-balanced side."

    return {
        "has_data":      True,
        "home_matches":  home_matches,
        "home_goals":    home_goals,
        "home_gpg":      hgpg,
        "away_matches":  away_matches,
        "away_goals":    away_goals,
        "away_gpg":      agpg,
        "narrative":     narrative,
    }


# ---------------------------------------------------------------------------
# 8. Player form streaks
# ---------------------------------------------------------------------------

def player_form_streaks(
    players_summary: list,
    club_filter: str = "",
    age_filter: str = "",
    top_n: int = 5,
) -> dict:
    """
    Returns players with longest current scoring streak and longest goalless drought.
    """
    streaks = []
    droughts = []

    for p in players_summary:
        name = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
        played = [
            m for m in sorted(p.get("matches", []), key=lambda x: x.get("date") or "")
            if (m.get("available") or m.get("started"))
            and (not club_filter or club_filter.lower() in (m.get("team_name", "") or "").lower())
            and (not age_filter  or age_filter.lower()  in (m.get("team_name", "") or "").lower())
        ]
        if len(played) < 3:
            continue

        # Current scoring streak (games with ≥1 goal from most recent backwards)
        scoring_streak = 0
        for m in reversed(played):
            if (m.get("goals") or 0) > 0:
                scoring_streak += 1
            else:
                break

        # Current goalless drought
        drought = 0
        for m in reversed(played):
            if (m.get("goals") or 0) == 0:
                drought += 1
            else:
                break

        team = _strip_age(played[-1].get("team_name", ""))
        total_goals = sum(m.get("goals", 0) or 0 for m in played)

        if scoring_streak >= 2:
            streaks.append({
                "Player":  name,
                "Team":    team,
                "Streak":  scoring_streak,
                "Total G": total_goals,
                "Matches": len(played),
            })

        if drought >= 3 and total_goals > 0:
            droughts.append({
                "Player":   name,
                "Team":     team,
                "Drought":  drought,
                "Total G":  total_goals,
                "Matches":  len(played),
            })

    streaks.sort(key=lambda x: -x["Streak"])
    droughts.sort(key=lambda x: -x["Drought"])

    return {
        "has_data":  bool(streaks or droughts),
        "streaks":   streaks[:top_n],
        "droughts":  droughts[:top_n],
    }


# ===========================================================================
# Streamlit page  —  call from app.py
# ===========================================================================

def show_insights_page():
    """
    Main entry point.  Call this from app.py after authentication.
    Reads data directly from fast_agent globals.
    """
    if not _HAS_ST:
        print("Streamlit not available — cannot render insights page.")
        return

    try:
        import fast_agent as fa
        fa._refresh_data()
        players_summary   = fa.players_summary
        staff_summary     = fa.staff_summary
        match_centre_data = fa.match_centre_data
        results           = fa.results
        USER_CONFIG       = fa.USER_CONFIG
    except ImportError:
        st.error("fast_agent.py not found in the same directory.")
        return

    # ── Page title ─────────────────────────────────────────────────────────
    st.markdown("### 📊 Season Insights Briefing")
    st.caption("A conversational read-out of your team's patterns, trends, and player form — all drawn from match data.")

    # ── Filters ────────────────────────────────────────────────────────────
    col_club, col_age = st.columns([3, 1])
    with col_club:
        default_club = USER_CONFIG.get("club", "")
        club_filter  = st.text_input("Club filter (leave blank for all clubs)",
                                     value=default_club,
                                     key="insights_club_filter")
    with col_age:
        default_age = USER_CONFIG.get("age_group", "")
        age_filter  = st.text_input("Age group (e.g. U16)",
                                    value=default_age,
                                    key="insights_age_filter")

    st.markdown("---")

    # ── Run all analyses ───────────────────────────────────────────────────
    goal_dist  = goal_minute_distribution(players_summary, club_filter, age_filter)
    card_dist  = card_minute_distribution(players_summary, staff_summary, club_filter, age_filter)
    comeback   = comeback_analysis(match_centre_data, club_filter, age_filter)
    starter    = starter_vs_sub_impact(players_summary, club_filter, age_filter)
    cs_rate    = clean_sheet_rate(results, club_filter, age_filter)
    fs_adv     = first_scorer_advantage(match_centre_data, club_filter, age_filter)
    ha_split   = home_away_split(results, club_filter, age_filter)
    streaks    = player_form_streaks(players_summary, club_filter, age_filter)

    any_data = any([
        goal_dist["has_data"], card_dist["has_data"], comeback["has_data"],
        starter["has_data"],   cs_rate["has_data"],   fs_adv["has_data"],
        ha_split["has_data"],  streaks["has_data"],
    ])

    if not any_data:
        st.warning(
            "No data found for the selected filters. "
            "Try clearing the club / age group filter to see all clubs, "
            "or check that your JSON files are loaded."
        )
        return

    # ── Build the briefing label ────────────────────────────────────────────
    subject = club_filter or "All Clubs"
    if age_filter:
        subject += f" ({age_filter})"

    st.markdown(f"#### 📋 Briefing — {subject}")

    # ─────────────────────────────────────────────────────────────────────
    # PARAGRAPH 1 — Goals & Timing
    # ─────────────────────────────────────────────────────────────────────
    if goal_dist["has_data"]:
        peak   = max(goal_dist["bands"], key=goal_dist["bands"].get)
        total  = goal_dist["total"]
        peak_n = goal_dist["bands"][peak]
        peak_pct = round(peak_n / total * 100)
        h1 = goal_dist["half_split"].get("1H", 0)
        h2 = goal_dist["half_split"].get("2H", 0)
        h1_pct = round(h1 / total * 100) if total else 0

        if h1_pct >= 60:
            half_sentence = f"The first half is considerably more productive, accounting for {h1_pct}% of goals ({h1} vs {h2})."
        elif h1_pct <= 40:
            half_sentence = f"Goals tend to come later — {100 - h1_pct}% arrive in the second half ({h2} vs {h1} in the first)."
        else:
            half_sentence = f"Goals are spread fairly evenly: {h1} in the first half and {h2} in the second."

        st.markdown(f"""
**⚽ Attacking Pattern**

Looking at {total} goals where minute data was recorded, the most dangerous 15-minute window is the **{peak}** period,
which accounts for {peak_n} goals — {peak_pct}% of the total. {half_sentence}
This is worth keeping in mind for warm-up routines and how the team sets up mentally at the start of each half.
        """)

        df_goals = pd.DataFrame({
            "Period": list(goal_dist["bands"].keys()),
            "Goals":  list(goal_dist["bands"].values()),
        })
        df_goals["%"] = (df_goals["Goals"] / total * 100).round(1)
        col_tbl, col_txt = st.columns([2, 1])
        with col_tbl:
            st.dataframe(df_goals, hide_index=True,
                column_config={
                    "Period": st.column_config.TextColumn("Period", width="small"),
                    "Goals":  st.column_config.NumberColumn("Goals", width="small"),
                    "%":      st.column_config.NumberColumn("%",     width="small"),
                },
                height=(len(df_goals) + 1) * 35 + 10)
        with col_txt:
            st.metric("1st Half", h1)
            st.metric("2nd Half", h2)
            st.metric("Total Goals", total)
        st.markdown("---")

    # ─────────────────────────────────────────────────────────────────────
    # PARAGRAPH 2 — Discipline
    # ─────────────────────────────────────────────────────────────────────
    if card_dist["has_data"]:
        yc_total = card_dist["yc_total"]
        rc_total = card_dist["rc_total"]
        yc       = card_dist["yellow"]
        rc       = card_dist["red"]

        late_yc  = sum(yc[b] for b in ["61–75", "76–90+"])
        late_pct = round(late_yc / yc_total * 100) if yc_total else 0
        peak_yc  = max(yc, key=yc.get) if yc_total else None

        if late_pct >= 50:
            yc_sentence = (f"Over half of all yellow cards ({late_pct}%) come in the last 30 minutes — "
                           f"a pattern that usually reflects fatigue or mounting frustration late in games.")
        elif peak_yc:
            yc_sentence = (f"Yellow cards cluster around the **{peak_yc}** window "
                           f"({yc[peak_yc]} of {yc_total}), which is the highest-risk period for discipline.")
        else:
            yc_sentence = f"There have been {yc_total} yellow cards across the season."

        rc_sentence = ""
        if rc_total > 0:
            peak_rc = max(rc, key=rc.get)
            rc_sentence = (f" Red cards are rare but have occurred {rc_total} time{'s' if rc_total > 1 else ''}, "
                           f"most commonly in the **{peak_rc}** period.")

        st.markdown(f"""
**🟨 Discipline**

{yc_sentence}{rc_sentence}
Teams that maintain composure in the final quarter often hold results — this is an area worth addressing
in training if the pattern is consistent across multiple age groups.
        """)

        col_y, col_r = st.columns(2)
        with col_y:
            st.caption("Yellow Card Distribution")
            yc_df = pd.DataFrame({"Period": BANDS, "Yellow": [yc[b] for b in BANDS]})
            st.dataframe(yc_df, hide_index=True, height=(len(yc_df)+1)*35+10)
        with col_r:
            st.caption("Red Card Distribution")
            rc_df = pd.DataFrame({"Period": BANDS, "Red": [rc[b] for b in BANDS]})
            st.dataframe(rc_df, hide_index=True, height=(len(rc_df)+1)*35+10)
        st.markdown("---")

    # ─────────────────────────────────────────────────────────────────────
    # PARAGRAPH 3 — Match patterns
    # ─────────────────────────────────────────────────────────────────────
    pattern_parts = []

    if fs_adv["has_data"]:
        wp = fs_adv["win_pct"]
        if wp >= 70:
            fs_line = f"Scoring first is nearly decisive — the opening goal leads to a win {wp}% of the time. Getting on the board early should be a clear game plan priority."
        elif wp >= 55:
            fs_line = f"The first goal carries real weight: the team that scores first wins {wp}% of matches. There's a strong case for pressing high and looking to open the scoring quickly."
        else:
            fs_line = f"Interestingly, the first goal isn't as decisive as you might expect — the opening scorer wins only {wp}% of the time, meaning matches stay open and comebacks are common."
        pattern_parts.append(fs_line)

    if ha_split["has_data"]:
        hgpg = ha_split["home_gpg"]
        agpg = ha_split["away_gpg"]
        hm   = ha_split["home_matches"]
        am   = ha_split["away_matches"]
        if hgpg > agpg + 0.3:
            ha_line = f"There's a notable home advantage — averaging {hgpg} goals per home game vs {agpg} away, across {hm} home and {am} away matches."
        elif agpg > hgpg + 0.3:
            ha_line = f"Unusually, the team actually scores more away from home ({agpg}/game) than at home ({hgpg}/game) — suggesting strong performances when travelling."
        else:
            ha_line = f"Home and away output is consistent ({hgpg} vs {agpg} goals/game), which suggests the team's style doesn't depend heavily on the venue."
        pattern_parts.append(ha_line)

    if cs_rate["has_data"]:
        rate   = cs_rate["rate_pct"]
        played = cs_rate["played"]
        cs     = cs_rate["clean_sheets"]
        if rate >= 50:
            cs_line = f"Defensively, this is an impressive unit — {cs} clean sheets from {played} games ({rate}%), keeping opponents off the scoresheet more often than not."
        elif rate >= 30:
            cs_line = f"The defence has been solid in patches, posting {cs} clean sheets from {played} games ({rate}%)."
        else:
            cs_line = f"Conceding is a concern — only {cs} clean sheets from {played} games ({rate}%), meaning the team rarely keeps a shut-out."
        pattern_parts.append(cs_line)

    if comeback["has_data"]:
        went = comeback["went_behind"]
        came = comeback["came_back"]
        rate = comeback["rate_pct"]
        if rate >= 60:
            cb_line = f"Perhaps most tellingly, the team shows excellent mental resilience — coming from behind to salvage a result in {came} of {went} occasions ({rate}%). That's a squad that doesn't give up."
        elif rate >= 40:
            cb_line = f"When behind, the team has shown the ability to fight back, recovering points in {came} of {went} deficits ({rate}%)."
        else:
            cb_line = f"Conceding the first goal tends to be costly — the team has come back in only {came} of {went} situations ({rate}%), so avoiding falling behind is crucial."
        pattern_parts.append(cb_line)

    if pattern_parts:
        st.markdown("**📈 Match Patterns**\n\n" + " ".join(pattern_parts))

        # Summary table
        pattern_rows = []
        if fs_adv["has_data"]:
            pattern_rows.append({"Metric": "First scorer wins", "Value": f"{fs_adv['win_pct']}%", "Sample": f"{fs_adv['total']} matches"})
        if ha_split["has_data"]:
            pattern_rows.append({"Metric": "Home goals/game",  "Value": str(ha_split["home_gpg"]), "Sample": f"{ha_split['home_matches']} home games"})
            pattern_rows.append({"Metric": "Away goals/game",  "Value": str(ha_split["away_gpg"]), "Sample": f"{ha_split['away_matches']} away games"})
        if cs_rate["has_data"]:
            pattern_rows.append({"Metric": "Clean sheet rate", "Value": f"{cs_rate['rate_pct']}%", "Sample": f"{cs_rate['played']} games"})
        if comeback["has_data"]:
            pattern_rows.append({"Metric": "Comeback rate",    "Value": f"{comeback['rate_pct']}%", "Sample": f"{comeback['went_behind']} deficits"})
        if pattern_rows:
            st.dataframe(pd.DataFrame(pattern_rows), hide_index=True,
                height=(len(pattern_rows)+1)*35+10,
                column_config={
                    "Metric": st.column_config.TextColumn("Metric", width="medium"),
                    "Value":  st.column_config.TextColumn("Value",  width="small"),
                    "Sample": st.column_config.TextColumn("Based on", width="medium"),
                })
        st.markdown("---")

    # ─────────────────────────────────────────────────────────────────────
    # PARAGRAPH 4 — Starters vs Subs
    # ─────────────────────────────────────────────────────────────────────
    if starter["has_data"]:
        sm    = starter["starter_matches"]
        sg    = starter["starter_goals"]
        sgpg  = starter["starter_gpg"]
        subm  = starter.get("sub_matches", 0)
        subg  = starter.get("sub_goals", 0)
        subgpg = starter.get("sub_gpg") or 0

        if subm:
            if sgpg > subgpg * 1.2:
                bench_line = (f"Starting players are clearly the primary source of goals — {sg} goals across {sm} appearances "
                              f"({sgpg:.2f}/game) compared to {subg} from bench players across {subm} appearances ({subgpg:.2f}/game). "
                              f"The starting XI is doing the heavy lifting.")
            elif subgpg and subgpg > sgpg * 1.2:
                bench_line = (f"Interestingly, substitutes are punching above their weight — {subgpg:.2f} goals per appearance "
                              f"vs {sgpg:.2f} for starters. Bringing on fresh legs seems to unlock something.")
            else:
                bench_line = (f"Goal contribution is well balanced across starters and subs — starters averaging {sgpg:.2f}/game "
                              f"and bench players {subgpg:.2f}/game across {sm} and {subm} appearances respectively.")
        else:
            bench_line = f"Starters have recorded {sg} goals across {sm} appearances ({sgpg:.2f}/game). No sub appearance data available."

        st.markdown(f"**🎽 Starters vs Substitutes**\n\n{bench_line}")

        rows = [{"Role": "Starter", "Matches": sm, "Goals": sg, "Goals/Match": sgpg}]
        if subm:
            rows.append({"Role": "Sub/Bench", "Matches": subm, "Goals": subg, "Goals/Match": subgpg})
        st.dataframe(pd.DataFrame(rows), hide_index=True, height=(len(rows)+1)*35+10)
        st.markdown("---")

    # ─────────────────────────────────────────────────────────────────────
    # PARAGRAPH 5 — Form streaks
    # ─────────────────────────────────────────────────────────────────────
    if streaks["has_data"]:
        streak_list  = streaks.get("streaks", [])
        drought_list = streaks.get("droughts", [])

        streak_text = drought_text = ""

        if streak_list:
            top    = streak_list[0]
            others = streak_list[1:3]
            streak_text = (f"**{top['Player']}** is the standout in-form scorer right now, "
                           f"netting in {top['Streak']} consecutive games.")
            if others:
                names = " and ".join(f"**{p['Player']}** ({p['Streak']} games)" for p in others)
                streak_text += f" {names} are also on scoring runs worth watching."

<<<<<<< HEAD
    # ─────────────────────────────────────────────────────────────────────
    # Section 5 — Form streaks
    # ─────────────────────────────────────────────────────────────────────
    with st.expander("🔥 Player Form — Streaks & Droughts", expanded=False):
        if streaks["has_data"]:
            col_s, col_d = st.columns(2)
            with col_s:
                st.markdown("**🔥 Current Scoring Streaks** (consecutive games with a goal)")
                if streaks["streaks"]:
                    st.dataframe(pd.DataFrame(streaks["streaks"]),
                                 hide_index=True,
                                 height=(len(streaks["streaks"])+1)*35+10)
                else:
                    st.caption("No active streaks of 2+ games.")
            with col_d:
                st.markdown("**❄️ Goalless Droughts** (games without scoring, minimum 3)")
                if streaks["droughts"]:
                    st.dataframe(pd.DataFrame(streaks["droughts"]),
                                 hide_index=True,
                                 height=(len(streaks["droughts"])+1)*35+10)
                else:
                    st.caption("No significant goalless runs found.")
        else:
            st.info("Not enough match data to compute streaks (minimum 3 matches per player).")
>>>>>>> 438a05f3cc32735b138d6cbf68a52647b3d0ff4c
=======
        if drought_list:
            top    = drought_list[0]
            others = drought_list[1:3]
            drought_text = (f"At the other end, **{top['Player']}** has gone {top['Drought']} games without a goal "
                            f"despite {top['Total G']} for the season — a player who may need a confidence boost or a tactical role change.")
            if others:
                names = " and ".join(f"**{p['Player']}** ({p['Drought']} games)" for p in others)
                drought_text += f" {names} are also experiencing lean patches."

        body = "\n\n".join(filter(None, [streak_text, drought_text]))
        if body:
            st.markdown(f"**🔥 Player Form**\n\n{body}")

        col_s, col_d = st.columns(2)
        with col_s:
            st.caption("🔥 Current Scoring Streaks (2+ games)")
            if streak_list:
                st.dataframe(pd.DataFrame(streak_list), hide_index=True,
                             height=(len(streak_list)+1)*35+10)
            else:
                st.caption("No active streaks of 2+ games.")
        with col_d:
            st.caption("❄️ Goalless Droughts (3+ games)")
            if drought_list:
                st.dataframe(pd.DataFrame(drought_list), hide_index=True,
                             height=(len(drought_list)+1)*35+10)
            else:
                st.caption("No significant goalless runs found.")
        st.markdown("---")
 
    st.caption("All figures are based on match records in the loaded JSON data files. Only events with recorded minutes are included in timing breakdowns.")
>>>>>>> a70a269ebcecea5d9ed8f12aa3b34d29f505c543
