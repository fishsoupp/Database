from flask import Blueprint, render_template, redirect, url_for, flash, session, request, current_app
from sqlalchemy.sql import text
from app import db  
from app import bcrypt
from .forms import LoginForm
from datetime import date
from flask import session, flash, redirect, url_for

adminRoutes = Blueprint("adminRoutes", __name__, template_folder="templates")

# Admin Landing Page
@adminRoutes.route("/landing")
def adminLanding():
    if not session.get('admin_logged_in'):
        return redirect(url_for('adminRoutes.login'))  
    
    # Query to get total goals for teams in the most recent tournament
    sql = text("""
        SELECT 
            t.team_name, 
            COUNT(g.goal_id) AS total_goals
        FROM 
            goals g
        JOIN 
            matches m ON g.match_id = m.match_id
        JOIN 
            teams t ON (t.team_id = m.home_team_id OR t.team_id = m.away_team_id)
        JOIN 
            tournaments tr ON tr.tournament_id = m.tournament_id
        WHERE 
            tr.tournament_id = (
                SELECT 
                    tournament_id 
                FROM 
                    matches
                GROUP BY 
                    tournament_id
                ORDER BY 
                    COUNT(match_id) DESC
                LIMIT 1
            )
        GROUP BY 
            t.team_name;
    """)

    with db.engine.connect() as conn:
        result = conn.execute(sql).fetchall()

    teams = [row[0] for row in result]
    goals = [row[1] for row in result]

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
        sql = text("""
            UPDATE 
                admin 
            SET 
                admin_name=:admin_name, 
                email=:email 
            WHERE 
                admin_id=:admin_id
        """)

        # Dictionary for SQL parameters
        sql_params = {
            'admin_name': admin_name,
            'email': email,
            'admin_id': admin_id
        }

        with db.engine.connect() as conn:
            conn.execute(sql, sql_params)
            conn.commit()
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
        sql = text("SELECT admin_id, admin_name, email, password FROM Admin WHERE email = :email")
        try:
            with db.engine.connect() as conn:
                result = conn.execute(sql, {'email': form.email.data}).fetchone()

            if result:
                stored_id, stored_admin_name, stored_email, stored_password = result

                if bcrypt.check_password_hash(stored_password, form.password.data):
                    session['admin_logged_in'] = True
                    session['admin_name'] = stored_admin_name 
                    session['admin_id'] = stored_id

                    print(f"session['admin_id']: {session['admin_id']}") 

                    with db.engine.connect() as conn:
                        conn.execute(text(f"SET myapp.admin_id = {stored_id};"))
                        conn.commit()
                    
                    flash('Logged in successfully!', 'success')
                    return redirect(url_for('adminRoutes.adminLanding'))
                else:
                    flash('Incorrect password. Please try again.', 'danger')
            else:
                flash('Email not found. Please check your email.', 'danger')

        except Exception as e:
            current_app.logger.error(f"Error during login: {str(e)}", exc_info=True)
            flash('An error occurred during login. Please try again.', 'danger')

    return render_template("adminLogin.html", form=form)


# Admin Logout 
@adminRoutes.route("/logout")
def logout():
    session.pop('admin_logged_in', None) 
    flash('You have been logged out.', 'info')
    return redirect(url_for('adminRoutes.login'))


