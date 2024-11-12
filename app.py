from flask import Flask, redirect, url_for, render_template, request
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from flask_bcrypt import Bcrypt
from sqlalchemy.sql import text
from math import ceil
import json
from decimal import Decimal


from os import getenv
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)


bcrypt = Bcrypt(app)

#Configuration for PostgreSQL database
app.config['SQLALCHEMY_DATABASE_URI'] = getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = '\xb0\t\xce\x90\x1a\xb7\xfb\x1e\xdb\xb5\xdd\xc0'

# Initialize the database
db = SQLAlchemy(app)

# Import routes
from admin.routes import adminRoutes
app.register_blueprint(adminRoutes, url_prefix="/admin")

def decimal_default(obj):
    """Convert Decimal objects to floats."""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

@app.route('/')
def home():
    page = request.args.get('page', 1, type=int)
    
    search_query = request.args.get('q', '')  

    per_page = 10  
    radar_chart_per_page = 21  
    offset = (page - 1) * per_page
    radar_offset = (page - 1) * radar_chart_per_page

    search_filter = f"%{search_query}%"  

    # Query for Most FIFA World Cup Wins 
    query_wc_wins = text("""
        SELECT teams.team_name, COUNT(tournaments.tournament_id) AS world_cup_wins
        FROM teams
        JOIN tournaments ON tournaments.winner_team_id = teams.team_id
        GROUP BY teams.team_name
        ORDER BY world_cup_wins DESC
        LIMIT :per_page OFFSET :offset
    """)

    # Query for Most Goals Scored by a Specific Player 
    query_most_goals = text("""
        SELECT players.player_name, SUM(player_performance.goals_scored) AS total_goals
        FROM players
        JOIN player_performance ON players.player_id = player_performance.player_id
        GROUP BY players.player_name
        ORDER BY total_goals DESC
        LIMIT :per_page OFFSET :offset
    """)

    # Query for Recent Match Results 
    query_recent_matches = text("""
        SELECT home_team.team_name AS home_team, away_team.team_name AS away_team,
               matches.home_team_goals, matches.away_team_goals, matches.match_id
        FROM matches
        JOIN teams AS home_team ON matches.home_team_id = home_team.team_id
        JOIN teams AS away_team ON matches.away_team_id = away_team.team_id
        ORDER BY matches.match_id DESC
        LIMIT :per_page OFFSET :offset
    """)

    # Query for Most Red/Yellow Cards 
    query_most_cards = text("""
        SELECT players.player_name, SUM(player_performance.yellow_cards) AS total_yellow, SUM(player_performance.red_cards) AS total_red
        FROM players
        JOIN player_performance ON players.player_id = player_performance.player_id
        GROUP BY players.player_name
        ORDER BY total_yellow DESC, total_red DESC
        LIMIT :per_page OFFSET :offset
    """)

    # Radar chart data: Fetch teams and their stats for radar chart display 
    query_team_stats = text("""
        SELECT teams.team_name, 
            AVG(CASE 
                WHEN matches.home_team_id = teams.team_id THEN player_performance.goals_scored
                WHEN matches.away_team_id = teams.team_id THEN player_performance.goals_scored
            END) AS avg_goals_scored, 
            AVG(CASE 
                WHEN matches.home_team_id = teams.team_id THEN matches.away_team_goals
                WHEN matches.away_team_id = teams.team_id THEN matches.home_team_goals
            END) AS avg_goals_conceded, 
            AVG(player_performance.yellow_cards + player_performance.red_cards) AS avg_cards,
            AVG(CASE 
                WHEN matches.home_team_id = teams.team_id AND matches.home_team_goals > matches.away_team_goals THEN 1
                WHEN matches.away_team_id = teams.team_id AND matches.away_team_goals > matches.home_team_goals THEN 1
                ELSE 0 
            END) AS win_rate
        FROM teams
        JOIN matches ON teams.team_id = matches.home_team_id OR teams.team_id = matches.away_team_id
        JOIN player_performance ON matches.match_id = player_performance.match_id
        WHERE teams.team_name ILIKE :search_filter
        GROUP BY teams.team_name
        LIMIT :radar_chart_per_page OFFSET :radar_offset
    """)

    # Execute queries and fetch results
    with db.engine.connect() as connection:
        wc_wins = connection.execute(query_wc_wins, {"per_page": per_page, "offset": offset}).fetchall()
        most_goals = connection.execute(query_most_goals, {"per_page": per_page, "offset": offset}).fetchall()
        recent_matches = connection.execute(query_recent_matches, {"per_page": per_page, "offset": offset}).fetchall()
        most_cards = connection.execute(query_most_cards, {"per_page": per_page, "offset": offset}).fetchall()
        team_stats = connection.execute(query_team_stats, {
            "search_filter": search_filter, 
            "radar_chart_per_page": radar_chart_per_page,
            "radar_offset": radar_offset
        }).fetchall()

        # Properly format the team_stats data into dictionaries
        teams_data = []
        for team in team_stats:
            teams_data.append({
                "team_name": team.team_name,
                "avg_goals_scored": float(team.avg_goals_scored) if team.avg_goals_scored is not None else 0,
                "avg_goals_conceded": float(team.avg_goals_conceded) if team.avg_goals_conceded is not None else 0,
                "avg_cards": float(team.avg_cards) if team.avg_cards is not None else 0,
                "win_rate": float(team.win_rate) if team.win_rate is not None else 0
            })

    # Total number of teams for pagination 
    query_total_teams = text("SELECT COUNT(*) FROM teams WHERE team_name ILIKE :search_filter")
    with db.engine.connect() as connection:
        total_teams = connection.execute(query_total_teams, {"search_filter": search_filter}).scalar()

    total_pages = (total_teams + per_page - 1) // per_page 

    return render_template(
        'index.html',
        wc_wins=wc_wins,
        most_goals=most_goals,
        recent_matches=recent_matches,
        most_cards=most_cards,
        teams_data=json.dumps(teams_data, default=decimal_default), 
        page=page,
        total_pages=total_pages, 
        search_query=search_query
    )


