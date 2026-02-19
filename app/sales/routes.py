from flask import render_template, request, redirect, url_for, flash, abort, session
from flask_login import login_required, current_user
from . import sales_bp
from ..extensions import db
from ..models import Product, Sale, InventoryMovement


@sales_bp.get("/new")
@login_required
def new_sale():
    products = Product.query.filter_by(
        business_id=current_user.business_id,
        is_active=True
    ).order_by(Product.name.asc()).all()

    # Últimas ventas (para mostrar abajo)
    recent_sales = Sale.query.filter_by(
        business_id=current_user.business_id
    ).order_by(Sale.created_at.desc()).limit(10).all()

    # Última venta (para resaltar)
    last_sale = None
    last_sale_id = session.get("last_sale_id")
    if last_sale_id:
        last_sale = Sale.query.filter_by(
            id=last_sale_id,
            business_id=current_user.business_id
        ).first()

    return render_template(
        "sales/new.html",
        products=products,
        recent_sales=recent_sales,
        last_sale=last_sale
    )


@sales_bp.post("/new")
@login_required
def create_sale():
    product_id = request.form.get("product_id")
    quantity = request.form.get("quantity", type=int)

    # Validaciones básicas
    if not product_id:
        flash("Selecciona un producto.", "danger")
        return redirect(url_for("sales.new_sale"))

    if quantity is None or quantity <= 0:
        flash("Cantidad inválida.", "danger")
        return redirect(url_for("sales.new_sale"))

    product = Product.query.get_or_404(product_id)

    # Seguridad multi-negocio
    if product.business_id != current_user.business_id:
        abort(403)

    # No vender inactivos
    if not product.is_active:
        flash("Producto inactivo. Actívalo para vender.", "warning")
        return redirect(url_for("sales.new_sale"))

    # Stock suficiente
    if product.stock < quantity:
        flash("Stock insuficiente.", "danger")
        return redirect(url_for("sales.new_sale"))

    # Kardex: calcular before/after
    stock_before = int(product.stock)
    stock_after = stock_before - quantity

    # Actualizar stock
    product.stock = stock_after

    # Registrar venta (guardamos nombre/precio por historial)
    sale = Sale(
        business_id=current_user.business_id,
        product_id=product.id,
        product_name=product.name,
        unit_price=product.price,
        quantity=quantity,
        total=product.price * quantity
    )

    db.session.add(sale)
    db.session.flush()  # ya existe sale.id sin commit

    # Kardex: movimiento OUT por venta
    movement = InventoryMovement(
        business_id=current_user.business_id,
        product_id=product.id,
        user_id=current_user.id,
        movement_type="out",
        quantity=quantity,
        stock_before=stock_before,
        stock_after=stock_after,
        note=f"Venta #{sale.id}"
    )

    db.session.add(movement)
    db.session.commit()

    session["last_sale_id"] = sale.id
    flash("Venta registrada ✅", "success")
    return redirect(url_for("sales.new_sale"))

