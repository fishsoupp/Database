from flask import Blueprint, render_template, redirect, url_for, flash, session, request
from .forms import LoginForm

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
        if form.username.data == 'fifa_admin' and form.password.data == 'fifa_admin!':
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
@adminRoutes.route("/players")
def players_management():
    # Simply serve the players management page
    return render_template("adminPlayers.html")


### Matches Management ###
@adminRoutes.route("/matches")
def matches_management():
    # Serve the matches management page
    return render_template("adminMatches.html")

### Goals Management ###
@adminRoutes.route("/goals")
def goals_management():
    # Serve the goals management page
    return render_template("adminGoals.html")


### Tournaments Management ###
@adminRoutes.route("/tournaments")
def tournaments_management():
    # Serve the tournaments management page
    return render_template("adminTournaments.html")

