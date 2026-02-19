from flask import render_template, request, redirect, url_for, flash, abort, Response
from flask_login import login_required, current_user
from datetime import datetime
import csv
from io import StringIO

from . import inventory_bp
from ..extensions import db
from ..models import Product, InventoryMovement


def _same_business(product: Product) -> bool:
    return product.business_id == current_user.business_id


@inventory_bp.get("/")
@login_required
def movements_home():
    # filtros
    product_id = request.args.get("product_id", type=int)
    movement_type = (request.args.get("movement_type") or "").strip()  # in/out/adjust
    limit = request.args.get("limit", default=200, type=int)

    if limit not in (50, 100, 200, 500):
        limit = 200

    q = InventoryMovement.query.filter(
        InventoryMovement.business_id == current_user.business_id
    )

    if product_id:
        q = q.filter(InventoryMovement.product_id == product_id)

    if movement_type in {"in", "out", "adjust"}:
        q = q.filter(InventoryMovement.movement_type == movement_type)

    movements = q.order_by(InventoryMovement.created_at.desc()).limit(limit).all()

    products = Product.query.filter_by(
        business_id=current_user.business_id
    ).order_by(Product.name.asc()).all()

    return render_template(
        "inventory/movements.html",
        movements=movements,
        products=products,
        product_id=product_id,
        movement_type=movement_type,
        limit=limit
    )


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

    # opcional: si está inactivo, permitir solo ajustes/entradas
    if not bool(getattr(product, "is_active", True)) and movement_type == "out":
        flash("Producto inactivo. Actívalo para poder dar salida.", "warning")
        return redirect(url_for("inventory.movements_home", product_id=product_id))

    if qty is None or qty <= 0:
        flash("Cantidad inválida. Debe ser mayor que 0.", "danger")
        return redirect(url_for("inventory.movements_home", product_id=product_id))

    before = int(product.stock or 0)

    # calcular stock_after
    if movement_type == "in":
        after = before + qty
        movement_qty = qty
    elif movement_type == "out":
        after = before - qty
        if after < 0:
            flash("No puedes sacar más de lo que hay en stock.", "warning")
            return redirect(url_for("inventory.movements_home", product_id=product_id))
        movement_qty = qty
    else:
        # adjust: qty se interpreta como NUEVO STOCK
        after = qty
        movement_qty = abs(after - before) if after != before else 0

    if movement_type == "adjust" and movement_qty == 0:
        flash("El ajuste no cambió el stock.", "info")
        return redirect(url_for("inventory.movements_home", product_id=product_id))

    # actualizar stock y guardar movimiento
    product.stock = after

    movement = InventoryMovement(
        business_id=current_user.business_id,
        product_id=product.id,
        user_id=current_user.id,
        movement_type=movement_type,
        quantity=movement_qty,
        stock_before=before,
        stock_after=after,
        note=note or None,
        created_at=datetime.utcnow(),
    )

    db.session.add(movement)
    db.session.commit()

    flash("Movimiento registrado ✅", "success")
    return redirect(url_for("inventory.movements_home", product_id=product_id))


@inventory_bp.get("/export/csv")
@login_required
def export_movements_csv():
    product_id = request.args.get("product_id", type=int)
    movement_type = (request.args.get("movement_type") or "").strip()
    limit = request.args.get("limit", default=500, type=int)

    if limit not in (100, 200, 500, 1000):
        limit = 500

    q = db.session.query(
        InventoryMovement.created_at,
        InventoryMovement.movement_type,
        InventoryMovement.quantity,
        InventoryMovement.stock_before,
        InventoryMovement.stock_after,
        InventoryMovement.note,
        Product.name.label("product_name")
    ).join(
        Product, Product.id == InventoryMovement.product_id
    ).filter(
        InventoryMovement.business_id == current_user.business_id
    )

    if product_id:
        q = q.filter(InventoryMovement.product_id == product_id)

    if movement_type in {"in", "out", "adjust"}:
        q = q.filter(InventoryMovement.movement_type == movement_type)

    rows = q.order_by(InventoryMovement.created_at.desc()).limit(limit).all()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["fecha", "tipo", "producto", "cantidad", "stock_antes", "stock_despues", "nota"])

    for r in rows:
        writer.writerow([
            r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            r.movement_type,
            r.product_name,
            int(r.quantity),
            int(r.stock_before),
            int(r.stock_after),
            r.note or ""
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=kardex_{datetime.utcnow().date()}.csv"}
    )
