from datetime import datetime, timedelta
from flask import render_template, request, url_for, flash, redirect, Response
from flask_login import login_required, current_user
from sqlalchemy import func, desc
from . import reports_bp
from ..models import Sale, SaleItem, Product
from ..extensions import db
import csv
from io import StringIO


@reports_bp.get("/")
@login_required
def reports_home():
    days = request.args.get("days", default=1, type=int)
    low = request.args.get("low", default=5, type=int)

    if days not in (1, 7, 30):
        days = 1
    if low is None or low < 0:
        low = 5

    end = datetime.utcnow()
    start = end - timedelta(days=days)

    # Total vendido + número de tickets (Sale)
    sales_total = db.session.query(
        func.coalesce(func.sum(Sale.total), 0)
    ).filter(
        Sale.business_id == current_user.business_id,
        Sale.created_at >= start,
        Sale.created_at <= end
    ).scalar()

    sales_count = db.session.query(
        func.count(Sale.id)
    ).filter(
        Sale.business_id == current_user.business_id,
        Sale.created_at >= start,
        Sale.created_at <= end
    ).scalar()

    # Top productos por cantidad e ingreso (SaleItem + Sale)
    top_by_qty = db.session.query(
        SaleItem.product_name,
        func.coalesce(func.sum(SaleItem.quantity), 0).label("qty"),
        func.coalesce(func.sum(SaleItem.total), 0).label("income"),
    ).join(
        Sale, Sale.id == SaleItem.sale_id
    ).filter(
        Sale.business_id == current_user.business_id,
        Sale.created_at >= start,
        Sale.created_at <= end
    ).group_by(
        SaleItem.product_name
    ).order_by(
        desc("qty")
    ).limit(10).all()

    # Stock bajo (Product)
    low_stock = Product.query.filter(
        Product.business_id == current_user.business_id,
        Product.stock <= low,
        Product.is_active == True
    ).order_by(Product.stock.asc()).all()

    return render_template(
        "reports/home.html",
        days=days,
        low=low,
        sales_total=sales_total,
        sales_count=sales_count,
        top_by_qty=top_by_qty,
        low_stock=low_stock
    )


@reports_bp.get("/export/csv")
@login_required
def export_csv():
    days = request.args.get("days", default=1, type=int)
    if days not in (1, 7, 30):
        days = 1

    end = datetime.utcnow()
    start = end - timedelta(days=days)

    rows = db.session.query(
        Sale.id.label("ticket_id"),
        Sale.created_at,
        SaleItem.product_name,
        SaleItem.unit_price,
        SaleItem.quantity,
        SaleItem.total
    ).join(
        Sale, Sale.id == SaleItem.sale_id
    ).filter(
        Sale.business_id == current_user.business_id,
        Sale.created_at >= start,
        Sale.created_at <= end
    ).order_by(Sale.created_at.desc(), Sale.id.desc()).all()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["ticket_id", "fecha", "producto", "precio_unitario", "cantidad", "total_linea"])

    for r in rows:
        writer.writerow([
            r.ticket_id,
            r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            r.product_name,
            f"{float(r.unit_price):.2f}",
            int(r.quantity),
            f"{float(r.total):.2f}",
        ])

    csv_data = output.getvalue()
    output.close()

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=ventas_{days}d.csv"}
    )


@reports_bp.get("/export-products-csv")
@login_required
def export_products_csv():
    products = Product.query.filter_by(
        business_id=current_user.business_id
    ).order_by(Product.name.asc()).all()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Producto", "Precio", "Stock", "Activo"])

    for p in products:
        writer.writerow([p.name, float(p.price), int(p.stock), "SI" if p.is_active else "NO"])

    output.seek(0)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            f"attachment; filename=inventario_{datetime.utcnow().date()}.csv"
        }
    )


@reports_bp.get("/export-sales-range")
@login_required
def export_sales_range():
    # formato esperado: YYYY-MM-DD
    start_str = request.args.get("start", "")
    end_str = request.args.get("end", "")

    if not start_str or not end_str:
        flash("Selecciona rango de fechas.", "warning")
        return redirect(url_for("reports.reports_home"))

    try:
        start = datetime.strptime(start_str, "%Y-%m-%d")
        end = datetime.strptime(end_str, "%Y-%m-%d")
        end = end.replace(hour=23, minute=59, second=59)
    except ValueError:
        flash("Formato de fecha inválido.", "danger")
        return redirect(url_for("reports.reports_home"))

    rows = db.session.query(
        Sale.id.label("ticket_id"),
        Sale.created_at,
        SaleItem.product_name,
        SaleItem.quantity,
        SaleItem.unit_price,
        SaleItem.total
    ).join(
        Sale, Sale.id == SaleItem.sale_id
    ).filter(
        Sale.business_id == current_user.business_id,
        Sale.created_at >= start,
        Sale.created_at <= end
    ).order_by(Sale.created_at.asc(), Sale.id.asc()).all()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Ticket", "Fecha", "Producto", "Cantidad", "Precio Unitario", "Total Línea"])

    for r in rows:
        writer.writerow([
            r.ticket_id,
            r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            r.product_name,
            int(r.quantity),
            f"{float(r.unit_price):.2f}",
            f"{float(r.total):.2f}"
        ])

    output.seek(0)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            f"attachment; filename=ventas_{start_str}_a_{end_str}.csv"
        }
    )
