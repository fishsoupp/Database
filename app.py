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

@app.route('/test-db')
def test_db():
    try:
        # Attempt to query the database
        result = db.session.execute(text('SELECT 1'))
        return f"Database connection test successful: {result.scalar()}"
    except Exception as e:
        return f"Database connection test failed: {str(e)}"

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