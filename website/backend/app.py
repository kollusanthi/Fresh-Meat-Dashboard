
from flask import Flask, request, jsonify, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db_connection, create_tables
from functools import wraps

app = Flask(__name__)

app.secret_key = "change-this-to-a-long-random-secret-key"
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax"
)

CORS(app, supports_credentials=True)


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "customer_id" not in session:
            return jsonify({"success": False, "message": "Please login first"}), 401
        return func(*args, **kwargs)
    return wrapper


def add_notification(customer_id, message):
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO notifications (customer_id, message) VALUES (?, ?)",
        (customer_id, message)
    )
    conn.commit()
    conn.close()


# HOME
@app.route("/")
def home():
    return jsonify({"message": "FreshMeat Backend Running Successfully"})


# REGISTER
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json() or {}

    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    phone = data.get("phone", "").strip()
    password = data.get("password", "")

    if not name or not email or not password:
        return jsonify({"success": False, "message": "Please fill all required fields"}), 400

    if len(password) < 8:
        return jsonify({"success": False, "message": "Password must contain at least 8 characters"}), 400

    conn = get_db_connection()

    try:
        conn.execute("""
            INSERT INTO customers (name, email, phone, password)
            VALUES (?, ?, ?, ?)
        """, (name, email, phone, generate_password_hash(password)))

        conn.commit()

        customer = conn.execute(
            "SELECT id, name, email, phone FROM customers WHERE email = ?",
            (email,)
        ).fetchone()

        session["customer_id"] = customer["id"]

        return jsonify({
            "success": True,
            "message": "Registration successful",
            "customer": dict(customer)
        })

    except Exception:
        return jsonify({"success": False, "message": "Email already registered"}), 409

    finally:
        conn.close()


# LOGIN
@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json() or {}

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    conn = get_db_connection()

    customer = conn.execute(
        "SELECT * FROM customers WHERE email = ?",
        (email,)
    ).fetchone()

    conn.close()

    if customer and check_password_hash(customer["password"], password):
        session.clear()
        session["customer_id"] = customer["id"]

        return jsonify({
            "success": True,
            "message": "Login successful",
            "customer": {
                "id": customer["id"],
                "name": customer["name"],
                "email": customer["email"],
                "phone": customer["phone"]
            }
        })

    return jsonify({"success": False, "message": "Invalid email or password"}), 401


# LOGOUT
@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully"})


# CURRENT CUSTOMER PROFILE
@app.route("/api/profile", methods=["GET"])
@login_required
def profile():
    conn = get_db_connection()

    customer = conn.execute("""
        SELECT id, name, email, phone
        FROM customers WHERE id = ?
    """, (session["customer_id"],)).fetchone()

    conn.close()

    return jsonify({"success": True, "customer": dict(customer)})


# UPDATE PROFILE
@app.route("/api/profile", methods=["PUT"])
@login_required
def update_profile():
    data = request.get_json() or {}

    name = data.get("name", "").strip()
    phone = data.get("phone", "").strip()

    if not name:
        return jsonify({"success": False, "message": "Name is required"}), 400

    conn = get_db_connection()

    conn.execute("""
        UPDATE customers SET name = ?, phone = ?
        WHERE id = ?
    """, (name, phone, session["customer_id"]))

    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Profile updated"})


