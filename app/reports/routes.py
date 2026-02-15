from datetime import datetime, timedelta
from flask import render_template, request, url_for, flash, redirect
from flask_login import login_required, current_user
from sqlalchemy import func
from . import reports_bp
from ..models import Sale, Product
from ..extensions import db
import csv
from io import StringIO
from flask import Response

@reports_bp.get("/")
@login_required
def reports_home():
    # rango (días) por query param: ?days=7
    try:
        days = int(request.args.get("days", "7"))
    except Exception:
        days = 7

    if days not in (1, 7, 30):
        days = 7

    start = datetime.utcnow() - timedelta(days=days)

    # Totales
    totals = db.session.query(
        func.count(Sale.id),
        func.coalesce(func.sum(Sale.total), 0)
    ).filter(
        Sale.business_id == current_user.business_id,
        Sale.created_at >= start
    ).first()

    sales_count = int(totals[0] or 0)
    sales_total = totals[1] or 0

    # Top productos (por cantidad)
    top_by_qty = db.session.query(
        Sale.product_name,
        func.sum(Sale.quantity).label("qty"),
        func.coalesce(func.sum(Sale.total), 0).label("income")
    ).filter(
        Sale.business_id == current_user.business_id,
        Sale.created_at >= start
    ).group_by(
        Sale.product_name
    ).order_by(
        func.sum(Sale.quantity).desc()
    ).limit(10).all()

    # Stock bajo (umbral configurable)
    try:
        low = int(request.args.get("low", "5"))
    except Exception:
        low = 5

    low_stock = Product.query.filter(
        Product.business_id == current_user.business_id,
        Product.stock <= low
    ).order_by(Product.stock.asc()).all()

    return render_template(
        "reports/home.html",
        days=days,
        low=low,
        sales_count=sales_count,
        sales_total=sales_total,
        top_by_qty=top_by_qty,
        low_stock=low_stock
    )

@reports_bp.get("/export-csv")
@login_required
def export_csv():

    biz = current_user.business

    sales = Sale.query.filter_by(
        business_id=biz.id
    ).order_by(Sale.created_at.desc()).all()

    # Crear CSV en memoria
    output = StringIO()
    writer = csv.writer(output)

    # encabezados
    writer.writerow([
        "Fecha",
        "Producto",
        "Cantidad",
        "Precio Unitario",
        "Total"
    ])

    # datos
    for s in sales:
        writer.writerow([
            s.created_at.strftime("%Y-%m-%d %H:%M"),
            s.product_name,
            s.quantity,
            s.unit_price,
            s.total
        ])

    output.seek(0)

    return Response(
        output,
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            f"attachment; filename=reporte_ventas_{datetime.utcnow().date()}.csv"
        }
    )

@reports_bp.get("/export-products-csv")
@login_required
def export_products_csv():
    products = Product.query.filter_by(
        business_id=current_user.business_id
    ).order_by(Product.name.asc()).all()

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(["Producto", "Precio", "Stock"])

    for p in products:
        writer.writerow([p.name, float(p.price), p.stock])

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
        # incluir todo el día final
        end = end.replace(hour=23, minute=59, second=59)
    except ValueError:
        flash("Formato de fecha inválido.", "danger")
        return redirect(url_for("reports.reports_home"))

    sales = Sale.query.filter(
        Sale.business_id == current_user.business_id,
        Sale.created_at >= start,
        Sale.created_at <= end
    ).order_by(Sale.created_at.asc()).all()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Fecha", "Producto", "Cantidad", "Precio Unitario", "Total"])

    for s in sales:
        writer.writerow([
            s.created_at.strftime("%Y-%m-%d %H:%M"),
            s.product_name,
            int(s.quantity),
            float(s.unit_price),
            float(s.total)
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
