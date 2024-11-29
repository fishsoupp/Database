from flask import Blueprint, jsonify, render_template, redirect, url_for, flash, session, request, current_app
from sqlalchemy.sql import text
from app import db, client, bcrypt  # Import db and bcrypt from app.py
from pymongo import MongoClient, errors
from .forms import LoginForm
from datetime import date
from bson.objectid import ObjectId
from os import getenv


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

    # Extract the tournament _id for the latest tournament
    latest_tournament_id = latest_tournament["_id"]

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

    teams = list(db.teams.find({}, {"_id": 1, "team_name": 1}))
    
    # Fetch players with embedded team details
    players = list(db.players.find(
        {},  
        {
            "_id": 1,
            "player_name": 1,
            "position": 1,
            "date_of_birth": 1,
            "caps": 1,
            "team.team_name": 1,  # Access team name from embedded team
            "team._id": 1,  # Access team _id
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
        # Fetch the data from the form
        team_oid = request.form.get('team')  # Team ID
        player_name = request.form.get('playerName').strip()  # Player name

        # Start a client session for the transaction
        session = client.start_session()

        try:
            # Start a transaction
            session.start_transaction()

            # Fetch the team details within the transaction
            team_details = db.teams.find_one({"_id": ObjectId(team_oid)}, session=session)

            if not team_details:
                flash("Selected team not found!", "danger")
                session.abort_transaction()
                return redirect(url_for('adminRoutes.players_management'))

            # Check if the player already exists in the selected team within the transaction
            existing_player = db.players.find_one(
                {"player_name": player_name, "team._id": team_details["_id"]},
                session=session
            )
            if existing_player:
                flash("This player already exists in the selected team!", "danger")
                session.abort_transaction()
                return redirect(url_for('adminRoutes.players_management'))

            # Prepare player data
            player = {
                "player_name": player_name,
                "team": {
                    "_id": team_details["_id"],
                    "team_name": team_details["team_name"],
                    "continent": team_details.get("continent", ""),
                    "fifa_code": team_details.get("fifa_code", "")
                },
                "position": request.form.get('position'),
                "date_of_birth": request.form.get('date_of_birth'),
                "caps": int(request.form.get('caps')),
                "player_performance": []
            }

            # Insert the new player within the transaction
            db.players.insert_one(player, session=session)

            # Commit the transaction
            session.commit_transaction()
            flash('Player added successfully!', 'success')

        except errors.DuplicateKeyError:
            # Handle duplicate entry due to unique index
            session.abort_transaction()
            flash("This player already exists in the database!", "danger")
        except errors.PyMongoError as e:
            # Handle other MongoDB errors
            session.abort_transaction()
            flash(f"Error adding player: {str(e)}", "danger")
        finally:
            # End the session
            session.end_session()

        return redirect(url_for('adminRoutes.players_management'))

    return redirect(url_for('adminRoutes.players_management'))

# Update Player
@adminRoutes.route('/players/update/<string:_id>', methods=['POST'])
def update_player(_id):
    if request.method == 'POST':
        # Convert the player ObjectId
        player_oid = ObjectId(_id)

        # Start a client session for the transaction
        session = client.start_session()

        try:
            # Start a transaction
            session.start_transaction()

            # Get the new team details from the form
            team_oid = request.form.get('team')
            team = db.teams.find_one({"_id": ObjectId(team_oid)}, {"_id": 1, "team_name": 1, "fifa_code": 1, "continent": 1}, session=session)

            if not team:
                flash(f"Team with ID {team_oid} not found.", 'danger')
                session.abort_transaction()
                return redirect(url_for('adminRoutes.players_management'))

            # Get the new player details from the form
            player_name = request.form.get('playerName').strip()
            position = request.form.get('position')
            date_of_birth = request.form.get('dateOfBirth')
            caps = int(request.form.get('caps'))

            # Check if another player with the same name exists in the same team
            existing_player = db.players.find_one(
                {"player_name": player_name, "team._id": team["_id"], "_id": {"$ne": player_oid}},
                session=session
            )
            if existing_player:
                flash(f"A player with the name '{player_name}' already exists in the selected team.", 'danger')
                session.abort_transaction()
                return redirect(url_for('adminRoutes.players_management'))

            # Prepare the updated player data
            player_data = {
                "player_name": player_name,
                "team": {
                    "_id": team["_id"],
                    "team_name": team["team_name"],
                    "fifa_code": team.get("fifa_code", ""),
                    "continent": team.get("continent", "")
                },
                "position": position,
                "date_of_birth": date_of_birth,
                "caps": caps
            }

            # Update the player document within the transaction
            db.players.update_one({"_id": player_oid}, {"$set": player_data}, session=session)

            # Commit the transaction
            session.commit_transaction()
            flash("Player updated successfully!", "success")

        except errors.PyMongoError as e:
            # Handle MongoDB errors
            session.abort_transaction()
            flash(f"Error updating player: {str(e)}", "danger")

        finally:
            # End the session
            session.end_session()

    return redirect(url_for('adminRoutes.players_management'))

# Delete Player
@adminRoutes.route('/players/delete/<string:_id>', methods=['POST'])
def delete_player(_id):
    try:

        player_oid = ObjectId(_id)

        db.players.delete_one({"_id": player_oid})
        flash(f"Player deleted successfully!", 'success')
    except Exception as e:
        flash(f"Error deleting player: {str(e)}", 'danger')

    return redirect(url_for('adminRoutes.players_management'))

@adminRoutes.route('/api/check_player_exists', methods=['GET'])
def check_player_exists():
    player_name = request.args.get('player_name').strip()
    team_id = request.args.get('team_id')

    existing_player = db.players.find_one({"player_name": player_name, "team._id": ObjectId(team_id)})
    return jsonify({"exists": bool(existing_player)})


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
                "foreignField": "_id",
                "as": "tournament_info"
            }
        },
        {"$unwind": "$tournament_info"},  

        # Project the required fields
        {
            "$project": {
                "_id": 1, 
                "tournament_id": "$tournament_info._id",
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
    teams = list(db.teams.find({}, {"_id": 1, "team_name": 1}))
    tournaments = list(db.tournaments.find({}, {"_id": 1, "year": 1}))
    stadiums = list(db.stadiums.find({}, {"_id": 1, "stadium_name": 1}))
    referees = list(db.referees.find({}, {"_id": 1, "referee_name": 1}))

    total_matches = db.matches.count_documents({})
    total_pages = (total_matches // per_page) + (1 if total_matches % per_page > 0 else 0)

    visible_pages = 5
    start_page = max(1, page - visible_pages // 2)
    end_page = min(total_pages, start_page + visible_pages - 1)

    return render_template("adminMatches.html", matches=matches, teams=teams,stadiums=stadiums, referees=referees, tournaments=tournaments, page=page, total_pages=total_pages, start_page=start_page, end_page=end_page)

# Add Match
# Add Match
@adminRoutes.route('/matches/add', methods=['POST'])
def add_match():
    if request.method == 'POST':
        # Start a client session for the transaction
        session = client.start_session()

        try:
            # Start a transaction
            session.start_transaction()

            # Fetch tournament details within the transaction
            tournament_id = request.form.get('tournament')
            tournament = db.tournaments.find_one({"_id": ObjectId(tournament_id)}, session=session)
            if not tournament:
                flash('Tournament not found.', 'danger')
                session.abort_transaction()
                return redirect(url_for('adminRoutes.matches_management'))

            # Fetch referee details within the transaction
            referee_id = request.form.get('referee')
            referee = db.referees.find_one({"_id": ObjectId(referee_id)}, {"_id": 1, "referee_name": 1}, session=session)
            if not referee:
                flash('Referee not found.', 'danger')
                session.abort_transaction()
                return redirect(url_for('adminRoutes.matches_management'))

            # Fetch stadium details within the transaction
            stadium_id = request.form.get('stadium')
            stadium = db.stadiums.find_one({"_id": ObjectId(stadium_id)}, {"_id": 1, "stadium_name": 1, "city": 1}, session=session)
            if not stadium:
                flash('Stadium not found.', 'danger')
                session.abort_transaction()
                return redirect(url_for('adminRoutes.matches_management'))

            # Fetch home team details within the transaction
            home_team_id = request.form.get('homeTeam')
            home_team = db.teams.find_one({"_id": ObjectId(home_team_id)}, {"_id": 1, "team_name": 1, "continent": 1, "fifa_code": 1}, session=session)
            if not home_team:
                flash('Home team not found.', 'danger')
                session.abort_transaction()
                return redirect(url_for('adminRoutes.matches_management'))

            # Fetch away team details within the transaction
            away_team_id = request.form.get('awayTeam')
            away_team = db.teams.find_one({"_id": ObjectId(away_team_id)}, {"_id": 1, "team_name": 1, "continent": 1, "fifa_code": 1}, session=session)
            if not away_team:
                flash('Away team not found.', 'danger')
                session.abort_transaction()
                return redirect(url_for('adminRoutes.matches_management'))

            # Check if a similar match already exists within the transaction
            existing_match = db.matches.find_one({
                "tournament_id": tournament["_id"],
                "home_team._id": home_team["_id"],
                "away_team._id": away_team["_id"],
            }, session=session)
            if existing_match:
                flash("This match already exists in the tournament!", "danger")
                session.abort_transaction()
                return redirect(url_for('adminRoutes.matches_management'))

            # Prepare the match document
            match = {
                "tournament_id": tournament["_id"],
                "home_team": home_team,
                "away_team": away_team,
                "home_team_goal": int(request.form.get('home_team_goals')),
                "away_team_goal": int(request.form.get('away_team_goals')),
                "round": request.form.get('round'),
                "referee": referee,
                "stadium": stadium
            }

            # Insert the new match within the transaction
            db.matches.insert_one(match, session=session)

            # Commit the transaction
            session.commit_transaction()
            flash('Match added successfully!', 'success')
        except errors.DuplicateKeyError:
            # Handle duplicate entry due to unique index
            session.abort_transaction()
            flash("This match already exists in the database!", "danger")
        except errors.PyMongoError as e:
            # Handle other MongoDB errors
            session.abort_transaction()
            flash(f"Error adding match: {str(e)}", "danger")
        finally:
            # End the session
            session.end_session()

        return redirect(url_for('adminRoutes.matches_management'))

    return redirect(url_for('adminRoutes.matches_management'))


# Update Match
@adminRoutes.route('/matches/update/<string:_id>', methods=['POST'])
def update_match(_id):
    if request.method == 'POST':
        # Convert the match _id from string to ObjectId
        match_oid = ObjectId(_id)

        # Start a client session for the transaction
        session = client.start_session()

        try:
            # Start a transaction
            session.start_transaction()

            # Fetch tournament details within the transaction
            tournament_id = request.form.get('tournament')
            tournament = db.tournaments.find_one({"_id": ObjectId(tournament_id)}, {"_id": 1}, session=session)
            if not tournament:
                flash('Tournament not found.', 'danger')
                session.abort_transaction()
                return redirect(url_for('adminRoutes.matches_management'))

            # Fetch referee details within the transaction
            referee_id = request.form.get('referee')
            referee = db.referees.find_one({"_id": ObjectId(referee_id)}, {"_id": 1, "referee_name": 1}, session=session)
            if not referee:
                flash('Referee not found.', 'danger')
                session.abort_transaction()
                return redirect(url_for('adminRoutes.matches_management'))

            # Fetch stadium details within the transaction
            stadium_id = request.form.get('stadium')
            stadium = db.stadiums.find_one({"_id": ObjectId(stadium_id)}, {"_id": 1, "stadium_name": 1, "city": 1}, session=session)
            if not stadium:
                flash('Stadium not found.', 'danger')
                session.abort_transaction()
                return redirect(url_for('adminRoutes.matches_management'))

            # Fetch home team details within the transaction
            home_team_id = request.form.get('homeTeam')
            home_team = db.teams.find_one({"_id": ObjectId(home_team_id)}, {"_id": 1, "team_name": 1, "continent": 1, "fifa_code": 1}, session=session)
            if not home_team:
                flash('Home team not found.', 'danger')
                session.abort_transaction()
                return redirect(url_for('adminRoutes.matches_management'))

            # Fetch away team details within the transaction
            away_team_id = request.form.get('awayTeam')
            away_team = db.teams.find_one({"_id": ObjectId(away_team_id)}, {"_id": 1, "team_name": 1, "continent": 1, "fifa_code": 1}, session=session)
            if not away_team:
                flash('Away team not found.', 'danger')
                session.abort_transaction()
                return redirect(url_for('adminRoutes.matches_management'))

            # Check if a similar match already exists (excluding the current match) within the transaction
            existing_match = db.matches.find_one({
                "tournament_id": tournament["_id"],
                "home_team._id": home_team["_id"],
                "away_team._id": away_team["_id"],
                "_id": {"$ne": match_oid}  # Exclude the current match being updated
            }, session=session)
            if existing_match:
                flash("A match with these details already exists!", "danger")
                session.abort_transaction()
                return redirect(url_for('adminRoutes.matches_management'))
            # Prepare the updated match data
            match_data = {
                "tournament_id": tournament["_id"],
                "home_team": home_team,
                "away_team": away_team,
                "home_team_goal": int(request.form.get('home_team_goals')),
                "away_team_goal": int(request.form.get('away_team_goals')),
                "round": request.form.get('round'),
                "referee": referee,
                "stadium": stadium
            }

            # Update the match within the transaction
            db.matches.update_one({"_id": match_oid}, {"$set": match_data}, session=session)

            # Commit the transaction
            session.commit_transaction()
            flash("Match updated successfully!", 'success')

        except errors.DuplicateKeyError:
            # Handle duplicate entry due to unique index
            session.abort_transaction()
            flash("This match already exists in the database!", "danger")
        except errors.PyMongoError as e:
            # Handle other MongoDB errors
            session.abort_transaction()
            flash(f"Error updating match: {str(e)}", "danger")
        finally:
            # End the session
            session.end_session()

        return redirect(url_for('adminRoutes.matches_management'))

    return redirect(url_for('adminRoutes.matches_management'))

# Delete Match
@adminRoutes.route('/matches/delete/<string:_id>', methods=['POST'])
def delete_match(_id):
    try:
        match_oid = ObjectId(_id)

        db.matches.delete_one({"_id": match_oid})
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
                "foreignField": "_id",
                "as": "player_info"
            }
        },
        {
            "$lookup": {
                "from": "matches",
                "localField": "match_id",
                "foreignField": "_id",
                "as": "match_info"
            }
        },
        {"$unwind": "$player_info"}, 
        {"$unwind": "$match_info"},   

        # Project the required fields
        {
            "$project": {
                "_id": 1, 
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
    players = list(db.players.find({}, {"_id": 1, "player_name": 1}))
    matches = list(db.matches.find({}, {"_id": 1, "home_team.team_name": 1, "away_team.team_name": 1}))

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

        # Fetch match and player details from the form
        match_id = request.form.get('match')
        player_id = request.form.get('player')
        minute_scored = request.form.get('minute') + "'"
        is_penalty = 'penalty' in request.form
        is_own_goal = 'ownGoal' in request.form

        # Start a client session for the transaction
        session = client.start_session()

        try:
            # Start the transaction
            session.start_transaction()

            # Fetch match details within the transaction
            match = db.matches.find_one({"_id": ObjectId(match_id)}, {"_id": 1}, session=session)
            if not match:
                flash('Match not found.', 'danger')
                session.abort_transaction()
                return redirect(url_for('adminRoutes.goals_management'))

            # Fetch player details within the transaction
            player = db.players.find_one({"_id": ObjectId(player_id)}, {"_id": 1}, session=session)
            if not player:
                flash('Player not found.', 'danger')
                session.abort_transaction()
                return redirect(url_for('adminRoutes.goals_management'))

            # Check if a goal with the same match_id and minute_scored already exists
            existing_goal = db.goals.find_one(
                {"match_id": ObjectId(match_id), "minute_scored": minute_scored},
                session=session
            )
            if existing_goal:
                flash('A goal at this time in the match has already been recorded.', 'danger')
                session.abort_transaction()
                return redirect(url_for('adminRoutes.goals_management'))

            # Prepare the goal document
            goal = {
                "player_id": ObjectId(player_id),
                "match_id": ObjectId(match_id),
                "minute_scored": minute_scored,
                "is_penalty": is_penalty,
                "is_own_goal": is_own_goal
            }

            # Insert the goal document within the transaction
            db.goals.insert_one(goal, session=session)

            # Commit the transaction
            session.commit_transaction()
            flash('Goal recorded successfully!', 'success')

        except errors.DuplicateKeyError:
            # Handle unique constraint violation
            session.abort_transaction()
            flash("A goal with the same match and time already exists.", "danger")
        except errors.PyMongoError as e:
            # Handle other MongoDB errors
            session.abort_transaction()
            flash(f"Error adding goal: {str(e)}", 'danger')
        finally:
            # End the session
            session.end_session()

        return redirect(url_for('adminRoutes.goals_management'))

# Update Goal
@adminRoutes.route('/goals/update/<string:_id>', methods=['POST'])
def update_goal(_id):
    goal_oid = ObjectId(_id)

    # Start a client session for the transaction
    session = client.start_session()

    try:
        # Start the transaction
        session.start_transaction()

        # Fetch the updated match details
        match_id = request.form.get('match')
        match = db.matches.find_one({"_id": ObjectId(match_id)}, {"_id": 1}, session=session)
        if not match:
            flash('Match not found.', 'danger')
            session.abort_transaction()
            return redirect(url_for('adminRoutes.goals_management'))

        # Fetch the updated player details
        player_id = request.form.get('player')
        player = db.players.find_one({"_id": ObjectId(player_id)}, {"_id": 1}, session=session)
        if not player:
            flash('Player not found.', 'danger')
            session.abort_transaction()
            return redirect(url_for('adminRoutes.goals_management'))

        # Prepare the updated goal data
        minute_scored = request.form.get('minute') + "'"
        is_penalty = 'penalty' in request.form
        is_own_goal = 'ownGoal' in request.form

        # Check if another goal with the same match_id and minute_scored exists
        existing_goal = db.goals.find_one(
            {"match_id": ObjectId(match_id), "minute_scored": minute_scored, "_id": {"$ne": goal_oid}},
            session=session
        )
        if existing_goal:
            flash("A goal with the same match and minute already exists.", "danger")
            session.abort_transaction()
            return redirect(url_for('adminRoutes.goals_management'))

        # Prepare the goal document for update
        goal_data = {
            "player_id": ObjectId(player_id),
            "match_id": ObjectId(match_id),
            "minute_scored": minute_scored,
            "is_penalty": is_penalty,
            "is_own_goal": is_own_goal
        }

        # Update the goal document within the transaction
        db.goals.update_one({"_id": goal_oid}, {"$set": goal_data}, session=session)

        # Commit the transaction
        session.commit_transaction()
        flash("Goal updated successfully!", "success")

    except errors.DuplicateKeyError:
        # Handle unique constraint violation
        session.abort_transaction()
        flash("A goal with the same match and minute already exists.", "danger")
    except errors.PyMongoError as e:
        # Handle other MongoDB errors
        session.abort_transaction()
        flash(f"Error updating goal: {str(e)}", "danger")
    finally:
        # End the session
        session.end_session()

    return redirect(url_for('adminRoutes.goals_management'))

# Delete Goal
@adminRoutes.route('/goals/delete/<string:_id>', methods=['POST'])
def delete_goal(_id):
    try:

        goal_oid = ObjectId(_id)

        db.goals.delete_one({"_id": goal_oid})
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
        "_id": 1,  
        "year": 1,
        "host_country": 1,
        "matches_played": 1,
        "winning_team": 1,
        "runner_up_team": 1,
        "scorers": 1
    }).skip(offset).limit(per_page))

    teams = list(db.teams.find({}, {"_id": 1, "team_name": 1}))

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
        # Start a client session for the transaction
        session = client.start_session()

        try:
            # Start a transaction
            session.start_transaction()

            # Fetch the winner and runner-up team details within the transaction
            winner_team_id = ObjectId(request.form.get('winner'))
            winner_team = db.teams.find_one({"_id": winner_team_id}, {"team_name": 1, "continent": 1, "fifa_code": 1}, session=session)

            runner_up_team_id = ObjectId(request.form.get('runnerUp'))
            runner_up_team = db.teams.find_one({"_id": runner_up_team_id}, {"team_name": 1, "continent": 1, "fifa_code": 1}, session=session)

            if not winner_team or not runner_up_team:
                flash("Invalid team selection for winner or runner-up.", 'danger')
                session.abort_transaction()
                return redirect(url_for('adminRoutes.tournaments_management'))

            # Get the year of the tournament
            year = int(request.form.get('year'))

            # Check if a tournament for the given year already exists within the transaction
            existing_tournament = db.tournaments.find_one({"year": year}, session=session)
            if existing_tournament:
                flash("A tournament for this year already exists!", "danger")
                session.abort_transaction()
                return redirect(url_for('adminRoutes.tournaments_management'))

            # Create the tournament document
            tournament = {
                "year": year,
                "host_country": request.form.get('hostCountry'),
                "winning_team": {**winner_team, "_id": winner_team_id},
                "runner_up_team": {**runner_up_team, "_id": runner_up_team_id},
                "matches_played": int(request.form.get('matchesPlayed')),
                "scorers": []  # Default empty list for scorers
            }

            # Insert the new tournament within the transaction
            db.tournaments.insert_one(tournament, session=session)

            # Commit the transaction
            session.commit_transaction()
            flash('Tournament added successfully!', 'success')

        except errors.DuplicateKeyError:
            # Handle duplicate entry due to unique index
            session.abort_transaction()
            flash("A tournament for this year already exists!", "danger")
        except errors.PyMongoError as e:
            # Handle other MongoDB errors
            session.abort_transaction()
            flash(f"Error adding tournament: {str(e)}", "danger")
        finally:
            # End the session
            session.end_session()

        return redirect(url_for('adminRoutes.tournaments_management'))

    return redirect(url_for('adminRoutes.tournaments_management'))


# Update Tournament
@adminRoutes.route('/tournaments/update/<string:_id>', methods=['POST'])
def update_tournament(_id):
    # Start a client session for the transaction
    session = client.start_session()

    try:
        # Start a transaction
        session.start_transaction()

        # Fetch the updated winner and runner-up team details within the transaction
        winner_team_id = ObjectId(request.form.get('winner'))
        winner_team = db.teams.find_one({"_id": winner_team_id}, {"team_name": 1, "continent": 1, "fifa_code": 1}, session=session)

        runner_up_team_id = ObjectId(request.form.get('runnerUp'))
        runner_up_team = db.teams.find_one({"_id": runner_up_team_id}, {"team_name": 1, "continent": 1, "fifa_code": 1}, session=session)

        if not winner_team or not runner_up_team:
            flash("Invalid team selection for winner or runner-up.", 'danger')
            session.abort_transaction()
            return redirect(url_for('adminRoutes.tournaments_management'))

        # Get the updated year of the tournament
        year = int(request.form.get('year'))
        # Check if another tournament for the given year already exists (excluding the current tournament)
        existing_tournament = db.tournaments.find_one({
            "year": year,
            "_id": {"$ne": ObjectId(_id)}  # Exclude the current tournament being updated
        }, session=session)

        if existing_tournament:
            flash("A tournament for this year already exists!", "danger")
            session.abort_transaction()
            return redirect(url_for('adminRoutes.tournaments_management'))

        # Prepare the updated tournament data
        tournament_data = {
            "year": year,
            "host_country": request.form.get('hostCountry'),
            "winning_team": {**winner_team, "_id": winner_team_id},
            "runner_up_team": {**runner_up_team, "_id": runner_up_team_id},
            "matches_played": int(request.form.get('matchesPlayed'))
        }

        # Update the tournament within the transaction
        db.tournaments.update_one({"_id": ObjectId(_id)}, {"$set": tournament_data}, session=session)

        # Commit the transaction
        session.commit_transaction()
        flash("Tournament updated successfully!", 'success')

    except errors.DuplicateKeyError:
        # Handle duplicate entry due to unique index
        session.abort_transaction()
        flash("A tournament for this year already exists!", "danger")
    except errors.PyMongoError as e:
        # Handle other MongoDB errors
        session.abort_transaction()
        flash(f"Error updating tournament: {str(e)}", "danger")
    finally:
        # End the session
        session.end_session()

    return redirect(url_for('adminRoutes.tournaments_management'))

# Delete Tournament
@adminRoutes.route('/tournaments/delete/<string:_id>', methods=['POST'])
def delete_tournament(_id):
    try:
        db.tournaments.delete_one({"_id": ObjectId(_id)})
        flash(f"Tournament deleted successfully!", 'success')
    except Exception as e:
        flash(f"Error deleting tournament: {str(e)}", 'danger')

    return redirect(url_for('adminRoutes.tournaments_management'))
