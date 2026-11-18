
from flask import Flask, jsonify, request
from flask_cors import CORS
from database import get_db_connection, create_tables

from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)


# --------------------------------
# HOME
# --------------------------------

@app.route("/")
def home():
    return jsonify({
        "message": "Premium Fresh Meat Backend is Running!"
    })


# --------------------------------
# CUSTOMER REGISTRATIONS
# --------------------------------

@app.route("/api/admin/customer-registrations", methods=["GET"])
def get_customers():

    conn = get_db_connection()

    customers = conn.execute("""
        SELECT id, name, email, phone, registered_at
        FROM customers
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return jsonify({
        "customers": [dict(customer) for customer in customers]
    })


# --------------------------------
# DASHBOARD OVERVIEW
# --------------------------------

@app.route("/api/admin/dashboard", methods=["GET"])
def dashboard():

    conn = get_db_connection()

    # Total orders
    total_orders = conn.execute("""
        SELECT COUNT(*) FROM orders
    """).fetchone()[0]

    # Total registered customers
    total_customers = conn.execute("""
        SELECT COUNT(*) FROM customers
    """).fetchone()[0]

    # Total revenue (excluding cancelled orders)
    total_revenue = conn.execute("""
        SELECT COALESCE(SUM(total_amount), 0)
        FROM orders
        WHERE LOWER(status) != 'cancelled'
    """).fetchone()[0]

    # Pending orders
    pending_orders = conn.execute("""
        SELECT COUNT(*)
        FROM orders
        WHERE LOWER(status) = 'pending'
    """).fetchone()[0]

    # Delivered orders
    delivered_orders = conn.execute("""
        SELECT COUNT(*)
        FROM orders
        WHERE LOWER(status) = 'delivered'
    """).fetchone()[0]

    # Last 7 days orders
    daily_orders = conn.execute("""
        SELECT
            DATE(order_date) AS date,
            COUNT(*) AS count
        FROM orders
        WHERE DATE(order_date) >= DATE('now', '-6 days')
        GROUP BY DATE(order_date)
        ORDER BY DATE(order_date)
    """).fetchall()

    # Last 7 days revenue
    daily_revenue = conn.execute("""
        SELECT
            DATE(order_date) AS date,
            SUM(total_amount) AS amount
        FROM orders
        WHERE DATE(order_date) >= DATE('now', '-6 days')
        AND LOWER(status) != 'cancelled'
        GROUP BY DATE(order_date)
        ORDER BY DATE(order_date)
    """).fetchall()

    # Recent orders
    recent_orders = conn.execute("""
        SELECT
            o.id,
            c.name AS customer_name,
            o.total_amount,
            o.status,
            GROUP_CONCAT(oi.product_name, ', ') AS products_summary
        FROM orders o
        JOIN customers c ON o.customer_id = c.id
        LEFT JOIN order_items oi ON o.id = oi.order_id
        GROUP BY o.id
        ORDER BY o.id DESC
        LIMIT 5
    """).fetchall()

    conn.close()

    return jsonify({

        "total_orders": total_orders,

        "total_customers": total_customers,

        "total_revenue": total_revenue,

        "pending_orders": pending_orders,

        "delivered_orders": delivered_orders,

        "daily_orders": [
            {
                "date": row["date"],
                "count": row["count"]
            }
            for row in daily_orders
        ],

        "daily_revenue": [
            {
                "date": row["date"],
                "amount": row["amount"]
            }
            for row in daily_revenue
        ],

        "recent_orders": [
            {
                "id": row["id"],
                "customer_name": row["customer_name"],
                "products_summary": row["products_summary"] or "No products",
                "total_amount": row["total_amount"],
                "status": row["status"]
            }
            for row in recent_orders
        ]

    })


# --------------------------------
# ALL CUSTOMER ORDERS
# --------------------------------

@app.route("/api/admin/orders", methods=["GET"])
def get_orders():

    conn = get_db_connection()

    order_rows = conn.execute("""
        SELECT
            o.id,
            c.name AS customer_name,
            c.phone,
            o.address,
            o.total_amount,
            o.status,
            o.payment_status,
            o.order_date,

            COALESCE(SUM(oi.quantity), 0) AS total_quantity,

            GROUP_CONCAT(
                DISTINCT oi.product_name
            ) AS products_summary

        FROM orders o

        JOIN customers c
            ON o.customer_id = c.id

        LEFT JOIN order_items oi
            ON o.id = oi.order_id

        GROUP BY o.id

        ORDER BY o.id DESC
    """).fetchall()

    result = []

    for order in order_rows:

        # Individual product details
        items = conn.execute("""
            SELECT
                product_name,
                quantity,
                price
            FROM order_items
            WHERE order_id = ?
        """, (order["id"],)).fetchall()

        result.append({

            "id": order["id"],

            "customer_name": order["customer_name"],

            "phone": order["phone"],

            "address": order["address"],

            "products_summary":
                order["products_summary"] or "No products",

            "total_quantity": order["total_quantity"],

            "total_amount": order["total_amount"],

            "order_date": order["order_date"],

            "status": order["status"],

            "payment_status": order["payment_status"],

            "items": [
                dict(item) for item in items
            ]

        })

    conn.close()

    return jsonify({
        "orders": result
    })


# --------------------------------
# NOTIFICATIONS
# --------------------------------

@app.route("/api/admin/notifications", methods=["GET"])
def get_notifications():

    conn = get_db_connection()

    rows = conn.execute("""
        SELECT *
        FROM notifications
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return jsonify({
        "notifications": [
            dict(row) for row in rows
        ]
    })


# --------------------------------
# MARK NOTIFICATIONS AS READ
# --------------------------------

@app.route("/api/admin/notifications/read", methods=["PUT"])
def mark_notifications_read():

    conn = get_db_connection()

    conn.execute("""
        UPDATE notifications
        SET is_read = 1
    """)

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Notifications marked as read"
    })




