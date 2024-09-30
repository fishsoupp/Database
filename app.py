from flask import Flask, redirect, url_for, render_template, request
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.sql import text
from math import ceil



from os import getenv
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)


#Configuration for PostgreSQL database
app.config['SQLALCHEMY_DATABASE_URI'] = getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = '\xb0\t\xce\x90\x1a\xb7\xfb\x1e\xdb\xb5\xdd\xc0'

# Initialize the database
db = SQLAlchemy(app)

# Import routes
from admin.routes import adminRoutes
app.register_blueprint(adminRoutes, url_prefix="/admin")


@app.route('/')
def home():
    return render_template("index.html")

@app.route('/index')
def index():
    return render_template("index.html")

@app.route('/ranking', defaults={'page': 1})
@app.route('/ranking/page/<int:page>')
def ranking(page):
    search_query = request.args.get('q', '')  # Get search term from query parameters
    per_page = 20  # Number of teams per page
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

    total_pages = (total_teams + per_page - 1) // per_page  # Calculate total pages

    # Pagination logic
    visible_pages = 5  # Number of visible page links
    start_page = max(1, page - visible_pages // 2)
    end_page = min(total_pages, start_page + visible_pages - 1)

    return render_template(
        'ranking.html',
        teams=teams,  # Teams fetched from the database
        page=page,
        per_page=per_page,  # Pass per_page to template
        total_pages=total_pages,
        start_page=start_page,
        end_page=end_page,
        search_query=search_query
    )












@app.route('/teams', defaults={'page': 1})
@app.route('/teams/page/<int:page>')
def teams(page):
    search_query = request.args.get('q', '')  # Get search term from query parameters
    per_page = 20  # Display 30 teams per page
    offset = (page - 1) * per_page

    # Create the search filter
    search_filter = f"%{search_query}%"

    # Fetch the total number of teams, including search filtering
    total_teams_query = text("""
        SELECT COUNT(*) FROM teams
        WHERE team_name ILIKE :search_filter OR continent ILIKE :search_filter
    """)
    with db.engine.connect() as connection:
        total_teams = connection.execute(total_teams_query, {"search_filter": search_filter}).scalar()

    # Fetch the teams for the current page, including search filtering
    query = text("""
        SELECT team_id, team_name, fifa_code, continent
        FROM teams
        WHERE team_name ILIKE :search_filter OR continent ILIKE :search_filter
        LIMIT :per_page OFFSET :offset
    """)
    
    with db.engine.connect() as connection:
        result = connection.execute(query, {"per_page": per_page, "offset": offset, "search_filter": search_filter})

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

    # Define the range of visible pages around the current page
    visible_pages = 5
    start_page = max(1, page - visible_pages // 2)
    end_page = min(total_pages, page + visible_pages // 2)

    return render_template("teams.html", teams=teams, page=page, total_pages=total_pages, start_page=start_page, end_page=end_page, search_query=search_query)





@app.route('/players', defaults={'page': 1})
@app.route('/players/page/<int:page>')
def players(page):
    search_query = request.args.get('q', '')  # Get search term from query parameters
    caps = request.args.get('caps', None, type=int)  # Get caps filter
    birth_year = request.args.get('birth_year', None, type=int)  # Get birth year filter
    countries = request.args.getlist('countries[]')  # Get selected countries (array of countries)

    per_page = 30  # Display 30 players per page
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
        query_params["countries"] = tuple(countries)  # Pass as a tuple for SQL IN clause

    # Combine the filters into the query
    filters_query = " AND ".join(filters)

    # Query to get the list of distinct countries (team names)
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
        # Fetch the list of distinct countries (team names)
        countries_list = connection.execute(countries_query).mappings().fetchall()
        countries = [{'team_name': row["team_name"]} for row in countries_list]  # Format countries

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
    search_query = request.args.get('q', '')  # Get search term from query parameters
    per_page = 30  # Display 10 matches per page
    offset = (page - 1) * per_page
    
    # Create the search filter
    search_filter = f"%{search_query}%"
    
    # Fetch the total number of matches
    total_matches_query = text("""
        SELECT COUNT(*)
        FROM matches
        JOIN teams AS home_team ON matches.home_team_id = home_team.team_id
        JOIN teams AS away_team ON matches.away_team_id = away_team.team_id
        JOIN stadiums ON matches.stadium_id = stadiums.stadium_id
        WHERE home_team.team_name ILIKE :search_filter
        OR away_team.team_name ILIKE :search_filter
        OR stadiums.stadium_name ILIKE :search_filter
    """)
    
    with db.engine.connect() as connection:
        total_matches = connection.execute(total_matches_query, {"search_filter": search_filter}).scalar()

    # Fetch the matches for the current page
    query = text("""
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
        WHERE home_team.team_name ILIKE :search_filter
        OR away_team.team_name ILIKE :search_filter
        OR stadiums.stadium_name ILIKE :search_filter
        ORDER BY matches.home_team_goals DESC
        LIMIT :per_page OFFSET :offset
    """)
    
    with db.engine.connect() as connection:
        result = connection.execute(query, {"per_page": per_page, "offset": offset, "search_filter": search_filter})

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

    return render_template("matches.html", matches=matches, page=page, total_pages=total_pages, start_page=start_page, end_page=end_page, search_query=search_query)





if __name__ == '__main__':
    app.run(debug=True)