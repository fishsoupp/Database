from flask import Blueprint, render_template, redirect, url_for, flash, session, request, current_app
from sqlalchemy.sql import text
from extensions import db, bcrypt  # Import db and bcrypt from extensions
from pymongo import MongoClient
from .forms import LoginForm
from datetime import date
from bson.objectid import ObjectId
from os import getenv

# MongoDB setup
client = MongoClient(getenv('MONGODB_URI'))
db = client.FIFA_DB

adminRoutes = Blueprint("adminRoutes", __name__, template_folder="templates")

# Admin Landing Page
@adminRoutes.route("/landing")
def adminLanding():
    if not session.get('admin_logged_in'):
        return redirect(url_for('adminRoutes.login'))
    
    # MongoDB aggregation to get total goals for teams in the most recent tournament
    result = db.matches.aggregate([
        {
            "$lookup": {
                "from": "goals",
                "localField": "match_id",
                "foreignField": "match_id",
                "as": "goals"
            }
        },
        {
            "$lookup": {
                "from": "teams",
                "localField": "home_team_id",
                "foreignField": "team_id",
                "as": "home_team"
            }
        },
        {
            "$unwind": "$home_team"
        },
        {
            "$group": {
                "_id": "$home_team.team_name",
                "total_goals": {"$sum": {"$size": "$goals"}}
            }
        },
        {
            "$sort": {"total_goals": -1}
        }
    ])

    teams = [row["_id"] for row in result]
    goals = [row["total_goals"] for row in result]

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

    players = list(db.players.find().skip(offset).limit(per_page))
    teams = list(db.teams.find({}, {"team_id": 1, "team_name": 1}))
    
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
        player = {
            "player_name": request.form.get('playerName'),
            "team_id": int(request.form.get('team')),
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
        player_data = {
            "player_name": request.form.get('playerName'),
            "team_id": int(request.form.get('team')),
            "position": request.form.get('position'),
            "date_of_birth": request.form.get('dateOfBirth'),
            "caps": int(request.form.get('caps'))
        }

        try:
            db.players.update_one({"_id": ObjectId(player_id)}, {"$set": player_data})
            flash(f"Player updated successfully!", 'success')
        except Exception as e:
            flash(f"Error updating player: {str(e)}", 'danger')

    return redirect(url_for('adminRoutes.players_management'))

# Delete Player
@adminRoutes.route('/players/delete/<string:player_id>', methods=['POST'])
def delete_player(player_id):
    try:
        db.players.delete_one({"_id": ObjectId(player_id)})
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

    matches = list(db.matches.find().skip(offset).limit(per_page))
    referees = list(db.referees.find({}, {"referee_id": 1, "referee_name": 1}))
    stadiums = list(db.stadiums.find({}, {"stadium_id": 1, "stadium_name": 1}))
    teams = list(db.teams.find({}, {"team_id": 1, "team_name": 1}))
    tournaments = list(db.tournaments.find({}, {"tournament_id": 1, "year": 1}))
    
    total_matches = db.matches.count_documents({})
    total_pages = (total_matches // per_page) + (1 if total_matches % per_page > 0 else 0)

    visible_pages = 5
    start_page = max(1, page - visible_pages // 2)
    end_page = min(total_pages, start_page + visible_pages - 1)

    return render_template("adminMatches.html", matches=matches, referees=referees, stadiums=stadiums, teams=teams, tournaments=tournaments, page=page, total_pages=total_pages, start_page=start_page, end_page=end_page)

# Add Match
@adminRoutes.route('/matches/add', methods=['POST'])
def add_match():
    if request.method == 'POST':
        match = {
            "tournament_id": int(request.form.get('tournament')),
            "stadium_id": int(request.form.get('stadium')),
            "home_team_id": int(request.form.get('homeTeam')),
            "away_team_id": int(request.form.get('awayTeam')),
            "home_team_goals": int(request.form.get('home_team_goals')),
            "away_team_goals": int(request.form.get('away_team_goals')),
            "round": request.form.get('round'),
            "referee_id": int(request.form.get('referee'))
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
        match_data = {
            "tournament_id": int(request.form.get('tournament')),
            "stadium_id": int(request.form.get('stadium')),
            "home_team_id": int(request.form.get('homeTeam')),
            "away_team_id": int(request.form.get('awayTeam')),
            "home_team_goals": int(request.form.get('home_team_goals')),
            "away_team_goals": int(request.form.get('away_team_goals')),
            "round": request.form.get('round'),
            "referee_id": int(request.form.get('referee'))
        }

        try:
            db.matches.update_one({"_id": ObjectId(match_id)}, {"$set": match_data})
            flash(f"Match updated successfully!", 'success')
        except Exception as e:
            flash(f"Error updating match: {str(e)}", 'danger')

    return redirect(url_for('adminRoutes.matches_management'))

# Delete Match
@adminRoutes.route('/matches/delete/<string:match_id>', methods=['POST'])
def delete_match(match_id):
    try:
        db.matches.delete_one({"_id": ObjectId(match_id)})
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

    goals = list(db.goals.find().skip(offset).limit(per_page))
    players = list(db.players.find({}, {"player_id": 1, "player_name": 1}))
    matches = list(db.matches.find({}, {"match_id": 1, "home_team_id": 1, "away_team_id": 1}))

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
        goal = {
            "player_id": int(request.form.get('player')),
            "match_id": int(request.form.get('match')),
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
    goal_data = {
        "player_id": int(request.form.get('player')),
        "match_id": int(request.form.get('match')),
        "minute_scored": int(request.form.get('minute')),
        "is_penalty": 'penalty' in request.form,
        "is_own_goal": 'ownGoal' in request.form
    }

    try:
        db.goals.update_one({"_id": ObjectId(goal_id)}, {"$set": goal_data})
        flash(f"Goal updated successfully!", 'success')
    except Exception as e:
        flash(f"Error updating goal: {str(e)}", 'danger')

    return redirect(url_for('adminRoutes.goals_management'))

# Delete Goal
@adminRoutes.route('/goals/delete/<string:goal_id>', methods=['POST'])
def delete_goal(goal_id):
    try:
        db.goals.delete_one({"_id": ObjectId(goal_id)})
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

    tournaments = list(db.tournaments.find().skip(offset).limit(per_page))
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
        tournament = {
            "year": int(request.form.get('year')),
            "host_country": request.form.get('hostCountry'),
            "winner_team_id": int(request.form.get('winner')),
            "runner_up_team_id": int(request.form.get('runnerUp')),
            "matches_played": int(request.form.get('matchesPlayed'))
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
    tournament_data = {
        "year": int(request.form.get('year')),
        "host_country": request.form.get('hostCountry'),
        "winner_team_id": int(request.form.get('winner')),
        "runner_up_team_id": int(request.form.get('runnerUp')),
        "matches_played": int(request.form.get('matchesPlayed'))
    }

    try:
        db.tournaments.update_one({"_id": ObjectId(tournament_id)}, {"$set": tournament_data})
        flash(f"Tournament updated successfully!", 'success')
    except Exception as e:
        flash(f"Error updating tournament: {str(e)}", 'danger')

    return redirect(url_for('adminRoutes.tournaments_management'))

# Delete Tournament
@adminRoutes.route('/tournaments/delete/<string:tournament_id>', methods=['POST'])
def delete_tournament(tournament_id):
    try:
        db.tournaments.delete_one({"_id": ObjectId(tournament_id)})
        flash(f"Tournament deleted successfully!", 'success')
    except Exception as e:
        flash(f"Error deleting tournament: {str(e)}", 'danger')

    return redirect(url_for('adminRoutes.tournaments_management'))
