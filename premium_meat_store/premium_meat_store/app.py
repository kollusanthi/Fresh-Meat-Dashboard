import os
import math
import random
import pymysql
from dotenv import load_dotenv
from pymysql.cursors import DictCursor
import smtplib
from email.message import EmailMessage
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.secret_key = 'premium_fresh_meat_secret_key_2026'
# MySQL connection settings are read from environment variables.
# Create the database once in MySQL: CREATE DATABASE premium_meat_store;
class HybridRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)

class MySQLCursor:
    def __init__(self, cursor): self.cursor = cursor
    def execute(self, sql, params=None):
        sql = sql.replace('INSERT OR IGNORE INTO', 'INSERT IGNORE INTO').replace('?', '%s')
        return self.cursor.execute(sql, params or ())
    def executemany(self, sql, params):
        sql = sql.replace('INSERT OR IGNORE INTO', 'INSERT IGNORE INTO').replace('?', '%s')
        return self.cursor.executemany(sql, params)
    def fetchone(self):
        row = self.cursor.fetchone()
        return HybridRow(row) if row is not None else None
    def fetchall(self):
        return [HybridRow(row) for row in self.cursor.fetchall()]

class MySQLConnection:
    def __init__(self, conn): self.conn = conn
    def cursor(self): return MySQLCursor(self.conn.cursor())
    def execute(self, sql, params=None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur
    def commit(self): return self.conn.commit()
    def close(self): return self.conn.close()



def get_db():
    print("Password loaded:", bool(os.getenv("DB_PASSWORD")))

    return MySQLConnection(pymysql.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', 'Santhi@17'),
        database=os.getenv('DB_NAME', 'freshmeat'),
        port=int(os.getenv('DB_PORT', '3306')),
        charset='utf8mb4',
        cursorclass=DictCursor,
        autocommit=False
    ))

