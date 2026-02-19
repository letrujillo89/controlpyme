from flask import render_template, redirect, url_for
from flask_login import login_required, current_user
from . import main_bp
from datetime import datetime, date, time, timedelta
from sqlalchemy import func
from ..models import Sale, SaleItem, Product
from ..extensions import db


@main_bp.get("/")
def landing():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("landing.html")


@main_bp.get("/dashboard")
@login_required
def dashboard():
    start = datetime.combine(date.today(), time.min)
    end = datetime.combine(date.today(), time.max)

    # Tickets del día
    sales_today = Sale.query.filter(
        Sale.business_id == current_user.business_id,
        Sale.created_at >= start,
        Sale.created_at <= end
    ).all()

    total_today = float(sum([s.total for s in sales_today])) if sales_today else 0.0
    sales_count = len(sales_today)

    products_count = Product.query.filter_by(
        business_id=current_user.business_id
    ).count()

    # Últimos tickets (para mostrar en dashboard)
    recent_sales = Sale.query.filter_by(
        business_id=current_user.business_id
    ).order_by(Sale.created_at.desc()).limit(10).all()

    # items para esos tickets (en una sola consulta)
    recent_ids = [s.id for s in recent_sales]
    items_map = {}
    if recent_ids:
        items = SaleItem.query.filter(
            SaleItem.sale_id.in_(recent_ids)
        ).order_by(SaleItem.sale_id.desc()).all()

        for it in items:
            items_map.setdefault(it.sale_id, []).append(it)

    return render_template(
        "main/dashboard.html",
        total_today=total_today,
        sales_count=sales_count,
        products_count=products_count,
        recent_sales=recent_sales,
        items_map=items_map
    )
