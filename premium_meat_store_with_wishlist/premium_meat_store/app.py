import os
import random
import sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'premium_fresh_meat_secret_key_2026'
DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'meat_store.db')

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # Users Table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        mobile TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )''')

    # Addresses Table
    c.execute('''CREATE TABLE IF NOT EXISTS addresses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        label TEXT,
        full_address TEXT,
        city TEXT,
        pincode TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')

    # Products Table
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        price_per_kg REAL NOT NULL,
        discount_percent INTEGER DEFAULT 0,
        description TEXT,
        image_url TEXT,
        in_stock INTEGER DEFAULT 1,
        featured INTEGER DEFAULT 0
    )''')

    # Wishlist Table
    c.execute('''CREATE TABLE IF NOT EXISTS wishlist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        UNIQUE(user_id, product_id),
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(product_id) REFERENCES products(id)
    )''')

    # Orders Table
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_code TEXT UNIQUE,
        user_id INTEGER,
        items_summary TEXT,
        total_quantity REAL,
        total_amount REAL,
        delivery_address TEXT,
        delivery_slot TEXT,
        payment_method TEXT,
        payment_status TEXT,
        delivery_status TEXT,
        order_date TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')

    # Seed Products if empty
    c.execute('SELECT COUNT(*) FROM products')
    if c.fetchone()[0] == 0:
        sample_products = [
            # Chicken
            ("Farm Fresh Chicken Curry Cut (Skinless)", "Chicken", 280.0, 15, "Tender, juicy bone-in chicken pieces ideal for rich Indian curries.", "https://images.unsplash.com/photo-1604503468506-a8da13d82791?auto=format&fit=crop&w=600&q=80", 1, 1),
            ("Boneless Chicken Breast Fillet", "Chicken", 360.0, 10, "Lean, high-protein chicken breast fillets cleaned and trimmed.", "https://images.unsplash.com/photo-1615486511484-92e172cc4fe0?auto=format&fit=crop&w=600&q=80", 1, 1),
            ("Chicken Drumsticks (Tangdi)", "Chicken", 340.0, 0, "Juicy whole chicken drumsticks perfect for grilling, tandoori, or frying.", "https://images.unsplash.com/photo-1587593810167-a84920ea0781?auto=format&fit=crop&w=600&q=80", 0, 0),
            ("Chicken Wings (With Skin)", "Chicken", 260.0, 20, "Crispy-ready whole chicken wings for BBQ, buffalo wings, or appetizers.", "https://images.unsplash.com/photo-1527477396000-e27163b481c2?auto=format&fit=crop&w=600&q=80", 1, 0),

            # Mutton
            ("Premium Goat Curry Cut (Bone-in)", "Mutton", 850.0, 10, "Fresh pasture-raised goat meat cut into uniform pieces for slow-cooked curries.", "https://images.unsplash.com/photo-1603048297172-c92544798d5a?auto=format&fit=crop&w=600&q=80", 1, 1),
            ("Boneless Mutton Cubes", "Mutton", 980.0, 5, "Tender boneless goat chunks ideal for kebabs, biryani, and rogan josh.", "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=600&q=80", 1, 0),
            ("Mutton Keema (Minced Goat Meat)", "Mutton", 900.0, 0, "Finely minced fresh goat meat for samosas, meatballs, and keema matar.", "https://images.unsplash.com/photo-1529692236671-f1f6cf9683ba?auto=format&fit=crop&w=600&q=80", 0, 0),
            ("Goat Ribs & Chops", "Mutton", 920.0, 12, "Succulent goat rib chops rich in flavor, ideal for pan-searing or grilling.", "https://images.unsplash.com/photo-1558030006-450675393462?auto=format&fit=crop&w=600&q=80", 1, 0),

            # Fish
            ("Seer Fish (Vanjaram / Surmai) Steaks", "Fish", 950.0, 12, "Freshly caught marine Seer fish sliced into thick, meaty steaks.", "https://images.unsplash.com/photo-1519708227418-c8fd9a32b7a2?auto=format&fit=crop&w=600&q=80", 1, 1),
            ("Rohu River Fish Curry Cut", "Fish", 320.0, 15, "Freshwater Rohu cleaned, descaled, and cut into traditional curry pieces.", "https://images.unsplash.com/photo-1534604973900-c43ab4c2e0ab?auto=format&fit=crop&w=600&q=80", 1, 0),
            ("Norwegian Atlantic Salmon Fillet", "Fish", 1650.0, 8, "Rich, omega-3 packed boneless salmon fillets ready for pan-searing.", "https://images.unsplash.com/photo-1599084993091-1cb5c0721cc6?auto=format&fit=crop&w=600&q=80", 1, 0),
            ("Pomfret Whole Cleaned (White)", "Fish", 880.0, 0, "Delicate, buttery whole white pomfret cleaned and slit for frying.", "https://images.unsplash.com/photo-1615141982883-c7ad0e69fd62?auto=format&fit=crop&w=600&q=80", 0, 0),

            # Seafood
            ("Fresh Tiger Prawns (Cleaned & Deveined)", "Seafood", 640.0, 18, "Large coastal tiger prawns peeled, deveined, and ready to cook.", "https://images.unsplash.com/photo-1565680018434-b513d5e5fd47?auto=format&fit=crop&w=600&q=80", 1, 1),
            ("Blue Swimmer Crabs (Whole Cleaned)", "Seafood", 580.0, 10, "Sweet and meaty coastal blue crabs cleaned and halved for crab masala.", "https://images.unsplash.com/photo-1559737558-2f5a35f4523b?auto=format&fit=crop&w=600&q=80", 1, 0),
            ("Fresh Squid Rings (Calamari)", "Seafood", 520.0, 0, "Tender, cleaned squid tubes sliced into rings for crispy calamari or stir-fry.", "https://images.unsplash.com/photo-1604909052743-94e838986d24?auto=format&fit=crop&w=600&q=80", 1, 0),
            ("Jumbo Sea Prawns (Tail-On)", "Seafood", 760.0, 10, "Export-quality jumbo prawns ideal for garlic butter prawns and grills.", "https://images.unsplash.com/photo-1559742811-822873691df8?auto=format&fit=crop&w=600&q=80", 0, 0)
        ]
        c.executemany('''INSERT INTO products 
            (name, category, price_per_kg, discount_percent, description, image_url, in_stock, featured) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', sample_products)

    conn.commit()
    conn.close()

init_db()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to continue.', 'warning')
            return redirect(url_for('auth', mode='login'))
        return f(*args, **kwargs)
    return decorated_function

def get_discounted_price(product):
    price = product['price_per_kg']
    disc = product['discount_percent']
    if disc and disc > 0:
        return round(price * (1 - disc / 100.0), 2)
    return price

def get_user_wishlist_ids():
    if 'user_id' in session:
        conn = get_db()
        rows = conn.execute('SELECT product_id FROM wishlist WHERE user_id = ?', (session['user_id'],)).fetchall()
        conn.close()
        return [r['product_id'] for r in rows]
    return session.get('guest_wishlist', [])

@app.context_processor
def inject_globals():
    cart = session.get('cart', {})
    cart_count = sum(item['qty'] for item in cart.values())
    wishlist_ids = get_user_wishlist_ids()
    return dict(
        cart_count=cart_count,
        wishlist_ids=wishlist_ids,
        wishlist_count=len(wishlist_ids),
        current_user=session.get('user_name'),
        get_discounted_price=get_discounted_price
    )

# 1. HOME PAGE
@app.route('/')
def home():
    conn = get_db()
    featured_products = conn.execute('SELECT * FROM products WHERE featured = 1').fetchall()
    offer_products = conn.execute('SELECT * FROM products WHERE discount_percent >= 12').fetchall()
    all_products = conn.execute('SELECT * FROM products LIMIT 8').fetchall()
    conn.close()
    return render_template('index.html', featured=featured_products, offers=offer_products, products=all_products)

# 3. PRODUCT PAGE (Categories & Search)
@app.route('/products')
def products():
    category = request.args.get('category', 'All')
    search_query = request.args.get('q', '').strip()
    conn = get_db()
    
    if search_query:
        items = conn.execute(
            'SELECT * FROM products WHERE name LIKE ? OR category LIKE ? OR description LIKE ?',
            (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%')
        ).fetchall()
    elif category != 'All':
        items = conn.execute('SELECT * FROM products WHERE category = ?', (category,)).fetchall()
    else:
        items = conn.execute('SELECT * FROM products').fetchall()
        
    conn.close()
    return render_template('products.html', products=items, active_category=category, search_query=search_query)

# WISHLIST PAGE & ACTIONS
@app.route('/wishlist')
def wishlist():
    w_ids = get_user_wishlist_ids()
    items = []
    if w_ids:
        conn = get_db()
        placeholders = ','.join('?' for _ in w_ids)
        items = conn.execute(f'SELECT * FROM products WHERE id IN ({placeholders})', w_ids).fetchall()
        conn.close()
    return render_template('wishlist.html', products=items)

@app.route('/wishlist/toggle/<int:product_id>', methods=['POST'])
def toggle_wishlist(product_id):
    conn = get_db()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    if not product:
        conn.close()
        return redirect(request.referrer or url_for('products'))

    if 'user_id' in session:
        user_id = session['user_id']
        existing = conn.execute('SELECT id FROM wishlist WHERE user_id = ? AND product_id = ?', (user_id, product_id)).fetchone()
        if existing:
            conn.execute('DELETE FROM wishlist WHERE user_id = ? AND product_id = ?', (user_id, product_id))
            flash(f'Removed {product["name"]} from your wishlist.', 'info')
        else:
            conn.execute('INSERT INTO wishlist (user_id, product_id) VALUES (?, ?)', (user_id, product_id))
            flash(f'Saved {product["name"]} to your wishlist!', 'success')
        conn.commit()
    else:
        guest_w = session.get('guest_wishlist', [])
        if product_id in guest_w:
            guest_w.remove(product_id)
            flash(f'Removed {product["name"]} from your wishlist.', 'info')
        else:
            guest_w.append(product_id)
            flash(f'Saved {product["name"]} to your wishlist!', 'success')
        session['guest_wishlist'] = guest_w

    conn.close()
    return redirect(request.referrer or url_for('wishlist'))

@app.route('/wishlist/move-to-cart/<int:product_id>', methods=['POST'])
def move_to_cart(product_id):
    conn = get_db()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    if not product or product['in_stock'] == 0:
        conn.close()
        flash('Sorry, this item is currently out of stock.', 'danger')
        return redirect(url_for('wishlist'))

    # Add to cart
    cart_data = session.get('cart', {})
    pid = str(product_id)
    final_price = get_discounted_price(product)
    if pid in cart_data:
        cart_data[pid]['qty'] += 1
    else:
        cart_data[pid] = {
            'name': product['name'],
            'image': product['image_url'],
            'price': final_price,
            'qty': 1
        }
    session['cart'] = cart_data

    # Remove from wishlist
    if 'user_id' in session:
        conn.execute('DELETE FROM wishlist WHERE user_id = ? AND product_id = ?', (session['user_id'], product_id))
        conn.commit()
    else:
        guest_w = session.get('guest_wishlist', [])
        if product_id in guest_w:
            guest_w.remove(product_id)
            session['guest_wishlist'] = guest_w

    conn.close()
    flash(f'Moved {product["name"]} from wishlist to cart!', 'success')
    return redirect(url_for('cart'))

# 2. CUSTOMER REGISTRATION, LOGIN, OTP & FORGOT PASSWORD
@app.route('/auth', methods=['GET', 'POST'])
def auth():
    mode = request.args.get('mode', 'login')
    conn = get_db()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'register':
            name = request.form.get('name').strip()
            mobile = request.form.get('mobile').strip()
            email = request.form.get('email').strip()
            password = request.form.get('password')

            existing = conn.execute('SELECT id FROM users WHERE email = ? OR mobile = ?', (email, mobile)).fetchone()
            if existing:
                flash('Email or Mobile number already registered!', 'danger')
                conn.close()
                return redirect(url_for('auth', mode='register'))

            otp = str(random.randint(1000, 9999))
            session['pending_reg'] = {
                'name': name,
                'mobile': mobile,
                'email': email,
                'password': generate_password_hash(password),
                'otp': otp
            }
            flash(f'OTP sent to {mobile}! (Demo OTP: {otp})', 'info')
            conn.close()
            return redirect(url_for('auth', mode='otp'))

        elif action == 'verify_otp':
            entered_otp = request.form.get('otp').strip()
            pending = session.get('pending_reg')
            if pending and entered_otp == pending['otp']:
                conn.execute(
                    'INSERT INTO users (name, mobile, email, password) VALUES (?, ?, ?, ?)',
                    (pending['name'], pending['mobile'], pending['email'], pending['password'])
                )
                conn.commit()
                user = conn.execute('SELECT * FROM users WHERE email = ?', (pending['email'],)).fetchone()
                session.pop('pending_reg', None)
                session['user_id'] = user['id']
                session['user_name'] = user['name']

                # Sync any guest wishlist items into database
                for pid in session.pop('guest_wishlist', []):
                    conn.execute('INSERT OR IGNORE INTO wishlist (user_id, product_id) VALUES (?, ?)', (user['id'], pid))
                conn.commit()

                flash('Mobile verified! Welcome to Premium Fresh Meat.', 'success')
                conn.close()
                return redirect(url_for('home'))
            else:
                flash('Invalid OTP! Please check the code and try again.', 'danger')
                conn.close()
                return redirect(url_for('auth', mode='otp'))

        elif action == 'login':
            identifier = request.form.get('identifier').strip()
            password = request.form.get('password')
            user = conn.execute(
                'SELECT * FROM users WHERE email = ? OR mobile = ?',
                (identifier, identifier)
            ).fetchone()

            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['user_name'] = user['name']

                # Sync any guest wishlist items into database
                for pid in session.pop('guest_wishlist', []):
                    conn.execute('INSERT OR IGNORE INTO wishlist (user_id, product_id) VALUES (?, ?)', (user['id'], pid))
                conn.commit()

                flash(f'Welcome back, {user["name"]}!', 'success')
                conn.close()
                return redirect(url_for('home'))
            else:
                flash('Invalid Email/Mobile or Password.', 'danger')
                conn.close()
                return redirect(url_for('auth', mode='login'))

        elif action == 'forgot_send_otp':
            mobile = request.form.get('mobile').strip()
            user = conn.execute('SELECT * FROM users WHERE mobile = ?', (mobile,)).fetchone()
            if not user:
                flash('No account found with this mobile number.', 'danger')
                conn.close()
                return redirect(url_for('auth', mode='forgot'))
            otp = str(random.randint(1000, 9999))
            session['reset_data'] = {'mobile': mobile, 'otp': otp}
            flash(f'Password Reset OTP sent to {mobile}! (Demo OTP: {otp})', 'info')
            conn.close()
            return redirect(url_for('auth', mode='reset'))

        elif action == 'reset_password':
            otp = request.form.get('otp').strip()
            new_pass = request.form.get('new_password')
            reset_data = session.get('reset_data')
            if reset_data and otp == reset_data['otp']:
                conn.execute(
                    'UPDATE users SET password = ? WHERE mobile = ?',
                    (generate_password_hash(new_pass), reset_data['mobile'])
                )
                conn.commit()
                session.pop('reset_data', None)
                flash('Password updated successfully! Please login.', 'success')
                conn.close()
                return redirect(url_for('auth', mode='login'))
            else:
                flash('Invalid OTP entered.', 'danger')
                conn.close()
                return redirect(url_for('auth', mode='reset'))

    conn.close()
    return render_template('auth.html', mode=mode)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

# 4. SHOPPING CART
@app.route('/cart')
def cart():
    cart_data = session.get('cart', {})
    cart_items = []
    subtotal = 0.0

    for pid, item in cart_data.items():
        line_total = round(item['price'] * item['qty'], 2)
        subtotal += line_total
        cart_items.append({
            'id': pid,
            'name': item['name'],
            'image': item['image'],
            'price': item['price'],
            'qty': item['qty'],
            'line_total': line_total
        })

    delivery_charge = 0.0 if (subtotal == 0 or subtotal >= 500) else 40.0
    grand_total = round(subtotal + delivery_charge, 2)

    return render_template(
        'cart.html',
        cart_items=cart_items,
        subtotal=round(subtotal, 2),
        delivery_charge=delivery_charge,
        grand_total=grand_total
    )

@app.route('/cart/add/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    conn = get_db()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    conn.close()

    if not product or product['in_stock'] == 0:
        flash('Sorry, this item is currently out of stock.', 'danger')
        return redirect(request.referrer or url_for('products'))

    cart_data = session.get('cart', {})
    pid = str(product_id)
    final_price = get_discounted_price(product)

    if pid in cart_data:
        cart_data[pid]['qty'] += 1
    else:
        cart_data[pid] = {
            'name': product['name'],
            'image': product['image_url'],
            'price': final_price,
            'qty': 1
        }

    session['cart'] = cart_data
    flash(f'Added {product["name"]} to cart!', 'success')
    return redirect(request.referrer or url_for('products'))

@app.route('/cart/update/<pid>/<action>')
def update_cart(pid, action):
    cart_data = session.get('cart', {})
    if pid in cart_data:
        if action == 'inc':
            cart_data[pid]['qty'] += 1
        elif action == 'dec':
            cart_data[pid]['qty'] -= 1
            if cart_data[pid]['qty'] <= 0:
                del cart_data[pid]
        elif action == 'remove':
            del cart_data[pid]
    session['cart'] = cart_data
    return redirect(url_for('cart'))

# 5. CHECKOUT & PAYMENT
@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cart_data = session.get('cart', {})
    if not cart_data:
        flash('Your cart is empty!', 'warning')
        return redirect(url_for('products'))

    conn = get_db()
    addresses = conn.execute('SELECT * FROM addresses WHERE user_id = ?', (session['user_id'],)).fetchall()

    subtotal = sum(item['price'] * item['qty'] for item in cart_data.values())
    delivery_charge = 0.0 if subtotal >= 500 else 40.0
    grand_total = round(subtotal + delivery_charge, 2)

    if request.method == 'POST':
        addr_choice = request.form.get('address_choice')
        if addr_choice == 'new':
            label = request.form.get('label', 'Home')
            full_addr = request.form.get('full_address', '').strip()
            city = request.form.get('city', '').strip()
            pincode = request.form.get('pincode', '').strip()
            if not full_addr or not city or not pincode:
                flash('Please fill in all new address fields.', 'danger')
                conn.close()
                return redirect(url_for('checkout'))
            conn.execute(
                'INSERT INTO addresses (user_id, label, full_address, city, pincode) VALUES (?, ?, ?, ?, ?)',
                (session['user_id'], label, full_addr, city, pincode)
            )
            conn.commit()
            selected_address = f"{label}: {full_addr}, {city} - {pincode}"
        else:
            addr_row = conn.execute('SELECT * FROM addresses WHERE id = ? AND user_id = ?', (addr_choice, session['user_id'])).fetchone()
            if not addr_row:
                flash('Please select a valid delivery address.', 'danger')
                conn.close()
                return redirect(url_for('checkout'))
            selected_address = f"{addr_row['label']}: {addr_row['full_address']}, {addr_row['city']} - {addr_row['pincode']}"

        delivery_date = request.form.get('delivery_date')
        delivery_time = request.form.get('delivery_time')
        payment_method = request.form.get('payment_method')

        items_list = [f"{v['name']} ({v['qty']} kg)" for v in cart_data.values()]
        total_qty = sum(v['qty'] for v in cart_data.values())
        order_code = f"PFM-{random.randint(100000, 999999)}"
        payment_status = "Paid Online" if payment_method == "Online Payment" else "Pending (COD)"

        conn.execute('''INSERT INTO orders 
            (order_code, user_id, items_summary, total_quantity, total_amount, delivery_address, delivery_slot, payment_method, payment_status, delivery_status, order_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
            order_code,
            session['user_id'],
            ", ".join(items_list),
            total_qty,
            grand_total,
            selected_address,
            f"{delivery_date} | {delivery_time}",
            payment_method,
            payment_status,
            "Confirmed & Preparing",
            datetime.now().strftime("%d %b %Y, %I:%M %p")
        ))
        conn.commit()
        conn.close()

        session.pop('cart', None)
        flash(f'Order {order_code} confirmed! Thank you for ordering fresh meat.', 'success')
        return redirect(url_for('orders'))

    conn.close()
    today_str = datetime.now().strftime("%Y-%m-%d")
    return render_template(
        'checkout.html',
        addresses=addresses,
        cart_data=cart_data,
        subtotal=round(subtotal, 2),
        delivery_charge=delivery_charge,
        grand_total=grand_total,
        today_str=today_str
    )

