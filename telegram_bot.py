import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from fast_agent import FastQueryRouter
import re
from collections import defaultdict

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load your data (similar to your Streamlit app)
def load_data():
    with open("data/master_results.json", "r", encoding="utf-8") as f:
        results = json.load(f)
    with open("data/fixtures.json", "r", encoding="utf-8") as f:
        fixtures = json.load(f)
    with open("data/players_summary.json", "r", encoding="utf-8") as f:
        players_data = json.load(f)
    return results, fixtures, players_data

results, fixtures, players_data = load_data()
router = FastQueryRouter()

# Telegram Bot Token (get from @BotFather)
TELEGRAM_TOKEN = "8241702379:AAG5dzZFPC3X71tnmUunEdNs7Rg1FeIel9Y"

# Store user sessions
user_sessions = {}

def base_club_name(team_name: str) -> str:
    """Return the base club name without age suffix."""
    if not team_name:
        return ""
    pattern = r'\s+U\d{2}$'
    cleaned = re.sub(pattern, '', team_name).strip()
    return cleaned

# Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message when /start is issued."""
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("📊 Leagues", callback_data='leagues')],
        [InlineKeyboardButton("🔍 Search Player", callback_data='search_player')],
        [InlineKeyboardButton("📅 My Next Match", callback_data='next_match')],
        [InlineKeyboardButton("🏆 Top Scorers", callback_data='top_scorers')],
        [InlineKeyboardButton("💬 Ask Question", callback_data='ask_question')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Hi {user.first_name}! ⚽\n"
        f"Welcome to Dribl Football Intelligence Bot!\n\n"
        f"Choose an option:",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button presses."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == 'leagues':
        await show_leagues(query, context)
    elif data == 'search_player':
        await query.edit_message_text("Please send me the player's name to search:")
        context.user_data['awaiting_player_search'] = True
    elif data == 'next_match':
        await query.edit_message_text("Please send me your team name to find upcoming matches:")
        context.user_data['awaiting_team_name'] = True
    elif data == 'top_scorers':
        await show_top_scorers(query, context)
    elif data == 'ask_question':
        await query.edit_message_text("Ask me anything about football stats! (e.g., 'when is my next match', 'stats for John')")
        context.user_data['awaiting_question'] = True
    elif data.startswith('league_'):
        league = data.replace('league_', '')
        await show_competitions(query, context, league)
    elif data.startswith('comp_'):
        comp = data.replace('comp_', '')
        await show_competition_details(query, context, comp)
    elif data == 'back_main':
        await show_main_menu(query)

async def show_main_menu(query):
    """Show the main menu."""
    keyboard = [
        [InlineKeyboardButton("📊 Leagues", callback_data='leagues')],
        [InlineKeyboardButton("🔍 Search Player", callback_data='search_player')],
        [InlineKeyboardButton("📅 My Next Match", callback_data='next_match')],
        [InlineKeyboardButton("🏆 Top Scorers", callback_data='top_scorers')],
        [InlineKeyboardButton("💬 Ask Question", callback_data='ask_question')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Main Menu:\nChoose an option:",
        reply_markup=reply_markup
    )

async def show_leagues(query, context):
    """Show all available leagues."""
    leagues = set()
    
    for item in results:
        league_name = item.get("attributes", {}).get("league_name")
        if league_name:
            if "YPL1" in league_name:
                leagues.add("YPL1")
            elif "YPL2" in league_name:
                leagues.add("YPL2")
            elif "YSL" in league_name:
                leagues.add("YSL")
            elif "VPL" in league_name:
                leagues.add("VPL")
    
    keyboard = []
    for league in sorted(leagues):
        keyboard.append([InlineKeyboardButton(league, callback_data=f'league_{league}')])
    
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data='back_main')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "Available Leagues:\nSelect a league to view competitions:",
        reply_markup=reply_markup
    )

async def show_competitions(query, context, league):
    """Show competitions in a specific league."""
    comps = set()
    
    for item in results + fixtures:
        attrs = item.get("attributes", {})
        league_name = attrs.get("league_name")
        if league_name and league in league_name:
            age = league_name.split()[0] if ' ' in league_name else ""
            comp_name = f"{age} {league}"
            comps.add(comp_name)
    
    if not comps:
        await query.edit_message_text(f"No competitions found in {league}.")
        return
    
    keyboard = []
    for comp in sorted(comps):
        keyboard.append([InlineKeyboardButton(comp, callback_data=f'comp_{comp}')])
    
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data='leagues')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"Competitions in {league}:\nSelect a competition:",
        reply_markup=reply_markup
    )

