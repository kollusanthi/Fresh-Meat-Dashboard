
const API_URL = "http://127.0.0.1:5000";

let customers = [];
let notifications = [];
let orders = [];

let ordersChart = null;
let revenueChart = null;


// PAGE NAVIGATION
function showPage(pageId, element) {

    document.querySelectorAll(".page").forEach(page => {
        page.hidden = true;
    });

    document.getElementById(pageId).hidden = false;

    document.querySelectorAll(".sidebar nav a").forEach(link => {
        link.classList.remove("active");
    });

    if (element) {
        element.classList.add("active");
    } else {
        document.querySelectorAll(".sidebar nav a").forEach(link => {
            if (link.getAttribute("onclick").includes(pageId)) {
                link.classList.add("active");
            }
        });
    }

    if (pageId === "dashboard") loadDashboard();
    if (pageId === "orders") loadOrders();
    if (pageId === "customers") loadCustomers();
}


// SAFE HTML
function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    }[char]));
}

function money(value) {
    return "₹" + Number(value || 0).toLocaleString("en-IN");
}


// DASHBOARD
async function loadDashboard() {

    try {
        const response = await fetch(`${API_URL}/api/admin/dashboard`);

        if (!response.ok) throw new Error("Dashboard API error");

        const data = await response.json();

        document.getElementById("totalOrders").innerText =
            data.total_orders ?? 0;

        document.getElementById("totalCustomers").innerText =
            data.total_customers ?? 0;

        document.getElementById("totalRevenue").innerText =
            money(data.total_revenue);

        document.getElementById("pendingOrders").innerText =
            data.pending_orders ?? 0;

        document.getElementById("deliveredOrders").innerText =
            data.delivered_orders ?? 0;

        createCharts(data.daily_orders || [], data.daily_revenue || []);

        renderRecentOrders(data.recent_orders || []);

    } catch (error) {
        console.error(error);
    }
}