@app.route("/api/orders", methods=["POST"])
def create_order():

    data = request.get_json(silent=True) or {}

    customer_id = data.get("customer_id")
    items = data.get("items", [])
    address = data.get("address", "")
    payment_status = data.get("payment_status", "Pending")

    if not customer_id or not items:
        return jsonify({
            "error": "Customer ID and products are required"
        }), 400

    conn = get_db_connection()

    try:
        customer = conn.execute("""
            SELECT id FROM customers WHERE id = ?
        """, (customer_id,)).fetchone()

        if not customer:
            return jsonify({
                "error": "Customer not found"
            }), 404

        total_amount = 0

        for item in items:
            quantity = int(item.get("quantity", 0))
            price = float(item.get("price", 0))

            if quantity <= 0 or price < 0 or not item.get("product_name"):
                return jsonify({
                    "error": "Invalid product details"
                }), 400

            total_amount += quantity * price

        cursor = conn.execute("""
            INSERT INTO orders
            (customer_id, total_amount, status, payment_status, address)
            VALUES (?, ?, 'Pending', ?, ?)
        """, (
            customer_id,
            total_amount,
            payment_status,
            address
        ))

        order_id = cursor.lastrowid

        for item in items:
            conn.execute("""
                INSERT INTO order_items
                (order_id, product_name, quantity, price)
                VALUES (?, ?, ?, ?)
            """, (
                order_id,
                item["product_name"],
                int(item["quantity"]),
                float(item["price"])
            ))

        conn.execute("""
            INSERT INTO notifications (message)
            VALUES (?)
        """, (f"New order #{order_id} received",))

        conn.commit()

        return jsonify({
            "message": "Order created successfully",
            "order_id": order_id,
            "total_amount": total_amount
        }), 201

    except (ValueError, TypeError):
        conn.rollback()
        return jsonify({
            "error": "Invalid quantity or price"
        }), 400

    except Exception as error:
        conn.rollback()
        return jsonify({
            "error": str(error)
        }), 500

    finally:
        conn.close()



# --------------------------------
# START SERVER
# --------------------------------

if __name__ == "__main__":

    create_tables()

    print("Premium Fresh Meat Backend Started")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