def send_email_otp(recipient, otp):
    host = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    port = int(os.getenv('MAIL_PORT', '587'))
    sender = os.getenv('MAIL_USERNAME', '')
    password = os.getenv('MAIL_PASSWORD', '')
    if not sender or not password:
        raise RuntimeError('Email is not configured. Set MAIL_USERNAME and MAIL_PASSWORD in .env.')
    message = EmailMessage()
    message['Subject'] = 'Your Premium Fresh Meat verification OTP'
    message['From'] = os.getenv('MAIL_FROM', sender)
    message['To'] = recipient
    message.set_content(
        f'Hello,\\n\\nYour OTP to complete Premium Fresh Meat registration is {otp}. '
        'It is valid for 5 minutes. Do not share this code with anyone.\\n\\n'
        'If you did not request this, please ignore this email.'
    )
    with smtplib.SMTP(host, port, timeout=20) as server:
        server.starttls()
        server.login(sender, password)
        server.send_message(message)

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # Users Table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name TEXT NOT NULL,
        mobile VARCHAR(30) UNIQUE NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL,
        password TEXT NOT NULL
    )''')

    # Addresses Table
    c.execute('''CREATE TABLE IF NOT EXISTS addresses (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INTEGER,
        label TEXT,
        full_address TEXT,
        city TEXT,
        pincode TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')

    # Products Table
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        price_per_kg DOUBLE NOT NULL,
        discount_percent INTEGER DEFAULT 0,
        description TEXT,
        image_url TEXT,
        in_stock INTEGER DEFAULT 1,
        featured INTEGER DEFAULT 0,
        cut_type VARCHAR(255) DEFAULT 'Standard Cut',
        shelf_life VARCHAR(255) DEFAULT '24 Hours Chilled (0°C - 4°C)',
        calories VARCHAR(100) DEFAULT '165 kcal / 100g'
    )''')

    # Wishlist Table
    c.execute('''CREATE TABLE IF NOT EXISTS wishlist (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        UNIQUE(user_id, product_id),
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(product_id) REFERENCES products(id)
    )''')

    # Orders Table
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INT AUTO_INCREMENT PRIMARY KEY,
        order_code VARCHAR(40) UNIQUE,
        user_id INTEGER,
        items_summary TEXT,
        total_quantity DOUBLE,
        total_amount DOUBLE,
        delivery_address TEXT,
        delivery_slot TEXT,
        payment_method TEXT,
        payment_status TEXT,
        delivery_status TEXT,
        order_date TEXT,
        action_reason TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')
    # Safe migration if database already exists without action_reason column
    c.execute("""SELECT COLUMN_NAME FROM information_schema.COLUMNS
                 WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'orders'""")
    existing_cols = [row['COLUMN_NAME'] for row in c.fetchall()]
    if "action_reason" not in existing_cols:
        c.execute("ALTER TABLE orders ADD COLUMN action_reason TEXT")

    # Seed Products if empty
    c.execute('SELECT COUNT(*) FROM products')
    if c.fetchone()[0] == 0:
        sample_products = [
            # Chicken
            ("Farm Fresh Chicken Curry Cut (Skinless)", "Chicken", 280.0, 15, "Tender, juicy bone-in chicken pieces ideal for rich Indian curries, masala gravies, and slow-simmered dishes.", "https://images.unsplash.com/photo-1604503468506-a8da13d82791?auto=format&fit=crop&w=800&q=80", 1, 1, "Medium Bone-In Pieces (16-20 pcs/kg)", "24 Hours Chilled (0°C - 4°C)", "165 kcal / 100g"),
            ("Boneless Chicken Breast Fillet", "Chicken", 360.0, 10, "Lean, high-protein chicken breast fillets cleaned, skinless, and trimmed for grilling, stir-fries, and healthy meal prep.", "https://images.unsplash.com/photo-1615486511484-92e172cc4fe0?auto=format&fit=crop&w=800&q=80", 1, 1, "Whole Boneless Fillets", "24 Hours Chilled (0°C - 4°C)", "145 kcal / 100g"),
            ("Chicken Drumsticks (Tangdi)", "Chicken", 340.0, 0, "Juicy whole chicken drumsticks perfect for tandoori marinades, oven roasting, or crispy fried chicken.", "https://images.unsplash.com/photo-1587593810167-a84920ea0781?auto=format&fit=crop&w=800&q=80", 0, 0, "Whole Leg Drumsticks (8-10 pcs/kg)", "24 Hours Chilled (0°C - 4°C)", "185 kcal / 100g"),
            ("Chicken Wings (With Skin)", "Chicken", 260.0, 20, "Crispy-ready whole chicken wings for smoky BBQ glazes, spicy buffalo wings, or party appetizers.", "https://images.unsplash.com/photo-1527477396000-e27163b481c2?auto=format&fit=crop&w=800&q=80", 1, 0, "Split & Whole Wings", "24 Hours Chilled (0°C - 4°C)", "203 kcal / 100g"),
            ("Chicken Lollipop (Frenched)", "Chicken", 350.0, 12, "Frenched chicken winglets shaped cleanly for restaurant-style Indo-Chinese starters.", "https://images.unsplash.com/photo-1562967914-608f82629710?auto=format&fit=crop&w=800&q=80", 1, 0, "Frenched Winglets (18-22 pcs/kg)", "24 Hours Chilled (0°C - 4°C)", "190 kcal / 100g"),

            # Mutton
            ("Premium Goat Curry Cut (Bone-in)", "Mutton", 850.0, 10, "Fresh pasture-raised young goat meat cut into uniform pieces for rich, slow-cooked Sunday curries.", "https://images.unsplash.com/photo-1603048297172-c92544798d5a?auto=format&fit=crop&w=800&q=80", 1, 1, "Shoulder & Rib Bone-In Cut", "48 Hours Chilled (0°C - 4°C)", "215 kcal / 100g"),
            ("Boneless Mutton Cubes", "Mutton", 980.0, 5, "Tender boneless goat leg chunks ideal for seekh kebabs, royal biryani, and Kashmiri rogan josh.", "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=800&q=80", 1, 0, "1-Inch Boneless Cubes", "48 Hours Chilled (0°C - 4°C)", "195 kcal / 100g"),
            ("Mutton Keema (Minced Goat Meat)", "Mutton", 900.0, 0, "Finely minced fresh goat meat with balanced fat ratio for samosas, meatballs, and keema matar.", "https://images.unsplash.com/photo-1529692236671-f1f6cf9683ba?auto=format&fit=crop&w=800&q=80", 0, 0, "Fine Double-Minced", "24 Hours Chilled (0°C - 4°C)", "225 kcal / 100g"),
            ("Goat Ribs & Chops", "Mutton", 920.0, 12, "Succulent goat rib chops rich in marbling and flavor, ideal for pan-searing or charcoal grilling.", "https://images.unsplash.com/photo-1558030006-450675393462?auto=format&fit=crop&w=800&q=80", 1, 0, "French-Trimmed Rib Chops", "48 Hours Chilled (0°C - 4°C)", "240 kcal / 100g"),

            # Fish
            ("Seer Fish (Vanjaram / Surmai) Steaks", "Fish", 950.0, 12, "Freshly caught marine Seer fish sliced into thick, meaty center steaks with single center bone.", "https://images.unsplash.com/photo-1519708227418-c8fd9a32b7a2?auto=format&fit=crop&w=800&q=80", 1, 1, "Thick Center Steaks (18mm)", "24 Hours Chilled (0°C - 2°C)", "135 kcal / 100g"),
            ("Rohu River Fish Curry Cut", "Fish", 320.0, 15, "Freshwater Rohu cleaned, descaled, and cut into traditional Bengali & South Indian curry pieces.", "https://images.unsplash.com/photo-1534604973900-c43ab4c2e0ab?auto=format&fit=crop&w=800&q=80", 1, 0, "Descaled Curry Steaks", "24 Hours Chilled (0°C - 2°C)", "115 kcal / 100g"),
            ("Norwegian Atlantic Salmon Fillet", "Fish", 1650.0, 8, "Rich, omega-3 packed boneless salmon fillets skin-on, ready for pan-searing or baking.", "https://images.unsplash.com/photo-1599084993091-1cb5c0721cc6?auto=format&fit=crop&w=800&q=80", 1, 0, "Pin-Bone Removed Fillet", "24 Hours Chilled (0°C - 2°C)", "208 kcal / 100g"),
            ("Pomfret Whole Cleaned (White)", "Fish", 880.0, 0, "Delicate, buttery whole white pomfret gutted, cleaned, and slit for masala tawa fry.", "https://images.unsplash.com/photo-1615141982883-c7ad0e69fd62?auto=format&fit=crop&w=800&q=80", 0, 0, "Whole Gutted & Slit", "24 Hours Chilled (0°C - 2°C)", "120 kcal / 100g"),

            # Seafood
            ("Fresh Tiger Prawns (Cleaned & Deveined)", "Seafood", 640.0, 18, "Large coastal tiger prawns peeled, deveined, and washed in chilled RO water—zero prep needed.", "https://images.unsplash.com/photo-1565680018434-b513d5e5fd47?auto=format&fit=crop&w=800&q=80", 1, 1, "Peeled & Deveined (30-40 count)", "24 Hours Chilled (0°C - 2°C)", "99 kcal / 100g"),
            ("Blue Swimmer Crabs (Whole Cleaned)", "Seafood", 580.0, 10, "Sweet and meaty coastal blue crabs shell-cleaned and halved for spicy Chettinad crab masala.", "https://images.unsplash.com/photo-1559737558-2f5a35f4523b?auto=format&fit=crop&w=800&q=80", 1, 0, "Cleaned & Halved", "24 Hours Chilled (0°C - 2°C)", "97 kcal / 100g"),
            ("Fresh Squid Rings (Calamari)", "Seafood", 520.0, 0, "Tender, cleaned squid tubes sliced into uniform rings for crispy golden calamari or garlic stir-fry.", "https://images.unsplash.com/photo-1604909052743-94e838986d24?auto=format&fit=crop&w=800&q=80", 1, 0, "Cleaned Tube Rings", "24 Hours Chilled (0°C - 2°C)", "92 kcal / 100g"),
            ("Jumbo Sea Prawns (Tail-On)", "Seafood", 760.0, 10, "Export-quality jumbo prawns with tail intact, ideal for garlic butter prawns and skewer grills.", "https://images.unsplash.com/photo-1559742811-822873691df8?auto=format&fit=crop&w=800&q=80", 0, 0, "Peeled Tail-On (16-20 count)", "24 Hours Chilled (0°C - 2°C)", "105 kcal / 100g")
        ]
        c.executemany('''INSERT INTO products 
            (name, category, price_per_kg, discount_percent, description, image_url, in_stock, featured, cut_type, shelf_life, calories) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', sample_products)

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
    all_products = conn.execute('SELECT * FROM products LIMIT 4').fetchall()
    conn.close()
    return render_template('index.html', featured=featured_products, products=all_products)

