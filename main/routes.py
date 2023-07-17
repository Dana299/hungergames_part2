from flask import render_template, request

from main import app


@app.route("/resources/", methods=["GET"])
def index():
    app.logger.info(f"GET - main page on {request.url} visited")
    return render_template("index.html")


@app.route("/logs/", methods=["GET"])
def get_logs():
    app.logger.info(f"GET - {request.url} visited")
    return render_template("logs.html")


@app.route("/add-resource/", methods=["GET", "POST"])
def add_resource():
    app.logger.info("User visit add_resource page")
    return render_template('add_resource.html')


@app.route("/test_logs/", methods=["GET"])
def test_logs():
    # app.logger.exception("EXCEPTION")
    app.logger.critical("critical")
    app.logger.warning("warning")
    app.logger.debug("debug")
    app.logger.info("info")
    return "<h1>Test log messages for all levels called. Check web log viewer</h1>"