@app.route('/teams_radar', defaults={'page': 1})
@app.route('/teams_radar/page/<int:page>')
def teams_radar(page):
    search_query = request.args.get('q', '') 
    per_page = 5 
    offset = (page - 1) * per_page
    search_filter = f"%{search_query}%"
    
    # Offensive Rating: Average goals scored per match
    query_offensive = text("""
        SELECT 
            teams.team_name,
            AVG(goals_scored) AS avg_goals_scored
        FROM 
            teams
        JOIN matches ON teams.team_id = matches.home_team_id OR teams.team_id = matches.away_team_id
        JOIN player_performance ON matches.match_id = player_performance.match_id
        WHERE teams.team_name ILIKE :search_filter
        GROUP BY teams.team_name
        ORDER BY teams.team_name
        LIMIT :per_page OFFSET :offset
    """)
    
    # Defensive Rating: Average goals conceded per match
    query_defensive = text("""
        SELECT 
            teams.team_name,
            AVG(CASE 
                WHEN teams.team_id = matches.home_team_id THEN matches.away_team_goals
                ELSE matches.home_team_goals
            END) AS avg_goals_conceded
        FROM 
            teams
        JOIN matches ON teams.team_id = matches.home_team_id OR teams.team_id = matches.away_team_id
        WHERE teams.team_name ILIKE :search_filter
        GROUP BY teams.team_name
        ORDER BY teams.team_name
        LIMIT :per_page OFFSET :offset
    """)

    # Aggressiveness: Average yellow and red cards per match
    query_aggressiveness = text("""
        SELECT 
            teams.team_name,
            AVG(player_performance.yellow_cards + player_performance.red_cards) AS avg_cards
        FROM 
            teams
        JOIN matches ON teams.team_id = matches.home_team_id OR teams.team_id = matches.away_team_id
        JOIN player_performance ON matches.match_id = player_performance.match_id
        WHERE teams.team_name ILIKE :search_filter
        GROUP BY teams.team_name
        ORDER BY teams.team_name
        LIMIT :per_page OFFSET :offset
    """)

    # Win Rate: Wins per match
    query_win_rate = text("""
        SELECT 
            teams.team_name,
            (SUM(CASE
                WHEN matches.home_team_id = teams.team_id AND matches.home_team_goals > matches.away_team_goals THEN 1
                WHEN matches.away_team_id = teams.team_id AND matches.away_team_goals > matches.home_team_goals THEN 1
                ELSE 0
            END) * 1.0 / COUNT(matches.match_id)) AS win_rate
        FROM 
            teams
        JOIN matches ON teams.team_id = matches.home_team_id OR teams.team_id = matches.away_team_id
        WHERE teams.team_name ILIKE :search_filter
        GROUP BY teams.team_name
        ORDER BY teams.team_name
        LIMIT :per_page OFFSET :offset
    """)

    with db.engine.connect() as connection:
        offensive_data = connection.execute(query_offensive, {"per_page": per_page, "offset": offset, "search_filter": search_filter}).fetchall()
        defensive_data = connection.execute(query_defensive, {"per_page": per_page, "offset": offset, "search_filter": search_filter}).fetchall()
        aggressiveness_data = connection.execute(query_aggressiveness, {"per_page": per_page, "offset": offset, "search_filter": search_filter}).fetchall()
        win_rate_data = connection.execute(query_win_rate, {"per_page": per_page, "offset": offset, "search_filter": search_filter}).fetchall()
    
    teams_data = []
    for i in range(len(offensive_data)):
        team = {
            "team_name": offensive_data[i]["team_name"],
            "avg_goals_scored": offensive_data[i]["avg_goals_scored"],
            "avg_goals_conceded": defensive_data[i]["avg_goals_conceded"],
            "avg_cards": aggressiveness_data[i]["avg_cards"],
            "win_rate": win_rate_data[i]["win_rate"]
        }
        teams_data.append(team)

    query_total_teams = text("""
        SELECT COUNT(*) FROM teams WHERE team_name ILIKE :search_filter
    """)

    with db.engine.connect() as connection:
        total_teams = connection.execute(query_total_teams, {"search_filter": search_filter}).scalar()

    total_pages = (total_teams + per_page - 1) // per_page  

    return render_template(
        'index.html',
        teams_data=teams_data,  
        page=page,
        per_page=per_page, 
        total_pages=total_pages,
        search_query=search_query
    )

