from flask import Flask, render_template
from database.models import init_db

app = Flask(__name__)
app.config["SECRET_KEY"] = "netter-pipeline-local"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload")
def upload():
    return render_template("upload.html")


@app.route("/review")
def review():
    return render_template("review.html")


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
