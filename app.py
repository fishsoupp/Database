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
from bson import ObjectId


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
                "from": "tournaments",              # join tournaments collection
                "localField": "_id",                # match by team's _id
                "foreignField": "winning_team._id", # tournament's winning team _id
                "as": "wins"                        # alias for joined data
            }
        },
        {
            "$addFields": {                         # calculate total wins
                "world_cup_wins": {"$size": "$wins"}
            }
        },
        {"$sort": {"world_cup_wins": -1}},          # sort by wins descending
        {"$skip": offset},                          # pagination offset
        {"$limit": per_page}                        # pagination limit
    ]))

    # Top Scorers
    most_goals = list(db.players.aggregate([
        {
            "$lookup": {                            # join with goals collection
                "from": "goals",
                "localField": "_id",                # player's _id
                "foreignField": "player_id",        # goal's player_id
                "as": "goal_data"                   # alias for joined data
            }
        },
        {
            "$addFields": {                         # calculate total goals
                "total_goals": {"$size": "$goal_data"}
            }
        },
        {"$sort": {"total_goals": -1}},             # sort by goals descending
        {"$skip": offset},                          # pagination offset
        {"$limit": per_page}                        # pagination limit
    ]))

    # Recent Matches
    recent_matches = list(db.matches.aggregate([
        {
            "$lookup": {
                "from": "teams",
                "localField": "home_team._id",      # match by home team _id
                "foreignField": "_id",
                "as": "home_team"
            }
        },
        {
            "$lookup": {
                "from": "teams",
                "localField": "away_team._id",      # match by away team _id
                "foreignField": "_id",
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
        {"$sort": {"_id": -1}},                     # sort by match ID descending
        {"$skip": offset},                          # pagination offset
        {"$limit": per_page}                        # pagination limit
    ]))

    # Players with Most Yellow and Red Cards
    most_cards = list(db.players.aggregate([
        {
            "$lookup": {                            # join with goals collection
                "from": "goals",
                "localField": "_id",                # match by player's _id
                "foreignField": "player_id",
                "as": "goal_data"
            }
        },
        {
            "$addFields": {                         # calculate yellow and red cards
                "total_yellow": {"$size": {"$filter": {
                    "input": "$goal_data",
                    "as": "goal",
                    "cond": {"$eq": ["$$goal.is_penalty", 1]}  # Assuming is_penalty == yellow card
                }}},
                "total_red": {"$size": {"$filter": {
                    "input": "$goal_data",
                    "as": "goal",
                    "cond": {"$eq": ["$$goal.is_own_goal", 1]}  # Assuming is_own_goal == red card
                }}}
            }
        },
        {
            "$addFields": {                         # calculate weighted score
                "weighted_score": {"$add": [
                    {"$multiply": ["$total_yellow", 1]},  # Yellow cards have a weight of 1
                    {"$multiply": ["$total_red", 3]}     # Red cards have a weight of 3
                ]}
            }
        },
        {"$sort": {"weighted_score": -1}},          # sort by weighted score
        {"$skip": offset},                          # pagination offset
        {"$limit": per_page}                        # pagination limit
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
    search_query = request.args.get('q', '')  # Search query for team name or continent
    min_matches = request.args.get('min_matches', type=int)  # Minimum matches for filter
    max_matches = request.args.get('max_matches', type=int)  # Maximum matches for filter
    per_page = 20  # Number of items per page
    page = request.args.get('page', 1, type=int)  # Current page number
    offset = (page - 1) * per_page  # Pagination offset

    # Step 1: Initialize filter query
    filter_query = {}

    # Step 2: Apply search filters (team name or continent)
    if search_query:
        filter_query['$or'] = [
            {'team_name': {'$regex': search_query, '$options': 'i'}},
            {'continent': {'$regex': search_query, '$options': 'i'}}
        ]

    # Step 3: Perform aggregation for matches played
    match_filter = []
    if min_matches is not None:
        match_filter.append({'total_matches': {'$gte': min_matches}})
    if max_matches is not None:
        match_filter.append({'total_matches': {'$lte': max_matches}})
    
    # Step 4: Aggregation pipeline
    pipeline = [
        {
            '$lookup': {
                'from': 'matches',  # Link to matches collection
                'localField': '_id',  # Match on team ID
                'foreignField': 'home_team._id',  # Match as home team
                'as': 'home_matches'
            }
        },
        {
            '$lookup': {
                'from': 'matches',  # Link to matches collection
                'localField': '_id',  # Match on team ID
                'foreignField': 'away_team._id',  # Match as away team
                'as': 'away_matches'
            }
        },
        {
            '$addFields': {  # Calculate total matches played
                'total_matches': {'$add': [{'$size': '$home_matches'}, {'$size': '$away_matches'}]}
            }
        },
        {
            '$match': {'$and': match_filter} if match_filter else {}  # Apply match filters
        },
        {'$skip': offset},  # Pagination offset
        {'$limit': per_page}  # Pagination limit
    ]

    # Step 5: Execute aggregation query
    teams = list(db.teams.aggregate(pipeline))

    # Step 6: Calculate total teams for pagination
    total_teams = db.teams.count_documents(filter_query)
    total_pages = ceil(total_teams / per_page)

    # Step 7: Calculate pagination ranges
    visible_pages = 5
    start_page = max(1, page - visible_pages // 2)
    end_page = min(total_pages, start_page + visible_pages - 1)
    if end_page - start_page < visible_pages and start_page > 1:
        start_page = max(1, end_page - visible_pages + 1)

    # Step 8: Render the template
    return render_template(
        'teams.html',
        teams=teams,
        page=page,
        total_pages=total_pages,
        start_page=start_page,
        end_page=end_page,
        search_query=search_query,
        min_matches=min_matches,
        max_matches=max_matches
    )




@app.route('/players')
def players():
    search_query = request.args.get('q', '')  # Search query for player name
    team_id = request.args.get('team_id')  # Selected team ID for filtering
    position = request.args.get('position')  # Player position filter
    per_page = 20  # Number of items per page
    page = request.args.get('page', 1, type=int)  # Current page number
    offset = (page - 1) * per_page  # Pagination offset

    # Create filter query
    filter_query = {}

    # Search by player name
    if search_query:
        filter_query['player_name'] = {'$regex': search_query, '$options': 'i'}

    # Filter by team ID
    if team_id:
        filter_query['team._id'] = ObjectId(team_id)  # Convert to ObjectId for matching

    # Filter by position
    if position:
        filter_query['position'] = position

    # Query the database with filters and pagination
    players = list(db.players.find(filter_query).skip(offset).limit(per_page))

    # Add team names for display
    for player in players:
        player['team_name'] = player['team']['team_name'] if player.get('team') else 'Unknown'

    # Query all teams for the filter dropdown
    teams = list(db.teams.find())

    # Calculate total players matching the filter
    total_players = db.players.count_documents(filter_query)
    total_pages = ceil(total_players / per_page)

    # Calculate the range of visible pages for pagination controls
    visible_pages = 5
    start_page = max(1, page - visible_pages // 2)
    end_page = min(total_pages, start_page + visible_pages - 1)
    if end_page - start_page < visible_pages and start_page > 1:
        start_page = max(1, end_page - visible_pages + 1)

    # Render the `players.html` template with the required context
    return render_template(
        'players.html',
        players=players,
        teams=teams,  # Pass the list of teams to the template
        page=page,
        total_pages=total_pages,
        start_page=start_page,
        end_page=end_page,
        search_query=search_query,
        team_id=team_id,
        position=position,
        per_page=per_page
    )









@app.route('/matches')
def matches():
    search_query = request.args.get('q', '')  # Search query for team or venue
    team_id = request.args.get('team_id')  # Filter by team ID
    round = request.args.get('round')  # Filter by round
    venue = request.args.get('venue')  # Filter by venue
    per_page = 20  # Number of items per page
    page = request.args.get('page', 1, type=int)  # Current page number
    offset = (page - 1) * per_page  # Pagination offset

    # Create filter query
    filter_query = {}

    # Search by team name or venue
    if search_query:
        filter_query['$or'] = [
            {'home_team.team_name': {'$regex': search_query, '$options': 'i'}},
            {'away_team.team_name': {'$regex': search_query, '$options': 'i'}},
            {'stadium.stadium_name': {'$regex': search_query, '$options': 'i'}}
        ]

    # Filter by team ID
    if team_id:
        filter_query['$or'] = [
            {'home_team._id': ObjectId(team_id)},
            {'away_team._id': ObjectId(team_id)}
        ]

    # Filter by round
    if round:
        filter_query['round'] = round

    # Filter by venue
    if venue:
        filter_query['stadium.stadium_name'] = {'$regex': venue, '$options': 'i'}

    # Query matches with pagination
    matches = list(db.matches.aggregate([
        {
            '$lookup': {
                'from': 'teams',
                'localField': 'home_team._id',
                'foreignField': '_id',
                'as': 'home_team'
            }
        },
        {
            '$lookup': {
                'from': 'teams',
                'localField': 'away_team._id',
                'foreignField': '_id',
                'as': 'away_team'
            }
        },
        {
            '$lookup': {
                'from': 'stadiums',
                'localField': 'stadium._id',
                'foreignField': '_id',
                'as': 'venue_info'
            }
        },
        {'$unwind': '$home_team'},
        {'$unwind': '$away_team'},
        {'$unwind': '$venue_info'},
        {'$match': filter_query},
        {'$sort': {'_id': -1}},
        {'$skip': offset},
        {'$limit': per_page}
    ]))

    # Add team and venue names for display
    for match in matches:
        match['home_team_name'] = match['home_team']['team_name']
        match['away_team_name'] = match['away_team']['team_name']
        match['venue'] = match['venue_info']['stadium_name']

    # Get list of teams for filter dropdown
    teams = list(db.teams.find())

    # Calculate total matches for pagination
    total_matches = db.matches.count_documents(filter_query)
    total_pages = ceil(total_matches / per_page)

    # Calculate visible pages for pagination
    visible_pages = 5
    start_page = max(1, page - visible_pages // 2)
    end_page = min(total_pages, start_page + visible_pages - 1)

    # Render template
    return render_template(
        'matches.html',
        matches=matches,
        teams=teams,  # Pass list of teams for filter
        page=page,
        total_pages=total_pages,
        start_page=start_page,
        end_page=end_page,
        search_query=search_query,
        team_id=team_id,
        round=round,
        venue=venue
    )




@app.route('/ranking')
def ranking():
    page = request.args.get('page', 1, type=int)  # Current page number
    search_query = request.args.get('q', '')     # Search query
    per_page = 10                                # Number of items per page
    offset = (page - 1) * per_page               # Calculate offset

    # Calculate world_cup_wins and matches_won
    teams = list(db.teams.aggregate([
        {
            "$lookup": {
                "from": "tournaments",            # Join with tournaments collection
                "localField": "_id",              # Match by team _id
                "foreignField": "winning_team._id", # Tournament's winning_team._id
                "as": "wins"
            }
        },
        {
            "$addFields": {
                "world_cup_wins": {"$size": "$wins"}  # Count the number of wins
            }
        },
        {
            "$lookup": {
                "from": "matches",                # Join with matches collection
                "let": {"team_id": "$_id"},       # Pass team _id as a variable
                "pipeline": [
                    {"$match": {"$expr": {"$or": [
                        {"$and": [{"$eq": ["$home_team._id", "$$team_id"]}, {"$gt": ["$home_team_goal", "$away_team_goal"]}]},
                        {"$and": [{"$eq": ["$away_team._id", "$$team_id"]}, {"$gt": ["$away_team_goal", "$home_team_goal"]}]}
                    ]}}},                         # Match wins for home or away team
                    {"$count": "wins"}            # Count wins
                ],
                "as": "matches_won_count"
            }
        },
        {
            "$addFields": {
                "matches_won": {"$ifNull": [{"$arrayElemAt": ["$matches_won_count.wins", 0]}, 0]}  # Get matches won count
            }
        },
        {"$sort": {"world_cup_wins": -1, "matches_won": -1}},  # Sort by world cup wins and matches won
        {"$skip": offset},                                      # Pagination offset
        {"$limit": per_page}                                    # Pagination limit
    ]))

    # Filter based on search query
    if search_query:
        teams = [team for team in teams if search_query.lower() in team["team_name"].lower()]

    # Calculate total teams for pagination
    total_teams = db.teams.count_documents({})
    total_pages = ceil(total_teams / per_page)

    # Calculate the start and end page for pagination controls
    visible_pages = 5  # Number of pages to display in pagination controls
    start_page = max(1, page - visible_pages // 2)
    end_page = min(total_pages, start_page + visible_pages - 1)

    # Adjust start_page if end_page is less than visible_pages
    if end_page - start_page < visible_pages and start_page > 1:
        start_page = max(1, end_page - visible_pages + 1)

    # Render the ranking page
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)