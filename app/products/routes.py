from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from . import products_bp
from ..extensions import db
from sqlalchemy import func
from datetime import datetime
from ..models import Product, Sale, InventoryMovement


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

    # switches del form
    merge_if_exists = request.form.get("merge_if_exists") == "1"
    update_price_if_merge = request.form.get("update_price_if_merge") == "1"
    is_active = request.form.get("is_active", "1") == "1"

    if not name or price is None:
        flash("Nombre y precio son obligatorios.", "danger")
        return redirect(url_for("products.new_product"))

    if price < 0:
        flash("El precio no puede ser negativo.", "danger")
        return redirect(url_for("products.new_product"))

    if stock < 0:
        flash("El stock no puede ser negativo.", "danger")
        return redirect(url_for("products.new_product"))

    # Buscar producto existente (mismo negocio, nombre case-insensitive)
    existing = Product.query.filter(
        Product.business_id == current_user.business_id,
        func.lower(Product.name) == name.lower()
    ).first()

    # ===== Caso 1: Existe y queremos MERGE =====
    if existing and merge_if_exists:
        before = int(existing.stock or 0)
        after = before + int(stock)

        # si el usuario puso stock 0 y solo quiere evitar duplicado:
        # igual permitimos actualizar precio/estado si lo marcó
        if update_price_if_merge:
            existing.price = price

        existing.is_active = is_active

        # si hay stock para sumar, registramos movimiento IN
        if stock > 0:
            mv = InventoryMovement(
                business_id=current_user.business_id,
                product_id=existing.id,
                user_id=current_user.id,
                movement_type="in",
                quantity=int(stock),
                stock_before=before,
                stock_after=after,
                note="Entrada por alta/merge de producto",
                created_at=datetime.utcnow()
            )
            db.session.add(mv)
            existing.stock = after

        db.session.commit()

        flash("Producto existente actualizado ✅ (se evitó duplicado)", "success")
        return redirect(url_for("products.edit_product", product_id=existing.id))

    # ===== Caso 2: Existe pero NO queremos merge =====
    if existing and not merge_if_exists:
        flash("Ese producto ya existe. Activa 'sumar stock al existente' o edítalo.", "warning")
        return redirect(url_for("products.edit_product", product_id=existing.id))

    # ===== Caso 3: No existe => Crear nuevo =====
    product = Product(
        name=name,
        price=price,
        stock=int(stock),
        business_id=current_user.business_id,
        is_active=is_active
    )

    db.session.add(product)
    db.session.flush()  # ya tenemos product.id

    # Kardex automático si nace con stock
    if stock > 0:
        mv = InventoryMovement(
            business_id=current_user.business_id,
            product_id=product.id,
            user_id=current_user.id,
            movement_type="in",
            quantity=int(stock),
            stock_before=0,
            stock_after=int(stock),
            note="Stock inicial (alta de producto)",
            created_at=datetime.utcnow()
        )
        db.session.add(mv)

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