##### Players Management Route ######
# Players 
@adminRoutes.route("/players", defaults={'page': 1})
@adminRoutes.route('/players/page/<int:page>')
def players_management(page):
    per_page = 30
    offset = (page - 1) * per_page 

    # Query to display player information
    sql = text("""
        SELECT 
            p.player_id, 
            p.player_name, 
            p.team_id, 
            p.position, 
            p.date_of_birth, 
            p.caps, 
            t.team_name
        FROM 
            players p
        JOIN 
            teams t ON p.team_id = t.team_id
        ORDER BY 
            p.player_id
        LIMIT :limit OFFSET :offset
    """)

    # Query to retrieve the list of team_name
    teams_sql = text("SELECT team_id, team_name FROM teams ORDER BY team_name")

    # Query to count total number of players
    count_sql = text("SELECT COUNT(*) FROM players")

    with db.engine.connect() as conn:
        result = conn.execute(sql, {'limit': per_page, 'offset': offset})
        team_result = conn.execute(teams_sql)
    
        players = []
        for row in result:
            players.append({
                'player_id': row.player_id, 
                'player_name': row.player_name,
                'team_name': row.team_name,
                'position': row.position,
                'date_of_birth': row.date_of_birth,
                'caps': row.caps
            })

        teams = []
        for row in team_result:
            teams.append({
                'team_id': row.team_id,
                'team_name': row.team_name,
            })
        
        total_players = conn.execute(count_sql).scalar()

    total_pages = (total_players // per_page) + (1 if total_players % per_page > 0 else 0)

    current_date = date.today().isoformat()

    # Pagination calculation
    if page > total_pages:
        page = total_pages  
    visible_pages = 5 
    start_page = max(1, page - visible_pages // 2)
    end_page = min(total_pages, start_page + visible_pages - 1)
    
    if end_page - start_page < visible_pages and start_page > 1:
        start_page = max(1, end_page - visible_pages + 1)

    return render_template("adminPlayers.html", players=players, teams=teams, page=page, total_pages=total_pages, start_page=start_page, end_page=end_page, current_date=current_date)

# Add Players
@adminRoutes.route('/players/add', methods=['POST'])
def add_player():

    if request.method == 'POST':
        player_name = request.form.get('playerName')
        team_id = request.form.get('team', type=int)
        position = request.form.get('position')
        date_of_birth = request.form.get('date_of_birth') 
        caps = request.form.get('caps', type=int)

        # Query for player insertion
        sql = text("""
            INSERT 
                INTO players (player_name, team_id, position, date_of_birth, caps)
            VALUES 
                (:player_name, :team_id, :position, :date_of_birth, :caps)
        """)
        
        try:
            with db.engine.connect() as conn:
                conn.execute(sql, {'player_name': player_name, 'team_id': team_id, 'position': position, 'date_of_birth': date_of_birth, 'caps': caps})
                conn.commit()

                flash('Player added successfully!', 'success')
        except Exception as e:
            flash(f"Error adding player: {str(e)}", 'danger')

        return redirect(url_for('adminRoutes.players_management'))
    
    return redirect(url_for('adminRoutes.players_management'))

# Player Update
@adminRoutes.route('/players/update/<int:player_id>', methods=['POST'])
def update_player(player_id):
    if request.method == 'POST':
        player_name = request.form.get('playerName')
        team_id = request.form.get('team', type=int)
        position = request.form.get('position')
        date_of_birth = request.form.get('dateOfBirth')
        caps = request.form.get('caps', type=int)

        # Query for updating of player
        sql = text("""
            UPDATE 
                players player_name = :player_name, 
                team_id = :team_id, 
                position = :position, 
                date_of_birth = :date_of_birth, 
                caps = :caps
            WHERE 
                player_id = :player_id
        """)

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
                conn.commit()  

                flash(f"Player with ID {player_id} updated successfully!", 'success')
        except Exception as e:
            flash(f"Error updating player: {str(e)}", 'danger')

    return redirect(url_for('adminRoutes.players_management'))

# Player Delete
@adminRoutes.route('/players/delete/<int:player_id>', methods=['POST'])
def delete_player(player_id):
    # Query for deletion of player
    sql = text("DELETE FROM players WHERE player_id = :player_id")
    
    try:
        with db.engine.connect() as conn:
            conn.execute(sql, {'player_id': player_id})
            conn.commit() 

            flash(f"Player with ID {player_id} deleted successfully!", 'success')
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

    # Query to display matches details
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

    # Queries to retrieve lists of referees, stadiums, teams, and tournaments
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

    if page > total_pages:
        page = total_pages
    visible_pages = 5 
    start_page = max(1, page - visible_pages // 2)
    end_page = min(total_pages, start_page + visible_pages - 1)

    if end_page - start_page < visible_pages and start_page > 1:
        start_page = max(1, end_page - visible_pages + 1)

    return render_template("adminMatches.html", matches=matches, referees=referees, stadiums=stadiums, teams=teams, tournaments=tournaments, page=page, total_pages=total_pages, start_page=start_page, end_page=end_page)

# Match Add
@adminRoutes.route('/matches/add', methods=['POST'])
def add_match():
    if request.method == 'POST':
        tournament_id = request.form.get('tournament', type=int)
        home_team_id = request.form.get('homeTeam', type=int)
        away_team_id = request.form.get('awayTeam', type=int)
        stadium_id = request.form.get('stadium', type=int)
        home_team_goals = request.form.get('home_team_goals', type=int)  
        away_team_goals = request.form.get('away_team_goals', type=int)
        round = request.form.get('round')
        referee_id = request.form.get('referee', type=int)

        # Query for insertion of matches
        sql = text("""
            INSERT 
                INTO matches (tournament_id, stadium_id, home_team_id, away_team_id, home_team_goals, away_team_goals, round, referee_id)
            VALUES 
                (:tournament_id, :stadium_id, :home_team_id, :away_team_id, :home_team_goals, :away_team_goals, :round, :referee_id)
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
                flash('Match added successfully!', 'success')

        except Exception as e:
            flash(f"Error adding match: {str(e)}", 'danger')

        return redirect(url_for('adminRoutes.matches_management'))

    return redirect(url_for('adminRoutes.matches_management'))

# Matches Update
@adminRoutes.route('/matches/update/<int:match_id>', methods=['POST'])
def update_match(match_id):
    if request.method == 'POST':
        tournament_id = request.form.get('tournament', type=int)
        home_team_id = request.form.get('homeTeam', type=int)
        away_team_id = request.form.get('awayTeam', type=int)
        stadium_id = request.form.get('stadium', type=int)
        home_team_goals = request.form.get('home_team_goals', type=int)
        away_team_goals = request.form.get('away_team_goals', type=int)
        round = request.form.get('round')
        referee_id = request.form.get('referee', type=int)

        # Query for updating of a match
        sql = text("""
            UPDATE 
                matches SET tournament_id = :tournament_id,
                home_team_id = :home_team_id,
                away_team_id = :away_team_id,
                stadium_id = :stadium_id,
                home_team_goals = :home_team_goals,
                away_team_goals = :away_team_goals,
                round = :round,
                referee_id = :referee_id
            WHERE 
                match_id = :match_id
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
                conn.commit() 
                flash(f"Match {match_id} updated successfully!", 'success')

        except Exception as e:
            flash(f"Error updating match: {str(e)}", 'danger')

    return redirect(url_for('adminRoutes.matches_management'))

# Match Delete
@adminRoutes.route('/matches/delete/<int:match_id>', methods=['POST'])
def delete_match(match_id):
    # Query to delete the match
    sql = text("DELETE FROM matches WHERE match_id = :match_id")
    
    try:
        with db.engine.connect() as conn:
            conn.execute(sql, {'match_id': match_id})
            conn.commit() 
            flash(f"Match with ID {match_id} deleted successfully!", 'success')

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

    # Query to fetch goals along with match and team details
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

    # Query to retrieve the list of player names
    players_sql = text("SELECT player_id, player_name FROM players ORDER BY player_name")

    # Query to retrieve match details
    matches_sql = text("""
        SELECT 
            m.match_id, ht.team_name AS home_team_name, at.team_name AS away_team_name, t.year AS tournament_year
        FROM 
            matches m
        JOIN 
            teams ht ON m.home_team_id = ht.team_id
        JOIN 
            teams at ON m.away_team_id = at.team_id
        JOIN 
            tournaments t ON m.tournament_id = t.tournament_id
        ORDER BY 
            m.match_id
    """)

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

    if page > total_pages:
        page = total_pages
    visible_pages = 5  
    start_page = max(1, page - visible_pages // 2)
    end_page = min(total_pages, start_page + visible_pages - 1)

    if end_page - start_page < visible_pages and start_page > 1:
        start_page = max(1, end_page - visible_pages + 1)

    return render_template("adminGoals.html", goals=goals, players=players, matches=matches, page=page, total_pages=total_pages, start_page=start_page, end_page=end_page)

# Add Goals
@adminRoutes.route('/goals/add', methods=['POST'])
def add_goal():
    if request.method == 'POST':
        player_id = request.form.get('player', type=int)
        match_id = request.form.get('match', type=int)
        minute_scored = request.form.get('minute', type=int)
        is_penalty = 'penalty' in request.form  
        is_own_goal = 'ownGoal' in request.form  

        # Query for insertion of new goal
        sql = text("""
            INSERT 
                INTO goals (player_id, match_id, minute_scored, is_penalty, is_own_goal)
            VALUES 
                (:player_id, :match_id, :minute_scored, :is_penalty, :is_own_goal)
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
                conn.commit() 
                flash('Goal recorded successfully!', 'success')

        except Exception as e:
            flash(f"Error adding goal: {str(e)}", 'danger')

        return redirect(url_for('adminRoutes.goals_management')) 

    flash('Failed to record the goal. Please try again.', 'danger')
    return redirect(url_for('adminRoutes.goals_management'))

# Update Goal
@adminRoutes.route('/goals/update/<int:goal_id>', methods=['POST'])
def update_goal(goal_id):
    player_id = request.form.get('player', type=int)
    match_id = request.form.get('match', type=int)
    minute_scored = request.form.get('minute', type=str)  
    is_penalty = request.form.get('penalty') is not None  
    is_own_goal = request.form.get('ownGoal') is not None  

    # Query to update the goal record
    sql = text("""
        UPDATE 
            goals
        SET 
            player_id = :player_id,
            match_id = :match_id,
            minute_scored = :minute_scored,
            is_penalty = :is_penalty,
            is_own_goal = :is_own_goal
        WHERE 
            goal_id = :goal_id
    """)

    params = {
        'player_id': player_id,
        'match_id': match_id,
        'minute_scored': minute_scored,
        'is_penalty': is_penalty,
        'is_own_goal': is_own_goal,
        'goal_id': goal_id
    }

    try:
        with db.engine.connect() as conn:
            conn.execute(sql, params)
            conn.commit() 

            flash(f"Goal {goal_id} updated successfully!", 'success')

    except Exception as e:
        flash(f"Error updating goal: {str(e)}", 'danger')

    return redirect(url_for('adminRoutes.goals_management'))

# Delete Goal
@adminRoutes.route('/goals/delete/<int:goal_id>', methods=['POST'])
def delete_goal(goal_id):
    # Query to delete the goal 
    sql = text("DELETE FROM goals WHERE goal_id = :goal_id")

    try:
        with db.engine.connect() as conn:
            conn.execute(sql, {'goal_id': goal_id})
            conn.commit() 

            flash(f"Goal with ID {goal_id} deleted successfully!", 'success')

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

    # Query to fetch tournaments along with team details
    sql = text("""
        SELECT
            t.tournament_id,
            t.year,
            t.host_country,
            t.winner_team_id,
            t.runner_up_team_id,
            t.matches_played,
            ht.team_name AS winner_team_name,
            at.team_name AS runner_up_name
        FROM
            tournaments t
        JOIN
            teams ht ON t.winner_team_id = ht.team_id
        JOIN
            teams at ON t.runner_up_team_id = at.team_id
        ORDER BY
             t.tournament_id
        LIMIT :limit OFFSET :offset
    """)

    # Query to retrieve the list of team names
    teams_sql = text("SELECT team_id, team_name FROM teams ORDER BY team_name")
        
    count_sql = text("SELECT COUNT(*) FROM tournaments")

    with db.engine.connect() as conn:
        result = conn.execute(sql, {'limit': per_page, 'offset': offset})
        tournaments = []
        for row in result:
            tournaments.append({
                'tournament_id': row.tournament_id,
                'year': row.year,
                'host_country': row.host_country,
                'winner_team_name': row.winner_team_name,
                'runner_up_name': row.runner_up_name,
                'matches_played': row.matches_played
            })

        total_tournaments = conn.execute(count_sql).scalar()

        teams = [{'team_id': row.team_id, 'team_name': row.team_name} for row in conn.execute(teams_sql)]

    total_pages = (total_tournaments // per_page) + (1 if total_tournaments % per_page > 0 else 0)

    if page > total_pages:
        page = total_pages
    visible_pages = 5  
    start_page = max(1, page - visible_pages // 2)
    end_page = min(total_pages, start_page + visible_pages - 1)

    if end_page - start_page < visible_pages and start_page > 1:
        start_page = max(1, end_page - visible_pages + 1)

    return render_template("adminTournaments.html", tournaments=tournaments, teams=teams, page=page, total_pages=total_pages, start_page=start_page, end_page=end_page)

# Add Tournament
@adminRoutes.route('/tournaments/add', methods=['POST'])
def add_tournament():
    if request.method == 'POST':
        year = request.form.get('year')
        host_country = request.form.get('hostCountry')
        winner_team_id = request.form.get('winner')
        runner_up_team_id = request.form.get('runnerUp')
        matches_played = request.form.get('matchesPlayed')

        # Query to insert a new tournament
        sql = text("""
            INSERT 
                INTO tournaments (year, host_country, winner_team_id, runner_up_team_id, matches_played)
            VALUES 
                (:year, :host_country, :winner_team_id, :runner_up_team_id, :matches_played)
        """)

        try:
            with db.engine.connect() as conn:
                conn.execute(sql, {
                    'year': year,
                    'host_country': host_country,
                    'winner_team_id': winner_team_id,
                    'runner_up_team_id': runner_up_team_id,
                    'matches_played': matches_played
                })
                conn.commit()
                flash('Tournament added successfully!', 'success')

        except Exception as e:
            flash(f"Error adding tournament: {str(e)}", 'danger')

        return redirect(url_for('adminRoutes.tournaments_management'))

# Update Tournament
@adminRoutes.route('/tournaments/update/<int:tournament_id>', methods=['POST'])
def update_tournament(tournament_id):
    if request.method == 'POST':
        year = request.form.get('year')
        host_country = request.form.get('hostCountry')
        winner_team_id = request.form.get('winner')
        runner_up_team_id = request.form.get('runnerUp')
        matches_played = request.form.get('matchesPlayed')

        sql = text("""
            UPDATE 
                tournaments
            SET 
                year = :year, host_country = :host_country, 
                winner_team_id = :winner_team_id, 
                runner_up_team_id = :runner_up_team_id, 
                matches_played = :matches_played
            WHERE 
                tournament_id = :tournament_id
        """)

        try:
            with db.engine.connect() as conn:
                conn.execute(sql, {
                    'tournament_id': tournament_id,
                    'year': year,
                    'host_country': host_country,
                    'winner_team_id': winner_team_id,
                    'runner_up_team_id': runner_up_team_id,
                    'matches_played': matches_played
                })
                conn.commit()
                flash(f"Tournament {tournament_id} updated successfully!", 'success')

        except Exception as e:
            flash(f"Error updating tournament: {str(e)}", 'danger')

        return redirect(url_for('adminRoutes.tournaments_management'))

# Delete Tournament
@adminRoutes.route('/tournaments/delete/<int:tournament_id>', methods=['POST'])
def delete_tournament(tournament_id):
    sql = text("DELETE FROM tournaments WHERE tournament_id = :tournament_id")

    try:
        with db.engine.connect() as conn:
            conn.execute(sql, {'tournament_id': tournament_id})
            conn.commit()
            flash(f"Tournament {tournament_id} deleted successfully!", 'success')
    except Exception as e:
        flash(f"Error deleting tournament: {str(e)}", 'danger')

    return redirect(url_for('adminRoutes.tournaments_management'))