# 3. PRODUCT PAGE (Multiple Pages with Pagination + Category & Search)
@app.route('/products')
def products():
    category = request.args.get('category', 'All')
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 6

    conn = get_db()
    if search_query:
        like_q = f'%{search_query}%'
        total_items = conn.execute(
            'SELECT COUNT(*) FROM products WHERE name LIKE ? OR category LIKE ? OR description LIKE ?',
            (like_q, like_q, like_q)
        ).fetchone()[0]
        total_pages = max(1, math.ceil(total_items / per_page))
        page = max(1, min(page, total_pages))
        offset = (page - 1) * per_page
        items = conn.execute(
            'SELECT * FROM products WHERE name LIKE ? OR category LIKE ? OR description LIKE ? LIMIT ? OFFSET ?',
            (like_q, like_q, like_q, per_page, offset)
        ).fetchall()
    elif category != 'All':
        total_items = conn.execute('SELECT COUNT(*) FROM products WHERE category = ?', (category,)).fetchone()[0]
        total_pages = max(1, math.ceil(total_items / per_page))
        page = max(1, min(page, total_pages))
        offset = (page - 1) * per_page
        items = conn.execute(
            'SELECT * FROM products WHERE category = ? LIMIT ? OFFSET ?',
            (category, per_page, offset)
        ).fetchall()
    else:
        total_items = conn.execute('SELECT COUNT(*) FROM products').fetchone()[0]
        total_pages = max(1, math.ceil(total_items / per_page))
        page = max(1, min(page, total_pages))
        offset = (page - 1) * per_page
        items = conn.execute('SELECT * FROM products LIMIT ? OFFSET ?', (per_page, offset)).fetchall()

    conn.close()
    return render_template(
        'products.html',
        products=items,
        active_category=category,
        search_query=search_query,
        page=page,
        total_pages=total_pages,
        total_items=total_items
    )

