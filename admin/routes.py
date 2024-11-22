from flask import Blueprint, render_template, redirect, url_for, flash, session, request, current_app
from sqlalchemy.sql import text
from app import db, bcrypt  # Import db and bcrypt from app.py
from pymongo import MongoClient
from .forms import LoginForm
from datetime import date
from bson.objectid import ObjectId

adminRoutes = Blueprint("adminRoutes", __name__, template_folder="templates")

# Admin Landing Page
@adminRoutes.route("/landing")
def adminLanding():
    if not session.get('admin_logged_in'):
        return redirect(url_for('adminRoutes.login'))
    
    # Get the latest tournament
    latest_tournament = db.tournaments.find_one({}, sort=[("year", -1)])
    if not latest_tournament:
        flash("No tournaments found!", "danger")
        return render_template("adminLanding.html", teams=[], goals=[])

    latest_tournament_id = latest_tournament["tournament_id"]

    # Aggregation pipeline to calculate total goals for teams
    result = db.matches.aggregate([
        {
            "$match": {
                "tournament_id": latest_tournament_id
            }
        },
        {
            "$facet": {
                "home_team_goals": [
                    {
                        "$group": {
                            "_id": "$home_team.team_name",  
                            "total_goals": {"$sum": "$home_team_goal"}  # Sum goals from home team
                        }
                    }
                ],
                "away_team_goals": [
                    {
                        "$group": {
                            "_id": "$away_team.team_name", 
                            "total_goals": {"$sum": "$away_team_goal"}  # Sum goals from away team
                        }
                    }
                ]
            }
        },
        {
            "$project": {
                "all_teams": {
                    "$concatArrays": ["$home_team_goals", "$away_team_goals"]  # Combine home and away results
                }
            }
        },
        {
            "$unwind": "$all_teams"
        },
        {
            "$group": {
                "_id": "$all_teams._id", 
                "total_goals": {"$sum": "$all_teams.total_goals"}  # Sum goals for each team
            }
        },
        {
            "$sort": {"total_goals": -1}  # Sort by total goals in descending order
        }
    ])

    # Convert the result to a list and prepare data for the chart
    result_list = list(result)

    teams = [row["_id"] for row in result_list]
    goals = [row["total_goals"] for row in result_list]

    return render_template("adminLanding.html", teams=teams, goals=goals)

# Admin Update Profile
@adminRoutes.route('/update_profile', methods=['POST'])
def update_profile():
    if not session.get('admin_logged_in'):
        return redirect(url_for('adminRoutes.login')) 
    
    admin_name = request.form.get('admin_name')
    email = request.form.get('email')
    admin_id = session.get('admin_id')
    
    if not admin_id:
        flash('Session expired. Please log in again.', 'danger')
        return redirect(url_for('adminRoutes.login'))

    try:
        db.admin.update_one(
            {"_id": ObjectId(admin_id)},
            {"$set": {"admin_name": admin_name, "email": email}}
        )
        session['admin_name'] = admin_name
        flash('Profile updated successfully!', 'success')
    except Exception as e:
        flash(f'Failed to update profile: {str(e)}', 'danger')
    
    return redirect(url_for('adminRoutes.adminLanding'))

# Admin Login
@adminRoutes.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        admin = db.admin.find_one({"email": form.email.data})

        if admin and bcrypt.check_password_hash(admin['password'], form.password.data):
            session['admin_logged_in'] = True
            session['admin_name'] = admin['admin_name']
            session['admin_id'] = str(admin['_id'])
            flash('Logged in successfully!', 'success')
            return redirect(url_for('adminRoutes.adminLanding'))
        else:
            flash('Invalid credentials. Please try again.', 'danger')

    return render_template("adminLogin.html", form=form)

# Admin Logout 
@adminRoutes.route("/logout")
def logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_id', None)
    session.pop('admin_name', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('adminRoutes.login'))

