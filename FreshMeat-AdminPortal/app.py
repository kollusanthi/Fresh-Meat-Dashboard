
import os
import uuid
import calendar
from mysql.connector.errors import IntegrityError

from datetime import date
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, send_from_directory, abort, flash
)

from werkzeug.utils import secure_filename
from database import get_db_connection, init_db


app = Flask(__name__)
app.secret_key = "freshmeet_admin_secret_key"

app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "uploads")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}


# --------------------------------------------------
# DATABASE HELPERS
# --------------------------------------------------

def get_columns(conn, table):
    result = conn.execute(
        f"PRAGMA table_info({table})"
    ).fetchall()
    return [row["name"] for row in result]


def table_exists(conn, table):
    result = conn.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type='table' AND name=?
        """,
        (table,)
    ).fetchone()
    return result is not None


def get_count(conn, table, condition=None):
    if not table_exists(conn, table):
        return 0

    query = f"SELECT COUNT(*) FROM {table}"

    if condition:
        query += f" WHERE {condition}"

    return conn.execute(query).fetchone()[0]


# --------------------------------------------------
# ADMIN LOGIN REQUIRED
# --------------------------------------------------

def admin_required(route):
    @wraps(route)
    def decorated(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("login"))
        return route(*args, **kwargs)
    return decorated


# --------------------------------------------------
# FILE HELPERS
# --------------------------------------------------

def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def save_uploaded_file(file):
    if not file or not file.filename:
        return None

    if not allowed_file(file.filename):
        raise ValueError(
            "Only PDF, PNG, JPG and JPEG files are allowed."
        )

    original = secure_filename(file.filename)
    extension = original.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{extension}"

    file.save(
        os.path.join(app.config["UPLOAD_FOLDER"], filename)
    )

    return filename


def get_document_fields(module):
    if module == "sellers":
        return {
            "aadhaar_document": "Aadhaar Document",
            "pan_document": "PAN Document",
            "shop_license_document": "Shop License",
            "bank_document": "Bank Document"
        }

    return {
        "aadhaar_document": "Aadhaar Document",
        "driving_license_document": "Driving License",
        "vehicle_rc_document": "Vehicle RC",
        "profile_photo": "Profile Photo"
    }


# --------------------------------------------------
# ADD MONTHS
# --------------------------------------------------

def add_months(original_date, months):
    month = original_date.month - 1 + months
    year = original_date.year + month // 12
    month = month % 12 + 1

    day = min(
        original_date.day,
        calendar.monthrange(year, month)[1]
    )

    return date(year, month, day)


# --------------------------------------------------
# OTHER MODULES CONFIGURATION
# --------------------------------------------------

MODULES = {
    "customers": {
        "title": "Customers",
        "table": "customers",
        "columns": ["id", "name", "email", "phone", "status"],
        "actions": ["Active", "Blocked"]
    },

    "products": {
        "title": "Products",
        "table": "products",
        "columns": ["id", "name", "category", "price", "status"],
        "actions": ["Pending", "Approved", "Rejected"]
    },

    "orders": {
        "title": "Orders",
        "table": "orders",
        "columns": ["id", "customer_id", "total_amount", "status"],
        "actions": ["Pending", "Processing", "Completed", "Cancelled"]
    },

    "payments": {
        "title": "Payments",
        "table": "payments",
        "columns": ["id", "order_id", "amount", "payment_status"],
        "actions": ["Pending", "Completed", "Failed"]
    },

    "complaints": {
        "title": "Complaints",
        "table": "complaints",
        "columns": ["id", "customer_id", "subject", "message", "status"],
        "actions": ["Open", "In Progress", "Resolved"]
    }
}


# --------------------------------------------------
# LOGIN
# --------------------------------------------------

@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():

    if "admin_id" in session:
        return redirect(url_for("dashboard"))

    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db_connection()

        admin = conn.execute(
            """
            SELECT * FROM admins
            WHERE username=? AND password=?
            """,
            (username, password)
        ).fetchone()

        conn.close()

        if admin:
            session["admin_id"] = admin["id"]
            session["admin_username"] = admin["username"]
            return redirect(url_for("dashboard"))

        error = "Invalid username or password"

    return render_template("login.html", error=error)


# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

@app.route("/dashboard")
@admin_required
def dashboard():

    conn = get_db_connection()

    stats = {}

    for table in [
        "customers", "sellers", "riders",
        "products", "orders"
    ]:
        stats[table] = get_count(conn, table)

    for table in ["sellers", "riders", "products", "orders"]:
        if table_exists(conn, table):
            columns = get_columns(conn, table)

            if "status" in columns:
                stats[f"pending_{table}"] = get_count(
                    conn, table, "status='Pending'"
                )
            else:
                stats[f"pending_{table}"] = 0
        else:
            stats[f"pending_{table}"] = 0

    stats["revenue"] = 0

    if table_exists(conn, "payments"):
        payment_columns = get_columns(conn, "payments")

        if "amount" in payment_columns and "payment_status" in payment_columns:
            stats["revenue"] = conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0)
                FROM payments
                WHERE payment_status='Completed'
                """
            ).fetchone()[0]

    stats["completed_orders"] = 0

    if table_exists(conn, "orders"):
        if "status" in get_columns(conn, "orders"):
            stats["completed_orders"] = get_count(
                conn, "orders", "status='Completed'"
            )

    stats["open_complaints"] = 0

    if table_exists(conn, "complaints"):
        if "status" in get_columns(conn, "complaints"):
            stats["open_complaints"] = get_count(
                conn, "complaints", "status='Open'"
            )

    conn.close()

    return render_template("dashboard.html", stats=stats)