// GRAPHS
function createCharts(dailyOrders, dailyRevenue) {

    if (ordersChart) ordersChart.destroy();
    if (revenueChart) revenueChart.destroy();

    const orderCanvas = document.getElementById("ordersChart");
    const revenueCanvas = document.getElementById("revenueChart");

    ordersChart = new Chart(orderCanvas, {
        type: "bar",
        data: {
            labels: dailyOrders.map(item => item.date),
            datasets: [{
                label: "Orders",
                data: dailyOrders.map(item => item.count),
                backgroundColor: "#a9232b",
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: { beginAtZero: true }
            }
        }
    });

    revenueChart = new Chart(revenueCanvas, {
        type: "line",
        data: {
            labels: dailyRevenue.map(item => item.date),
            datasets: [{
                label: "Revenue",
                data: dailyRevenue.map(item => item.amount),
                borderColor: "#a9232b",
                backgroundColor: "rgba(169,35,43,0.12)",
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: { beginAtZero: true }
            }
        }
    });
}


// RECENT ORDERS
function renderRecentOrders(list) {

    const table = document.getElementById("recentOrders");

    if (!list.length) {
        table.innerHTML = `<tr><td colspan="5">No orders available.</td></tr>`;
        return;
    }

    table.innerHTML = list.map(order => `
        <tr>
            <td>#${escapeHTML(order.id)}</td>
            <td>${escapeHTML(order.customer_name)}</td>
            <td>${escapeHTML(order.products_summary)}</td>
            <td>${money(order.total_amount)}</td>
            <td><span class="status">${escapeHTML(order.status)}</span></td>
        </tr>
    `).join("");
}


// ORDERS
async function loadOrders() {

    try {
        const response = await fetch(`${API_URL}/api/admin/orders`);

        if (!response.ok) throw new Error("Orders API error");

        const result = await response.json();

        orders = result.orders || [];

        renderOrders();

    } catch (error) {
        console.error(error);

        document.getElementById("ordersTable").innerHTML =
            `<tr><td colspan="9">Unable to connect to backend or load orders.</td></tr>`;
    }
}


// DISPLAY ORDERS
function renderOrders() {

    const table = document.getElementById("ordersTable");

    const search = document.getElementById("orderSearch")
        .value.toLowerCase();

    const filtered = orders.filter(order =>
        String(order.id).toLowerCase().includes(search) ||
        String(order.customer_name).toLowerCase().includes(search) ||
        String(order.phone).includes(search)
    );

    document.getElementById("orderCount").innerText =
        orders.length;

    const customerMap = {};

    let totalQuantity = 0;

    orders.forEach(order => {

        const phone = String(order.phone || "");

        if (!customerMap[phone]) {
            customerMap[phone] = {
                name: order.customer_name,
                phone: phone,
                count: 0,
                spent: 0
            };
        }

        customerMap[phone].count++;
        customerMap[phone].spent += Number(order.total_amount || 0);

        totalQuantity += Number(order.total_quantity || 0);
    });

    document.getElementById("uniqueCustomers").innerText =
        Object.keys(customerMap).filter(phone => phone !== "").length;

    document.getElementById("productsSold").innerText =
        totalQuantity;

    if (!filtered.length) {
        table.innerHTML = `<tr><td colspan="9">No orders found.</td></tr>`;
    } else {
        table.innerHTML = filtered.map(order => `

            <tr>
                <td>#${escapeHTML(order.id)}</td>
                <td>${escapeHTML(order.customer_name)}</td>
                <td>${escapeHTML(order.phone)}</td>
                <td>${escapeHTML(order.products_summary)}</td>
                <td>${Number(order.total_quantity || 0)}</td>
                <td>${money(order.total_amount)}</td>
                <td>${escapeHTML(order.order_date)}</td>
                <td>
                    <span class="status ${String(order.status).toLowerCase()}">
                        ${escapeHTML(order.status)}
                    </span>
                </td>
                <td>
                    <button class="details-btn"
                        onclick="showOrderDetails(${Number(order.id)})">
                        View
                    </button>
                </td>
            </tr>

        `).join("");
    }

    renderCustomerOrderHistory(customerMap);
}


// CUSTOMER-WISE ORDER HISTORY
function renderCustomerOrderHistory(customerMap) {

    const table = document.getElementById("customerOrdersTable");

    const list = Object.values(customerMap);

    if (!list.length) {
        table.innerHTML = `<tr><td colspan="4">No customer orders found.</td></tr>`;
        return;
    }

    table.innerHTML = list.map(customer => `
        <tr>
            <td>${escapeHTML(customer.name)}</td>
            <td>${escapeHTML(customer.phone)}</td>
            <td><strong>${customer.count}</strong></td>
            <td>${money(customer.spent)}</td>
        </tr>
    `).join("");
}


// ORDER DETAILS POPUP
function showOrderDetails(id) {

    const order = orders.find(item => Number(item.id) === id);

    if (!order) return;

    const items = Array.isArray(order.items) ? order.items : [];

    document.getElementById("orderDetails").innerHTML = `

        <div class="detail-row">
            <strong>Order ID:</strong> #${escapeHTML(order.id)}
        </div>

        <div class="detail-row">
            <strong>Customer:</strong> ${escapeHTML(order.customer_name)}
        </div>

        <div class="detail-row">
            <strong>Phone:</strong> ${escapeHTML(order.phone)}
        </div>

        <div class="detail-row">
            <strong>Address:</strong> ${escapeHTML(order.address || "Not available")}
        </div>

        <div class="detail-row">
            <strong>Order Date:</strong> ${escapeHTML(order.order_date)}
        </div>

        <div class="detail-row">
            <strong>Payment:</strong> ${escapeHTML(order.payment_status || "Not available")}
        </div>

        <div class="detail-row">
            <strong>Status:</strong> ${escapeHTML(order.status)}
        </div>

        <h3 style="margin-top:20px;">Ordered Products</h3>

        ${items.length ? items.map(item => `
            <div class="detail-row">
                <strong>${escapeHTML(item.product_name)}</strong>
                <br>
                Quantity: ${Number(item.quantity || 0)}
                <br>
                Price: ${money(item.price)}
                <br>
                Subtotal: ${money(Number(item.price || 0) * Number(item.quantity || 0))}
            </div>
        `).join("") : "<p>No product details available.</p>"}

        <div class="detail-row">
            <strong>Total Amount:</strong> ${money(order.total_amount)}
        </div>
    `;

    document.getElementById("orderModal").hidden = false;
}


function closeOrderModal() {
    document.getElementById("orderModal").hidden = true;
}


// EXISTING CUSTOMER REGISTRATION CODE
async function loadCustomers() {

    try {
        const response = await fetch(
            `${API_URL}/api/admin/customer-registrations`
        );

        const result = await response.json();

        if (!response.ok) throw new Error("Unable to load customers");

        customers = result.customers.map(customer => ({
            ...customer,
            date: new Date(customer.registered_at + " UTC")
                .toLocaleString("en-IN"),
            status: "New"
        }));

        renderCustomers();

    } catch (error) {
        console.error(error);

        document.getElementById("customerTable").innerHTML =
            `<tr><td colspan="5">Unable to connect to backend.</td></tr>`;
    }
}


function renderCustomers() {

    const table = document.getElementById("customerTable");

    const search = document.getElementById("searchInput")
        .value.toLowerCase();

    const filtered = customers.filter(customer =>
        customer.name.toLowerCase().includes(search) ||
        customer.email.toLowerCase().includes(search) ||
        customer.phone.includes(search)
    );

    document.getElementById("totalCount").innerText =
        customers.length;

    document.getElementById("matchingCount").innerText =
        filtered.length;

    document.getElementById("latestDate").innerText =
        customers.length ? customers[0].date : "--";

    if (!filtered.length) {
        table.innerHTML = `<tr><td colspan="5">No customers found.</td></tr>`;
        return;
    }

    table.innerHTML = filtered.map(customer => `
        <tr>
            <td>
                <strong>${escapeHTML(customer.name)}</strong><br>
                <small>Customer ID: #${escapeHTML(customer.id)}</small>
            </td>
            <td>${escapeHTML(customer.email)}</td>
            <td>${escapeHTML(customer.phone)}</td>
            <td>${escapeHTML(customer.date)}</td>
            <td><span class="status">New</span></td>
        </tr>
    `).join("");
}


// NOTIFICATIONS
async function showNotifications() {

    const panel = document.getElementById("notificationPanel");

    panel.hidden = !panel.hidden;

    if (panel.hidden) return;

    try {
        const response = await fetch(
            `${API_URL}/api/admin/notifications`
        );

        const result = await response.json();

        notifications = result.notifications || [];

        renderNotifications();

    } catch (error) {
        console.error(error);
    }
}


function renderNotifications() {

    const unread = notifications.filter(
        item => item.is_read === 0
    ).length;

    document.getElementById("notificationCount").innerText = unread;

    document.getElementById("notificationList").innerHTML =
        notifications.map(item => `
            <li>
                ${escapeHTML(item.message)}
                <small>${escapeHTML(item.created_at)}</small>
            </li>
        `).join("");
}


async function markRead() {

    await fetch(`${API_URL}/api/admin/notifications/read`, {
        method: "PUT"
    });

    notifications = notifications.map(item => ({
        ...item,
        is_read: 1
    }));

    renderNotifications();
}


// SEARCH
document.getElementById("searchInput")
    .addEventListener("input", renderCustomers);

document.getElementById("orderSearch")
    .addEventListener("input", renderOrders);


// LOGOUT
function logout() {
    if (confirm("Are you sure you want to logout?")) {
        alert("Logout functionality needs authentication setup.");
    }
}


// INITIAL LOAD
loadDashboard();
