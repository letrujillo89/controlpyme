from flask import Flask
from .config import Config
from .extensions import db, login_manager, migrate
from flask import redirect, url_for, request
from flask_login import current_user
from datetime import datetime



def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from .models import User  # importante para el user_loader

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Blueprints
    from .auth import auth_bp
    from .main import main_bp    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)    
    from .products import products_bp
    app.register_blueprint(products_bp)
    from .sales import sales_bp
    app.register_blueprint(sales_bp)
    from .reports import reports_bp
    app.register_blueprint(reports_bp)
    from .billing import billing_bp
    app.register_blueprint(billing_bp)
    from .admin import admin_bp
    app.register_blueprint(admin_bp)
    from .inventory import inventory_bp
    app.register_blueprint(inventory_bp)


    @app.before_request
    def enforce_billing():
        # Si no está logueado, no hacemos nada
        if not current_user.is_authenticated:
            return
            
        # ⭐ ADMIN NUNCA BLOQUEADO
        if getattr(current_user, "is_admin", False):
            return
            
        biz = current_user.business

        # Si es Pro, no bloqueamos
        if biz.is_pro:
            return

        # Si aún está en trial, no bloqueamos
        if biz.trial_ends_at and biz.trial_ends_at > datetime.utcnow():
            return

        # Rutas permitidas aun si expiró
        allowed_endpoints = {
            "auth.logout",
            "billing.expired",
            "billing.upgrade",
            "static"
        }

        # Si quiere ir a esas rutas, dejarlo
        if request.endpoint in allowed_endpoints or (request.endpoint and request.endpoint.startswith("auth.")):
            return

        # Si expiró, mandarlo a pantalla de pago
        return redirect(url_for("billing.expired"))
        
    @app.context_processor
    def inject_now():
        from datetime import datetime
        return {"now": datetime.utcnow()}

    @app.context_processor
    def inject_now():
        from datetime import datetime
        return {"now": datetime.utcnow()}


    if app.config.get("ENV") == "development":
        with app.app_context():
            db.create_all()

    return app