# PRODUCTS
@app.route("/api/products", methods=["GET"])
def products():
    category = request.args.get("category")

    conn = get_db_connection()

    if category:
        rows = conn.execute(
            "SELECT * FROM products WHERE category = ?",
            (category,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM products").fetchall()

    conn.close()

    return jsonify([dict(row) for row in rows])


# ADD PRODUCT (ADMIN/SEEDING USE)
@app.route("/api/products", methods=["POST"])
def add_product():
    data = request.get_json() or {}

    required = ["name", "category", "price"]
    if any(data.get(key) in (None, "") for key in required):
        return jsonify({"success": False, "message": "Name, category and price are required"}), 400

    try:
        price = float(data["price"])
        stock = int(data.get("stock", 100))
        if price < 0 or stock < 0:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid price or stock"}), 400

    conn = get_db_connection()

    cursor = conn.execute("""
        INSERT INTO products (name, category, description, price, image, stock)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        data["name"], data["category"], data.get("description", ""),
        price, data.get("image", ""), stock
    ))

    conn.commit()
    product_id = cursor.lastrowid
    conn.close()

    return jsonify({"success": True, "product_id": product_id}), 201


# ADD TO CART
@app.route("/api/cart/add", methods=["POST"])
@login_required
def add_to_cart():
    data = request.get_json() or {}

    try:
        product_id = int(data.get("product_id"))
        quantity = int(data.get("quantity", 1))
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid product or quantity"}), 400

    weight = data.get("weight", "500g")

    if quantity < 1:
        return jsonify({"success": False, "message": "Quantity must be at least 1"}), 400

    conn = get_db_connection()

    product = conn.execute(
        "SELECT id, stock FROM products WHERE id = ?", (product_id,)
    ).fetchone()

    if not product:
        conn.close()
        return jsonify({"success": False, "message": "Product not found"}), 404

    existing = conn.execute("""
        SELECT id, quantity FROM cart
        WHERE customer_id = ? AND product_id = ? AND weight = ?
    """, (session["customer_id"], product_id, weight)).fetchone()

    new_quantity = quantity + (existing["quantity"] if existing else 0)

    if new_quantity > product["stock"]:
        conn.close()
        return jsonify({"success": False, "message": "Not enough stock"}), 400

    if existing:
        conn.execute(
            "UPDATE cart SET quantity = ? WHERE id = ?",
            (new_quantity, existing["id"])
        )
    else:
        conn.execute("""
            INSERT INTO cart (customer_id, product_id, quantity, weight)
            VALUES (?, ?, ?, ?)
        """, (session["customer_id"], product_id, quantity, weight))

    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Added to bag"})


# VIEW CART
@app.route("/api/cart", methods=["GET"])
@login_required
def view_cart():
    conn = get_db_connection()

    rows = conn.execute("""
        SELECT cart.id, cart.product_id, cart.quantity, cart.weight,
               products.name, products.price, products.image,
               (products.price * cart.quantity) AS subtotal
        FROM cart
        JOIN products ON products.id = cart.product_id
        WHERE cart.customer_id = ?
    """, (session["customer_id"],)).fetchall()

    conn.close()

    items = [dict(row) for row in rows]

    return jsonify({
        "success": True,
        "items": items,
        "total": sum(item["subtotal"] for item in items),
        "item_count": sum(item["quantity"] for item in items)
    })


# UPDATE CART QUANTITY
@app.route("/api/cart/<int:cart_id>", methods=["PUT"])
@login_required
def update_cart(cart_id):
    data = request.get_json() or {}

    try:
        quantity = int(data.get("quantity"))
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid quantity"}), 400

    if quantity < 1:
        return jsonify({"success": False, "message": "Quantity must be at least 1"}), 400

    conn = get_db_connection()

    item = conn.execute("""
        SELECT cart.id, products.stock
        FROM cart JOIN products ON products.id = cart.product_id
        WHERE cart.id = ? AND cart.customer_id = ?
    """, (cart_id, session["customer_id"])).fetchone()

    if not item:
        conn.close()
        return jsonify({"success": False, "message": "Cart item not found"}), 404

    if quantity > item["stock"]:
        conn.close()
        return jsonify({"success": False, "message": "Not enough stock"}), 400

    conn.execute("UPDATE cart SET quantity = ? WHERE id = ?", (quantity, cart_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Cart updated"})


# REMOVE CART ITEM
@app.route("/api/cart/<int:cart_id>", methods=["DELETE"])
@login_required
def remove_cart_item(cart_id):
    conn = get_db_connection()

    conn.execute("""
        DELETE FROM cart WHERE id = ? AND customer_id = ?
    """, (cart_id, session["customer_id"]))

    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Item removed"})


# CLEAR CART
@app.route("/api/cart/clear", methods=["DELETE"])
@login_required
def clear_cart():
    conn = get_db_connection()

    conn.execute(
        "DELETE FROM cart WHERE customer_id = ?",
        (session["customer_id"],)
    )

    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Cart cleared"})


# WISHLIST
@app.route("/api/wishlist", methods=["GET"])
@login_required
def view_wishlist():
    conn = get_db_connection()

    rows = conn.execute("""
        SELECT products.*
        FROM wishlist
        JOIN products ON products.id = wishlist.product_id
        WHERE wishlist.customer_id = ?
    """, (session["customer_id"],)).fetchall()

    conn.close()

    return jsonify([dict(row) for row in rows])


@app.route("/api/wishlist/<int:product_id>", methods=["POST"])
@login_required
def toggle_wishlist(product_id):
    conn = get_db_connection()

    exists = conn.execute("""
        SELECT id FROM wishlist
        WHERE customer_id = ? AND product_id = ?
    """, (session["customer_id"], product_id)).fetchone()

    if exists:
        conn.execute("DELETE FROM wishlist WHERE id = ?", (exists["id"],))
        message = "Removed from wishlist"
        added = False
    else:
        product = conn.execute(
            "SELECT id FROM products WHERE id = ?", (product_id,)
        ).fetchone()

        if not product:
            conn.close()
            return jsonify({"success": False, "message": "Product not found"}), 404

        conn.execute("""
            INSERT INTO wishlist (customer_id, product_id)
            VALUES (?, ?)
        """, (session["customer_id"], product_id))

        message = "Added to wishlist"
        added = True

    conn.commit()
    conn.close()

    return jsonify({"success": True, "added": added, "message": message})


# SAVED ADDRESSES
@app.route("/api/addresses", methods=["GET"])
@login_required
def get_addresses():
    conn = get_db_connection()

    rows = conn.execute("""
        SELECT * FROM addresses WHERE customer_id = ?
        ORDER BY is_default DESC, id DESC
    """, (session["customer_id"],)).fetchall()

    conn.close()

    return jsonify([dict(row) for row in rows])


@app.route("/api/addresses", methods=["POST"])
@login_required
def add_address():
    data = request.get_json() or {}

    required = ["full_name", "phone", "address", "pincode"]
    if any(not str(data.get(key, "")).strip() for key in required):
        return jsonify({"success": False, "message": "Please fill all required address fields"}), 400

    conn = get_db_connection()

    cursor = conn.execute("""
        INSERT INTO addresses
        (customer_id, full_name, phone, address, city, pincode, is_default)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        session["customer_id"], data["full_name"], data["phone"],
        data["address"], data.get("city", ""), data["pincode"],
        int(bool(data.get("is_default", False)))
    ))

    conn.commit()
    address_id = cursor.lastrowid
    conn.close()

    return jsonify({"success": True, "address_id": address_id}), 201


@app.route("/api/addresses/<int:address_id>", methods=["DELETE"])
@login_required
def delete_address(address_id):
    conn = get_db_connection()

    conn.execute("""
        DELETE FROM addresses WHERE id = ? AND customer_id = ?
    """, (address_id, session["customer_id"]))

    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Address deleted"})


# CHECKOUT / PLACE ORDER
@app.route("/api/checkout", methods=["POST"])
@login_required
def checkout():
    data = request.get_json() or {}
    address_id = data.get("address_id")
    payment_method = data.get("payment_method", "COD")

    conn = get_db_connection()

    address = conn.execute("""
        SELECT id FROM addresses
        WHERE id = ? AND customer_id = ?
    """, (address_id, session["customer_id"])).fetchone()

    if not address:
        conn.close()
        return jsonify({"success": False, "message": "Select a valid address"}), 400

    items = conn.execute("""
        SELECT cart.product_id, cart.quantity, cart.weight,
               products.name, products.price, products.stock
        FROM cart JOIN products ON products.id = cart.product_id
        WHERE cart.customer_id = ?
    """, (session["customer_id"],)).fetchall()

    if not items:
        conn.close()
        return jsonify({"success": False, "message": "Your bag is empty"}), 400

    for item in items:
        if item["quantity"] > item["stock"]:
            conn.close()
            return jsonify({"success": False, "message": "Insufficient stock for " + item["name"]}), 400

    total = sum(item["price"] * item["quantity"] for item in items)

    cursor = conn.execute("""
        INSERT INTO orders (customer_id, address_id, total_amount, payment_method)
        VALUES (?, ?, ?, ?)
    """, (session["customer_id"], address_id, total, payment_method))

    order_id = cursor.lastrowid

    for item in items:
        conn.execute("""
            INSERT INTO order_items
            (order_id, product_id, product_name, quantity, weight, price)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            order_id, item["product_id"], item["name"],
            item["quantity"], item["weight"], item["price"]
        ))

        conn.execute("""
            UPDATE products SET stock = stock - ?
            WHERE id = ?
        """, (item["quantity"], item["product_id"]))

    conn.execute("DELETE FROM cart WHERE customer_id = ?", (session["customer_id"],))

    conn.commit()
    conn.close()

    add_notification(session["customer_id"], f"Your order #{order_id} has been placed.")

    return jsonify({
        "success": True,
        "message": "Order placed successfully",
        "order_id": order_id,
        "total": total
    }), 201


# MY ORDERS
@app.route("/api/orders", methods=["GET"])
@login_required
def my_orders():
    conn = get_db_connection()

    orders = conn.execute("""
        SELECT * FROM orders
        WHERE customer_id = ?
        ORDER BY id DESC
    """, (session["customer_id"],)).fetchall()

    result = []

    for order in orders:
        items = conn.execute("""
            SELECT * FROM order_items WHERE order_id = ?
        """, (order["id"],)).fetchall()

        result.append({
            "order": dict(order),
            "items": [dict(item) for item in items]
        })

    conn.close()

    return jsonify(result)


# ORDER DETAILS
@app.route("/api/orders/<int:order_id>", methods=["GET"])
@login_required
def order_details(order_id):
    conn = get_db_connection()

    order = conn.execute("""
        SELECT * FROM orders
        WHERE id = ? AND customer_id = ?
    """, (order_id, session["customer_id"])).fetchone()

    if not order:
        conn.close()
        return jsonify({"success": False, "message": "Order not found"}), 404

    items = conn.execute(
        "SELECT * FROM order_items WHERE order_id = ?", (order_id,)
    ).fetchall()

    conn.close()

    return jsonify({
        "order": dict(order),
        "items": [dict(item) for item in items]
    })


# NOTIFICATIONS
@app.route("/api/notifications", methods=["GET"])
@login_required
def notifications():
    conn = get_db_connection()

    rows = conn.execute("""
        SELECT * FROM notifications
        WHERE customer_id = ?
        ORDER BY id DESC
    """, (session["customer_id"],)).fetchall()

    conn.close()

    return jsonify([dict(row) for row in rows])


# MARK NOTIFICATION READ
@app.route("/api/notifications/<int:notification_id>/read", methods=["PUT"])
@login_required
def mark_notification_read(notification_id):
    conn = get_db_connection()

    conn.execute("""
        UPDATE notifications SET is_read = 1
        WHERE id = ? AND customer_id = ?
    """, (notification_id, session["customer_id"]))

    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Notification updated"})


# PRODUCT REVIEW
@app.route("/api/reviews", methods=["POST"])
@login_required
def add_review():
    data = request.get_json() or {}

    try:
        product_id = int(data.get("product_id"))
        rating = int(data.get("rating"))
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid product or rating"}), 400

    if rating < 1 or rating > 5:
        return jsonify({"success": False, "message": "Rating must be between 1 and 5"}), 400

    conn = get_db_connection()

    product = conn.execute(
        "SELECT id FROM products WHERE id = ?", (product_id,)
    ).fetchone()

    if not product:
        conn.close()
        return jsonify({"success": False, "message": "Product not found"}), 404

    conn.execute("""
        INSERT INTO reviews (customer_id, product_id, rating, comment)
        VALUES (?, ?, ?, ?)
    """, (
        session["customer_id"], product_id,
        rating, data.get("comment", "")
    ))

    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Review submitted"}), 201


@app.route("/api/products/<int:product_id>/reviews", methods=["GET"])
def product_reviews(product_id):
    conn = get_db_connection()

    rows = conn.execute("""
        SELECT reviews.rating, reviews.comment, reviews.created_at,
               customers.name
        FROM reviews
        JOIN customers ON customers.id = reviews.customer_id
        WHERE reviews.product_id = ?
        ORDER BY reviews.id DESC
    """, (product_id,)).fetchall()

    conn.close()

    return jsonify([dict(row) for row in rows])


if __name__ == "__main__":
    create_tables()
    app.run(debug=True, port=5000)