# FULL-SCREEN PRODUCT DETAIL PAGE + SUGGESTED ITEMS AT BOTTOM
@app.route('/product/<int:product_id>')
def product_detail(product_id):
    conn = get_db()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    if not product:
        conn.close()
        flash('Product not found.', 'danger')
        return redirect(url_for('products'))

    same_cat = conn.execute(
        'SELECT * FROM products WHERE category = ? AND id != ? LIMIT 4',
        (product['category'], product_id)
    ).fetchall()

    suggestions = list(same_cat)
    if len(suggestions) < 4:
        needed = 4 - len(suggestions)
        existing_ids = [product_id] + [s['id'] for s in suggestions]
        placeholders = ','.join('?' for _ in existing_ids)
        more = conn.execute(
            f'SELECT * FROM products WHERE id NOT IN ({placeholders}) LIMIT ?',
            (*existing_ids, needed)
        ).fetchall()
        suggestions.extend(more)

    conn.close()
    return render_template('product_detail.html', product=product, suggestions=suggestions)

# WISHLIST PAGE & ACTIONS (Supports AJAX so screen never jumps to top)
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
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    conn = get_db()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    if not product:
        conn.close()
        if is_ajax:
            return jsonify({'success': False, 'message': 'Product not found'}), 404
        return redirect(request.referrer or url_for('products'))

    in_wishlist = False
    if 'user_id' in session:
        user_id = session['user_id']
        existing = conn.execute('SELECT id FROM wishlist WHERE user_id = ? AND product_id = ?', (user_id, product_id)).fetchone()
        if existing:
            conn.execute('DELETE FROM wishlist WHERE user_id = ? AND product_id = ?', (user_id, product_id))
            msg = f'Removed {product["name"]} from your wishlist.'
            in_wishlist = False
        else:
            conn.execute('INSERT INTO wishlist (user_id, product_id) VALUES (?, ?)', (user_id, product_id))
            msg = f'Saved {product["name"]} to your wishlist!'
            in_wishlist = True
        conn.commit()
    else:
        guest_w = session.get('guest_wishlist', [])
        if product_id in guest_w:
            guest_w.remove(product_id)
            msg = f'Removed {product["name"]} from your wishlist.'
            in_wishlist = False
        else:
            guest_w.append(product_id)
            msg = f'Saved {product["name"]} to your wishlist!'
            in_wishlist = True
        session['guest_wishlist'] = guest_w

    conn.close()
    w_count = len(get_user_wishlist_ids())

    if is_ajax:
        return jsonify({
            'success': True,
            'in_wishlist': in_wishlist,
            'wishlist_count': w_count,
            'message': msg
        })

    flash(msg, 'success' if in_wishlist else 'info')
    return redirect(request.referrer or url_for('wishlist'))

