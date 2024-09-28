from flask import Flask, redirect, url_for, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import text
from admin.routes import adminRoutes

from os import getenv
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.register_blueprint(adminRoutes, url_prefix="/admin")

#Configuration for PostgreSQL database
app.config['SQLALCHEMY_DATABASE_URI'] = getenv('DATABASE_URL')
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
    # Use a connection context manager to execute the query
    with db.engine.connect() as connection:
        query = text("SELECT team_id, team_name, fifa_code, continent FROM teams")
        result = connection.execute(query)

        teams = []
        for row in result:
            teams.append({
                "team_id": row["team_id"],
                "team_name": row["team_name"],
                "fifa_code": row["fifa_code"],
                "continent": row["continent"]
            })

    return render_template("teams.html", teams=teams)



@app.route('/players')
def players():
    query = text("SELECT player_id, player_name, team_id, position, date_of_birth, caps FROM players")
    result = db.engine.execute(query)
    
    players = []
    for row in result:
        players.append({
            "player_id": row["player_id"],
            "player_name": row["player_name"],
            "team_id": row["team_id"],
            "position": row["position"],
            "date_of_birth": row["date_of_birth"],
            "caps": row["caps"]
        })
    
    return render_template("players.html", players=players)

@app.route('/match')
def stats():
    return render_template("matches.html")

if __name__ == '__main__':
    app.run(debug=True)