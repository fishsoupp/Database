from flask import Flask, redirect, url_for, render_template
from admin.routes import adminRoutes

app = Flask(__name__)
app.register_blueprint(adminRoutes, url_prefix="/admin")

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

@app.route('/stats')
def stats():
    return render_template("statistics.html")


if __name__ == '__main__':
    app.run(debug=True)