@app.route('/wishlist/move-to-cart/<int:product_id>', methods=['POST'])
def move_to_cart(product_id):
    conn = get_db()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    if not product or product['in_stock'] == 0:
        conn.close()
        flash('Sorry, this item is currently out of stock.', 'danger')
        return redirect(url_for('wishlist'))

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
            try:
                send_email_otp(email, otp)
                pending_data = session['pending_reg']
                pending_data['otp_created_at'] = datetime.now().timestamp()
                session['pending_reg'] = pending_data
                flash(f'Verification OTP sent to {email}. Please check your inbox and spam folder.', 'info')
            except Exception as exc:
                session.pop('pending_reg', None)
                flash(f'Could not send verification email: {exc}', 'danger')
                conn.close()
                return redirect(url_for('auth', mode='register'))
            conn.close()
            return redirect(url_for('auth', mode='otp'))

        elif action == 'verify_otp':
            entered_otp = request.form.get('otp').strip()
            pending = session.get('pending_reg')
            if pending and datetime.now().timestamp() - pending.get('otp_created_at', 0) <= 300 and entered_otp == pending['otp']:
                conn.execute(
                    'INSERT INTO users (name, mobile, email, password) VALUES (?, ?, ?, ?)',
                    (pending['name'], pending['mobile'], pending['email'], pending['password'])
                )
                conn.commit()
                user = conn.execute('SELECT * FROM users WHERE email = ?', (pending['email'],)).fetchone()
                session.pop('pending_reg', None)
                session['user_id'] = user['id']
                session['user_name'] = user['name']

                for pid in session.pop('guest_wishlist', []):
                    conn.execute('INSERT IGNORE INTO wishlist (user_id, product_id) VALUES (?, ?)', (user['id'], pid))
                conn.commit()

                flash('Email verified! Welcome to Premium Fresh Meat.', 'success')
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

                for pid in session.pop('guest_wishlist', []):
                    conn.execute('INSERT IGNORE INTO wishlist (user_id, product_id) VALUES (?, ?)', (user['id'], pid))
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
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    conn = get_db()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    conn.close()

    if not product or product['in_stock'] == 0:
        msg = 'Sorry, this item is currently out of stock.'
        if is_ajax:
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'danger')
        return redirect(request.referrer or url_for('products'))

    qty_to_add = request.form.get('qty', 1, type=int)
    if qty_to_add < 1:
        qty_to_add = 1

    cart_data = session.get('cart', {})
    pid = str(product_id)
    final_price = get_discounted_price(product)

    if pid in cart_data:
        cart_data[pid]['qty'] += qty_to_add
    else:
        cart_data[pid] = {
            'name': product['name'],
            'image': product['image_url'],
            'price': final_price,
            'qty': qty_to_add
        }

    session['cart'] = cart_data
    cart_count = sum(item['qty'] for item in cart_data.values())
    msg = f'Added {product["name"]} ({qty_to_add} kg) to cart!'

    if is_ajax:
        return jsonify({
            'success': True,
            'cart_count': cart_count,
            'message': msg
        })

    flash(msg, 'success')
    return redirect(request.referrer or url_for('products'))

