from flask import render_template, redirect, url_for
from flask_login import login_required, current_user
from . import main_bp
from datetime import datetime, date, time, timedelta
from ..models import Sale, Product


@main_bp.get("/")
def landing():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("landing.html")


@main_bp.get("/dashboard")
@login_required
def dashboard():

    # --- Hoy ---
    start_today = datetime.combine(date.today(), time.min)
    end_today = datetime.combine(date.today(), time.max)

    sales_today = Sale.query.filter(
        Sale.business_id == current_user.business_id,
        Sale.created_at >= start_today,
        Sale.created_at <= end_today
    ).all()

    total_today = sum([float(s.total) for s in sales_today]) if sales_today else 0

    # --- Últimos 7 días ---
    start_7d = datetime.utcnow() - timedelta(days=7)

    sales_7d = Sale.query.filter(
        Sale.business_id == current_user.business_id,
        Sale.created_at >= start_7d
    ).all()

    total_7d = sum([float(s.total) for s in sales_7d]) if sales_7d else 0
    sales_7d_count = len(sales_7d)

    # --- Productos ---
    products_count = Product.query.filter_by(
        business_id=current_user.business_id
    ).count()

    # --- Stock bajo ---
    LOW_STOCK_THRESHOLD = 5  # puedes ajustar
    low_stock = Product.query.filter(
        Product.business_id == current_user.business_id,
        Product.stock <= LOW_STOCK_THRESHOLD
    ).order_by(Product.stock.asc()).limit(8).all()

    low_stock_count = Product.query.filter(
        Product.business_id == current_user.business_id,
        Product.stock <= LOW_STOCK_THRESHOLD
    ).count()

    # --- Últimas ventas ---
    last_sales = Sale.query.filter(
        Sale.business_id == current_user.business_id
    ).order_by(Sale.created_at.desc()).limit(8).all()

    return render_template(
        "main/dashboard.html",
        total_today=total_today,
        sales_count=len(sales_today),
        products_count=products_count,
        total_7d=total_7d,
        sales_7d_count=sales_7d_count,
        low_stock=low_stock,
        low_stock_count=low_stock_count,
        last_sales=last_sales
    )