# --------------------------------------------------
# SELLER AND RIDER LIST
# --------------------------------------------------

@app.route("/manage/<module>")
@admin_required
def manage_people(module):

    if module not in ("sellers", "riders"):
        abort(404)

    search = request.args.get("search", "").strip()
    status = request.args.get("status", "All")

    conn = get_db_connection()

    query = f"SELECT * FROM {module} WHERE 1=1"
    params = []

    if search:
        query += """
            AND (
                name LIKE ?
                OR email LIKE ?
                OR phone LIKE ?
            )
        """
        term = f"%{search}%"
        params.extend([term, term, term])

    if status != "All":
        query += " AND status=?"
        params.append(status)

    query += " ORDER BY id DESC"

    rows = conn.execute(query, params).fetchall()

    total_records = conn.execute(
        f"SELECT COUNT(*) FROM {module}"
    ).fetchone()[0]

    conn.close()

    title = "Sellers" if module == "sellers" else "Riders"

    return render_template(
        "people_list.html",
        rows=rows,
        module=module,
        title=title,
        search=search,
        selected_status=status,
        total_records=total_records
    )


# --------------------------------------------------
# SELLER / RIDER PROFILE DETAILS
# --------------------------------------------------

@app.route("/<module>/<int:record_id>")
@admin_required
def person_details(module, record_id):

    if module not in ("sellers", "riders"):
        abort(404)

    conn = get_db_connection()

    person = conn.execute(
        f"SELECT * FROM {module} WHERE id=?",
        (record_id,)
    ).fetchone()

    conn.close()

    if not person:
        abort(404)

    document_fields = get_document_fields(module)

    documents = {
        label: (
            person[field]
            if field in person.keys()
            else None
        )
        for field, label in document_fields.items()
    }

    return render_template(
        "person_details.html",
        person=person,
        module=module,
        title="Seller Details" if module == "sellers" else "Rider Details",
        documents=documents
    )


# --------------------------------------------------
# UPLOAD / REPLACE SELLER OR RIDER DOCUMENT
# --------------------------------------------------