@app.route('/cart/update/<pid>/<action>', methods=['GET', 'POST'])
def update_cart(pid, action):
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    cart_data = session.get('cart', {})
    item_qty = 0
    line_total = 0.0

    if pid in cart_data:
        if action == 'inc':
            cart_data[pid]['qty'] += 1
        elif action == 'dec':
            cart_data[pid]['qty'] -= 1
            if cart_data[pid]['qty'] <= 0:
                del cart_data[pid]
        elif action == 'remove':
            del cart_data[pid]

        if pid in cart_data:
            item_qty = cart_data[pid]['qty']
            line_total = round(cart_data[pid]['price'] * item_qty, 2)

    session['cart'] = cart_data

    subtotal = round(sum(item['price'] * item['qty'] for item in cart_data.values()), 2)
    delivery_charge = 0.0 if (subtotal == 0 or subtotal >= 500) else 40.0
    grand_total = round(subtotal + delivery_charge, 2)
    cart_count = sum(item['qty'] for item in cart_data.values())
    amount_needed_for_free = round(max(0.0, 500.0 - subtotal), 2)

    if is_ajax:
        return jsonify({
            'success': True,
            'removed': pid not in cart_data,
            'qty': item_qty,
            'line_total': line_total,
            'subtotal': subtotal,
            'delivery_charge': delivery_charge,
            'grand_total': grand_total,
            'cart_count': cart_count,
            'amount_needed_for_free': amount_needed_for_free
        })

    return redirect(url_for('cart'))

# 5. CHECKOUT & STRICT ONLINE PAYMENT VALIDATION
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
                flash('Please fill in all new delivery address fields before placing the order.', 'danger')
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

        payment_detail_note = "Cash on Delivery"
        if payment_method == "Online Payment":
            online_channel = request.form.get('online_channel', '').strip()
            if online_channel == 'UPI':
                upi_id = request.form.get('upi_id', '').strip()
                if not upi_id or '@' not in upi_id:
                    flash('Order blocked: Please enter a valid UPI ID (e.g. name@upi) to complete Online Payment.', 'danger')
                    conn.close()
                    return redirect(url_for('checkout'))
                payment_detail_note = f"Online (UPI: {upi_id})"
            elif online_channel == 'Card':
                card_name = request.form.get('card_name', '').strip()
                card_number = request.form.get('card_number', '').replace(' ', '').strip()
                card_expiry = request.form.get('card_expiry', '').strip()
                card_cvv = request.form.get('card_cvv', '').strip()
                if not card_name or len(card_number) < 12 or not card_expiry or len(card_cvv) < 3:
                    flash('Order blocked: Please fill in complete Cardholder Name, Card Number, Expiry Date, and CVV.', 'danger')
                    conn.close()
                    return redirect(url_for('checkout'))
                payment_detail_note = f"Online (Card ending ****{card_number[-4:]})"
            elif online_channel == 'NetBanking':
                bank_name = request.form.get('bank_name', '').strip()
                account_ref = request.form.get('bank_user_id', '').strip()
                if not bank_name or not account_ref:
                    flash('Order blocked: Please select your Bank and enter your NetBanking Customer ID.', 'danger')
                    conn.close()
                    return redirect(url_for('checkout'))
                payment_detail_note = f"Online (NetBanking: {bank_name})"
            else:
                flash('Order blocked: Please choose UPI, Card, or NetBanking and enter payment details.', 'danger')
                conn.close()
                return redirect(url_for('checkout'))

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
            payment_detail_note,
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

