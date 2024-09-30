from flask import Flask, redirect, url_for, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import text

from os import getenv
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)


#Configuration for PostgreSQL database
app.config['SQLALCHEMY_DATABASE_URI'] = getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = '\xb0\t\xce\x90\x1a\xb7\xfb\x1e\xdb\xb5\xdd\xc0'

# Initialize the database
db = SQLAlchemy(app)

# Import routes
from admin.routes import adminRoutes
app.register_blueprint(adminRoutes, url_prefix="/admin")


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