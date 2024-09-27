from flask import Flask, redirect, url_for, render_template
from flask_sqlalchemy import SQLAlchemy
from admin.routes import adminRoutes

app = Flask(__name__)
app.register_blueprint(adminRoutes, url_prefix="/admin")

# Configuration for PostgreSQL database
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:password@localhost/TicketGrabdb'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize the database
db = SQLAlchemy(app)


@app.route('/')
def hello_world():
    return render_template("index.html")

if __name__ == '__main__':
    app.run(debug=True)