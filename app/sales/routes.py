from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from . import sales_bp
from ..extensions import db
from ..models import Product, Sale, InventoryMovement
from datetime import datetime


@sales_bp.get("/new")
@login_required
def new_sale():
    products = Product.query.filter_by(
        business_id=current_user.business_id
        ).order_by(Product.name.asc()).all()


    return render_template("sales/new.html", products=products)


@sales_bp.post("/new")
@login_required
def create_sale():

    product_id = request.form.get("product_id", type=int)
    quantity = request.form.get("quantity", type=int)

    if not product_id:
        flash("Selecciona un producto.", "danger")
        return redirect(url_for("sales.new_sale"))

    if quantity is None or quantity <= 0:
        flash("Cantidad inválida.", "danger")
        return redirect(url_for("sales.new_sale"))

    product = Product.query.get_or_404(product_id)

    # Seguridad: que el producto sea del mismo negocio
    if product.business_id != current_user.business_id:
        abort(403)

    before = int(product.stock or 0)

    if before < quantity:
        flash("Stock insuficiente", "danger")
        return redirect(url_for("sales.new_sale"))

    after = before - quantity

    # 1) Actualizar stock
    product.stock = after

    # 2) Crear venta
    total = product.price * quantity

    sale = Sale(
        business_id=current_user.business_id,
        product_id=product.id,
        product_name=product.name,
        unit_price=product.price,
        quantity=quantity,
        total=total,
        created_at=datetime.utcnow()
    )

    # 3) Crear movimiento kardex (salida)
    movement = InventoryMovement(
        business_id=current_user.business_id,
        product_id=product.id,
        user_id=current_user.id,
        movement_type="out",
        quantity=quantity,           # siempre positiva
        stock_before=before,
        stock_after=after,
        note="Venta automática",
        created_at=datetime.utcnow()
    )

    db.session.add(sale)
    db.session.add(movement)
    db.session.commit()

    flash("Venta registrada ✅", "success")
    return redirect(url_for("main.dashboard"))
