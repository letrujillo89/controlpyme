from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import products_bp
from ..extensions import db
from ..models import Product

@products_bp.get("/")
@login_required
def list_products():
    products = Product.query.filter_by(
        business_id=current_user.business_id
    ).all()

    return render_template("products/list.html", products=products)


@products_bp.get("/new")
@login_required
def new_product():
    return render_template("products/new.html")


@products_bp.post("/new")
@login_required
def create_product():

    name = request.form.get("name")
    price = request.form.get("price")
    stock = request.form.get("stock")

    product = Product(
        name=name,
        price=price,
        stock=stock,
        business_id=current_user.business_id
    )

    db.session.add(product)
    db.session.commit()

    flash("Producto creado ✅", "success")
    return redirect(url_for("products.list_products"))