##### Players Management Route ######
# Players 
@adminRoutes.route("/players", defaults={'page': 1})
@adminRoutes.route('/players/page/<int:page>')
def players_management(page):
    per_page = 30
    offset = (page - 1) * per_page

    teams = list(db.teams.find({}, {"team_id": 1, "team_name": 1}))
    
    # Fetch players with embedded team details
    players = list(db.players.find(
        {},  
        {
            "player_id": 1,
            "player_name": 1,
            "position": 1,
            "date_of_birth": 1,
            "caps": 1,
            "team.team_id": 1,  
            "team.team_name": 1 
        }
    ).skip(offset).limit(per_page))

    total_players = db.players.count_documents({})
    total_pages = (total_players // per_page) + (1 if total_players % per_page > 0 else 0)

    current_date = date.today().isoformat()

    visible_pages = 5
    start_page = max(1, page - visible_pages // 2)
    end_page = min(total_pages, start_page + visible_pages - 1)

    return render_template("adminPlayers.html", players=players, teams=teams, page=page, total_pages=total_pages, start_page=start_page, end_page=end_page, current_date=current_date)

# Add Players
@adminRoutes.route('/players/add', methods=['POST'])
def add_player():
    if request.method == 'POST':

        # Get the latest player_id and increment it by 1
        latest_player = db.players.find_one(sort=[("player_id", -1)]) 
        new_player_id = latest_player["player_id"] + 1 if latest_player else 1  
        
         # Fetch the selected team details
        team_id = int(request.form.get('team'))
        team_details = db.teams.find_one({"team_id": team_id})  

        # Prepare the new player data
        player = {
            "player_id": new_player_id,  
            "player_name": request.form.get('playerName'),
            "team": { 
                "team_id": team_details["team_id"],
                "team_name": team_details["team_name"],
                "continent": team_details["continent"],  
                "fifa_code": team_details["fifa_code"]      
            },
            "position": request.form.get('position'),
            "date_of_birth": request.form.get('date_of_birth'),
            "caps": int(request.form.get('caps'))
        }

        try:
            db.players.insert_one(player)
            flash('Player added successfully!', 'success')
        except Exception as e:
            flash(f"Error adding player: {str(e)}", 'danger')

        return redirect(url_for('adminRoutes.players_management'))
    
    return redirect(url_for('adminRoutes.players_management'))

# Update Player
@adminRoutes.route('/players/update/<string:player_id>', methods=['POST'])
def update_player(player_id):
    if request.method == 'POST':

        # Get the team details from the teams collection
        team_id = int(request.form.get('team'))
        team = db.teams.find_one({"team_id": team_id}, {"team_id": 1, "team_name": 1, "fifa_code": 1, "continent": 1})

        if not team:
            flash(f"Team with ID {team_id} not found.", 'danger')
            return redirect(url_for('adminRoutes.players_management'))

        # Prepare the player data with embedded team details
        player_data = {
            "player_name": request.form.get('playerName'),
            "team": {
                "team_id": team["team_id"],
                "team_name": team["team_name"],
                "fifa_code": team["fifa_code"],
                "continent": team["continent"]
            },
            "position": request.form.get('position'),
            "date_of_birth": request.form.get('dateOfBirth'),
            "caps": int(request.form.get('caps'))
        }

        try:
            db.players.update_one({"player_id": int(player_id)}, {"$set": player_data})
            flash(f"Player updated successfully!", 'success')
        except Exception as e:
            flash(f"Error updating player: {str(e)}", 'danger')

    return redirect(url_for('adminRoutes.players_management'))

# Delete Player
@adminRoutes.route('/players/delete/<string:player_id>', methods=['POST'])
def delete_player(player_id):
    try:
        db.players.delete_one({"player_id": int(player_id)})
        flash(f"Player deleted successfully!", 'success')
    except Exception as e:
        flash(f"Error deleting player: {str(e)}", 'danger')

    return redirect(url_for('adminRoutes.players_management'))

##### Matches Management #####
# Matches
@adminRoutes.route("/matches", defaults={'page': 1})
@adminRoutes.route('/matches/page/<int:page>')
def matches_management(page):
    per_page = 30
    offset = (page - 1) * per_page

    # Fetch matches directly with embedded team details
    matches_cursor = db.matches.aggregate([
        {
            "$lookup": {
                "from": "tournaments",
                "localField": "tournament_id",
                "foreignField": "tournament_id",
                "as": "tournament_info"
            }
        },
        {"$unwind": "$tournament_info"},  

        # Project the required fields
        {
            "$project": {
                "_id": 0,  # Exclude the default _id field
                "match_id": 1,
                "tournament_id": "$tournament_info.tournament_id",
                "tournament_year": "$tournament_info.year",  
                "home_team": 1,  
                "away_team": 1, 
                "home_team_goal": 1,
                "away_team_goal": 1,
                "round": 1,
                "referee": 1,
                "stadium": 1
            }
        },
        {"$skip": offset},
        {"$limit": per_page}
    ])

    matches = list(matches_cursor)  # Convert cursor to a list

    # These are the required list for dropdowns
    teams = list(db.teams.find({}, {"team_id": 1, "team_name": 1}))
    tournaments = list(db.tournaments.find({}, {"tournament_id": 1, "year": 1}))
    stadiums = list(db.stadiums.find({}, {"stadium_id": 1, "stadium_name": 1}))
    referees = list(db.referees.find({}, {"referee_id": 1, "referee_name": 1}))

    total_matches = db.matches.count_documents({})
    total_pages = (total_matches // per_page) + (1 if total_matches % per_page > 0 else 0)

    visible_pages = 5
    start_page = max(1, page - visible_pages // 2)
    end_page = min(total_pages, start_page + visible_pages - 1)

    return render_template("adminMatches.html", matches=matches, teams=teams,stadiums=stadiums, referees=referees, tournaments=tournaments, page=page, total_pages=total_pages, start_page=start_page, end_page=end_page)

# Add Match
@adminRoutes.route('/matches/add', methods=['POST'])
def add_match():
    if request.method == 'POST':

        # Get the latest player_id and increment it by 1
        latest_match = db.matches.find_one(sort=[("match_id", -1)]) 
        new_match_id = latest_match["match_id"] + 1 if latest_match else 1  

        # Fetch referee details
        referee_id = int(request.form.get('referee'))
        referee = db.referees.find_one({"referee_id": referee_id}, {"_id": 0, "referee_id": 1, "referee_name": 1})
        if not referee:
            flash('Referee not found.', 'danger')
            return redirect(url_for('adminRoutes.matches_management'))

        # Fetch stadium details
        stadium_id = int(request.form.get('stadium'))
        stadium = db.stadiums.find_one({"stadium_id": stadium_id}, {"_id": 0, "stadium_id": 1, "stadium_name": 1, "city": 1})
        if not stadium:
            flash('Stadium not found.', 'danger')
            return redirect(url_for('adminRoutes.matches_management'))

        # Fetch home team details
        home_team_id = int(request.form.get('homeTeam'))
        home_team = db.teams.find_one(
            {"team_id": home_team_id},
            {"_id": 0, "team_id": 1, "team_name": 1, "continent": 1, "fifa_code": 1}
        )
        if not home_team:
            flash('Home team not found.', 'danger')
            return redirect(url_for('adminRoutes.matches_management'))

        # Fetch away team details
        away_team_id = int(request.form.get('awayTeam'))
        away_team = db.teams.find_one(
            {"team_id": away_team_id},
            {"_id": 0, "team_id": 1, "team_name": 1, "continent": 1, "fifa_code": 1}
        )
        if not away_team:
            flash('Away team not found.', 'danger')
            return redirect(url_for('adminRoutes.matches_management'))

        # Prepare the match document
        match = {
            "match_id": new_match_id,
            "tournament_id": int(request.form.get('tournament')),
            "home_team": home_team, 
            "away_team": away_team, 
            "home_team_goal": int(request.form.get('home_team_goals')),
            "away_team_goal": int(request.form.get('away_team_goals')),
            "round": request.form.get('round'),
            "referee": referee,     
            "stadium": stadium      
        }

        try:
            db.matches.insert_one(match)
            flash('Match added successfully!', 'success')
        except Exception as e:
            flash(f"Error adding match: {str(e)}", 'danger')

        return redirect(url_for('adminRoutes.matches_management'))

    return redirect(url_for('adminRoutes.matches_management'))

# Update Match
@adminRoutes.route('/matches/update/<string:match_id>', methods=['POST'])
def update_match(match_id):
    if request.method == 'POST':

        # Fetch referee details
        referee_id = int(request.form.get('referee'))
        referee = db.referees.find_one({"referee_id": referee_id}, {"_id": 0, "referee_id": 1, "referee_name": 1})
        if not referee:
            flash('Referee not found.', 'danger')
            return redirect(url_for('adminRoutes.matches_management'))

        # Fetch stadium details
        stadium_id = int(request.form.get('stadium'))
        stadium = db.stadiums.find_one({"stadium_id": stadium_id}, {"_id": 0, "stadium_id": 1, "stadium_name": 1, "city": 1})
        if not stadium:
            flash('Stadium not found.', 'danger')
            return redirect(url_for('adminRoutes.matches_management'))

        # Fetch home team details
        home_team_id = int(request.form.get('homeTeam'))
        home_team = db.teams.find_one(
            {"team_id": home_team_id},
            {"_id": 0, "team_id": 1, "team_name": 1, "continent": 1, "fifa_code": 1}
        )
        if not home_team:
            flash('Home team not found.', 'danger')
            return redirect(url_for('adminRoutes.matches_management'))

        # Fetch away team details
        away_team_id = int(request.form.get('awayTeam'))
        away_team = db.teams.find_one(
            {"team_id": away_team_id},
            {"_id": 0, "team_id": 1, "team_name": 1, "continent": 1, "fifa_code": 1}
        )
        if not away_team:
            flash('Away team not found.', 'danger')
            return redirect(url_for('adminRoutes.matches_management'))

        # Prepare the match data with embedded details
        match_data = {
            "tournament_id": int(request.form.get('tournament')),
            "home_team": home_team,
            "away_team": away_team,  
            "home_team_goal": int(request.form.get('home_team_goals')),
            "away_team_goal": int(request.form.get('away_team_goals')),
            "round": request.form.get('round'),
            "referee": referee,    
            "stadium": stadium     
        }

        try:
            db.matches.update_one({"match_id": int(match_id)}, {"$set": match_data})
            flash(f"Match updated successfully!", 'success')
        except Exception as e:
            flash(f"Error updating match: {str(e)}", 'danger')

    return redirect(url_for('adminRoutes.matches_management'))

# Delete Match
@adminRoutes.route('/matches/delete/<string:match_id>', methods=['POST'])
def delete_match(match_id):
    try:
        db.matches.delete_one({"match_id": int(match_id)})
        flash(f"Match deleted successfully!", 'success')
    except Exception as e:
        flash(f"Error deleting match: {str(e)}", 'danger')

    return redirect(url_for('adminRoutes.matches_management'))

##### Goals Management #####
# Goals
@adminRoutes.route("/goals", defaults={'page': 1})
@adminRoutes.route('/goals/page/<int:page>')
def goals_management(page):
    per_page = 30
    offset = (page - 1) * per_page

    # Aggregation pipeline to join players and matches with embedded team details
    goals_cursor = db.goals.aggregate([
        {
            "$lookup": {
                "from": "players",
                "localField": "player_id",
                "foreignField": "player_id",
                "as": "player_info"
            }
        },
        {
            "$lookup": {
                "from": "matches",
                "localField": "match_id",
                "foreignField": "match_id",
                "as": "match_info"
            }
        },
        {"$unwind": "$player_info"}, 
        {"$unwind": "$match_info"},   

        # Project the required fields
        {
            "$project": {
                "_id": 0,  # Exclude MongoDB's default _id
                "goal_id": 1,
                "minute_scored": 1,
                "is_penalty": 1,
                "is_own_goal": 1,
                "player": "$player_info", 
                "match": "$match_info"   
            }
        },
        {"$skip": offset},
        {"$limit": per_page}
    ])

    goals = list(goals_cursor)
    players = list(db.players.find({}, {"player_id": 1, "player_name": 1}))
    matches = list(db.matches.find({}, {"match_id": 1, "home_team.team_name": 1, "away_team.team_name": 1}))

    total_goals = db.goals.count_documents({})
    total_pages = (total_goals // per_page) + (1 if total_goals % per_page > 0 else 0)

    visible_pages = 5
    start_page = max(1, page - visible_pages // 2)
    end_page = min(total_pages, start_page + visible_pages - 1)

    return render_template("adminGoals.html", goals=goals, players=players, matches=matches, page=page, total_pages=total_pages, start_page=start_page, end_page=end_page)

# Add Goal
@adminRoutes.route('/goals/add', methods=['POST'])
def add_goal():
    if request.method == 'POST':

        # Get the latest goal_id and increment it by 1
        latest_goal = db.goals.find_one(sort=[("goal_id", -1)]) 
        new_goal_id = latest_goal["goal_id"] + 1 if latest_goal else 1  

        # Fetch match details
        match_id = int(request.form.get('match'))
        match = db.matches.find_one(
            {"match_id": match_id},
            {"_id": 0, "match_id": 1, "home_team": 1, "away_team": 1}
        )
        if not match:
            flash('Match not found.', 'danger')
            return redirect(url_for('adminRoutes.goals_management'))

        # Fetch player details
        player_id = int(request.form.get('player'))
        player = db.players.find_one(
            {"player_id": player_id},
            {"_id": 0, "player_id": 1, "player_name": 1}
        )
        if not player:
            flash('Player not found.', 'danger')
            return redirect(url_for('adminRoutes.goals_management'))

        # Prepare the goal document
        goal = {
            "goal_id": new_goal_id,
            "player_id": player_id, 
            "match_id": match_id, 
            "minute_scored": int(request.form.get('minute')),
            "is_penalty": 'penalty' in request.form,
            "is_own_goal": 'ownGoal' in request.form
        }

        try:
            db.goals.insert_one(goal)
            flash('Goal recorded successfully!', 'success')
        except Exception as e:
            flash(f"Error adding goal: {str(e)}", 'danger')

        return redirect(url_for('adminRoutes.goals_management'))

# Update Goal
@adminRoutes.route('/goals/update/<string:goal_id>', methods=['POST'])
def update_goal(goal_id):
    # Fetch match details
    match_id = int(request.form.get('match'))
    match = db.matches.find_one(
        {"match_id": match_id},
        {"_id": 0, "match_id": 1, "home_team": 1, "away_team": 1}
    )
    if not match:
        flash('Match not found.', 'danger')
        return redirect(url_for('adminRoutes.goals_management'))

    # Fetch player details
    player_id = int(request.form.get('player'))
    player = db.players.find_one(
        {"player_id": player_id},
        {"_id": 0, "player_id": 1, "player_name": 1}
    )
    if not player:
        flash('Player not found.', 'danger')
        return redirect(url_for('adminRoutes.goals_management'))

    # Prepare the updated goal data
    goal_data = {
        "player_id": player_id, 
        "match_id": match_id,  
        "minute_scored": int(request.form.get('minute')),
        "is_penalty": 'penalty' in request.form,
        "is_own_goal": 'ownGoal' in request.form
    }

    try:
        db.goals.update_one({"goal_id": int(goal_id)}, {"$set": goal_data})
        flash(f"Goal updated successfully!", 'success')
    except Exception as e:
        flash(f"Error updating goal: {str(e)}", 'danger')

    return redirect(url_for('adminRoutes.goals_management'))

# Delete Goal
@adminRoutes.route('/goals/delete/<string:goal_id>', methods=['POST'])
def delete_goal(goal_id):
    try:
        db.goals.delete_one({"goal_id": int(goal_id)})
        flash(f"Goal deleted successfully!", 'success')
    except Exception as e:
        flash(f"Error deleting goal: {str(e)}", 'danger')

    return redirect(url_for('adminRoutes.goals_management'))

##### Tournaments Management #####
# Tournaments
@adminRoutes.route("/tournaments", defaults={'page': 1})
@adminRoutes.route('/tournaments/page/<int:page>')
def tournaments_management(page):
    per_page = 30
    offset = (page - 1) * per_page

    # Fetch tournaments directly with embedded team and scorer details
    tournaments = list(db.tournaments.find({}, {
        "_id": 0,  # Exclude the default _id field
        "tournament_id": 1,
        "year": 1,
        "host_country": 1,
        "matches_played": 1,
        "winning_team": 1,
        "runner_up_team": 1,
        "scorers": 1
    }).skip(offset).limit(per_page))

    teams = list(db.teams.find({}, {"team_id": 1, "team_name": 1}))

    total_tournaments = db.tournaments.count_documents({})
    total_pages = (total_tournaments // per_page) + (1 if total_tournaments % per_page > 0 else 0)

    visible_pages = 5
    start_page = max(1, page - visible_pages // 2)
    end_page = min(total_pages, start_page + visible_pages - 1)

    return render_template("adminTournaments.html", tournaments=tournaments, teams=teams, page=page, total_pages=total_pages, start_page=start_page, end_page=end_page)

# Add Tournament
@adminRoutes.route('/tournaments/add', methods=['POST'])
def add_tournament():
    if request.method == 'POST':

        # Fetch the winner and runner-up team details from the database
        winner_team = db.teams.find_one({"team_id": int(request.form.get('winner'))}, {"_id": 0})
        runner_up_team = db.teams.find_one({"team_id": int(request.form.get('runnerUp'))}, {"_id": 0})
        
        if not winner_team or not runner_up_team:
            flash("Invalid team selection for winner or runner-up.", 'danger')
            return redirect(url_for('adminRoutes.tournaments_management'))

        # Create tournament document
        tournament = {
            "tournament_id": db.tournaments.count_documents({}) + 1,  
            "year": int(request.form.get('year')),
            "host_country": request.form.get('hostCountry'),
            "winning_team": winner_team,
            "runner_up_team": runner_up_team,
            "matches_played": int(request.form.get('matchesPlayed')),
            "scorers": [] 
        }

        try:
            db.tournaments.insert_one(tournament)
            flash('Tournament added successfully!', 'success')
        except Exception as e:
            flash(f"Error adding tournament: {str(e)}", 'danger')

        return redirect(url_for('adminRoutes.tournaments_management'))

# Update Tournament
@adminRoutes.route('/tournaments/update/<string:tournament_id>', methods=['POST'])
def update_tournament(tournament_id):
    
    # Fetch the updated winner and runner-up team details from the database
    winner_team = db.teams.find_one({"team_id": int(request.form.get('winner'))}, {"_id": 0})
    runner_up_team = db.teams.find_one({"team_id": int(request.form.get('runnerUp'))}, {"_id": 0})

    if not winner_team or not runner_up_team:
        flash("Invalid team selection for winner or runner-up.", 'danger')
        return redirect(url_for('adminRoutes.tournaments_management'))

    # Prepare updated tournament data
    tournament_data = {
        "year": int(request.form.get('year')),
        "host_country": request.form.get('hostCountry'),
        "winning_team": winner_team,
        "runner_up_team": runner_up_team,
        "matches_played": int(request.form.get('matchesPlayed'))
    }

    try:
        db.tournaments.update_one({"tournament_id": int(tournament_id)}, {"$set": tournament_data})
        flash(f"Tournament updated successfully!", 'success')
    except Exception as e:
        flash(f"Error updating tournament: {str(e)}", 'danger')

    return redirect(url_for('adminRoutes.tournaments_management'))

# Delete Tournament
@adminRoutes.route('/tournaments/delete/<string:tournament_id>', methods=['POST'])
def delete_tournament(tournament_id):
    try:
        db.tournaments.delete_one({"tournament_id": int(tournament_id)})
        flash(f"Tournament deleted successfully!", 'success')
    except Exception as e:
        flash(f"Error deleting tournament: {str(e)}", 'danger')

    return redirect(url_for('adminRoutes.tournaments_management'))
