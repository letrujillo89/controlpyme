from datetime import datetime, timedelta
from flask import render_template, redirect, url_for, flash, abort, request
from flask_login import login_required, current_user

from . import admin_bp
from ..extensions import db
from ..models import Business, User, PaymentProof


def admin_required():
    if not current_user.is_authenticated or not getattr(current_user, "is_admin", False):
        abort(403)


@admin_bp.get("/")
@login_required
def dashboard():
    admin_required()

    # métricas simples
    total_business = Business.query.count()
    pro_business = Business.query.filter_by(is_pro=True).count()
    pending_payments = PaymentProof.query.filter_by(status="pending").count()

    return render_template(
        "admin/dashboard.html",
        total_business=total_business,
        pro_business=pro_business,
        pending_payments=pending_payments
    )


@admin_bp.get("/businesses")
@login_required
def businesses():
    admin_required()

    q = (request.args.get("q") or "").strip()
    query = Business.query

    if q:
        query = query.filter(Business.name.ilike(f"%{q}%"))

    businesses = query.order_by(Business.id.desc()).all()
    return render_template("admin/businesses.html", businesses=businesses, q=q, now=datetime.utcnow())


@admin_bp.post("/businesses/<int:biz_id>/activate-pro")
@login_required
def activate_pro(biz_id):
    admin_required()

    biz = Business.query.get_or_404(biz_id)
    biz.is_pro = True
    if hasattr(biz, "payment_status"):
        biz.payment_status = "approved"
    db.session.commit()

    flash(f"Plan Pro activado para: {biz.name}", "success")
    return redirect(url_for("admin.businesses"))


@admin_bp.post("/businesses/<int:biz_id>/deactivate-pro")
@login_required
def deactivate_pro(biz_id):
    admin_required()

    biz = Business.query.get_or_404(biz_id)
    biz.is_pro = False
    db.session.commit()

    flash(f"Plan Pro desactivado para: {biz.name}", "warning")
    return redirect(url_for("admin.businesses"))


@admin_bp.post("/businesses/<int:biz_id>/extend-trial")
@login_required
def extend_trial(biz_id):
    admin_required()

    biz = Business.query.get_or_404(biz_id)
    # extender 7 días desde hoy
    if hasattr(biz, "trial_ends_at") and biz.trial_ends_at:
        biz.trial_ends_at = datetime.utcnow() + timedelta(days=7)
        db.session.commit()

    flash(f"Trial extendido 7 días para: {biz.name}", "info")
    return redirect(url_for("admin.businesses"))


@admin_bp.get("/payments")
@login_required
def payments():
    admin_required()

    pending = PaymentProof.query.filter_by(status="pending").order_by(PaymentProof.created_at.desc()).all()
    return render_template("admin/payments.html", pending=pending)


@admin_bp.post("/payments/<int:proof_id>/approve")
@login_required
def approve_payment(proof_id):
    admin_required()

    proof = PaymentProof.query.get_or_404(proof_id)
    proof.status = "approved"

    biz = proof.business
    biz.is_pro = True
    if hasattr(biz, "payment_status"):
        biz.payment_status = "approved"

    db.session.commit()
    flash("Pago aprobado ✅. Plan Pro activado.", "success")
    return redirect(url_for("admin.payments"))


@admin_bp.post("/payments/<int:proof_id>/reject")
@login_required
def reject_payment(proof_id):
    admin_required()

    proof = PaymentProof.query.get_or_404(proof_id)
    proof.status = "rejected"

    biz = proof.business
    if hasattr(biz, "payment_status"):
        biz.payment_status = "trial"

    db.session.commit()
    flash("Comprobante rechazado.", "warning")
    return redirect(url_for("admin.payments"))


@admin_bp.get("/users")
@login_required
def users():
    admin_required()

    users = User.query.order_by(User.id.desc()).limit(200).all()
    return render_template("admin/users.html", users=users)
