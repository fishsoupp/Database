from flask import Flask, redirect, url_for, render_template, request
from extensions import bcrypt, db  # Import bcrypt and db from extensions
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
from os import getenv
from dotenv import load_dotenv
from math import ceil
import json
from sqlalchemy.sql import text
from decimal import Decimal

# Load environment variables
load_dotenv()

app = Flask(__name__)
bcrypt = Bcrypt(app)

# MongoDB connection
client = MongoClient(getenv('MONGODB_URI'))
app.config['SECRET_KEY'] = '\xb0\t\xce\x90\x1a\xb7\xfb\x1e\xdb\xb5\xdd\xc0'

db = client.get_database('FIFA_DB')

def decimal_default(obj):
    """Convert Decimal objects to floats."""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

from admin.routes import adminRoutes
app.register_blueprint(adminRoutes, url_prefix="/admin")

@app.route('/')
def home():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('q', '')

    per_page = 10
    offset = (page - 1) * per_page

    # Most FIFA World Cup Wins
    wc_wins = list(db.teams.aggregate([
        {
            "$lookup": {                            # join
                "from": "tournaments",              # join which table
                "localField": "team_id",            # by the team's id
                "foreignField": "winning_team_id",  # tournament's team's id
                "as": "wins"                        # as the new name 
            }
        },
        {
            "$addFields": {                         # new column
                "world_cup_wins": {"$size": "$wins"}# name world_cup_wins
            }
        },
        {"$sort": {"world_cup_wins": -1}},
        {"$skip": offset},
        {"$limit": per_page}
    ]))

    # Top Scorers
    most_goals = list(db.players.aggregate([
        {"$lookup": {"from": "player_performance", "localField": "player_id", "foreignField": "player_id", "as": "performance"}},
        {"$addFields": {"total_goals": {"$sum": "$performance.goals_scored"}}},
        {"$sort": {"total_goals": -1}},
        {"$skip": offset},
        {"$limit": per_page}
    ]))

    # Recent Matches
    recent_matches = list(db.matches.aggregate([
        {
            "$lookup": {
                "from": "teams",
                "localField": "home_team_id",
                "foreignField": "team_id",
                "as": "home_team"
            }
        },
        {
            "$lookup": {
                "from": "teams",
                "localField": "away_team_id",
                "foreignField": "team_id",
                "as": "away_team"
            }
        },
        {"$unwind": "$home_team"},
        {"$unwind": "$away_team"},
        {
            "$project": {
                "match_id": 1,
                "home_team_name": "$home_team.team_name",
                "away_team_name": "$away_team.team_name",
                "home_team_goal": 1,
                "away_team_goal": 1,
                "round": 1
            }
        },
        {"$sort": {"match_id": -1}},
        {"$skip": offset},
        {"$limit": per_page}
    ]))

    # Players with Most Yellow and Red Cards
    most_cards = list(db.players.aggregate([
        {"$lookup": {"from": "player_performance", "localField": "player_id", "foreignField": "player_id", "as": "performance"}},
        {"$addFields": {
            "total_yellow": {"$sum": "$performance.yellow_cards"},
            "total_red": {"$sum": "$performance.red_cards"}
        }},
        {"$sort": {"total_yellow": -1, "total_red": -1}},
        {"$skip": offset},
        {"$limit": per_page}
    ]))

    return render_template(
        'index.html',
        wc_wins=wc_wins,
        most_goals=most_goals,
        recent_matches=recent_matches,
        most_cards=most_cards,
        page=page,
        total_pages=ceil(len(wc_wins) / per_page),
        search_query=search_query
    )




