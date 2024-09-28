from flask import Flask, redirect, url_for, render_template
from flask_sqlalchemy import SQLAlchemy
from admin.routes import adminRoutes

app = Flask(__name__)
app.register_blueprint(adminRoutes, url_prefix="/admin")

#Configuration for PostgreSQL database
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://fifa_admin:fifa_admin!@localhost/fifa_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


# Initialize the database
db = SQLAlchemy(app)

@app.route('/')
def home():
    return render_template("index.html")

@app.route('/index')
def index():
    return render_template("index.html")


@app.route('/ranking')
def ranking():
    return render_template("ranking.html")

@app.route('/teams')
def teams():
    return render_template("teams.html")

@app.route('/players')
def players():
    return render_template("players.html")

@app.route('/match')
def stats():
    return render_template("matches.html")


if __name__ == '__main__':
    app.run(debug=True)