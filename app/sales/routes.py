from flask import render_template, request, redirect, url_for, flash, abort, session
from flask_login import login_required, current_user
from . import sales_bp
from ..extensions import db
from ..models import Product, Sale, SaleItem, InventoryMovement
from decimal import Decimal

def _get_cart():
    cart = session.get("cart", [])
    if not isinstance(cart, list):
        cart = []
    return cart

def _save_cart(cart):
    session["cart"] = cart
    session.modified = True

def _cart_total(cart):
    return sum(Decimal(str(i["total"])) for i in cart) if cart else Decimal("0.00")

@sales_bp.get("/new")
@login_required
def new_sale():
    
    cart = _get_cart()
    cart_total = _cart_total(cart)
    
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
        cart=cart,
        cart_total=cart_total,
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
    
@sales_bp.post("/cart/add")
@login_required
def cart_add():
    product_id = request.form.get("product_id")
    quantity = request.form.get("quantity", type=int)

    if not product_id:
        flash("Selecciona un producto.", "danger")
        return redirect(url_for("sales.new_sale"))

    if quantity is None or quantity <= 0:
        flash("Cantidad inválida.", "danger")
        return redirect(url_for("sales.new_sale"))

    product = Product.query.get_or_404(product_id)
    if product.business_id != current_user.business_id:
        abort(403)

    if not product.is_active:
        flash("Producto inactivo. Actívalo para vender.", "warning")
        return redirect(url_for("sales.new_sale"))

    # Validación stock considerando lo que ya está en carrito
    cart = _get_cart()
    in_cart_qty = sum(int(i["quantity"]) for i in cart if int(i["product_id"]) == product.id)
    if product.stock < (in_cart_qty + quantity):
        flash("Stock insuficiente (considerando el carrito).", "danger")
        return redirect(url_for("sales.new_sale"))

    unit_price = Decimal(str(product.price))
    total = unit_price * Decimal(quantity)

    cart.append({
        "product_id": product.id,
        "product_name": product.name,
        "unit_price": str(unit_price),
        "quantity": int(quantity),
        "total": str(total)
    })

    _save_cart(cart)
    flash("Agregado al carrito ✅", "success")
    return redirect(url_for("sales.new_sale"))

@sales_bp.post("/cart/remove/<int:idx>")
@login_required
def cart_remove(idx):
    cart = _get_cart()
    if idx < 0 or idx >= len(cart):
        flash("Item inválido.", "danger")
        return redirect(url_for("sales.new_sale"))

    cart.pop(idx)
    _save_cart(cart)
    flash("Item eliminado del carrito.", "info")
    return redirect(url_for("sales.new_sale"))

@sales_bp.post("/cart/clear")
@login_required
def cart_clear():
    session.pop("cart", None)
    flash("Carrito vaciado.", "info")
    return redirect(url_for("sales.new_sale"))

@sales_bp.post("/checkout")
@login_required
def checkout():

    cart = session.get("cart", [])

    if not cart:
        flash("El carrito está vacío.", "warning")
        return redirect(url_for("sales.new_sale"))

    try:
        # ===== crear venta (ticket) =====
        sale = Sale(
            business_id=current_user.business_id,
            total=0
        )

        db.session.add(sale)
        db.session.flush()  # obtiene ID sin commit

        total_sale = Decimal("0.00")

        # ===== procesar items =====
        for item in cart:

            product = Product.query.get(item["product_id"])

            if not product:
                raise Exception("Producto no encontrado")

            if not product.is_active:
                raise Exception(f"{product.name} está inactivo")

            quantity = int(item["quantity"])
            unit_price = Decimal(str(item["unit_price"]))
            total = Decimal(str(item["total"]))

            if product.stock < quantity:
                raise Exception(f"Stock insuficiente: {product.name}")

            stock_before = product.stock
            product.stock -= quantity
            stock_after = product.stock

            # ---- SaleItem ----
            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=product.id,
                product_name=product.name,
                unit_price=unit_price,
                quantity=quantity,
                total=total
            )

            db.session.add(sale_item)

            # ---- Kardex OUT ----
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

            total_sale += total

        # ===== actualizar total venta =====
        sale.total = total_sale

        db.session.commit()
        session["last_sale_id"] = sale.id
        session.modified = True

        # ===== limpiar carrito =====
        session.pop("cart", None)

        flash(f"Venta #{sale.id} registrada ✅", "success")

    except Exception as e:
        db.session.rollback()
        flash(str(e), "danger")

    return redirect(url_for("sales.new_sale"))
