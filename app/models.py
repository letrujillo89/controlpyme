from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from .extensions import db
from datetime import datetime, timedelta

class Business(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)

    # SaaS Billing
    trial_ends_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.utcnow() + timedelta(days=7))
    is_pro = db.Column(db.Boolean, nullable=False, default=False)

    users = db.relationship("User", backref="business", lazy=True)
    payment_status = db.Column(db.String(20), default="trial")
    # valores:    # trial    # pending    # approved
    payment_status = db.Column(db.String(20), nullable=False, default="trial")
    # trial | pending | approved

    
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False)
    
    is_admin = db.Column(db.Boolean, default=False)

    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    business_id = db.Column(
        db.Integer,
        db.ForeignKey("business.id"),
        nullable=False,
        index=True
    )

    name = db.Column(db.String(150), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    business = db.relationship("Business")

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=True, index=True)
    product_name = db.Column(db.String(150), nullable=True)
    unit_price = db.Column(db.Numeric(10, 2), nullable=True)
    quantity = db.Column(db.Integer, nullable=True)
    total = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    product = db.relationship("Product")

class PaymentProof(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)

    filename = db.Column(db.String(255), nullable=False)     # nombre guardado en disco
    original_name = db.Column(db.String(255), nullable=True) # nombre original
    mime_type = db.Column(db.String(80), nullable=True)

    status = db.Column(db.String(20), nullable=False, default="pending")
    # pending | approved | rejected

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    business = db.relationship("Business")
    user = db.relationship("User")
    
class InventoryMovement(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)

    movement_type = db.Column(db.String(20), nullable=False)  # in | out | adjust
    quantity = db.Column(db.Integer, nullable=False)          # cantidad del movimiento (siempre positiva)
    stock_before = db.Column(db.Integer, nullable=False)
    stock_after = db.Column(db.Integer, nullable=False)

    note = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    business = db.relationship("Business")
    product = db.relationship("Product")
    user = db.relationship("User")
    
class SaleItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    sale_id = db.Column(
        db.Integer,
        db.ForeignKey("sale.id"),
        nullable=False,
        index=True
    )

    product_id = db.Column(
        db.Integer,
        db.ForeignKey("product.id"),
        nullable=False
    )

    product_name = db.Column(db.String(150), nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Numeric(10, 2), nullable=False)

    sale = db.relationship("Sale", backref="items")
    product = db.relationship("Product")