async def show_competition_details(query, context, competition):
    """Show ladder for a competition."""
    # Compute ladder (using your existing logic)
    results_for_comp = []
    for item in results:
        attrs = item.get("attributes", {})
        league_name = attrs.get("league_name")
        status = attrs.get("status")
        if league_name and status == "complete" and competition in league_name:
            results_for_comp.append(item)
    
    # Compute ladder
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
        
        if None in [home, away, hs, as_]:
            continue
        
        try:
            hs = int(hs)
            as_ = int(as_)
        except:
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
    
    for team in table:
        table[team]["gd"] = table[team]["gf"] - table[team]["ga"]
    
    ladder = sorted(
        table.values(),
        key=lambda r: (-r["points"], -r["gd"], -r["gf"], r["ga"], r["club"].lower())
    )
    
    # Format message
    message = f"🏆 *{competition} Ladder*\n\n"
    message += "Pos | Team | Pld | W | D | L | GF | GA | GD | Pts\n"
    message += "--- | --- | --- | --- | --- | --- | --- | --- | --- | ---\n"
    
    for i, row in enumerate(ladder[:10], 1):  # Top 10 only
        club_display = base_club_name(row["club"])
        message += f"{i}. {club_display} | {row['played']} | {row['wins']} | {row['draws']} | {row['losses']} | {row['gf']} | {row['ga']} | {row['gd']} | {row['points']}\n"
    
    if len(ladder) > 10:
        message += f"\n... and {len(ladder) - 10} more teams"
    
    keyboard = [
        [InlineKeyboardButton("⬅️ Back", callback_data='leagues')],
        [InlineKeyboardButton("🏠 Main Menu", callback_data='back_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_top_scorers(query, context):
    """Show top scorers."""
    players = players_data.get("players", [])
    
    # Sort by goals
    top_scorers = sorted(
        players,
        key=lambda p: p.get("stats", {}).get("goals", 0),
        reverse=True
    )[:10]
    
    message = "⚽ *Top 10 Scorers*\n\n"
    message += "Player | Team | Goals | Matches\n"
    message += "--- | --- | --- | ---\n"
    
    for i, player in enumerate(top_scorers, 1):
        name = f"{player.get('first_name', '')} {player.get('last_name', '')}"
        team = base_club_name(player.get("team_name", ""))
        goals = player.get("stats", {}).get("goals", 0)
        matches = player.get("stats", {}).get("matches_played", 0)
        message += f"{i}. {name} | {team} | {goals} | {matches}\n"
    
    keyboard = [
        [InlineKeyboardButton("⬅️ Back", callback_data='back_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages."""
    message_text = update.message.text
    user_data = context.user_data
    
    if user_data.get('awaiting_player_search'):
        # Search for player
        players = players_data.get("players", [])
        matched_players = []
        
        for player in players:
            full_name = f"{player.get('first_name', '')} {player.get('last_name', '')}"
            if message_text.lower() in full_name.lower():
                matched_players.append(player)
        
        if matched_players:
            player = matched_players[0]  # Take first match
            stats = player.get("stats", {})
            message = f"*Player Found:* {player.get('first_name')} {player.get('last_name')}\n"
            message += f"Team: {base_club_name(player.get('team_name', ''))}\n"
            message += f"Jersey: {player.get('jersey', 'N/A')}\n"
            message += f"Matches: {stats.get('matches_played', 0)}\n"
            message += f"Goals: {stats.get('goals', 0)}\n"
            message += f"Yellow Cards: {stats.get('yellow_cards', 0)}\n"
            message += f"Red Cards: {stats.get('red_cards', 0)}"
        else:
            message = f"No player found with name containing '{message_text}'"
        
        user_data['awaiting_player_search'] = False
        await update.message.reply_text(message, parse_mode='Markdown')
        
    elif user_data.get('awaiting_team_name'):
        # Find upcoming matches for team
        upcoming_matches = []
        for item in fixtures:
            attrs = item.get("attributes", {})
            home = attrs.get("home_team_name")
            away = attrs.get("away_team_name")
            
            if message_text.lower() in base_club_name(home).lower() or \
               message_text.lower() in base_club_name(away).lower():
                upcoming_matches.append(item)
        
        if upcoming_matches:
            message = f"*Upcoming matches for {message_text}:*\n\n"
            for match in upcoming_matches[:5]:  # Limit to 5
                attrs = match.get("attributes", {})
                message += f"📅 {attrs.get('date', '')}\n"
                message += f"🏆 {attrs.get('league_name', '')}\n"
                message += f"🏠 {base_club_name(attrs.get('home_team_name', ''))} vs {base_club_name(attrs.get('away_team_name', ''))}\n"
                message += f"📍 {attrs.get('venue_name', '')}\n"
                message += "─" * 20 + "\n"
        else:
            message = f"No upcoming matches found for '{message_text}'"
        
        user_data['awaiting_team_name'] = False
        await update.message.reply_text(message, parse_mode='Markdown')
        
    elif user_data.get('awaiting_question'):
        # Use your router to answer questions
        response = router.process(message_text)
        
        if isinstance(response, dict):
            if response.get("type") == "table":
                message = f"*{response.get('title')}*\n\n"
                for row in response.get('data', []):
                    message += str(row) + "\n"
            else:
                message = str(response)
        else:
            message = str(response)
        
        user_data['awaiting_question'] = False
        await update.message.reply_text(message, parse_mode='Markdown')
        
    else:
        # Default: try to answer with router
        response = router.process(message_text)
        await update.message.reply_text(str(response))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a help message."""
    help_text = """
    🤖 *Dribl Football Intelligence Bot*
    
    *Commands:*
    /start - Start the bot
    /help - Show this help message
    /leagues - View available leagues
    /topscorers - Show top scorers
    
    *Features:*
    • View league ladders
    • Search for players
    • Find upcoming matches
    • Ask questions about stats
    
    *Try these:*
    "when is my next match"
    "stats for [player name]"
    "top scorers in YPL1"
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

def main():
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("leagues", lambda u, c: show_leagues(u.callback_query, c) if u.callback_query else None))
    application.add_handler(CommandHandler("topscorers", lambda u, c: show_top_scorers(u.callback_query, c) if u.callback_query else None))
    
    # Add callback query handler
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Add message handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start the bot
    print("🤖 Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()