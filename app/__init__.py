import os
from flask import Flask
from .extensions import db, login_manager, mail, migrate
from .config import config_by_name


def create_app(config_name=None):
    app = Flask(__name__)

    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "production")

    app.config.from_object(config_by_name[config_name])

    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)

    from .routes.auth import auth_bp
    from .routes.admin import admin_bp
    from .routes.podcasts import podcasts_bp
    from .routes.guests import guests_bp
    from .routes.invitations import invitations_bp
    from .routes.main import main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(podcasts_bp, url_prefix="/podcasts")
    app.register_blueprint(guests_bp, url_prefix="/guests")
    app.register_blueprint(invitations_bp, url_prefix="/invitations")

    _register_cli(app)

    return app


def _register_cli(app):
    @app.cli.command("seed")
    def seed():
        from .seed import run_seed
        run_seed()
        print("Seeding complete.")
