from flask import jsonify

from app import app


@app.route("/next-webinars", methods=["GET"])
def get_webinars_list():
    return jsonify(
        [
            {
                "time": 1630933800,
                "title": "Presentation Mobilic",
                "link": "abc",
            },
            {
                "time": 1631695500,
                "title": "Autre chose à propos de Mobilic",
                "link": "abc",
            },
            {
                "time": 1632306600,
                "title": "Quelque chose de très très très très très très très très très très très très très très très très looooooooooooooooooong à propos de Mobilic",
                "link": "abc",
            },
        ]
    )