@app.route(
    "/upload-document/<module>/<int:record_id>",
    methods=["POST"]
)
@admin_required
def upload_person_document(module, record_id):

    if module not in ("sellers", "riders"):
        abort(404)

    document_fields = get_document_fields(module)

    label_to_field = {
        label: field
        for field, label in document_fields.items()
    }

    selected_label = next(
        (
            label for label in label_to_field
            if request.files.get(label)
            and request.files.get(label).filename
        ),
        None
    )

    if not selected_label:
        flash("Please select a document to upload.")
        return redirect(url_for(
            "person_details",
            module=module,
            record_id=record_id
        ))

    field = label_to_field[selected_label]
    uploaded_file = request.files.get(selected_label)

    conn = get_db_connection()
    new_filename = None

    try:
        columns = get_columns(conn, module)

        if field not in columns:
            flash(f"Database column missing: {field}")
            return redirect(url_for(
                "person_details",
                module=module,
                record_id=record_id
            ))

        person = conn.execute(
            f"SELECT * FROM {module} WHERE id=?",
            (record_id,)
        ).fetchone()

        if not person:
            abort(404)

        old_filename = person[field]

        try:
            new_filename = save_uploaded_file(uploaded_file)
        except ValueError as error:
            flash(str(error))
            return redirect(url_for(
                "person_details",
                module=module,
                record_id=record_id
            ))

        if not new_filename:
            flash("Please select a valid document.")
            return redirect(url_for(
                "person_details",
                module=module,
                record_id=record_id
            ))

        conn.execute(
            f"UPDATE {module} SET {field}=? WHERE id=?",
            (new_filename, record_id)
        )

        conn.commit()

        if old_filename:
            old_safe_name = secure_filename(old_filename)

            if old_safe_name == old_filename:
                old_path = os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    old_safe_name
                )

                if os.path.isfile(old_path):
                    try:
                        os.remove(old_path)
                    except OSError:
                        pass

        flash(f"{selected_label} uploaded successfully!")

    except Exception:
        conn.rollback()

        if new_filename:
            new_path = os.path.join(
                app.config["UPLOAD_FOLDER"],
                new_filename
            )
            if os.path.isfile(new_path):
                try:
                    os.remove(new_path)
                except OSError:
                    pass

        raise

    finally:
        conn.close()

    return redirect(url_for(
        "person_details",
        module=module,
        record_id=record_id
    ))


# --------------------------------------------------
# APPROVE / REJECT / BLOCK SELLER OR RIDER
# --------------------------------------------------

@app.route("/review/<module>/<int:record_id>", methods=["POST"])
@admin_required
def review_person(module, record_id):

    if module not in ("sellers", "riders"):
        abort(404)

    action = request.form.get("action", "").strip()
    reason = request.form.get("rejection_reason", "").strip()
    cooldown = request.form.get("cooldown", "3")
    custom_date = request.form.get("custom_date", "").strip()

    allowed_actions = [
        "Approved", "Rejected", "Blocked", "Pending"
    ]

    if action not in allowed_actions:
        flash("Invalid status selected.")
        return redirect(url_for(
            "person_details", module=module, record_id=record_id
        ))

    conn = get_db_connection()

    person = conn.execute(
        f"SELECT id FROM {module} WHERE id=?",
        (record_id,)
    ).fetchone()

    if not person:
        conn.close()
        abort(404)

    if action == "Approved":
        conn.execute(
            f"""
            UPDATE {module}
            SET status='Approved',
                rejection_reason=NULL,
                reapply_after=NULL
            WHERE id=?
            """,
            (record_id,)
        )

    elif action in ("Rejected", "Blocked"):

        if not reason:
            conn.close()
            flash("Please enter a reason.")
            return redirect(url_for(
                "person_details", module=module, record_id=record_id
            ))

        if cooldown == "3":
            reapply_after = add_months(date.today(), 3).isoformat()

        elif cooldown == "6":
            reapply_after = add_months(date.today(), 6).isoformat()

        elif cooldown == "custom" and custom_date:
            try:
                parsed_date = date.fromisoformat(custom_date)
                reapply_after = parsed_date.isoformat()
            except ValueError:
                conn.close()
                flash("Invalid custom date.")
                return redirect(url_for(
                    "person_details", module=module, record_id=record_id
                ))

        else:
            conn.close()
            flash("Please select a valid re-application date.")
            return redirect(url_for(
                "person_details", module=module, record_id=record_id
            ))

        if reapply_after <= date.today().isoformat():
            conn.close()
            flash("Re-application date must be in the future.")
            return redirect(url_for(
                "person_details", module=module, record_id=record_id
            ))

        conn.execute(
            f"""
            UPDATE {module}
            SET status=?,
                rejection_reason=?,
                reapply_after=?
            WHERE id=?
            """,
            (action, reason, reapply_after, record_id)
        )

    else:
        conn.execute(
            f"""
            UPDATE {module}
            SET status='Pending',
                rejection_reason=NULL,
                reapply_after=NULL
            WHERE id=?
            """,
            (record_id,)
        )

    conn.commit()
    conn.close()

    flash(f"{module[:-1].title()} status updated successfully!")

    return redirect(url_for(
        "person_details", module=module, record_id=record_id
    ))