# 6. MY ORDERS & TRACKING
@app.route('/orders')
@login_required
def orders():
    conn = get_db()
    user_orders = conn.execute(
        'SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC',
        (session['user_id'],)
    ).fetchall()
    conn.close()
    return render_template('orders.html', orders=user_orders)

@app.route('/orders/cancel/<int:order_id>', methods=['POST'])
@login_required
def cancel_order(order_id):
    conn = get_db()
    order = conn.execute('SELECT * FROM orders WHERE id = ? AND user_id = ?', (order_id, session['user_id'])).fetchone()
    if order and order['delivery_status'] not in ['Delivered', 'Cancelled']:
        new_pay_status = "Refund Initiated" if order['payment_status'] == "Paid Online" else "Cancelled"
        conn.execute(
            'UPDATE orders SET delivery_status = ?, payment_status = ? WHERE id = ?',
            ('Cancelled', new_pay_status, order_id)
        )
        conn.commit()
        flash(f'Order {order["order_code"]} has been cancelled.', 'info')
    conn.close()
    return redirect(url_for('orders'))

# 7. MY ACCOUNT
@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    conn = get_db()
    user_id = session['user_id']

    if request.method == 'POST':
        form_type = request.form.get('form_type')

        if form_type == 'edit_profile':
            name = request.form.get('name').strip()
            mobile = request.form.get('mobile').strip()
            email = request.form.get('email').strip()
            conn.execute('UPDATE users SET name = ?, mobile = ?, email = ? WHERE id = ?', (name, mobile, email, user_id))
            conn.commit()
            session['user_name'] = name
            flash('Profile updated successfully!', 'success')

        elif form_type == 'change_password':
            old_pw = request.form.get('old_password')
            new_pw = request.form.get('new_password')
            user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
            if check_password_hash(user['password'], old_pw):
                conn.execute('UPDATE users SET password = ? WHERE id = ?', (generate_password_hash(new_pw), user_id))
                conn.commit()
                flash('Password changed successfully!', 'success')
            else:
                flash('Current password is incorrect.', 'danger')

        elif form_type == 'add_address':
            label = request.form.get('label')
            full_addr = request.form.get('full_address')
            city = request.form.get('city')
            pincode = request.form.get('pincode')
            conn.execute(
                'INSERT INTO addresses (user_id, label, full_address, city, pincode) VALUES (?, ?, ?, ?, ?)',
                (user_id, label, full_addr, city, pincode)
            )
            conn.commit()
            flash('New address saved!', 'success')

        elif form_type == 'delete_address':
            addr_id = request.form.get('address_id')
            conn.execute('DELETE FROM addresses WHERE id = ? AND user_id = ?', (addr_id, user_id))
            conn.commit()
            flash('Address removed.', 'info')

        conn.close()
        return redirect(url_for('account'))

    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    addresses = conn.execute('SELECT * FROM addresses WHERE user_id = ?', (user_id,)).fetchall()
    order_history = conn.execute('SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC', (user_id,)).fetchall()
    conn.close()

    return render_template('account.html', user=user, addresses=addresses, orders=order_history)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
