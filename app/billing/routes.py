from datetime import datetime
from flask import render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from . import billing_bp
from ..extensions import db
import os
from werkzeug.utils import secure_filename
from flask import current_app, send_from_directory
from flask_login import current_user
from ..models import PaymentProof


@billing_bp.get("/expired")
@login_required
def expired():
    biz = current_user.business
    return render_template("billing/expired.html", biz=biz, now=datetime.utcnow())

@billing_bp.post("/upgrade")
@login_required
def upgrade():
    # Por ahora: activar manualmente Pro (luego aquí va Stripe)
    biz = current_user.business
    biz.is_pro = True
    db.session.commit()
    flash("Plan Pro activado ✅ (modo demo).", "success")
    return redirect(url_for("main.dashboard"))

@billing_bp.get("/plan")
@login_required
def plan():
    biz = current_user.business
    return render_template("billing/plan.html", biz=biz, now=datetime.utcnow())

@billing_bp.get("/pay")
@login_required
def pay():
    return render_template("billing/pay.html")
    
@billing_bp.get("/approve/<int:business_id>")
@login_required
def approve(business_id):

    from ..models import Business
    biz = Business.query.get_or_404(business_id)

    biz.is_pro = True
    biz.payment_status = "approved"

    db.session.commit()

    return "Cliente activado ✅"
    
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@billing_bp.get("/upload-proof")
@login_required
def upload_proof():
    biz = current_user.business
    return render_template("billing/upload_proof.html", biz=biz)


@billing_bp.post("/upload-proof")
@login_required
def upload_proof_post():
    biz = current_user.business

    if "file" not in request.files:
        flash("No se recibió archivo.", "danger")
        return redirect(url_for("billing.upload_proof"))

    f = request.files["file"]
    if not f or f.filename == "":
        flash("Selecciona un archivo.", "danger")
        return redirect(url_for("billing.upload_proof"))

    if not allowed_file(f.filename):
        flash("Formato no permitido. Usa PNG, JPG, JPEG o PDF.", "danger")
        return redirect(url_for("billing.upload_proof"))

    # carpeta destino (instance/uploads)
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_dir, exist_ok=True)

    original = secure_filename(f.filename)
    ext = original.rsplit(".", 1)[1].lower()

    # nombre único
    unique_name = f"proof_biz{biz.id}_user{current_user.id}_{int(datetime.utcnow().timestamp())}.{ext}"
    path = os.path.join(upload_dir, unique_name)
    f.save(path)

    proof = PaymentProof(
        business_id=biz.id,
        user_id=current_user.id,
        filename=unique_name,
        original_name=original,
        mime_type=f.mimetype,
        status="pending"
    )
    db.session.add(proof)

    # marcar negocio como pendiente
    biz.payment_status = "pending"
    db.session.commit()

    flash("Comprobante enviado ✅. En revisión.", "success")
    return redirect(url_for("billing.plan"))


# Mostrar comprobante (solo dueño o admin)
@billing_bp.get("/proof/<int:proof_id>")
@login_required
def view_proof(proof_id):
    proof = PaymentProof.query.get_or_404(proof_id)

    # permiso: mismo negocio o admin
    if proof.business_id != current_user.business_id and not _is_admin():
        abort(403)

    upload_dir = current_app.config["UPLOAD_FOLDER"]
    return send_from_directory(upload_dir, proof.filename, as_attachment=False)

def _is_admin() -> bool:
    # Cambia tu correo aquí, o mejor por variable de entorno después
    admin_emails = {"ltrujilloirarragorri@gmail.com"}  # <-- pon tu correo real
    return current_user.is_authenticated and current_user.email in admin_emails

@billing_bp.get("/admin/payments")
@login_required
def admin_payments():
    if not _is_admin():
        abort(403)

    pending = PaymentProof.query.filter_by(status="pending").order_by(PaymentProof.created_at.desc()).all()
    return render_template("billing/admin_payments.html", pending=pending)


@billing_bp.post("/admin/payments/<int:proof_id>/approve")
@login_required
def admin_approve(proof_id):
    if not _is_admin():
        abort(403)

    proof = PaymentProof.query.get_or_404(proof_id)
    proof.status = "approved"

    biz = proof.business
    biz.is_pro = True
    biz.payment_status = "approved"

    db.session.commit()
    flash("Pago aprobado ✅. Plan Pro activado.", "success")
    return redirect(url_for("billing.admin_payments"))


@billing_bp.post("/admin/payments/<int:proof_id>/reject")
@login_required
def admin_reject(proof_id):
    if not _is_admin():
        abort(403)

    proof = PaymentProof.query.get_or_404(proof_id)
    proof.status = "rejected"

    biz = proof.business
    biz.payment_status = "trial"  # o "rejected" si quieres
    db.session.commit()

    flash("Comprobante rechazado.", "warning")
    return redirect(url_for("billing.admin_payments"))






    
    
    
    
    