# --------------------------------------------------
# SECURE DOCUMENT VIEW
# --------------------------------------------------

@app.route("/documents/<filename>")
@admin_required
def view_document(filename):

    safe_name = secure_filename(filename)

    if safe_name != filename:
        abort(404)

    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"], safe_name
    )

    if not os.path.isfile(file_path):
        abort(404)

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        safe_name,
        as_attachment=False
    )


# --------------------------------------------------
# CUSTOMER DETAILS AND ORDER HISTORY
# --------------------------------------------------

@app.route("/customers/<int:record_id>")
@admin_required
def customer_details(record_id):

    conn = get_db_connection()

    if not table_exists(conn, "customers"):
        conn.close()
        abort(404)

    customer = conn.execute(
        "SELECT * FROM customers WHERE id=?",
        (record_id,)
    ).fetchone()

    if not customer:
        conn.close()
        abort(404)

    orders = []
    order_count = 0
    total_spending = 0

    if table_exists(conn, "orders"):
        order_columns = get_columns(conn, "orders")

        if "customer_id" in order_columns:
            orders = conn.execute(
                """
                SELECT * FROM orders
                WHERE customer_id=?
                ORDER BY id DESC
                """,
                (record_id,)
            ).fetchall()

            order_count = len(orders)

            if "total_amount" in order_columns:
                if "status" in order_columns:
                    total_spending = conn.execute(
                        """
                        SELECT COALESCE(SUM(total_amount), 0)
                        FROM orders
                        WHERE customer_id=?
                        AND status != 'Cancelled'
                        """,
                        (record_id,)
                    ).fetchone()[0]
                else:
                    total_spending = conn.execute(
                        """
                        SELECT COALESCE(SUM(total_amount), 0)
                        FROM orders
                        WHERE customer_id=?
                        """,
                        (record_id,)
                    ).fetchone()[0]

    conn.close()

    return render_template(
        "customer_details.html",
        customer=customer,
        orders=orders,
        order_count=order_count,
        total_spending=total_spending
    )


# --------------------------------------------------
# CUSTOMERS / PRODUCTS / ORDERS / PAYMENTS / COMPLAINTS
# --------------------------------------------------

@app.route("/manage/<module>/records", methods=["GET", "POST"])
@admin_required
def manage_records(module):

    if module not in MODULES:
        abort(404)

    config = MODULES[module]
    table = config["table"]

    conn = get_db_connection()

    if not table_exists(conn, table):
        conn.close()
        abort(404)

    actual_columns = get_columns(conn, table)

    display_columns = [
        column for column in config["columns"]
        if column in actual_columns
    ]

    status_column = (
        "payment_status" if module == "payments" else "status"
    )

    if request.method == "POST":

        action = request.form.get("action", "").strip()
        record_id = request.form.get("record_id", "").strip()

        if not record_id.isdigit():
            conn.close()
            flash("Invalid record selected.")
            return redirect(url_for("manage_records", module=module))

        if action == "delete":
            conn.execute(
                f"DELETE FROM {table} WHERE id=?",
                (record_id,)
            )
            conn.commit()
            conn.close()

            flash("Record deleted successfully!")
            return redirect(url_for("manage_records", module=module))

        new_status = request.form.get(
            "new_status", ""
        ).strip()

        if not new_status and action in config["actions"]:
            new_status = action

        if (
            new_status in config["actions"]
            and status_column in actual_columns
        ):
            conn.execute(
                f"""
                UPDATE {table}
                SET {status_column}=?
                WHERE id=?
                """,
                (new_status, record_id)
            )
            conn.commit()
            conn.close()

            flash("Status updated successfully!")
            return redirect(url_for("manage_records", module=module))

        conn.close()
        flash("Unable to update this record.")
        return redirect(url_for("manage_records", module=module))

    search = request.args.get("search", "").strip()

    query = f"SELECT * FROM {table} WHERE 1=1"
    params = []

    searchable_columns = [
        column for column in display_columns
        if column != "id"
    ]

    if search and searchable_columns:
        search_conditions = []

        for column in searchable_columns:
            search_conditions.append(f"CAST({column} AS TEXT) LIKE ?")
            params.append(f"%{search}%")

        query += " AND (" + " OR ".join(search_conditions) + ")"

    query += " ORDER BY id DESC"

    rows = conn.execute(query, params).fetchall()

    total_records = conn.execute(
        f"SELECT COUNT(*) FROM {table}"
    ).fetchone()[0]

    conn.close()

    return render_template(
        "manage_records.html",
        title=config["title"],
        module=module,
        columns=display_columns,
        actions=config["actions"],
        rows=rows,
        search=search,
        total_records=total_records,
        status_column=status_column
    )


