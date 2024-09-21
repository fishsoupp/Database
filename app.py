from flask import Flask, redirect, url_for, render_template
from admin.routes import adminRoutes

app = Flask(__name__)
app.register_blueprint(adminRoutes, url_prefix="/admin")

@app.route('/')
def hello_world():
    return render_template("index.html")

if __name__ == '__main__':
    app.run(debug=True)