from flask import Blueprint, render_template, redirect, url_for, flash, session, request, current_app
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import text
from app import db  
from .forms import LoginForm
from datetime import date

adminRoutes = Blueprint("adminRoutes", __name__, template_folder="templates")


# Admin Landing Page
@adminRoutes.route("/landing")
def adminLanding():
    if not session.get('admin_logged_in'):
        return redirect(url_for('adminRoutes.login'))  # Redirect if not logged in
    return render_template("adminLanding.html")

# Admin Login Route
@adminRoutes.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        # Dummy authentication logic (replace with real DB check later)
        if form.username.data == 'test' and form.password.data == 'test':
            flash('Logged in successfully!', 'success')
            session['admin_logged_in'] = True  # Store admin login status in session
            return redirect(url_for('adminRoutes.adminLanding'))  # Redirect to landing 
        else:
            flash('Login failed. Please check your credentials.', 'danger')
    return render_template("adminLogin.html", form=form, background_image=True)

# Admin Logout Route
@adminRoutes.route("/logout")
def logout():
    session.pop('admin_logged_in', None)  # Clear admin session
    flash('You have been logged out.', 'info')
    return redirect(url_for('adminRoutes.login'))



### Players Management Route ###
@adminRoutes.route("/players", defaults={'page': 1})
@adminRoutes.route('/players/page/<int:page>')
def players_management(page):
    per_page = 30  # Number of records to display per page
    offset = (page - 1) * per_page  # Calculate the offset

    sql = text("""
        SELECT p.player_id, p.player_name, p.team_id, p.position, p.date_of_birth, p.caps, t.team_name
        FROM players p
        JOIN teams t ON p.team_id = t.team_id
        ORDER BY p.player_id
        LIMIT :limit OFFSET :offset
    """)

    teams_sql = text("SELECT team_id, team_name FROM teams ORDER BY team_name")

    # Query to count total number of players
    count_sql = text("SELECT COUNT(*) FROM players")

    with db.engine.connect() as conn:
        result = conn.execute(sql, {'limit': per_page, 'offset': offset})
        team_result = conn.execute(teams_sql)
    
        players = []
        for row in result:
            # Accessing columns directly by name
            players.append({
                'player_id': row.player_id,  # Direct attribute access
                'player_name': row.player_name,
                'team_name': row.team_name,
                'position': row.position,
                'date_of_birth': row.date_of_birth,
                'caps': row.caps
            })

        teams = []
        for row in team_result:
            teams.append({
                'team_id': row.team_id,  # Direct attribute access
                'team_name': row.team_name,
            })
        
        total_players = conn.execute(count_sql).scalar()  # Get total number of players

    total_pages = (total_players // per_page) + (1 if total_players % per_page > 0 else 0)

    # Current date in the required format for HTML input elements
    current_date = date.today().isoformat()

    # Adjust the range of visible pages
    if page > total_pages:
        page = total_pages  # Adjust current page if out of bounds
    visible_pages = 5  # This can be adjusted as needed
    start_page = max(1, page - visible_pages // 2)
    end_page = min(total_pages, start_page + visible_pages - 1)
    
    if end_page - start_page < visible_pages and start_page > 1:
        start_page = max(1, end_page - visible_pages + 1)


    return render_template("adminPlayers.html", players=players, teams=teams, page=page, total_pages=total_pages, start_page=start_page, end_page=end_page, current_date=current_date)


@adminRoutes.route('/players/add', methods=['POST'])
def add_player():

    if request.method == 'POST':
        # Get form data
        player_name = request.form.get('playerName')
        team_id = request.form.get('team', type=int)
        position = request.form.get('position')
        date_of_birth = request.form.get('date_of_birth') 
        caps = request.form.get('caps', type=int)

        # Debugging 
        # flash(f"Received data: player_name={player_name}, team_id={team_id}, position={position}, date_of_birth={date_of_birth}, caps={caps}", 'success')
        # current_app.logger.debug(f"Received data: player_name={player_name}, team_id={team_id}, position={position}, date_of_birth={date_of_birth}, caps={caps}")

        # Construct the raw SQL query
        sql = text("""
            INSERT INTO players (player_name, team_id, position, date_of_birth, caps)
            VALUES (:player_name, :team_id, :position, :date_of_birth, :caps)
        """)
        
        try:
            with db.engine.connect() as conn:
                conn.execute(sql, {'player_name': player_name, 'team_id': team_id, 'position': position, 'date_of_birth': date_of_birth, 'caps': caps})
                conn.commit()
                # Flash a success message and redirect
                flash('Player added successfully!', 'success')
        except Exception as e:
            # Flash an error message if something goes wrong
            current_app.logger.error(f"Error adding player: {str(e)}", exc_info=True)
            flash(f"Error adding player: {str(e)}", 'danger')

        return redirect(url_for('adminRoutes.players_management'))
    
    # If not a POST request, redirect to the players management page
    return redirect(url_for('adminRoutes.players_management'))

@adminRoutes.route('/players/update/<int:player_id>', methods=['POST'])
def update_player(player_id):
    if request.method == 'POST':
        # Extract data from the form
        player_name = request.form.get('playerName')
        team_id = request.form.get('team', type=int)
        position = request.form.get('position')
        date_of_birth = request.form.get('dateOfBirth')
        caps = request.form.get('caps', type=int)

        # Construct the SQL query to update the player
        sql = text("""
            UPDATE players
            SET player_name = :player_name, 
                team_id = :team_id, 
                position = :position, 
                date_of_birth = :date_of_birth, 
                caps = :caps
            WHERE player_id = :player_id
        """)

        # Dictionary for SQL parameters
        sql_params = {
            'player_id': player_id,
            'player_name': player_name,
            'team_id': team_id,
            'position': position,
            'date_of_birth': date_of_birth,
            'caps': caps
        }

        try:
            with db.engine.connect() as conn:
                conn.execute(sql, sql_params)
                conn.commit()  # Commit the transaction
                flash(f"Player with ID {player_id} updated successfully!", 'success')
        except Exception as e:
            current_app.logger.error(f"Error updating player: {str(e)}", exc_info=True)
            flash(f"Error updating player: {str(e)}", 'danger')

    return redirect(url_for('adminRoutes.players_management'))


@adminRoutes.route('/players/delete/<int:player_id>', methods=['POST'])
def delete_player(player_id):
    # Construct the SQL query to delete the player
    sql = text("DELETE FROM players WHERE player_id = :player_id")
    
    try:
        with db.engine.connect() as conn:
            conn.execute(sql, {'player_id': player_id})
            conn.commit()  # Commit the transaction
            flash(f"Player with ID {player_id} deleted successfully!", 'success')
    except Exception as e:
        current_app.logger.error(f"Error deleting player: {str(e)}", exc_info=True)
        flash(f"Error deleting player: {str(e)}", 'danger')

    return redirect(url_for('adminRoutes.players_management'))








### Matches Management ###
@adminRoutes.route("/matches", defaults={'page': 1})
@adminRoutes.route('/matches/page/<int:page>')
def matches_management(page):
    per_page = 30  # Number of records to display per page
    offset = (page - 1) * per_page  # Calculate the offset

    sql = text("""
        SELECT
            m.match_id,
            m.tournament_id,
            m.stadium_id,
            m.home_team_id,
            m.away_team_id,
            m.home_team_goals,
            m.away_team_goals,
            m.round,
            m.referee_id,
            t.year AS tournament_year,
            ht.team_name AS home_team_name,
            at.team_name AS away_team_name,
            s.stadium_name,
            r.referee_name
        FROM
            matches m
        JOIN
            tournaments t ON m.tournament_id = t.tournament_id
        JOIN
            teams ht ON m.home_team_id = ht.team_id
        JOIN
            teams at ON m.away_team_id = at.team_id
        JOIN
            stadiums s ON m.stadium_id = s.stadium_id
        JOIN
            referees r ON m.referee_id = r.referee_id
        ORDER BY
            m.match_id
        LIMIT :limit OFFSET :offset
    """)

    referees_sql = text("SELECT referee_id, referee_name FROM referees ORDER BY referee_name")
    stadiums_sql = text("SELECT stadium_id, stadium_name FROM stadiums ORDER BY stadium_name")
    teams_sql = text("SELECT team_id, team_name FROM teams ORDER BY team_name")
    tournaments_sql = text("SELECT tournament_id, year AS tournament_year FROM tournaments ORDER BY tournament_year")

    count_sql = text("SELECT COUNT(*) FROM matches")

    with db.engine.connect() as conn:
        result = conn.execute(sql, {'limit': per_page, 'offset': offset})
        matches = []
        for row in result:
            matches.append({
                'match_id': row.match_id,
                'tournament_year': row.tournament_year,
                'home_team_name': row.home_team_name,
                'away_team_name': row.away_team_name,
                'stadium_name': row.stadium_name,
                'home_team_goals': row.home_team_goals,
                'away_team_goals': row.away_team_goals,
                'round': row.round,
                'referee_name': row.referee_name
            })

        referees = [{'referee_id': row.referee_id, 'referee_name': row.referee_name} for row in conn.execute(referees_sql)]
        stadiums = [{'stadium_id': row.stadium_id, 'stadium_name': row.stadium_name} for row in conn.execute(stadiums_sql)]
        teams = [{'team_id': row.team_id, 'team_name': row.team_name} for row in conn.execute(teams_sql)]
        tournaments = [{'tournament_id': row.tournament_id, 'tournament_year': row.tournament_year} for row in conn.execute(tournaments_sql)]
        
        total_matches = conn.execute(count_sql).scalar()

    total_pages = (total_matches // per_page) + (1 if total_matches % per_page > 0 else 0)

    # Adjust the range of visible pages
    if page > total_pages:
        page = total_pages
    visible_pages = 5  # This can be adjusted as needed
    start_page = max(1, page - visible_pages // 2)
    end_page = min(total_pages, start_page + visible_pages - 1)

    if end_page - start_page < visible_pages and start_page > 1:
        start_page = max(1, end_page - visible_pages + 1)

    return render_template("adminMatches.html", matches=matches, referees=referees, stadiums=stadiums, teams=teams, tournaments=tournaments, page=page, total_pages=total_pages, start_page=start_page, end_page=end_page)






@adminRoutes.route('/matches/add', methods=['POST'])
def add_match():
    if request.method == 'POST':
        # Get form data from the match creation form
        tournament_id = request.form.get('tournament', type=int)
        home_team_id = request.form.get('homeTeam', type=int)
        away_team_id = request.form.get('awayTeam', type=int)
        stadium_id = request.form.get('stadium', type=int)
        home_team_goals = request.form.get('home_team_goals', type=int)  # Separate input for home team goals
        away_team_goals = request.form.get('away_team_goals', type=int)  # Separate input for away team goals
        round = request.form.get('round')
        referee_id = request.form.get('referee', type=int)

        # Debugging 
        current_app.logger.debug(f"Received data: tournament_id={tournament_id}, home_team_id={home_team_id}, away_team_id={away_team_id}, stadium_id={stadium_id}, home_team_goals={home_team_goals}, away_team_goals={away_team_goals}, round={round}, referee_id={referee_id}")

        # Construct the raw SQL query to insert the match data
        sql = text("""
            INSERT INTO matches (tournament_id, stadium_id, home_team_id, away_team_id, home_team_goals, away_team_goals, round, referee_id)
            VALUES (:tournament_id, :stadium_id, :home_team_id, :away_team_id, :home_team_goals, :away_team_goals, :round, :referee_id)
        """)
        
        try:
            with db.engine.connect() as conn:
                conn.execute(sql, {
                    'tournament_id': tournament_id,
                    'stadium_id': stadium_id,
                    'home_team_id': home_team_id,
                    'away_team_id': away_team_id,
                    'home_team_goals': home_team_goals,
                    'away_team_goals': away_team_goals,
                    'round': round,
                    'referee_id': referee_id
                })
                conn.commit()
                # Flash a success message and redirect
                flash('Match added successfully!', 'success')
        except Exception as e:
            # Flash an error message if something goes wrong
            current_app.logger.error(f"Error adding match: {str(e)}", exc_info=True)
            flash(f"Error adding match: {str(e)}", 'danger')

        return redirect(url_for('adminRoutes.matches_management'))

    # If not a POST request, redirect to the matches management page
    return redirect(url_for('adminRoutes.matches_management'))


@adminRoutes.route('/matches/update/<int:match_id>', methods=['POST'])
def update_match(match_id):
    if request.method == 'POST':
        # Get form data
        tournament_id = request.form.get('tournament', type=int)
        home_team_id = request.form.get('homeTeam', type=int)
        away_team_id = request.form.get('awayTeam', type=int)
        stadium_id = request.form.get('stadium', type=int)
        home_team_goals = request.form.get('home_team_goals', type=int)
        away_team_goals = request.form.get('away_team_goals', type=int)
        round = request.form.get('round')
        referee_id = request.form.get('referee', type=int)

        # Construct the raw SQL query to update the match
        sql = text("""
            UPDATE matches
            SET tournament_id = :tournament_id,
                home_team_id = :home_team_id,
                away_team_id = :away_team_id,
                stadium_id = :stadium_id,
                home_team_goals = :home_team_goals,
                away_team_goals = :away_team_goals,
                round = :round,
                referee_id = :referee_id
            WHERE match_id = :match_id
        """)

        try:
            with db.engine.connect() as conn:
                conn.execute(sql, {
                    'tournament_id': tournament_id,
                    'home_team_id': home_team_id,
                    'away_team_id': away_team_id,
                    'stadium_id': stadium_id,
                    'home_team_goals': home_team_goals,
                    'away_team_goals': away_team_goals,
                    'round': round,
                    'referee_id': referee_id,
                    'match_id': match_id
                })
                conn.commit()  # Commit the transaction
                flash(f"Match {match_id} updated successfully!", 'success')
        except Exception as e:
            current_app.logger.error(f"Error updating match: {str(e)}", exc_info=True)
            flash(f"Error updating match: {str(e)}", 'danger')

    return redirect(url_for('adminRoutes.matches_management'))


@adminRoutes.route('/matches/delete/<int:match_id>', methods=['POST'])
def delete_match(match_id):
    # SQL to delete the match
    sql = text("DELETE FROM matches WHERE match_id = :match_id")
    
    try:
        with db.engine.connect() as conn:
            conn.execute(sql, {'match_id': match_id})
            conn.commit()  # Commit the transaction
            flash(f"Match with ID {match_id} deleted successfully!", 'success')
    except Exception as e:
        current_app.logger.error(f"Error deleting match: {str(e)}", exc_info=True)
        flash(f"Error deleting match: {str(e)}", 'danger')
    
    return redirect(url_for('adminRoutes.matches_management'))



### Goals Management ###
### Goals Management ###
@adminRoutes.route("/goals", defaults={'page': 1})
@adminRoutes.route('/goals/page/<int:page>')
def goals_management(page):
    per_page = 30  # Number of records to display per page
    offset = (page - 1) * per_page  # Calculate the offset

    # SQL to fetch goals along with match and team details
    sql = text("""
        SELECT
            g.goal_id,
            g.player_id,
            g.match_id,
            g.minute_scored,
            g.is_penalty,
            g.is_own_goal,
            ht.team_name AS home_team_name,
            at.team_name AS away_team_name,
            p.player_name
        FROM
            goals g
        JOIN
            matches m ON g.match_id = m.match_id
        JOIN
            teams ht ON m.home_team_id = ht.team_id
        JOIN
            teams at ON m.away_team_id = at.team_id
        JOIN
            players p ON g.player_id = p.player_id
        ORDER BY
            g.goal_id
        LIMIT :limit OFFSET :offset
    """)

    players_sql = text("SELECT player_id, player_name FROM players ORDER BY player_name")
    matches_sql = text("""
        SELECT m.match_id, ht.team_name AS home_team_name, at.team_name AS away_team_name, t.year AS tournament_year
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        JOIN tournaments t ON m.tournament_id = t.tournament_id
        ORDER BY m.match_id
    """)

    # SQL to count total number of goals
    count_sql = text("SELECT COUNT(*) FROM goals")

    with db.engine.connect() as conn:
        result = conn.execute(sql, {'limit': per_page, 'offset': offset})
        goals = []
        for row in result:
            goals.append({
                'goal_id': row.goal_id,
                'player_name': row.player_name,
                'match_id': row.match_id,
                'home_team_name': row.home_team_name,
                'away_team_name': row.away_team_name,
                'minute_scored': f"{row.minute_scored}'",
                'is_penalty': row.is_penalty,
                'is_own_goal': row.is_own_goal
            })

        players = [{'player_id': row.player_id, 'player_name': row.player_name} for row in conn.execute(players_sql)]
        matches = [{'match_id': row.match_id, 'home_team_name': row.home_team_name, 'away_team_name': row.away_team_name, 'tournament_year': row.tournament_year} for row in conn.execute(matches_sql)]

        total_goals = conn.execute(count_sql).scalar()

    total_pages = (total_goals // per_page) + (1 if total_goals % per_page > 0 else 0)

    # Adjust the range of visible pages
    if page > total_pages:
        page = total_pages
    visible_pages = 5  # This can be adjusted as needed
    start_page = max(1, page - visible_pages // 2)
    end_page = min(total_pages, start_page + visible_pages - 1)

    if end_page - start_page < visible_pages and start_page > 1:
        start_page = max(1, end_page - visible_pages + 1)

    return render_template("adminGoals.html", goals=goals, players=players, matches=matches, page=page, total_pages=total_pages, start_page=start_page, end_page=end_page)


@adminRoutes.route('/goals/add', methods=['POST'])
def add_goal():
    if request.method == 'POST':
        # Get form data from the request
        player_id = request.form.get('player', type=int)
        match_id = request.form.get('match', type=int)
        minute_scored = request.form.get('minute', type=int)
        is_penalty = 'penalty' in request.form  # Checkbox handling: True if checked, False otherwise
        is_own_goal = 'ownGoal' in request.form  # Checkbox handling: True if checked, False otherwise

        # Construct the raw SQL query to insert a new goal
        sql = text("""
            INSERT INTO goals (player_id, match_id, minute_scored, is_penalty, is_own_goal)
            VALUES (:player_id, :match_id, :minute_scored, :is_penalty, :is_own_goal)
        """)

        try:
            with db.engine.connect() as conn:
                conn.execute(sql, {
                    'player_id': player_id,
                    'match_id': match_id,
                    'minute_scored': minute_scored,
                    'is_penalty': is_penalty,
                    'is_own_goal': is_own_goal
                })
                conn.commit()  # Commit the transaction
                flash('Goal recorded successfully!', 'success')
        except Exception as e:
            current_app.logger.error(f"Error adding goal: {str(e)}", exc_info=True)
            flash(f"Error adding goal: {str(e)}", 'danger')

        return redirect(url_for('adminRoutes.goals_management'))  # Redirect to the goals management page

    # If there are any issues with the POST request
    flash('Failed to record the goal. Please try again.', 'danger')
    return redirect(url_for('adminRoutes.goals_management'))


@adminRoutes.route('/goals/update/<int:goal_id>', methods=['POST'])
def update_goal(goal_id):
    # Fetch the form data
    player_id = request.form.get('player', type=int)
    match_id = request.form.get('match', type=int)
    minute_scored = request.form.get('minute', type=str)  # Keep it as a string if you want to add the apostrophe after.
    is_penalty = request.form.get('penalty') is not None  # Checkbox is checked if it is present in the form.
    is_own_goal = request.form.get('ownGoal') is not None  # Checkbox is checked if it is present in the form.

    # Construct the raw SQL query to update the goal record
    sql = text("""
        UPDATE goals
        SET player_id = :player_id,
            match_id = :match_id,
            minute_scored = :minute_scored,
            is_penalty = :is_penalty,
            is_own_goal = :is_own_goal
        WHERE goal_id = :goal_id
    """)

    # Construct SQL parameters
    params = {
        'player_id': player_id,
        'match_id': match_id,
        'minute_scored': minute_scored,
        'is_penalty': is_penalty,
        'is_own_goal': is_own_goal,
        'goal_id': goal_id
    }

    try:
        # Execute the SQL query
        with db.engine.connect() as conn:
            conn.execute(sql, params)
            conn.commit()  # Commit the changes

            # Flash success message
            flash(f"Goal {goal_id} updated successfully!", 'success')

    except Exception as e:
        # Handle any exceptions and log the error
        current_app.logger.error(f"Error updating goal: {str(e)}", exc_info=True)
        flash(f"Error updating goal: {str(e)}", 'danger')

    # Redirect back to the goals management page
    return redirect(url_for('adminRoutes.goals_management'))


@adminRoutes.route('/goals/delete/<int:goal_id>', methods=['POST'])
def delete_goal(goal_id):
    # Construct the SQL query to delete the goal by goal_id
    sql = text("DELETE FROM goals WHERE goal_id = :goal_id")

    try:
        # Execute the delete operation
        with db.engine.connect() as conn:
            conn.execute(sql, {'goal_id': goal_id})
            conn.commit()  # Commit the transaction

            # Flash success message
            flash(f"Goal with ID {goal_id} deleted successfully!", 'success')

    except Exception as e:
        # Handle any exceptions and log the error
        current_app.logger.error(f"Error deleting goal: {str(e)}", exc_info=True)
        flash(f"Error deleting goal: {str(e)}", 'danger')

    # Redirect back to the goals management page
    return redirect(url_for('adminRoutes.goals_management'))



### Tournaments Management ###
@adminRoutes.route("/tournaments")
def tournaments_management():
    # Serve the tournaments management page
    return render_template("adminTournaments.html")