# --------------------------------------------------
# ORDER DETAILS
# --------------------------------------------------

@app.route("/orders/<int:order_id>")
@admin_required
def order_details(order_id):

    conn = get_db_connection()

    order = conn.execute(
        "SELECT * FROM orders WHERE id=?",
        (order_id,)
    ).fetchone()

    if not order:
        conn.close()
        abort(404)

    customer = None
    payment = None

    if table_exists(conn, "customers"):
        customer = conn.execute(
            "SELECT * FROM customers WHERE id=?",
            (order["customer_id"],)
        ).fetchone()

    if table_exists(conn, "payments"):
        payment = conn.execute(
            """
            SELECT * FROM payments
            WHERE order_id=?
            ORDER BY id DESC
            LIMIT 1
            """,
            (order_id,)
        ).fetchone()

    conn.close()

    return render_template(
        "order_details.html",
        order=order,
        customer=customer,
        payment=payment
    )


# --------------------------------------------------
# PAYMENT DETAILS
# --------------------------------------------------

@app.route("/payments/<int:payment_id>")
@admin_required
def payment_details(payment_id):

    conn = get_db_connection()

    payment = conn.execute(
        "SELECT * FROM payments WHERE id=?",
        (payment_id,)
    ).fetchone()

    if not payment:
        conn.close()
        abort(404)

    order = None

    if table_exists(conn, "orders"):
        order = conn.execute(
            "SELECT * FROM orders WHERE id=?",
            (payment["order_id"],)
        ).fetchone()

    conn.close()

    return render_template(
        "payment_details.html",
        payment=payment,
        order=order
    )


# --------------------------------------------------
# COMPLAINT DETAILS
# --------------------------------------------------

@app.route("/complaints/<int:complaint_id>")
@admin_required
def complaint_details(complaint_id):

    conn = get_db_connection()

    complaint = conn.execute(
        "SELECT * FROM complaints WHERE id=?",
        (complaint_id,)
    ).fetchone()

    if not complaint:
        conn.close()
        abort(404)

    customer = None

    if table_exists(conn, "customers"):
        customer = conn.execute(
            "SELECT * FROM customers WHERE id=?",
            (complaint["customer_id"],)
        ).fetchone()

    conn.close()

    return render_template(
        "complaint_details.html",
        complaint=complaint,
        customer=customer
    )


@app.route("/complaints/<int:complaint_id>/status", methods=["POST"])
@admin_required
def update_complaint_status(complaint_id):

    new_status = request.form.get("new_status", "").strip()
    allowed_statuses = MODULES["complaints"]["actions"]

    if new_status not in allowed_statuses:
        flash("Invalid complaint status.")
        return redirect(url_for(
            "complaint_details",
            complaint_id=complaint_id
        ))

    conn = get_db_connection()
    complaint = conn.execute(
        "SELECT id FROM complaints WHERE id=?",
        (complaint_id,)
    ).fetchone()

    if not complaint:
        conn.close()
        abort(404)

    conn.execute(
        "UPDATE complaints SET status=? WHERE id=?",
        (new_status, complaint_id)
    )
    conn.commit()
    conn.close()

    flash("Complaint status updated successfully!")
    return redirect(url_for(
        "complaint_details",
        complaint_id=complaint_id
    ))


# --------------------------------------------------
# REPORTS
# --------------------------------------------------