@app.route('/api/search-suggestions')
def search_suggestions():
    q = request.args.get('q', '').strip()
    if len(q) < 1:
        return jsonify([])
    conn = get_db()
    like_q = f'%{q}%'
    rows = conn.execute(
        'SELECT id, name, category, price_per_kg, discount_percent, image_url, in_stock FROM products WHERE name LIKE ? OR category LIKE ? OR cut_type LIKE ? LIMIT 6',
        (like_q, like_q, like_q)
    ).fetchall()
    conn.close()
    results = []
    for r in rows:
        results.append({
            'id': r['id'],
            'name': r['name'],
            'category': r['category'],
            'price': get_discounted_price(r),
            'image_url': r['image_url'],
            'in_stock': r['in_stock']
        })
    return jsonify(results)

@app.route('/orders/cancel/<int:order_id>', methods=['POST'])
@login_required
def cancel_order(order_id):
    reason_choice = request.form.get('reason_choice', '').strip()
    custom_reason = request.form.get('custom_reason', '').strip()
    if not reason_choice:
        flash('Please select a reason for cancelling the order.', 'warning')
        return redirect(url_for('orders'))
    if reason_choice == 'Other' and not custom_reason:
        flash('Please specify your cancellation reason.', 'warning')
        return redirect(url_for('orders'))

    full_reason = f"{reason_choice}: {custom_reason}" if (reason_choice == 'Other' and custom_reason) else (
        f"{reason_choice} ({custom_reason})" if custom_reason else reason_choice
    )

    conn = get_db()
    order = conn.execute('SELECT * FROM orders WHERE id = ? AND user_id = ?', (order_id, session['user_id'])).fetchone()
    if order and order['delivery_status'] not in ['Delivered', 'Cancelled', 'Return Requested', 'Returned']:
        new_pay_status = "Refund Initiated" if order['payment_status'] == "Paid Online" else "Cancelled"
        conn.execute(
            'UPDATE orders SET delivery_status = ?, payment_status = ?, action_reason = ? WHERE id = ?',
            ('Cancelled', new_pay_status, full_reason, order_id)
        )
        conn.commit()
        flash(f'Order {order["order_code"]} has been cancelled. Reason recorded.', 'info')
    conn.close()
    return redirect(url_for('orders'))

@app.route('/orders/return/<int:order_id>', methods=['POST'])
@login_required
def return_order(order_id):
    reason_choice = request.form.get('reason_choice', '').strip()
    custom_reason = request.form.get('custom_reason', '').strip()
    if not reason_choice:
        flash('Please select a reason for returning the order.', 'warning')
        return redirect(url_for('orders'))
    if reason_choice == 'Other' and not custom_reason:
        flash('Please specify your return reason.', 'warning')
        return redirect(url_for('orders'))

    full_reason = f"{reason_choice}: {custom_reason}" if (reason_choice == 'Other' and custom_reason) else (
        f"{reason_choice} ({custom_reason})" if custom_reason else reason_choice
    )

    conn = get_db()
    order = conn.execute('SELECT * FROM orders WHERE id = ? AND user_id = ?', (order_id, session['user_id'])).fetchone()
    if order and order['delivery_status'] == 'Delivered':
        new_pay_status = "Return Refund Initiated" if "Paid" in order['payment_status'] else "Return Approved (COD)"
        conn.execute(
            'UPDATE orders SET delivery_status = ?, payment_status = ?, action_reason = ? WHERE id = ?',
            ('Return Requested', new_pay_status, full_reason, order_id)
        )
        conn.commit()
        flash(f'Return request submitted for Order {order["order_code"]}. Our cold-chain pickup team will contact you shortly.', 'success')
    conn.close()
    return redirect(url_for('orders'))

# Customer profile support pages
@app.route('/account/notifications')
@login_required
def notifications():
    conn = get_db()
    user_notifications = conn.execute(
        'SELECT order_code, delivery_status, payment_status, order_date FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 20',
        (session['user_id'],)
    ).fetchall()
    conn.close()
    return render_template('account_info.html', page='notifications', notifications=user_notifications)

@app.route('/privacy-policy')
def privacy_policy():
    return render_template('account_info.html', page='privacy')

@app.route('/help-support')
def help_support():
    return render_template('account_info.html', page='support')

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
