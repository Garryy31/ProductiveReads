from pathlib import Path

from flask import Flask

from config import Config
from models.db import close_db, init_db
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.books import books_bp
from routes.cart import cart_bp
from routes.checkout import checkout_bp
from routes.main import main_bp
from routes.orders import orders_bp
from routes.payment import payment_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    app.teardown_appcontext(close_db)
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(books_bp)
    app.register_blueprint(cart_bp)
    app.register_blueprint(checkout_bp)
    app.register_blueprint(payment_bp)
    app.register_blueprint(orders_bp)

    with app.app_context():
        init_db()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
