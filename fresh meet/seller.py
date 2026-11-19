
from flask import (
    Flask, send_from_directory, jsonify, request,
    session
)
import sqlite3
import os
import secrets
from functools import wraps
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)
from werkzeug.utils import secure_filename

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_FOLDER = os.path.join(BASE_DIR, "frontend")
UPLOAD_FOLDER = os.path.join(FRONTEND_FOLDER, "uploads")
DATABASE = os.path.join(BASE_DIR, "freshmeet.db")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.secret_key = os.environ.get("FRESHMEET_SECRET_KEY") or secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


# ---------------- DATABASE ----------------

def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def add_missing_columns(connection, table, columns):
    existing = {
        row["name"]
        for row in connection.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()
    }

    for column, definition in columns.items():
        if column not in existing:
            connection.execute(
                f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
            )


def setup_database():
    connection = get_db()

    # Preserve existing seller records and add only missing columns.
    add_missing_columns(connection, "sellers", {
        "state": "TEXT",
        "pincode": "TEXT",
        "reason": "TEXT DEFAULT ''",
        "aadhaar_file": "TEXT",
        "pan_file": "TEXT",
        "fssai_file": "TEXT"
    })

    # Preserve existing products and add missing columns.
    connection.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            status TEXT DEFAULT 'Active',
            reason TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (seller_id) REFERENCES sellers(id)
        )
    """)

    add_missing_columns(connection, "products", {
        "description": "TEXT DEFAULT ''",
        "category": "TEXT DEFAULT ''",
        "image": "TEXT DEFAULT ''",
        "updated_at": "TIMESTAMP"
    })

    connection.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            customer_phone TEXT NOT NULL,
            customer_address TEXT NOT NULL,
            total_amount REAL NOT NULL DEFAULT 0,
            order_status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            seller_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (seller_id) REFERENCES sellers(id)
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (seller_id) REFERENCES sellers(id)
        )
    """)


    # Customer return requests and rider pickup assignments
    connection.execute("""
        CREATE TABLE IF NOT EXISTS return_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            order_item_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            seller_id INTEGER NOT NULL,
            customer_name TEXT NOT NULL,
            customer_phone TEXT NOT NULL,
            customer_address TEXT NOT NULL DEFAULT '',
            quantity INTEGER NOT NULL,
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Requested',
            seller_note TEXT DEFAULT '',
            item_condition TEXT DEFAULT '',
            rider_name TEXT DEFAULT '',
            rider_phone TEXT DEFAULT '',
            rider_status TEXT DEFAULT 'Not Assigned',
            restocked INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (order_item_id) REFERENCES order_items(id),
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (seller_id) REFERENCES sellers(id)
        )
    """)

    # Customer product reviews
    connection.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            seller_id INTEGER NOT NULL,
            customer_name TEXT NOT NULL,
            rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
            comment TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (order_id, product_id),
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (seller_id) REFERENCES sellers(id)
        )
    """)

    connection.commit()
    connection.close()


# ---------------- COMMON HELPERS ----------------

def seller_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        seller_id = session.get("seller_id")

        if not seller_id:
            return jsonify({"error": "Please log in first."}), 401

        connection = get_db()
        seller = connection.execute(
            "SELECT id, status FROM sellers WHERE id = ?",
            (seller_id,)
        ).fetchone()
        connection.close()

        if not seller:
            session.clear()
            return jsonify({"error": "Seller account not found."}), 403

        return function(*args, **kwargs)

    return wrapper


def get_seller_id():
    return session.get("seller_id")


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def save_product_image(file):
    if not file or not file.filename:
        return ""

    if not allowed_file(file.filename):
        raise ValueError("Only PNG, JPG, JPEG and WEBP images are allowed.")

    filename = secure_filename(file.filename)
    unique_name = secrets.token_hex(8) + "_" + filename
    file.save(os.path.join(UPLOAD_FOLDER, unique_name))

    return "/uploads/" + unique_name


def request_value(name, default=""):
    if request.is_json:
        data = request.get_json(silent=True) or {}
        return data.get(name, default)

    return request.form.get(name, default)


# ---------------- FRONTEND ----------------

@app.route("/")
def home():
    return send_from_directory(FRONTEND_FOLDER, "index.html")


@app.route("/<path:filename>")
def frontend_files(filename):
    return send_from_directory(FRONTEND_FOLDER, filename)


@app.route("/uploads/<path:filename>")
def uploaded_images(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route("/api/test")
def test():
    return jsonify({
        "message": "FreshMeet seller backend is running successfully!"
    })


# ---------------- SELLER REGISTRATION ----------------

@app.route("/api/seller/register", methods=["POST"])
def register_seller():
    data = request.get_json(silent=True) or {}

    required = [
        "name", "shop", "phone", "email",
        "password", "category", "city", "state", "address",
        "pincode"]

    if any(not str(data.get(field, "")).strip() for field in required):
        return jsonify({"error": "Please fill all required fields."}), 400

    if len(data["password"]) < 6:
        return jsonify({
            "error": "Password must contain at least 6 characters."
        }), 400

    connection = get_db()

    try:
        connection.execute("""
            INSERT INTO sellers (
                full_name, shop_name, phone, email, password,
                business_type, fssai_number, pan_number,
                city, state, pincode, address, status, reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active', '')
        """, (
            data["name"].strip(),
            data["shop"].strip(),
            data["phone"].strip(),
            data["email"].strip().lower(),
            generate_password_hash(data["password"]),
            data["category"].strip(),
            data.get("fssai", ""),
            data.get("pan", ""),
            data["city"].strip(),
            data["state"].strip(),
            data.get("pincode", ""),
            data["address"].strip()
        ))

        connection.commit()

        return jsonify({
            "message": "Registration successful. You can now log in to your seller portal."
        }), 201

    except sqlite3.IntegrityError:
        return jsonify({"error": "This email is already registered."}), 409

    except sqlite3.Error:
        return jsonify({"error": "Database error during registration."}), 500

    finally:
        connection.close()


# ---------------- SELLER LOGIN ----------------

@app.route("/api/seller/login", methods=["POST"])
def seller_login():
    data = request.get_json(silent=True) or {}

    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if not email or not password:
        return jsonify({"error": "Enter your email and password."}), 400

    connection = get_db()
    seller = connection.execute(
        "SELECT * FROM sellers WHERE email = ?",
        (email,)
    ).fetchone()
    connection.close()

    if not seller or not check_password_hash(seller["password"], password):
        return jsonify({"error": "Invalid email or password."}), 401

    session.clear()
    session["seller_id"] = seller["id"]

    return jsonify({
        "message": "Login successful.",
        "seller": {
            "id": seller["id"],
            "name": seller["full_name"],
            "shop": seller["shop_name"],
            "email": seller["email"]
        }
    })


# ---------------- SELLER LOGOUT ----------------

@app.route("/api/seller/logout", methods=["POST"])
def seller_logout():
    session.clear()
    return jsonify({"message": "Logged out successfully."})


# ---------------- SELLER PROFILE ----------------

@app.route("/api/seller/me", methods=["GET"])
@seller_required
def seller_profile():
    connection = get_db()

    seller = connection.execute("""
        SELECT
            id, full_name, phone, email, shop_name,
            business_type, address, city, state,
            pincode, fssai_number, pan_number, status, created_at
        FROM sellers
        WHERE id = ?
    """, (get_seller_id(),)).fetchone()

    connection.close()

    return jsonify({"seller": dict(seller)})


# ---------------- DASHBOARD STATS ----------------

@app.route("/api/seller/stats", methods=["GET"])
@seller_required
def seller_stats():
    connection = get_db()
    seller_id = get_seller_id()

    products = connection.execute(
        "SELECT COUNT(*) FROM products WHERE seller_id = ?",
        (seller_id,)
    ).fetchone()[0]

    orders = connection.execute(
        "SELECT COUNT(DISTINCT order_id) FROM order_items WHERE seller_id = ?",
        (seller_id,)
    ).fetchone()[0]

    pending = connection.execute("""
        SELECT COUNT(DISTINCT oi.order_id)
        FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        WHERE oi.seller_id = ? AND o.order_status = 'Pending'
    """, (seller_id,)).fetchone()[0]

    notifications = connection.execute(
        "SELECT COUNT(*) FROM notifications WHERE seller_id = ? AND is_read = 0",
        (seller_id,)
    ).fetchone()[0]

    connection.close()

    return jsonify({
        "products": products,
        "orders": orders,
        "pending": pending,
        "notifications": notifications
    })


# ---------------- PRODUCT MANAGEMENT ----------------

@app.route("/api/seller/products", methods=["GET", "POST"])
@seller_required
def seller_products():
    seller_id = get_seller_id()
    connection = get_db()

    if request.method == "GET":
        rows = connection.execute("""
            SELECT * FROM products
            WHERE seller_id = ?
            ORDER BY id DESC
        """, (seller_id,)).fetchall()

        connection.close()
        return jsonify({"products": [dict(row) for row in rows]})

    name = str(request_value("name")).strip()
    price = request_value("price")
    quantity = request_value("quantity")

    if not name or price in (None, "") or quantity in (None, ""):
        connection.close()
        return jsonify({"error": "Enter product name, price and quantity."}), 400

    try:
        price = float(price)
        quantity = int(quantity)

        if price < 0 or quantity < 0:
            raise ValueError()

        image = save_product_image(request.files.get("image"))

        connection.execute("""
            INSERT INTO products (
                seller_id, name, description, category,
                price, quantity, image, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Active')
        """, (
            seller_id,
            name,
            request_value("description"),
            request_value("category"),
            price,
            quantity,
            image
        ))

        connection.commit()
        connection.close()

        return jsonify({"message": "Product added successfully."}), 201

    except ValueError as error:
        connection.close()
        message = str(error) or "Enter a valid price and quantity."
        return jsonify({"error": message}), 400

    except sqlite3.Error:
        connection.close()
        return jsonify({"error": "Unable to save product."}), 500


@app.route("/api/seller/products/<int:product_id>", methods=["PUT", "DELETE"])
@seller_required
def manage_product(product_id):
    seller_id = get_seller_id()
    connection = get_db()

    product = connection.execute("""
        SELECT * FROM products
        WHERE id = ? AND seller_id = ?
    """, (product_id, seller_id)).fetchone()

    if not product:
        connection.close()
        return jsonify({"error": "Product not found."}), 404

    if request.method == "DELETE":
        connection.execute(
            "DELETE FROM products WHERE id = ? AND seller_id = ?",
            (product_id, seller_id)
        )
        connection.commit()
        connection.close()

        return jsonify({"message": "Product deleted successfully."})

    try:
        name = str(request_value("name", product["name"])).strip()
        price = float(request_value("price", product["price"]))
        quantity = int(request_value("quantity", product["quantity"]))

        if not name or price < 0 or quantity < 0:
            raise ValueError("Enter valid product details.")

        image = product["image"] or ""
        uploaded_file = request.files.get("image")

        if uploaded_file and uploaded_file.filename:
            image = save_product_image(uploaded_file)

        connection.execute("""
            UPDATE products
            SET name = ?, description = ?, category = ?,
                price = ?, quantity = ?, image = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND seller_id = ?
        """, (
            name,
            request_value("description", product["description"] or ""),
            request_value("category", product["category"] or ""),
            price,
            quantity,
            image,
            product_id,
            seller_id
        ))

        connection.commit()
        connection.close()

        return jsonify({"message": "Product updated successfully."})

    except (ValueError, TypeError):
        connection.close()
        return jsonify({"error": "Enter valid product details."}), 400

    except sqlite3.Error:
        connection.close()
        return jsonify({"error": "Unable to update product."}), 500


# ---------------- SELLER ORDERS ----------------

@app.route("/api/seller/orders", methods=["GET"])
@seller_required
def seller_orders():
    connection = get_db()
    seller_id = get_seller_id()

    rows = connection.execute("""
        SELECT
            o.id,
            o.customer_name,
            o.customer_phone,
            o.customer_address,
            o.total_amount,
            o.order_status,
            o.created_at,
            GROUP_CONCAT(
                p.name || ' x ' || oi.quantity,
                ', '
            ) AS items_summary
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.id
        JOIN products p ON p.id = oi.product_id
        WHERE oi.seller_id = ?
        GROUP BY o.id
        ORDER BY o.id DESC
    """, (seller_id,)).fetchall()

    connection.close()
    return jsonify({"orders": [dict(row) for row in rows]})


# ---------------- NOTIFICATIONS ----------------

@app.route("/api/seller/notifications", methods=["GET"])
@seller_required
def seller_notifications():
    connection = get_db()

    rows = connection.execute("""
        SELECT * FROM notifications
        WHERE seller_id = ?
        ORDER BY id DESC
    """, (get_seller_id(),)).fetchall()

    connection.close()

    return jsonify({"notifications": [dict(row) for row in rows]})


@app.route("/api/seller/notifications/<int:notification_id>/read", methods=["PATCH"])
@seller_required
def mark_notification_read(notification_id):
    connection = get_db()

    cursor = connection.execute("""
        UPDATE notifications
        SET is_read = 1
        WHERE id = ? AND seller_id = ?
    """, (notification_id, get_seller_id()))

    connection.commit()
    connection.close()

    if cursor.rowcount == 0:
        return jsonify({"error": "Notification not found."}), 404

    return jsonify({"message": "Notification marked as read."})


@app.route("/api/seller/notifications/read-all", methods=["PATCH"])
@seller_required
def mark_all_notifications_read():
    connection = get_db()

    connection.execute("""
        UPDATE notifications
        SET is_read = 1
        WHERE seller_id = ?
    """, (get_seller_id(),))

    connection.commit()
    connection.close()

    return jsonify({"message": "All notifications marked as read."})


# ---------------- CUSTOMER PRODUCT RETURNS ----------------

@app.route("/api/customer/orders/<int:order_id>/returns", methods=["POST"])
def customer_create_return():
    data = request.get_json(silent=True) or {}
    customer_phone = str(data.get("customer_phone", "")).strip()
    reason = str(data.get("reason", "")).strip()
    try:
        order_item_id = int(data.get("order_item_id"))
        quantity = int(data.get("quantity", 1))
    except (TypeError, ValueError):
        return jsonify({"error": "Valid order item and quantity are required."}), 400

    if not customer_phone or not reason or quantity < 1:
        return jsonify({"error": "Phone, return reason and valid quantity are required."}), 400

    connection = get_db()
    item = connection.execute("""
        SELECT oi.id, oi.order_id, oi.product_id, oi.seller_id, oi.quantity,
               p.name AS product_name, o.customer_name, o.customer_phone, o.customer_address, o.order_status
        FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        JOIN products p ON p.id = oi.product_id
        WHERE oi.id = ? AND oi.order_id = ?
    """, (order_item_id, order_id)).fetchone()

    if not item or str(item["customer_phone"]).strip() != customer_phone:
        connection.close()
        return jsonify({"error": "Order item/customer details do not match."}), 404
    if quantity > int(item["quantity"]):
        connection.close()
        return jsonify({"error": "Return quantity cannot exceed purchased quantity."}), 400
    if str(item["order_status"]).lower() in ("cancelled", "canceled"):
        connection.close()
        return jsonify({"error": "Cancelled orders cannot be returned."}), 400

    duplicate = connection.execute("""
        SELECT id FROM return_requests
        WHERE order_item_id = ? AND status NOT IN ('Rejected', 'Closed')
    """, (order_item_id,)).fetchone()
    if duplicate:
        connection.close()
        return jsonify({"error": "A return request already exists for this item."}), 409

    cursor = connection.execute("""
        INSERT INTO return_requests (order_id, order_item_id, product_id, seller_id,
            customer_name, customer_phone, customer_address, quantity, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (order_id, order_item_id, item["product_id"], item["seller_id"],
          item["customer_name"], customer_phone, item["customer_address"], quantity, reason))
    connection.execute("""
        INSERT INTO notifications (seller_id, title, message) VALUES (?, ?, ?)
    """, (item["seller_id"], "New return request",
          f"Return requested for {item['product_name']} (Order #{order_id}). Reason: {reason}"))
    connection.commit()
    return_id = cursor.lastrowid
    connection.close()
    return jsonify({"message": "Return request submitted to seller.", "return_id": return_id}), 201


# ---------------- SELLER RETURN MANAGEMENT ----------------

@app.route("/api/seller/returns", methods=["GET"])
@seller_required
def seller_get_returns():
    connection = get_db()
    rows = connection.execute("""
        SELECT r.*, p.name AS product_name, p.image AS product_image
        FROM return_requests r JOIN products p ON p.id = r.product_id
        WHERE r.seller_id = ? ORDER BY r.id DESC
    """, (get_seller_id(),)).fetchall()
    connection.close()
    return jsonify({"returns": [dict(row) for row in rows]})


@app.route("/api/seller/returns/<int:return_id>/decision", methods=["PATCH"])
@seller_required
def seller_decide_return(return_id):
    data = request.get_json(silent=True) or {}
    decision = str(data.get("decision", "")).strip().lower()
    note = str(data.get("seller_note", "")).strip()
    if decision not in ("approve", "reject"):
        return jsonify({"error": "Decision must be approve or reject."}), 400
    connection = get_db()
    row = connection.execute("SELECT * FROM return_requests WHERE id = ? AND seller_id = ?",
                              (return_id, get_seller_id())).fetchone()
    if not row:
        connection.close(); return jsonify({"error": "Return request not found."}), 404
    if row["status"] != "Requested":
        connection.close(); return jsonify({"error": "Return request already processed."}), 409
    status = "Approved" if decision == "approve" else "Rejected"
    connection.execute("UPDATE return_requests SET status=?, seller_note=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                       (status, note, return_id))
    connection.commit(); connection.close()
    return jsonify({"message": f"Return request {status.lower()}."})


@app.route("/api/seller/returns/<int:return_id>/assign-rider", methods=["PATCH"])
@seller_required
def seller_assign_return_rider(return_id):
    data = request.get_json(silent=True) or {}
    rider_name = str(data.get("rider_name", "")).strip()
    rider_phone = str(data.get("rider_phone", "")).strip()
    if not rider_name or not rider_phone:
        return jsonify({"error": "Rider name and phone are required."}), 400
    if not rider_phone.isdigit() or len(rider_phone) != 10:
        return jsonify({"error": "Enter a valid 10-digit rider phone number."}), 400
    connection = get_db()
    row = connection.execute("SELECT * FROM return_requests WHERE id=? AND seller_id=?",
                              (return_id, get_seller_id())).fetchone()
    if not row:
        connection.close(); return jsonify({"error": "Return request not found."}), 404
    if row["status"] != "Approved":
        connection.close(); return jsonify({"error": "Approve the return before assigning a rider."}), 409
    connection.execute("""
        UPDATE return_requests SET rider_name=?, rider_phone=?, rider_status='Assigned',
            status='Pickup Assigned', updated_at=CURRENT_TIMESTAMP WHERE id=?
    """, (rider_name, rider_phone, return_id))
    connection.commit(); connection.close()
    return jsonify({"message": f"Rider {rider_name} assigned successfully."})


@app.route("/api/seller/returns/<int:return_id>/received", methods=["PATCH"])
@seller_required
def seller_confirm_return_received(return_id):
    data = request.get_json(silent=True) or {}
    condition = str(data.get("item_condition", "")).strip().lower()
    note = str(data.get("seller_note", "")).strip()
    if condition not in ("resellable", "damaged", "wrong_item", "opened", "expired"):
        return jsonify({"error": "Condition must be resellable, damaged, wrong_item, opened or expired."}), 400
    connection = get_db()
    row = connection.execute("SELECT * FROM return_requests WHERE id=? AND seller_id=?",
                              (return_id, get_seller_id())).fetchone()
    if not row:
        connection.close(); return jsonify({"error": "Return request not found."}), 404
    if row["status"] not in ("Approved", "Pickup Assigned"):
        connection.close(); return jsonify({"error": "Only approved returns can be marked received."}), 409
    restocked = 0
    status = "Received - Not Restocked"
    if condition == "resellable":
        connection.execute("UPDATE products SET quantity=quantity+?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND seller_id=?",
                           (row["quantity"], row["product_id"], get_seller_id()))
        restocked = 1; status = "Closed"
    connection.execute("""
        UPDATE return_requests SET status=?, item_condition=?, seller_note=?, restocked=?,
            rider_status='Completed', updated_at=CURRENT_TIMESTAMP WHERE id=?
    """, (status, condition, note, restocked, return_id))
    connection.commit(); connection.close()
    return jsonify({"message": "Return received and inspected. Stock updated only if resellable.",
                    "restocked": bool(restocked)})


# ---------------- CHANGE PASSWORD ----------------

@app.route("/api/seller/change-password", methods=["POST"])
@seller_required
def change_password():
    data = request.get_json(silent=True) or {}

    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")
    confirm_password = data.get("confirm_password", "")

    if not current_password or not new_password or not confirm_password:
        return jsonify({"error": "Please fill all password fields."}), 400

    if new_password != confirm_password:
        return jsonify({"error": "New passwords do not match."}), 400

    if len(new_password) < 6:
        return jsonify({
            "error": "New password must contain at least 6 characters."
        }), 400

    connection = get_db()

    seller = connection.execute(
        "SELECT password FROM sellers WHERE id = ?",
        (get_seller_id(),)
    ).fetchone()

    if not seller or not check_password_hash(
        seller["password"], current_password
    ):
        connection.close()
        return jsonify({"error": "Current password is incorrect."}), 400

    connection.execute("""
        UPDATE sellers
        SET password = ?
        WHERE id = ?
    """, (generate_password_hash(new_password), get_seller_id()))

    connection.commit()
    connection.close()

    return jsonify({"message": "Password changed successfully."})




# ---------------- SELLER CUSTOMER REVIEWS ----------------

@app.route("/api/seller/reviews", methods=["GET"])
@seller_required
def seller_reviews():
    connection = get_db()
    seller_id = get_seller_id()

    rows = connection.execute("""
        SELECT
            r.id,
            r.order_id,
            r.product_id,
            r.customer_name,
            r.rating,
            r.comment,
            r.created_at,
            p.name AS product_name,
            p.image AS product_image
        FROM reviews r
        JOIN products p ON p.id = r.product_id
        WHERE r.seller_id = ?
        ORDER BY r.created_at DESC, r.id DESC
    """, (seller_id,)).fetchall()

    connection.close()

    return jsonify({
        "reviews": [dict(row) for row in rows]
    })


# ---------------- CUSTOMER SUBMIT PRODUCT REVIEW ----------------

@app.route("/api/reviews", methods=["POST"])
def create_product_review():
    data = request.get_json(silent=True) or {}

    try:
        order_id = int(data.get("order_id"))
        product_id = int(data.get("product_id"))
        rating = int(data.get("rating"))
    except (TypeError, ValueError):
        return jsonify({
            "error": "Enter a valid order ID, product ID and rating."
        }), 400

    customer_phone = str(data.get("customer_phone", "")).strip()
    comment = str(data.get("comment", "")).strip()

    if not customer_phone or not comment:
        return jsonify({
            "error": "Customer phone and review comment are required."
        }), 400

    if rating < 1 or rating > 5:
        return jsonify({"error": "Rating must be between 1 and 5."}), 400

    if len(comment) > 1000:
        return jsonify({"error": "Review must be 1000 characters or less."}), 400

    connection = get_db()

    try:
        purchased_item = connection.execute("""
            SELECT
                o.id AS order_id,
                o.customer_name,
                oi.product_id,
                oi.seller_id
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.id
            WHERE o.id = ?
              AND oi.product_id = ?
              AND o.customer_phone = ?
        """, (order_id, product_id, customer_phone)).fetchone()

        if not purchased_item:
            return jsonify({
                "error": "No matching purchase was found. Check your order ID and phone number."
            }), 404

        connection.execute("""
            INSERT INTO reviews (
                order_id, product_id, seller_id,
                customer_name, rating, comment
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            purchased_item["order_id"],
            purchased_item["product_id"],
            purchased_item["seller_id"],
            purchased_item["customer_name"],
            rating,
            comment
        ))

        connection.commit()

        return jsonify({
            "message": "Thank you! Your product review was submitted."
        }), 201

    except sqlite3.IntegrityError:
        connection.rollback()
        return jsonify({
            "error": "You have already reviewed this product for this order."
        }), 409

    except sqlite3.Error:
        connection.rollback()
        return jsonify({"error": "Unable to save your review."}), 500

    finally:
        connection.close()


# ---------------- CUSTOMER ORDER API ----------------
# Your customer-facing checkout must call this API to create
# orders and notify the relevant sellers.

@app.route("/api/orders", methods=["POST"])
def create_customer_order():
    data = request.get_json(silent=True) or {}

    customer_name = str(data.get("customer_name", "")).strip()
    customer_phone = str(data.get("customer_phone", "")).strip()
    customer_address = str(data.get("customer_address", "")).strip()
    items = data.get("items", [])

    if not customer_name or not customer_phone or not customer_address:
        return jsonify({"error": "Enter all customer details."}), 400

    if not isinstance(items, list) or not items:
        return jsonify({"error": "Your order has no products."}), 400

    connection = get_db()

    try:
        order_lines = []
        total_amount = 0

        for item in items:
            product_id = int(item.get("product_id"))
            quantity = int(item.get("quantity"))

            if quantity <= 0:
                raise ValueError("Invalid product quantity.")

            product = connection.execute("""
                SELECT id, seller_id, name, price, quantity
                FROM products
                WHERE id = ? AND status = 'Active'
            """, (product_id,)).fetchone()

            if not product:
                raise ValueError("A selected product is unavailable.")

            if int(product["quantity"] or 0) < quantity:
                raise ValueError(
                    "Not enough stock for " + product["name"]
                )

            line_total = float(product["price"]) * quantity
            total_amount += line_total

            order_lines.append({
                "product_id": product["id"],
                "seller_id": product["seller_id"],
                "name": product["name"],
                "quantity": quantity,
                "price": product["price"]
            })

        cursor = connection.execute("""
            INSERT INTO orders (
                customer_name, customer_phone,
                customer_address, total_amount, order_status
            )
            VALUES (?, ?, ?, ?, 'Pending')
        """, (
            customer_name,
            customer_phone,
            customer_address,
            total_amount
        ))

        order_id = cursor.lastrowid

        for item in order_lines:
            connection.execute("""
                INSERT INTO order_items (
                    order_id, product_id, seller_id, quantity, price
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                order_id,
                item["product_id"],
                item["seller_id"],
                item["quantity"],
                item["price"]
            ))

            connection.execute("""
                UPDATE products
                SET quantity = CAST(quantity AS INTEGER) - ?
                WHERE id = ?
            """, (item["quantity"], item["product_id"]))

            connection.execute("""
                INSERT INTO notifications (
                    seller_id, title, message
                )
                VALUES (?, ?, ?)
            """, (
                item["seller_id"],
                "New order received",
                "You received an order for " + item["name"]
                + " (Quantity: " + str(item["quantity"]) + ")."
            ))

        connection.commit()

        return jsonify({
            "message": "Order placed successfully.",
            "order_id": order_id,
            "total_amount": total_amount
        }), 201

    except (ValueError, TypeError) as error:
        connection.rollback()
        return jsonify({"error": str(error)}), 400

    except sqlite3.Error:
        connection.rollback()
        return jsonify({"error": "Unable to place order."}), 500

    finally:
        connection.close()


# ---------------- START SERVER ----------------

if __name__ == "__main__":
    setup_database()
    app.run(debug=True, port=5000)