@app.route('/ranking', defaults={'page': 1})
@app.route('/ranking/page/<int:page>')
def ranking(page):
    search_query = request.args.get('q', '')  
    per_page = 20 
    offset = (page - 1) * per_page
    
    search_filter = f"%{search_query}%"

    # Subquery for matches won
    query_matches_won = text("""
        SELECT
            teams.team_id,
            teams.team_name,
            teams.fifa_code,
            COALESCE(SUM(CASE
                WHEN matches.home_team_id = teams.team_id AND matches.home_team_goals > matches.away_team_goals THEN 1
                WHEN matches.away_team_id = teams.team_id AND matches.away_team_goals > matches.home_team_goals THEN 1
                ELSE 0
            END), 0) AS matches_won
        FROM teams
        LEFT JOIN matches ON teams.team_id = matches.home_team_id OR teams.team_id = matches.away_team_id
        GROUP BY teams.team_id
    """)

    # Subquery for world cup wins
    query_wc_wins = text("""
        SELECT
            teams.team_id,
            COALESCE(COUNT(DISTINCT tournaments.tournament_id), 0) AS world_cup_wins
        FROM teams
        LEFT JOIN tournaments ON tournaments.winner_team_id = teams.team_id
        GROUP BY teams.team_id
    """)

    # Main query combining the results from both subqueries
    query_combined = text(f"""
        SELECT
            matches_won.team_name,
            matches_won.fifa_code,
            matches_won.matches_won,
            wc_wins.world_cup_wins
        FROM ({query_matches_won}) AS matches_won
        LEFT JOIN ({query_wc_wins}) AS wc_wins ON matches_won.team_id = wc_wins.team_id
        ORDER BY matches_won.matches_won DESC, wc_wins.world_cup_wins DESC
        LIMIT :per_page OFFSET :offset
    """)

    with db.engine.connect() as connection:
        result_combined = connection.execute(query_combined, {
            "per_page": per_page,
            "offset": offset
        }).mappings()

        teams = []
        for row in result_combined:
            teams.append({
                "team_name": row["team_name"],
                "fifa_code": row["fifa_code"],
                "matches_won": row["matches_won"],
                "world_cup_wins": row["world_cup_wins"],
            })

    # Count total number of teams for pagination
    query_total_teams = text("""
        SELECT COUNT(DISTINCT teams.team_id)
        FROM teams
    """)

    with db.engine.connect() as connection:
        total_teams = connection.execute(query_total_teams).scalar()

    total_pages = (total_teams + per_page - 1) // per_page  

    # Pagination logic
    visible_pages = 5  
    start_page = max(1, page - visible_pages // 2)
    end_page = min(total_pages, start_page + visible_pages - 1)

    return render_template(
        'ranking.html',
        teams=teams, 
        page=page,
        per_page=per_page,  
        total_pages=total_pages,
        start_page=start_page,
        end_page=end_page,
        search_query=search_query
    )


@app.route('/teams', defaults={'page': 1})
@app.route('/teams/page/<int:page>')
def teams(page):
    search_query = request.args.get('q', '') 
    matches_played = request.args.get('matches_played', None, type=int)  
    player_caps = request.args.get('player_caps', None, type=int)  
    min_matches = request.args.get('min_matches', None, type=int)
    max_matches = request.args.get('max_matches', None, type=int)  

    per_page = 20  
    offset = (page - 1) * per_page

    # Base query filter
    filters = ["(team_name ILIKE :search_filter OR continent ILIKE :search_filter)"]
    query_params = {"search_filter": f"%{search_query}%"}

    # Handle the "Minimum Number of Matches Played" filter
    if matches_played is not None:
        filters.append("""
            (SELECT COUNT(*) FROM matches WHERE matches.home_team_id = teams.team_id OR matches.away_team_id = teams.team_id) >= :matches_played
        """)
        query_params["matches_played"] = matches_played

    # Handle the "Minimum Number of Caps" filter 
    if player_caps is not None:
        filters.append("""
            EXISTS (
                SELECT 1
                FROM players
                WHERE players.team_id = teams.team_id
                GROUP BY players.team_id
                HAVING SUM(players.caps) >= :player_caps
            )
        """)
        query_params["player_caps"] = player_caps

    # Handle the "Range of Matches Played" filter
    if min_matches is not None and max_matches is not None:
        filters.append("""
            teams.team_id IN (
                SELECT team_id
                FROM matches
                WHERE matches.home_team_id = teams.team_id OR matches.away_team_id = teams.team_id
                GROUP BY team_id
                HAVING COUNT(match_id) BETWEEN :min_matches AND :max_matches
            )
        """)
        query_params["min_matches"] = min_matches
        query_params["max_matches"] = max_matches

    # Combine the filters into the SQL query
    filters_query = " AND ".join(filters)

    # Fetch the total number of teams based on filters
    total_teams_query = text(f"""
        SELECT COUNT(*)
        FROM teams
        WHERE {filters_query}
    """)

    # Fetch the filtered teams
    query = text(f"""
        SELECT team_id, team_name, fifa_code, continent
        FROM teams
        WHERE {filters_query}
        LIMIT :per_page OFFSET :offset
    """)

    with db.engine.connect() as connection:
        total_teams = connection.execute(total_teams_query, query_params).scalar()
        result = connection.execute(query, {**query_params, "per_page": per_page, "offset": offset})

        teams = []
        for row in result.mappings():
            teams.append({
                "team_id": row["team_id"],
                "team_name": row["team_name"],
                "fifa_code": row["fifa_code"],
                "continent": row["continent"]
            })

    # Calculate total pages
    total_pages = ceil(total_teams / per_page)

    # Calculate pagination range
    visible_pages = 5
    start_page = max(1, page - visible_pages // 2)
    end_page = min(total_pages, start_page + visible_pages - 1)

    return render_template("teams.html", teams=teams, page=page, total_pages=total_pages, start_page=start_page, end_page=end_page, search_query=search_query, matches_played=matches_played, player_caps=player_caps, min_matches=min_matches, max_matches=max_matches)


@app.route('/players', defaults={'page': 1})
@app.route('/players/page/<int:page>')
def players(page):
    search_query = request.args.get('q', '') 
    caps = request.args.get('caps', None, type=int) 
    birth_year = request.args.get('birth_year', None, type=int)  
    countries = request.args.getlist('countries[]')  

    per_page = 30 
    offset = (page - 1) * per_page
    
    # Base SQL query for filtering
    filters = ["(players.player_name ILIKE :search_filter OR teams.team_name ILIKE :search_filter)"]
    query_params = {"search_filter": f"%{search_query}%"}

    # Apply caps filter if it is provided
    if caps is not None:
        filters.append("players.caps >= :caps")
        query_params["caps"] = caps

    # Apply birth year filter if it is provided
    if birth_year:
        filters.append("EXTRACT(YEAR FROM players.date_of_birth) = :birth_year")
        query_params["birth_year"] = birth_year

    # Apply country filter if selected countries are provided
    if countries:
        filters.append("teams.team_name IN :countries")
        query_params["countries"] = tuple(countries) 

    # Combine the filters into the query
    filters_query = " AND ".join(filters)

    # Query to get the list of distinct countries 
    countries_query = text("""
        SELECT DISTINCT teams.team_name
        FROM teams
        ORDER BY teams.team_name
    """)

    # Query to get the total number of players based on filters
    total_players_query = text(f"""
        SELECT COUNT(*)
        FROM players
        JOIN teams ON players.team_id = teams.team_id
        WHERE {filters_query}
    """)

    # Query to get the players based on filters
    query = text(f"""
        SELECT players.player_id, players.player_name, teams.team_name, players.position, players.date_of_birth, players.caps
        FROM players
        JOIN teams ON players.team_id = teams.team_id
        WHERE {filters_query}
        LIMIT :per_page OFFSET :offset
    """)
    
    with db.engine.connect() as connection:
        # Fetch the list of distinct countries 
        countries_list = connection.execute(countries_query).mappings().fetchall()
        countries = [{'team_name': row["team_name"]} for row in countries_list] 

        total_players = connection.execute(total_players_query, query_params).scalar()

        result = connection.execute(query, {**query_params, "per_page": per_page, "offset": offset})

        players = []
        for row in result.mappings():
            players.append({
                "player_id": row["player_id"],
                "player_name": row["player_name"],
                "team_name": row["team_name"],
                "position": row["position"],
                "date_of_birth": row["date_of_birth"],
                "caps": row["caps"]
            })
        
    # Calculate total pages
    total_pages = ceil(total_players / per_page)

    # Define the range of visible pages around the current page
    visible_pages = 5
    start_page = max(1, page - visible_pages // 2)
    end_page = min(total_pages, page + visible_pages // 2)

    return render_template("players.html", players=players, page=page, total_pages=total_pages, start_page=start_page, end_page=end_page, caps=caps,
        birth_year=birth_year,
        selected_countries=countries, countries=countries)


@app.route('/match', defaults={'page': 1})
@app.route('/match/page/<int:page>')
def match(page):
    search_query = request.args.get('q', '') 
    intersect_team = request.args.get('intersect_team', None)  
    except_team = request.args.get('except_team', None)  
    goals_threshold = request.args.get('goals_threshold', None, type=int)  
    per_page = 30  
    offset = (page - 1) * per_page
    
    # Fetch teams for the dropdown options in the filter modal
    teams_query = text("SELECT team_name FROM teams")
    with db.engine.connect() as connection:
        teams_result = connection.execute(teams_query).mappings().all()
    teams = [row["team_name"] for row in teams_result]  

    # Create the search filter
    search_filter = f"%{search_query}%"

    # Base query filter
    filters = ["""
        (home_team.team_name ILIKE :search_filter 
        OR away_team.team_name ILIKE :search_filter 
        OR stadiums.stadium_name ILIKE :search_filter)
    """]
    query_params = {"search_filter": search_filter}

    # Handle the "INTERSECT" filter for team intersection
    if intersect_team:
        filters.append(f"""
            matches.match_id IN (
                SELECT match_id FROM matches WHERE matches.home_team_id IN (
                    SELECT team_id FROM teams WHERE team_name = :intersect_team
                )
                UNION
                SELECT match_id FROM matches WHERE matches.away_team_id IN (
                    SELECT team_id FROM teams WHERE team_name = :intersect_team
                )
            )

        """)
        query_params["intersect_team"] = intersect_team

    # Handle the "EXCEPT" filter to exclude a team
    if except_team:
        filters.append(f"""
            matches.match_id NOT IN (
                SELECT match_id FROM matches WHERE matches.home_team_id IN (
                    SELECT team_id FROM teams WHERE team_name = :except_team
                )
                UNION
                SELECT match_id FROM matches WHERE matches.away_team_id IN (
                    SELECT team_id FROM teams WHERE team_name = :except_team
                )
            )
        """)
        query_params["except_team"] = except_team

    # Handle the "SOME" filter for minimum goals scored
    if goals_threshold:
        filters.append(f"""
            (matches.home_team_goals >= :goals_threshold 
            OR matches.away_team_goals >= :goals_threshold)
        """)
        query_params["goals_threshold"] = goals_threshold

    # Combine the filters into the SQL query
    filters_query = " AND ".join(filters)

    # Fetch the total number of matches based on filters
    total_matches_query = text(f"""
        SELECT COUNT(*)
        FROM matches
        JOIN teams AS home_team ON matches.home_team_id = home_team.team_id
        JOIN teams AS away_team ON matches.away_team_id = away_team.team_id
        JOIN stadiums ON matches.stadium_id = stadiums.stadium_id
        WHERE {filters_query}
    """)

    # Fetch the filtered matches
    query = text(f"""
        SELECT home_team.team_name AS home_team_name,
               away_team.team_name AS away_team_name,
               matches.home_team_goals,
               matches.away_team_goals,
               matches.round,
               stadiums.stadium_name AS venue
        FROM matches
        JOIN teams AS home_team ON matches.home_team_id = home_team.team_id
        JOIN teams AS away_team ON matches.away_team_id = away_team.team_id
        JOIN stadiums ON matches.stadium_id = stadiums.stadium_id
        WHERE {filters_query}
        ORDER BY matches.match_id DESC
        LIMIT :per_page OFFSET :offset
    """)

    with db.engine.connect() as connection:
        total_matches = connection.execute(total_matches_query, query_params).scalar()
        result = connection.execute(query, {**query_params, "per_page": per_page, "offset": offset})

        matches = []
        for row in result.mappings():
            matches.append({
                "home_team_name": row["home_team_name"],
                "away_team_name": row["away_team_name"],
                "home_team_goals": row["home_team_goals"],
                "away_team_goals": row["away_team_goals"],
                "round": row["round"],
                "venue": row["venue"]
            })

    # Calculate total pages
    total_pages = ceil(total_matches / per_page)

    # Define the range of visible pages around the current page
    visible_pages = 5
    start_page = max(1, page - visible_pages // 2)
    end_page = min(total_pages, page + visible_pages // 2)

    return render_template("matches.html", matches=matches, page=page, total_pages=total_pages, start_page=start_page, end_page=end_page, search_query=search_query, intersect_team=intersect_team, except_team=except_team, goals_threshold=goals_threshold, teams=teams)


if __name__ == '__main__':
    app.run(debug=True)