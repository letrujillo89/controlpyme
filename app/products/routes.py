from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from . import products_bp
from ..extensions import db
from ..models import Product, Sale

@products_bp.get("/")
@login_required
def list_products():
    products = Product.query.filter_by(
        business_id=current_user.business_id
    ).order_by(Product.is_active.desc(), Product.name.asc()).all()


    return render_template("products/list.html", products=products)


@products_bp.get("/new")
@login_required
def new_product():
    return render_template("products/new.html")


@products_bp.post("/new")
@login_required
def create_product():

    name = (request.form.get("name") or "").strip()
    price = request.form.get("price", type=float)
    stock = request.form.get("stock", type=int) or 0

    if not name or price is None:
        flash("Nombre y precio son obligatorios.", "danger")
        return redirect(url_for("products.new_product"))

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

@products_bp.get("/<int:product_id>/edit")
@login_required
def edit_product(product_id):
    p = Product.query.get_or_404(product_id)
    if p.business_id != current_user.business_id:
        abort(403)
    return render_template("products/edit.html", p=p)

@products_bp.post("/<int:product_id>/edit")
@login_required
def edit_product_post(product_id):
    p = Product.query.get_or_404(product_id)
    if p.business_id != current_user.business_id:
        abort(403)

    name = (request.form.get("name") or "").strip()
    price = request.form.get("price", type=float)
    stock = request.form.get("stock", type=int)

    if not name or price is None:
        flash("Nombre y precio son obligatorios.", "danger")
        return redirect(url_for("products.edit_product", product_id=product_id))

    if price < 0:
        flash("El precio no puede ser negativo.", "danger")
        return redirect(url_for("products.edit_product", product_id=product_id))

    if stock is None:
        stock = int(p.stock or 0)

    p.name = name
    p.price = price
    p.stock = stock

    db.session.commit()
    flash("Producto actualizado ✅", "success")
    return redirect(url_for("products.list_products"))

@products_bp.post("/<int:product_id>/toggle")
@login_required
def toggle_product(product_id):
    p = Product.query.get_or_404(product_id)
    if p.business_id != current_user.business_id:
        abort(403)

    p.is_active = not bool(p.is_active)
    db.session.commit()

    flash("Producto actualizado ✅", "success")
    return redirect(url_for("products.list_products"))

@products_bp.post("/<int:product_id>/delete")
@login_required
def delete_product(product_id):
    p = Product.query.get_or_404(product_id)
    if p.business_id != current_user.business_id:
        abort(403)

    # Si tiene ventas, NO se elimina (para no perder historial)
    has_sales = Sale.query.filter_by(
        business_id=current_user.business_id,
        product_id=p.id
    ).count() > 0

    if has_sales:
        flash("Este producto ya tiene ventas. Mejor desactívalo para conservar historial.", "warning")
        return redirect(url_for("products.list_products"))

    db.session.delete(p)
    db.session.commit()
    flash("Producto eliminado ✅", "success")
    return redirect(url_for("products.list_products"))

@products_bp.post("/<int:product_id>/price")
@login_required
def update_price(product_id):
    p = Product.query.get_or_404(product_id)
    if p.business_id != current_user.business_id:
        abort(403)

    price = request.form.get("price", type=float)
    if price is None or price < 0:
        flash("Precio inválido.", "danger")
        return redirect(url_for("products.list_products"))

    p.price = price
    db.session.commit()
    flash("Precio actualizado ✅", "success")
    return redirect(url_for("products.list_products"))
