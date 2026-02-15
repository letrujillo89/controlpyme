from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from datetime import datetime

from . import inventory_bp
from ..extensions import db
from ..models import Product, InventoryMovement


def _same_business(product: Product) -> bool:
    return product.business_id == current_user.business_id


@inventory_bp.get("/")
@login_required
def movements_home():
    # lista últimos movimientos
    movements = InventoryMovement.query.filter(
        InventoryMovement.business_id == current_user.business_id
    ).order_by(InventoryMovement.created_at.desc()).limit(200).all()

    products = Product.query.filter_by(business_id=current_user.business_id).order_by(Product.name.asc()).all()

    return render_template("inventory/movements.html", movements=movements, products=products)


@inventory_bp.post("/move")
@login_required
def create_movement():
    product_id = request.form.get("product_id", type=int)
    movement_type = (request.form.get("movement_type") or "").strip()
    qty = request.form.get("quantity", type=int)
    note = (request.form.get("note") or "").strip()[:255]

    if movement_type not in {"in", "out", "adjust"}:
        flash("Tipo de movimiento inválido.", "danger")
        return redirect(url_for("inventory.movements_home"))

    if not product_id:
        flash("Selecciona un producto.", "danger")
        return redirect(url_for("inventory.movements_home"))

    product = Product.query.get_or_404(product_id)
    if not _same_business(product):
        abort(403)

    if qty is None or qty <= 0:
        flash("Cantidad inválida. Debe ser mayor que 0.", "danger")
        return redirect(url_for("inventory.movements_home"))

    before = int(product.stock or 0)

    # calcular stock_after
    if movement_type == "in":
        after = before + qty
    elif movement_type == "out":
        after = before - qty
        if after < 0:
            flash("No puedes sacar más de lo que hay en stock.", "warning")
            return redirect(url_for("inventory.movements_home"))
    else:
        # adjust: qty se interpreta como NUEVO STOCK
        after = qty
        qty = abs(after - before) if after != before else 0

    # si adjust no cambia nada
    if movement_type == "adjust" and qty == 0:
        flash("El ajuste no cambió el stock.", "info")
        return redirect(url_for("inventory.movements_home"))

    # actualizar stock y guardar movimiento
    product.stock = after

    movement = InventoryMovement(
        business_id=current_user.business_id,
        product_id=product.id,
        user_id=current_user.id,
        movement_type=movement_type,
        quantity=qty,
        stock_before=before,
        stock_after=after,
        note=note or None,
        created_at=datetime.utcnow(),
    )

    db.session.add(movement)
    db.session.commit()

    flash("Movimiento registrado ✅", "success")
    return redirect(url_for("inventory.movements_home"))