@app.route("/reports")
@admin_required
def reports():

    conn = get_db_connection()

    report = {
        "total_customers": get_count(conn, "customers"),
        "total_sellers": get_count(conn, "sellers"),
        "total_riders": get_count(conn, "riders"),
        "total_products": get_count(conn, "products"),
        "total_orders": get_count(conn, "orders"),
        "completed_orders": 0,
        "cancelled_orders": 0,
        "total_revenue": 0
    }

    if table_exists(conn, "orders"):
        order_columns = get_columns(conn, "orders")

        if "status" in order_columns:
            report["completed_orders"] = get_count(
                conn, "orders", "status='Completed'"
            )
            report["cancelled_orders"] = get_count(
                conn, "orders", "status='Cancelled'"
            )

    if table_exists(conn, "payments"):
        payment_columns = get_columns(conn, "payments")

        if "amount" in payment_columns and "payment_status" in payment_columns:
            report["total_revenue"] = conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0)
                FROM payments
                WHERE payment_status='Completed'
                """
            ).fetchone()[0]

    conn.close()

    return render_template("reports.html", report=report)


# --------------------------------------------------
# NOTIFICATIONS
# --------------------------------------------------

@app.route("/notifications", methods=["GET", "POST"])
@admin_required
def notifications():

    conn = get_db_connection()

    if not table_exists(conn, "notifications"):
        conn.close()
        flash(
            "Notifications table is not available.",
            "notification"
        )
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        action = request.form.get("action", "").strip()

        if action == "create":

            title = request.form.get("title", "").strip()
            message = request.form.get("message", "").strip()
            target = request.form.get(
                "target", "All Users"
            ).strip()

            allowed_targets = [
                "All Users",
                "Customers",
                "Sellers",
                "Riders"
            ]

            if not title or not message:
                flash(
                    "Please enter title and message.",
                    "notification"
                )

            elif target not in allowed_targets:
                flash(
                    "Invalid notification recipient.",
                    "notification"
                )

            else:
                conn.execute(
                    """
                    INSERT INTO notifications
                    (title, message, target)
                    VALUES (?, ?, ?)
                    """,
                    (title, message, target)
                )

                conn.commit()

                flash(
                    "Notification created successfully!",
                    "notification"
                )

        elif action == "delete":

            notification_id = request.form.get(
                "notification_id", ""
            ).strip()

            if notification_id.isdigit():

                conn.execute(
                    """
                    DELETE FROM notifications
                    WHERE id=?
                    """,
                    (int(notification_id),)
                )

                conn.commit()

                flash(
                    "Notification deleted successfully!",
                    "notification"
                )

            else:
                flash(
                    "Invalid notification selected.",
                    "notification"
                )

        conn.close()

        return redirect(url_for("notifications"))

    rows = conn.execute(
        """
        SELECT * FROM notifications
        ORDER BY id DESC
        """
    ).fetchall()

    analytics = {
        "total": len(rows),
        "all_users": 0,
        "customers": 0,
        "sellers": 0,
        "riders": 0
    }

    for notification in rows:

        target = notification["target"]

        if target == "All Users":
            analytics["all_users"] += 1

        elif target == "Customers":
            analytics["customers"] += 1

        elif target == "Sellers":
            analytics["sellers"] += 1

        elif target == "Riders":
            analytics["riders"] += 1

    conn.close()

    return render_template(
        "notifications.html",
        rows=rows,
        analytics=analytics
    )


# --------------------------------------------------
# SETTINGS
# --------------------------------------------------

@app.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():

    conn = get_db_connection()

    admin = conn.execute(
        """
        SELECT * FROM admins
        WHERE id=?
        """,
        (session["admin_id"],)
    ).fetchone()

    message = ""

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        old_password = request.form.get("old_password", "")
        new_password = request.form.get("new_password", "")

        if not username or not old_password or not new_password:
            message = "Please fill all fields."

        elif not admin or old_password != admin["password"]:
            message = "Current password is incorrect."

        else:
            try:
                conn.execute(
                    """
                    UPDATE admins
                    SET username=?, password=?
                    WHERE id=?
                    """,
                    (
                        username,
                        new_password,
                        session["admin_id"]
                    )
                )

                conn.commit()
                session["admin_username"] = username
                message = "Settings updated successfully!"

                admin = conn.execute(
                    """
                    SELECT * FROM admins
                    WHERE id=?
                    """,
                    (session["admin_id"],)
                ).fetchone()

            except IntegrityError:
                message = "Username already exists."

    conn.close()

    return render_template(
        "settings.html",
        admin=admin,
        message=message
    )


# --------------------------------------------------
# LOGOUT
# --------------------------------------------------

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# --------------------------------------------------
# RUN APPLICATION
# --------------------------------------------------

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