@app.route('/teams')
def teams():
    search_query = request.args.get('q', '')
    per_page = 20
    page = request.args.get('page', 1, type=int)
    offset = (page - 1) * per_page

    # Filter based on search query
    filter_query = {'team_name': {'$regex': search_query, '$options': 'i'}} if search_query else {}

    # Pagination
    teams = list(db.teams.find(filter_query).skip(offset).limit(per_page))
    total_teams = db.teams.count_documents(filter_query)
    total_pages = ceil(total_teams / per_page)

    # Calculate the start and end page for pagination
    visible_pages = 5  # Number of pages to display in pagination controls
    start_page = max(1, page - visible_pages // 2)
    end_page = min(total_pages, start_page + visible_pages - 1)

    # Adjust start_page if end_page is less than visible_pages
    if end_page - start_page < visible_pages and start_page > 1:
        start_page = max(1, end_page - visible_pages + 1)

    return render_template(
        'teams.html',
        teams=teams,
        page=page,
        total_pages=total_pages,
        start_page=start_page,
        end_page=end_page,
        search_query=search_query
    )



@app.route('/players')
def players():
    search_query = request.args.get('q', '')
    per_page = 20
    page = request.args.get('page', 1, type=int)
    offset = (page - 1) * per_page

    # Filter based on search query
    filter_query = {'player_name': {'$regex': search_query, '$options': 'i'}} if search_query else {}

    # Retrieve players with pagination
    players = list(db.players.find(filter_query).skip(offset).limit(per_page))

    # Process players data for display
    for player in players:
        player['team_name'] = db.teams.find_one({'team_id': player['team_id']}).get('team_name', 'Unknown') if player.get('team_id') else 'Unknown'

    total_players = db.players.count_documents(filter_query)
    total_pages = ceil(total_players / per_page)

    # Calculate start and end page for pagination
    visible_pages = 5  # Number of pages to display in pagination controls
    start_page = max(1, page - visible_pages // 2)
    end_page = min(total_pages, start_page + visible_pages - 1)

    # Adjust start_page if end_page is less than visible_pages
    if end_page - start_page < visible_pages and start_page > 1:
        start_page = max(1, end_page - visible_pages + 1)

    return render_template(
        'players.html',
        players=players,
        page=page,
        total_pages=total_pages,
        start_page=start_page,
        end_page=end_page,
        search_query=search_query
    )


@app.route('/matches')
def matches():
    search_query = request.args.get('q', '')
    per_page = 20
    page = request.args.get('page', 1, type=int)
    offset = (page - 1) * per_page

    # Define the filter for search functionality
    filter_query = {}
    if search_query:
        filter_query['$or'] = [
            {'home_team.team_name': {'$regex': search_query, '$options': 'i'}},
            {'away_team.team_name': {'$regex': search_query, '$options': 'i'}}
        ]

    # Perform the aggregation to retrieve match data with home, away teams, and venue
    try:
        matches = list(db.matches.aggregate([
            {'$lookup': {
                'from': 'teams',
                'localField': 'home_team_id',
                'foreignField': 'team_id',
                'as': 'home_team'
            }},
            {'$lookup': {
                'from': 'teams',
                'localField': 'away_team_id',
                'foreignField': 'team_id',
                'as': 'away_team'
            }},
            {'$lookup': {
                'from': 'stadiums',  # Collection for venue information
                'localField': 'stadium_id',  # The field in matches referring to stadiums
                'foreignField': 'stadium_id',  # Field to match in the stadiums collection
                'as': 'venue_info'
            }},
            {'$unwind': '$home_team'},
            {'$unwind': '$away_team'},
            {'$unwind': {'path': '$venue_info', 'preserveNullAndEmptyArrays': True}},  # Allow for missing venues
            {'$match': filter_query},
            {'$sort': {'match_id': -1}},
            {'$skip': offset},
            {'$limit': per_page}
        ]))

        # Process matches to set venue and score fields correctly
        for match in matches:
            match['home_team_name'] = match['home_team'].get('team_name', 'Unknown')
            match['away_team_name'] = match['away_team'].get('team_name', 'Unknown')
            match['venue'] = match.get('venue_info', {}).get('stadium_name', 'Unknown')  # Use stadium_name from venue_info
            match['home_team_goal'] = match.get('home_team_goal', 'N/A')
            match['away_team_goal'] = match.get('away_team_goal', 'N/A')

        # Debugging: print the processed matches to check the data
        print("Processed Matches:", matches)

        # Count documents based on filter query
        total_matches = db.matches.count_documents(filter_query)
        total_pages = ceil(total_matches / per_page)

        # Calculate start and end page for pagination controls
        visible_pages = 5
        start_page = max(1, page - visible_pages // 2)
        end_page = min(total_pages, start_page + visible_pages - 1)
        if end_page - start_page < visible_pages and start_page > 1:
            start_page = max(1, end_page - visible_pages + 1)

        return render_template(
            'matches.html',
            matches=matches,
            page=page,
            total_pages=total_pages,
            start_page=start_page,
            end_page=end_page,
            search_query=search_query
        )

    except Exception as e:
        print("Error retrieving matches:", e)
        return render_template('matches.html', matches=[], page=1, total_pages=1, start_page=1, end_page=1)

@app.route('/ranking')
def ranking():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('q', '')

    per_page = 10
    offset = (page - 1) * per_page

    # Calculate world_cup_wins and matches_won
    teams = list(db.teams.aggregate([
        {
            "$lookup": {
                "from": "tournaments",
                "localField": "team_id",
                "foreignField": "winning_team_id",
                "as": "wins"
            }
        },
        {
            "$addFields": {
                "world_cup_wins": {"$size": "$wins"}
            }
        },
        {
            "$lookup": {
                "from": "matches",
                "let": {"team_id": "$team_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$or": [
                        {"$and": [{"$eq": ["$home_team_id", "$$team_id"]}, {"$gt": ["$home_team_goal", "$away_team_goal"]}]},
                        {"$and": [{"$eq": ["$away_team_id", "$$team_id"]}, {"$gt": ["$away_team_goal", "$home_team_goal"]}]}
                    ]}}},
                    {"$count": "wins"}
                ],
                "as": "matches_won_count"
            }
        },
        {
            "$addFields": {
                "matches_won": {"$ifNull": [{"$arrayElemAt": ["$matches_won_count.wins", 0]}, 0]}
            }
        },
        {"$sort": {"world_cup_wins": -1, "matches_won": -1}},  # Sort by world cup wins and then matches won
        {"$skip": offset},
        {"$limit": per_page}
    ]))

    # Filter based on search query
    if search_query:
        teams = [team for team in teams if search_query.lower() in team["team_name"].lower()]

    total_teams = db.teams.count_documents({})
    total_pages = ceil(total_teams / per_page)

    # Calculate the start and end page for pagination
    visible_pages = 5  # Number of pages to display in pagination controls
    start_page = max(1, page - visible_pages // 2)
    end_page = min(total_pages, start_page + visible_pages - 1)

    # Adjust start_page if end_page is less than visible_pages
    if end_page - start_page < visible_pages and start_page > 1:
        start_page = max(1, end_page - visible_pages + 1)

    return render_template(
        'ranking.html',
        teams=teams,
        page=page,
        total_pages=total_pages,
        start_page=start_page,
        end_page=end_page,
        per_page=per_page,
        search_query=search_query
    )





if __name__ == '__main__':
    app.run(debug=True)
