from flask import Blueprint, render_template

adminRoutes = Blueprint("adminRoutes", __name__, template_folder="templates")

@adminRoutes.route("/")
def adminLanding ():
    return render_template("adminLanding.html")