import os
import warnings

from flask import Flask, send_from_directory, jsonify

from config import Config
from extensions import db, login_manager


def create_app(config_class=Config):
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config.from_object(config_class)

    if config_class.using_dev_secret() and not app.debug:
        warnings.warn("SECRET_KEY не задан, запустите scripts/gen_secrets.py", stacklevel=1)

    db.init_app(app)
    login_manager.init_app(app)

    from models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        return jsonify(error="Требуется авторизация"), 401

    from blueprints.auth import auth_bp
    from blueprints.courses import courses_bp
    from blueprints.quiz import quiz_bp
    from blueprints.phishing import phishing_bp
    from blueprints.assistant import assistant_bp
    from blueprints.stats import stats_bp
    from blueprints.scan import scan_bp
    from blueprints.admin import admin_bp

    for bp in (auth_bp, courses_bp, quiz_bp, phishing_bp, assistant_bp, stats_bp, scan_bp, admin_bp):
        app.register_blueprint(bp)

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.get("/<path:page>")
    def pages(page):
        if os.path.isfile(os.path.join(app.static_folder, page)):
            return send_from_directory(app.static_folder, page)
        target = page if page.endswith(".html") else f"{page}.html"
        if os.path.isfile(os.path.join(app.static_folder, target)):
            return send_from_directory(app.static_folder, target)
        return send_from_directory(app.static_folder, "index.html")

    @app.get("/api/health")
    def health():
        return jsonify(status="ok", service="CyberBook")

    with app.app_context():
        db.create_all()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
