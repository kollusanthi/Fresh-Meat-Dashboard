// ======================================================
// FRESHMEAT SELLER PORTAL - COMPLETE JAVASCRIPT
// ======================================================


// ---------------- API CONFIGURATION ----------------

const API = {
    register: "/api/seller/register",
    login: "/api/seller/login",
    logout: "/api/seller/logout",
    me: "/api/seller/me",
    stats: "/api/seller/stats",
    products: "/api/seller/products",
    orders: "/api/seller/orders",
    returns: "/api/seller/returns",
    reviews: "/api/seller/reviews",
    notifications: "/api/seller/notifications",
    password: "/api/seller/change-password",
    riders: "/api/seller/riders",
assignments: "/api/seller/rider-assignments"

};

let productsCache = [];
let notificationsCache = [];


// ======================================================
// NOTIFICATION BELL SYSTEM
// ======================================================

let knownNotificationIds = new Set();
let notificationPollingStarted = false;
let notificationPollingTimer = null;
let notificationAudioContext = null;


// Play notification sound
function playNotificationSound() {
    try {
        const AudioContextClass =
            window.AudioContext || window.webkitAudioContext;

        if (!AudioContextClass) return;

        if (!notificationAudioContext) {
            notificationAudioContext = new AudioContextClass();
        }

        if (notificationAudioContext.state === "suspended") {
            notificationAudioContext.resume();
        }

        const oscillator =
            notificationAudioContext.createOscillator();

        const gain =
            notificationAudioContext.createGain();

        oscillator.connect(gain);
        gain.connect(notificationAudioContext.destination);

        oscillator.type = "sine";

        oscillator.frequency.setValueAtTime(
            880,
            notificationAudioContext.currentTime
        );

        gain.gain.setValueAtTime(
            0.25,
            notificationAudioContext.currentTime
        );

        gain.gain.exponentialRampToValueAtTime(
            0.001,
            notificationAudioContext.currentTime + 0.5
        );

        oscillator.start();

        oscillator.stop(
            notificationAudioContext.currentTime + 0.5
        );

    } catch (error) {
        console.log("Notification sound error:", error);
    }
}


// Update unread notification count
function updateBellCount(notifications) {

    const bellCount =
        document.getElementById("bellCount");

    if (!bellCount) return;

    const unreadCount = notifications.filter(item =>
        Number(item.is_read) === 0
    ).length;

    bellCount.textContent = unreadCount;

    bellCount.classList.toggle(
        "hidden",
        unreadCount === 0
    );

    const dashboardCount =
        document.getElementById("statNotifications");

    if (dashboardCount) {
        dashboardCount.textContent = unreadCount;
    }
}


// Check for new notifications
async function checkNewNotifications() {

    try {

        const data = await apiRequest(API.notifications);

        const notifications = data.notifications || [];

        const newNotifications = notifications.filter(item =>
            !knownNotificationIds.has(Number(item.id))
        );

        // Play sound only when a new notification arrives
        // after the initial notification check
        if (
            knownNotificationIds.size > 0 &&
            newNotifications.length > 0
        ) {
            playNotificationSound();
        }

        // Store notification IDs
        notifications.forEach(item => {
            knownNotificationIds.add(Number(item.id));
        });

        notificationsCache = notifications;

        updateBellCount(notifications);

        // Refresh notification page if currently open
        const page =
            document.getElementById("notificationsPage");

        if (page && !page.classList.contains("hidden")) {
            displayNotifications();
        }

    } catch (error) {

        console.log(
            "Notification check failed:",
            error.message
        );

    }
}


// Start automatic notification checking
function startNotificationPolling() {

    if (notificationPollingStarted) return;

    notificationPollingStarted = true;

    // First check
    checkNewNotifications();

    // Check every 10 seconds
    notificationPollingTimer = setInterval(
        checkNewNotifications,
        10000
    );
}


// Stop notification checking during logout
function stopNotificationPolling() {

    if (notificationPollingTimer) {
        clearInterval(notificationPollingTimer);
        notificationPollingTimer = null;
    }

    notificationPollingStarted = false;

    knownNotificationIds.clear();
}


// Notification bell click event
const notificationBell =
    document.getElementById("notificationBell");

if (notificationBell) {

    notificationBell.addEventListener("click", () => {

        showPage("notifications");

    });

}


// ======================================================
// COMMON FUNCTIONS
// ======================================================


// API request function
async function apiRequest(url, options = {}) {

    const response = await fetch(url, {

        credentials: "same-origin",

        ...options

    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {

        throw new Error(
            data.error ||
            data.message ||
            "Something went wrong."
        );

    }

    return data;
}


// Show messages
function showMessage(elementId, message, success = false) {

    const element =
        document.getElementById(elementId);

    if (!element) return;

    element.textContent = message;

    element.style.color =
        success ? "#16864c" : "#c0392b";
}


// Escape HTML
function escapeHTML(value) {

    return String(value ?? "").replace(/[&<>"']/g, character => ({

        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"

    })[character]);

}


// ======================================================
// AUTH TABS
// ======================================================

const loginTab =
    document.getElementById("loginTab");

const registerTab =
    document.getElementById("registerTab");


if (loginTab && registerTab) {

    loginTab.addEventListener("click", () => {

        loginTab.classList.add("active");

        registerTab.classList.remove("active");

        document.getElementById("loginForm")
            .classList.remove("hidden");

        document.getElementById("registerForm")
            .classList.add("hidden");

    });


    registerTab.addEventListener("click", () => {

        registerTab.classList.add("active");

        loginTab.classList.remove("active");

        document.getElementById("registerForm")
            .classList.remove("hidden");

        document.getElementById("loginForm")
            .classList.add("hidden");

    });

}


// ======================================================
// SELLER REGISTRATION
// ======================================================

const registerForm =
    document.getElementById("registerForm");

if (registerForm) {

    registerForm.addEventListener("submit", async event => {

        event.preventDefault();

        const form = event.target;

        const data = Object.fromEntries(
            new FormData(form).entries()
        );

        try {

            const result = await apiRequest(API.register, {

                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify(data)

            });

            showMessage(
                "registerMessage",
                result.message,
                true
            );

            form.reset();

        } catch (error) {

            showMessage(
                "registerMessage",
                error.message
            );

        }

    });

}


// ======================================================
// SELLER LOGIN
// ======================================================

const loginForm =
    document.getElementById("loginForm");

if (loginForm) {

    loginForm.addEventListener("submit", async event => {

        event.preventDefault();

        const form = event.target;

        const data = Object.fromEntries(
            new FormData(form).entries()
        );

        try {

            const result = await apiRequest(API.login, {

                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify(data)

            });

            showMessage(
                "loginMessage",
                "Login successful!",
                true
            );

            document.getElementById("sellerName").textContent =
                result.seller.name || "Seller";

            form.reset();

            await openPortal();

        } catch (error) {

            showMessage(
                "loginMessage",
                error.message
            );

        }

    });

}


// ======================================================
// PORTAL NAVIGATION
// ======================================================

const navButtons =
    document.querySelectorAll(".nav-btn");


navButtons.forEach(button => {

    button.addEventListener("click", () => {

        showPage(button.dataset.page);

    });

});


function showPage(page) {

    document.querySelectorAll(".page-section")
        .forEach(section => {

            section.classList.add("hidden");

        });


    const selectedPage =
        document.getElementById(page + "Page");


    if (selectedPage) {

        selectedPage.classList.remove("hidden");

    }


    navButtons.forEach(button => {

        button.classList.toggle(
            "active",
            button.dataset.page === page
        );

    });


    const titles = {

        dashboard: "Dashboard",
        products: "My Products",
        orders: "My Orders",
         riders: "Rider Management",
        returns: "Customer Returns",
        reviews: "Customer Reviews",
        notifications: "Notifications",
        profile: "My Profile"

    };


    const pageTitle =
        document.getElementById("pageTitle");

    if (pageTitle) {

        pageTitle.textContent =
            titles[page] || "Dashboard";

    }


    if (page === "dashboard") loadDashboard();

    if (page === "products") loadProducts();

    if (page === "orders") loadOrders();
    if (page === "riders") {
    loadRiders();
    loadRiderAssignments();
}

    if (page === "returns") loadReturns();

    if (page === "reviews") loadReviews();

    if (page === "notifications") loadNotifications();

    if (page === "profile") loadProfile();

}


// Open seller portal
async function openPortal() {

    document.getElementById("authView")
        .classList.add("hidden");

    document.getElementById("portalView")
        .classList.remove("hidden");

    showPage("dashboard");

    // Start automatic notification checking
    startNotificationPolling();

}
// ======================================================
// DASHBOARD ANALYTICS
// ======================================================

async function loadDashboard() {

    try {

        const data = await apiRequest(API.stats);

        // Dashboard statistics
        document.getElementById("statProducts").textContent =
            data.products ?? 0;

        document.getElementById("statOrders").textContent =
            data.orders ?? 0;

        document.getElementById("statPending").textContent =
            data.pending ?? 0;

        document.getElementById("statNotifications").textContent =
            data.notifications ?? 0;

        document.getElementById("statRevenue").textContent =
            "₹" + Number(data.revenue ?? 0).toLocaleString("en-IN");

        document.getElementById("statTodaySales").textContent =
            "₹" + Number(data.today_sales ?? 0).toLocaleString("en-IN");

        document.getElementById("statMonthSales").textContent =
            "₹" + Number(data.month_sales ?? 0).toLocaleString("en-IN");

        document.getElementById("statLowStock").textContent =
            data.low_stock_count ?? 0;


        // Last 7 Days Sales Chart
        const chart = document.getElementById("salesChart");

        if (chart) {

            const sales = data.sales_chart ?? [];

            if (sales.length === 0) {

                chart.innerHTML =
                    "<p>No delivered sales recorded in the last 7 days.</p>";

            } else {

                const maxAmount = Math.max(
                    ...sales.map(item => Number(item.amount)),
                    1
                );

                chart.innerHTML = sales.map(item => {

                    const amount = Number(item.amount);

                    const height = Math.max(
                        (amount / maxAmount) * 180,
                        5
                    );

                    const date = escapeHTML(item.date);

                    return `
                        <div class="sales-bar-item">
                            <div class="sales-amount">
                                ₹${amount.toLocaleString("en-IN")}
                            </div>

                            <div class="sales-bar"
                                 style="height:${height}px">
                            </div>

                            <div class="sales-date">${date}</div>
                        </div>
                    `;

                }).join("");

            }

        }


        // Low Stock Products
        const lowStockList =
            document.getElementById("lowStockList");

        if (lowStockList) {

            const products = data.low_stock_products ?? [];

            if (products.length === 0) {

                lowStockList.innerHTML = `
                    <tr>
                        <td colspan="4">No low stock products.</td>
                    </tr>
                `;

            } else {

                lowStockList.innerHTML = products.map(product => `

                    <tr>
                        <td>${escapeHTML(product.name)}</td>
                        <td>${escapeHTML(product.category || "-")}</td>
                        <td>₹${Number(product.price).toLocaleString("en-IN")}</td>
                        <td>${Number(product.quantity)}</td>
                    </tr>

                `).join("");

            }

        }

    } catch (error) {

        console.error("Dashboard error:", error.message);

    }

}



// ======================================================
// PRODUCTS
// ======================================================

const productForm =
    document.getElementById("productForm");

const productFormContainer =
    document.getElementById("productFormContainer");
// AUTOMATIC DISCOUNT PRICE CALCULATION

const productPriceInput = document.getElementById("productPrice");
const productDiscountInput = document.getElementById("productDiscount");
const offerPriceInput = document.getElementById("offerPrice");

function calculateOfferPrice() {
    const price = Number(productPriceInput.value) || 0;
    const discount = Number(productDiscountInput.value) || 0;

    if (discount < 0 || discount > 100) {
        offerPriceInput.value = "Enter discount between 0 and 100";
        return;
    }

    const finalPrice = price - (price * discount / 100);

    offerPriceInput.value = "₹" + finalPrice.toFixed(2);
}

productPriceInput.addEventListener("input", calculateOfferPrice);
productDiscountInput.addEventListener("input", calculateOfferPrice);
// PRODUCT IMAGE PREVIEW

const productImageInput = document.getElementById("productImage");
const imagePreviewContainer = document.getElementById("imagePreviewContainer");
const productImagePreview = document.getElementById("productImagePreview");

productImageInput.addEventListener("change", function () {

    const file = this.files[0];

    if (file) {

        if (!file.type.startsWith("image/")) {
            alert("Please select a valid image.");
            this.value = "";
            imagePreviewContainer.classList.add("hidden");
            return;
        }

        const imageURL = URL.createObjectURL(file);

        productImagePreview.src = imageURL;

        imagePreviewContainer.classList.remove("hidden");

    } else {

        imagePreviewContainer.classList.add("hidden");
        productImagePreview.src = "";

    }

});

const showProductFormBtn =
    document.getElementById("showProductFormBtn");

if (showProductFormBtn) {

    showProductFormBtn.addEventListener("click", () => {

        productForm.reset();

        productForm.elements.product_id.value = "";

        document.getElementById("productFormTitle")
            .textContent = "Add New Product";

        productFormContainer.classList.remove("hidden");

        showMessage("productMessage", "");

    });

}


const cancelProductBtn =
    document.getElementById("cancelProductBtn");

if (cancelProductBtn) {

    cancelProductBtn.addEventListener("click", () => {

        productFormContainer.classList.add("hidden");

    });

}


// Load products
async function loadProducts() {

    try {

        const data = await apiRequest(API.products);

        productsCache = data.products || [];

        displayProducts();

    } catch (error) {

        document.getElementById("productList").textContent =
            error.message;

    }

}


// Display products
function displayProducts() {

    const container =
        document.getElementById("productList");

    if (!container) return;


    if (productsCache.length === 0) {

        container.innerHTML =
            "<p>No products added yet.</p>";

        return;

    }


    container.innerHTML = productsCache.map(product => {

        const image = product.image

            ? `<img src="${escapeHTML(product.image)}"
                    alt="${escapeHTML(product.name)}">`

            : "";


        return `

            <div class="product-card">

                ${image}

                <h3>${escapeHTML(product.name)}</h3>

                <p>
                    Category:
                    ${escapeHTML(product.category || "Not specified")}
                </p>

                <p>
                    Price:
                    ₹${Number(product.price).toFixed(2)}
                </p>
                <p>
    Quantity:
    ${escapeHTML(product.quantity)}
    ${product.quantity_unit === "grams" ? "grams" : "kg"}
</p>


                <p>
                    Status:
                    ${escapeHTML(product.status)}
                </p>

                <p>
                    ${escapeHTML(product.description || "")}
                </p>


                <div class="product-actions">

                    <button class="edit-btn"
                        data-edit="${product.id}">
                        Edit
                    </button>

                    <button class="delete-btn"
                        data-delete="${product.id}">
                        Delete
                    </button>

                </div>

            </div>

        `;

    }).join("");


    container.querySelectorAll("[data-edit]")
        .forEach(button => {

            button.addEventListener("click", () => {

                editProduct(Number(button.dataset.edit));

            });

        });


    container.querySelectorAll("[data-delete]")
        .forEach(button => {

            button.addEventListener("click", () => {

                deleteProduct(Number(button.dataset.delete));

            });

        });

}


// Add / Update product
if (productForm) {

    productForm.addEventListener("submit", async event => {

        event.preventDefault();

        const productId =
            productForm.elements.product_id.value;

        const formData =
            new FormData(productForm);


        const url = productId

            ? `${API.products}/${productId}`

            : API.products;


        try {

            const result = await apiRequest(url, {

                method: productId ? "PUT" : "POST",

                body: formData

            });


            showMessage(
                "productMessage",
                result.message,
                true
            );


            productForm.reset();

            productFormContainer.classList.add("hidden");


            await loadProducts();

            await loadDashboard();


        } catch (error) {

            showMessage(
                "productMessage",
                error.message
            );

        }

    });

}


// Edit product
function editProduct(productId) {

    const product = productsCache.find(
        item => Number(item.id) === productId
    );

    if (!product) return;


    productForm.reset();

    productForm.elements.product_id.value = product.id;

    productForm.elements.name.value = product.name;

    productForm.elements.category.value =
        product.category || "";

    productForm.elements.price.value = product.price;

    productForm.elements.quantity.value =
        product.quantity;
        productForm.elements.quantity_unit.value =
    product.quantity_unit || "kg";

    productForm.elements.description.value =
        product.description || "";


    document.getElementById("productFormTitle")
        .textContent = "Edit Product";


    productFormContainer.classList.remove("hidden");

    showMessage("productMessage", "");

    productFormContainer.scrollIntoView({
        behavior: "smooth"
    });

}


// Delete product
async function deleteProduct(productId) {

    if (!confirm("Are you sure you want to delete this product?")) {
        return;
    }


    try {

        const result = await apiRequest(
            `${API.products}/${productId}`,
            {
                method: "DELETE"
            }
        );


        alert(result.message);

        await loadProducts();

        await loadDashboard();


    } catch (error) {

        alert(error.message);

    }

}


// ======================================================
// ORDERS
// ======================================================

async function loadOrders() {

    const container =
        document.getElementById("orderList");

    try {

        const data = await apiRequest(API.orders);

        const orders = data.orders || [];


        if (orders.length === 0) {

            container.innerHTML =
                '<tr><td colspan="7">No orders available.</td></tr>';

            return;

        }


        container.innerHTML = orders.map(order => `

            <tr>

                <td>#${escapeHTML(order.id)}</td>

                <td>${escapeHTML(order.customer_name)}</td>

                <td>${escapeHTML(order.customer_phone)}</td>

                <td>${escapeHTML(order.items_summary || "")}</td>

                <td>₹${Number(order.total_amount).toFixed(2)}</td>

                <td>
    ${escapeHTML(order.seller_status || order.order_status || order.status)}

    ${order.seller_status !== "Accepted" ? `
        <button class="primary-btn"
                onclick="acceptCustomerOrder(${order.id})">
            Accept Order
        </button>
    ` : `
        <button class="primary-btn"
                onclick="assignRiderToOrder(${order.id})">
            Assign Rider
        </button>
    `}
</td>

                <td>${escapeHTML(order.created_at)}</td>

            </tr>

        `).join("");


    } catch (error) {

        container.innerHTML = `
            <tr>
                <td colspan="7">
                    ${escapeHTML(error.message)}
                </td>
            </tr>
        `;

    }

}


// ======================================================
// CUSTOMER RETURNS
// ======================================================

async function loadReturns() {

    const container =
        document.getElementById("returnList");

    if (!container) return;


    container.textContent =
        "Loading return requests...";


    try {

        const data = await apiRequest(API.returns);

        const returns = data.returns || [];


        if (returns.length === 0) {

            container.innerHTML =
                "<p>No customer return requests available.</p>";

            return;

        }


        container.innerHTML = returns.map(item => {

            const status =
                String(item.status || "Requested");

            const isRequested =
                status === "Requested";

            const canAssign =
                status === "Approved";

            const canReceive =
                status === "Approved" ||
                status === "Pickup Assigned";


            return `

                <div class="notification-card">

                    <h3>
                        Return #${escapeHTML(item.id)}
                        -
                        ${escapeHTML(item.product_name || "Product")}
                    </h3>


                    <p>
                        <strong>Order ID:</strong>
                        #${escapeHTML(item.order_id)}
                    </p>

                    <p>
                        <strong>Customer:</strong>
                        ${escapeHTML(item.customer_name)}
                    </p>

                    <p>
                        <strong>Phone:</strong>
                        ${escapeHTML(item.customer_phone)}
                    </p>

                    <p>
                        <strong>Address:</strong>
                        ${escapeHTML(item.customer_address || "Not provided")}
                    </p>

                    <p>
                        <strong>Quantity:</strong>
                        ${escapeHTML(item.quantity)}
                    </p>

                    <p>
                        <strong>Return reason:</strong>
                        ${escapeHTML(item.reason)}
                    </p>

                    <p>
                        <strong>Status:</strong>
                        ${escapeHTML(status)}
                    </p>

                    <p>
                        <strong>Rider:</strong>
                        ${escapeHTML(item.rider_name || "Not assigned")}
                    </p>

                    <p>
                        <strong>Rider phone:</strong>
                        ${escapeHTML(item.rider_phone || "Not assigned")}
                    </p>

                    <p>
                        <strong>Rider status:</strong>
                        ${escapeHTML(item.rider_status || "Not assigned")}
                    </p>

                    <p>
                        <strong>Item condition:</strong>
                        ${escapeHTML(item.item_condition || "Not inspected")}
                    </p>


                    ${item.seller_note ? `

                        <p>
                            <strong>Seller note:</strong>
                            ${escapeHTML(item.seller_note)}
                        </p>

                    ` : ""}


                    ${isRequested ? `

                        <div class="form-actions">

                            <button type="button"
                                class="primary-btn"
                                data-return-decision="${item.id}"
                                data-decision="approve">

                                Approve

                            </button>


                            <button type="button"
                                class="secondary-btn"
                                data-return-decision="${item.id}"
                                data-decision="reject">

                                Reject

                            </button>

                        </div>


                        <label for="return-note-${item.id}">
                            Seller note (optional)
                        </label>

                        <textarea
                            id="return-note-${item.id}"
                            rows="2"
                            placeholder="Enter reason or note">
                        </textarea>

                    ` : ""}


                    ${canAssign ? `

                        <div class="form-card">

                            <h4>Assign Return Pickup Rider</h4>


                            <label for="rider-name-${item.id}">
                                Rider Name
                            </label>

                            <input
                                type="text"
                                id="rider-name-${item.id}"
                                placeholder="Enter rider name">


                            <label for="rider-phone-${item.id}">
                                Rider Phone
                            </label>

                            <input
                                type="tel"
                                id="rider-phone-${item.id}"
                                maxlength="10"
                                pattern="[0-9]{10}"
                                placeholder="10-digit phone number">


                            <button type="button"
                                class="primary-btn"
                                data-assign-rider="${item.id}">

                                Assign Rider

                            </button>

                        </div>

                    ` : ""}


                    ${canReceive ? `

                        <div class="form-card">

                            <h4>Confirm Returned Item Received</h4>


                            <label for="condition-${item.id}">
                                Item Condition
                            </label>

                            <select id="condition-${item.id}">

                                <option value="">
                                    Select condition
                                </option>

                                <option value="resellable">
                                    Good / Resellable
                                </option>

                                <option value="damaged">
                                    Damaged
                                </option>

                                <option value="wrong_item">
                                    Wrong Item
                                </option>

                                <option value="opened">
                                    Opened
                                </option>

                                <option value="expired">
                                    Expired
                                </option>

                            </select>


                            <label for="received-note-${item.id}">
                                Inspection Note
                            </label>

                            <textarea
                                id="received-note-${item.id}"
                                rows="2"
                                placeholder="Enter inspection details">
                            </textarea>


                            <button type="button"
                                class="primary-btn"
                                data-return-received="${item.id}">

                                Confirm Received

                            </button>

                        </div>

                    ` : ""}

                </div>

            `;

        }).join("");


        // Approve / Reject buttons
        container.querySelectorAll("[data-return-decision]")
            .forEach(button => {

                button.addEventListener("click", () => {

                    const id =
                        Number(button.dataset.returnDecision);

                    const decision =
                        button.dataset.decision;

                    const note =
                        document.getElementById(
                            `return-note-${id}`
                        )?.value || "";


                    decideReturn(id, decision, note);

                });

            });


        // Assign rider buttons
        container.querySelectorAll("[data-assign-rider]")
            .forEach(button => {

                button.addEventListener("click", () => {

                    const id =
                        Number(button.dataset.assignRider);

                    const riderName =
                        document.getElementById(
                            `rider-name-${id}`
                        )?.value.trim();

                    const riderPhone =
                        document.getElementById(
                            `rider-phone-${id}`
                        )?.value.trim();


                    assignReturnRider(
                        id,
                        riderName,
                        riderPhone
                    );

                });

            });


        // Confirm returned item buttons
        container.querySelectorAll("[data-return-received]")
            .forEach(button => {

                button.addEventListener("click", () => {

                    const id =
                        Number(button.dataset.returnReceived);

                    const condition =
                        document.getElementById(
                            `condition-${id}`
                        )?.value;

                    const note =
                        document.getElementById(
                            `received-note-${id}`
                        )?.value || "";


                    confirmReturnReceived(
                        id,
                        condition,
                        note
                    );

                });

            });


    } catch (error) {

        container.textContent = error.message;

    }

}


// ======================================================
// APPROVE / REJECT RETURN
// ======================================================

async function decideReturn(returnId, decision, note) {

    const actionText =
        decision === "approve" ? "approve" : "reject";


    if (!confirm(
        `Are you sure you want to ${actionText} this return?`
    )) {
        return;
    }


    try {

        const result = await apiRequest(
            `${API.returns}/${returnId}/decision`,
            {

                method: "PATCH",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({

                    decision: decision,

                    seller_note: note

                })

            }
        );


        alert(
            result.message || "Return request updated."
        );

        await loadReturns();

    } catch (error) {

        alert(error.message);

    }

}


// ======================================================
// ASSIGN RETURN PICKUP RIDER
// ======================================================

async function assignReturnRider(
    returnId,
    riderName,
    riderPhone
) {

    if (!riderName || !riderPhone) {

        alert(
            "Please enter rider name and phone number."
        );

        return;

    }


    if (!/^[0-9]{10}$/.test(riderPhone)) {

        alert(
            "Enter a valid 10-digit rider phone number."
        );

        return;

    }


    try {

        const result = await apiRequest(
            `${API.returns}/${returnId}/assign-rider`,
            {

                method: "PATCH",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({

                    rider_name: riderName,

                    rider_phone: riderPhone

                })

            }
        );


        alert(
            result.message ||
            "Rider assigned successfully."
        );

        await loadReturns();

    } catch (error) {

        alert(error.message);

    }

}


// ======================================================
// CONFIRM RETURNED ITEM RECEIVED
// ======================================================

async function confirmReturnReceived(
    returnId,
    condition,
    note
) {

    if (!condition) {

        alert(
            "Please select the returned item's condition."
        );

        return;

    }


    if (!confirm(
        "Confirm that the returned item has been received and inspected?"
    )) {

        return;

    }


    try {

        const result = await apiRequest(
            `${API.returns}/${returnId}/received`,
            {

                method: "PATCH",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({

                    item_condition: condition,

                    seller_note: note

                })

            }
        );


        alert(
            result.message ||
            "Return inspection saved."
        );


        await loadReturns();

        await loadProducts();

        await loadDashboard();


    } catch (error) {

        alert(error.message);

    }

}


// ======================================================
// CUSTOMER REVIEWS
// ======================================================

async function loadReviews() {

    const container =
        document.getElementById("reviewList");

    if (!container) return;


    container.textContent =
        "Loading customer reviews...";


    try {

        const data = await apiRequest(API.reviews);

        const reviews = data.reviews || [];


        if (reviews.length === 0) {

            container.innerHTML =
                "<p>No customer reviews available yet.</p>";

            return;

        }


        container.innerHTML = reviews.map(review => {

            const rating = Math.max(
                0,
                Math.min(5, Number(review.rating) || 0)
            );

            const stars =
                "★".repeat(rating) +
                "☆".repeat(5 - rating);


            return `

                <div class="notification-card">

                    <h3>
                        ${escapeHTML(review.product_name || "Product")}
                    </h3>


                    <p>
                        <strong>Customer:</strong>
                        ${escapeHTML(review.customer_name)}
                    </p>


                    <p>
                        <strong>Rating:</strong>
                        <span>${stars}</span>
                        (${rating}/5)
                    </p>


                    <p>
                        <strong>Review:</strong>
                        ${escapeHTML(review.comment)}
                    </p>


                    <p>
                        <strong>Order ID:</strong>
                        #${escapeHTML(review.order_id)}
                    </p>


                    <small>
                        ${escapeHTML(review.created_at || "")}
                    </small>

                </div>

            `;

        }).join("");


    } catch (error) {

        container.textContent = error.message;

    }

}


// ======================================================
// REFRESH BUTTONS
// ======================================================

const refreshReturnsButton =
    document.getElementById("refreshReturnsBtn");

if (refreshReturnsButton) {

    refreshReturnsButton.addEventListener(
        "click",
        loadReturns
    );

}


const refreshReviewsButton =
    document.getElementById("refreshReviewsBtn");

if (refreshReviewsButton) {

    refreshReviewsButton.addEventListener(
        "click",
        loadReviews
    );

}


// ======================================================
// NOTIFICATIONS PAGE
// ======================================================

async function loadNotifications() {

    const container =
        document.getElementById("notificationList");

    if (!container) return;


    try {

        const data = await apiRequest(API.notifications);

        notificationsCache = data.notifications || [];


        // Update bell unread count
        updateBellCount(notificationsCache);


        // Display notifications
        displayNotifications();


    } catch (error) {

        container.textContent = error.message;

    }

}


// Display notifications
function displayNotifications() {

    const container =
        document.getElementById("notificationList");

    if (!container) return;


    if (notificationsCache.length === 0) {

        container.textContent =
            "No notifications available.";

        return;

    }


    container.innerHTML = notificationsCache.map(notification => `

        <div class="notification-card ${
            notification.is_read ? "" : "unread"
        }">

            <h3>
                ${escapeHTML(notification.title)}
            </h3>


            <p>
                ${escapeHTML(notification.message)}
            </p>


            <small>
                ${escapeHTML(notification.created_at)}
            </small>


            ${
                notification.is_read

                ? "<small>Read</small>"

                : `

                    <button
                        class="secondary-btn mark-read-btn"
                        data-notification="${notification.id}">

                        Mark as Read

                    </button>

                `

            }

        </div>

    `).join("");


    // Mark as read buttons
    container.querySelectorAll(".mark-read-btn")
        .forEach(button => {

            button.addEventListener("click", async () => {

                await markNotificationRead(
                    Number(button.dataset.notification)
                );

            });

        });

}


// Mark one notification as read
async function markNotificationRead(notificationId) {

    try {

        await apiRequest(
            `${API.notifications}/${notificationId}/read`,
            {
                method: "PATCH"
            }
        );


        await loadNotifications();

        await loadDashboard();


    } catch (error) {

        alert(error.message);

    }

}


// Mark all notifications as read
const markAllReadBtn =
    document.getElementById("markAllReadBtn");

if (markAllReadBtn) {

    markAllReadBtn.addEventListener(
        "click",
        async () => {

            try {

                await apiRequest(
                    `${API.notifications}/read-all`,
                    {
                        method: "PATCH"
                    }
                );


                await loadNotifications();

                await loadDashboard();


            } catch (error) {

                alert(error.message);

            }

        }
    );

}


// ======================================================
// SELLER PROFILE
// ======================================================

async function loadProfile() {

    const container =
        document.getElementById("profileDetails");

    try {

        const data = await apiRequest(API.me);

        const seller = data.seller;


        document.getElementById("sellerName").textContent =
            seller.full_name || "Seller";


        const fields = [

            ["Full Name", seller.full_name],

            ["Shop Name", seller.shop_name],

            ["Phone", seller.phone],

            ["Email", seller.email],

            ["Business Category", seller.business_type],

            ["City", seller.city],

            ["State", seller.state],

            ["PIN Code", seller.pincode],

            ["Address", seller.address],

            ["FSSAI Number", seller.fssai_number],

            ["PAN Number", seller.pan_number],

            ["Account Status", seller.status]

        ];


        container.innerHTML = fields.map(([label, value]) => `

            <p>

                <strong>
                    ${escapeHTML(label)}:
                </strong>

                ${escapeHTML(value || "Not provided")}

            </p>

        `).join("");


    } catch (error) {

        container.textContent = error.message;

    }

}


// ======================================================
// CHANGE PASSWORD
// ======================================================

const passwordForm =
    document.getElementById("passwordForm");

if (passwordForm) {

    passwordForm.addEventListener("submit", async event => {

        event.preventDefault();

        const form = event.target;

        const data = Object.fromEntries(
            new FormData(form).entries()
        );


        try {

            const result = await apiRequest(API.password, {

                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify(data)

            });


            showMessage(
                "passwordMessage",
                result.message,
                true
            );

            form.reset();


        } catch (error) {

            showMessage(
                "passwordMessage",
                error.message
            );

        }

    });

}


// ======================================================
// LOGOUT
// ======================================================

const logoutBtn =
    document.getElementById("logoutBtn");

if (logoutBtn) {

    logoutBtn.addEventListener("click", async () => {

        try {

            await apiRequest(API.logout, {

                method: "POST"

            });

        } catch (error) {

            console.error(error);

        }


        // Stop notification polling
        stopNotificationPolling();


        document.getElementById("portalView")
            .classList.add("hidden");

        document.getElementById("authView")
            .classList.remove("hidden");


        showPage("dashboard");

    });

}


// ======================================================
// CHECK EXISTING SESSION
// ======================================================

async function checkExistingSession() {

    try {

        const data = await apiRequest(API.me);


        document.getElementById("sellerName").textContent =
            data.seller.full_name || "Seller";


        await openPortal();


    } catch (error) {

        document.getElementById("authView")
            .classList.remove("hidden");

        document.getElementById("portalView")
            .classList.add("hidden");

    }

}


// Start session check
checkExistingSession();


// ======================================================
// RIDER MANAGEMENT
// ======================================================

// Load Riders
async function loadRiders() {
    const riderList = document.getElementById("riderList");
    if (!riderList) return;

    riderList.textContent = "Loading riders...";

    try {
        const data = await apiRequest(API.riders);
        const riders = data.riders || [];

        if (riders.length === 0) {
            riderList.innerHTML = "<p>No riders added yet.</p>";
            return;
        }

        riderList.innerHTML = riders.map(rider => `
            <div class="form-card">
                <h3>${escapeHTML(rider.rider_name)}</h3>
                <p>Phone: ${escapeHTML(rider.phone)}</p>
                <p>Vehicle: ${escapeHTML(rider.vehicle_number || "-")}</p>
                <p>Type: ${escapeHTML(rider.vehicle_type || "-")}</p>
                <p>Status: ${escapeHTML(rider.availability || "Available")}</p>
            </div>
        `).join("");

    } catch (error) {
        riderList.textContent = error.message;
    }
}


// Add Rider
const riderForm = document.getElementById("riderForm");

if (riderForm) {
    riderForm.addEventListener("submit", async event => {
        event.preventDefault();

        const riderData = {
            rider_name: document.getElementById("riderName").value.trim(),
            phone: document.getElementById("riderPhone").value.trim(),
            vehicle_number: document.getElementById("vehicleNumber").value.trim(),
            vehicle_type: document.getElementById("vehicleType").value
        };

        try {
            const result = await apiRequest(API.riders, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(riderData)
            });

            showMessage("riderMessage", result.message || "Rider added successfully!", true);
            riderForm.reset();
            await loadRiders();

        } catch (error) {
            showMessage("riderMessage", error.message);
        }
    });
}


// Load Rider Assignments
async function loadRiderAssignments() {
    const assignmentList = document.getElementById("riderAssignmentList");
    if (!assignmentList) return;

    try {
        const data = await apiRequest(API.assignments);
        const assignments = data.assignments || [];

        if (assignments.length === 0) {
            assignmentList.innerHTML =
                '<tr><td colspan="6">No deliveries available.</td></tr>';
            return;
        }

        assignmentList.innerHTML = assignments.map(item => `
            <tr>
                <td>#${escapeHTML(item.order_id)}</td>
                <td>${escapeHTML(item.rider_name)}</td>
                <td>${escapeHTML(item.rider_phone)}</td>
                <td>${escapeHTML(item.vehicle_number || "-")}</td>
                <td>${escapeHTML(item.status)}</td>
                <td>
                    <select onchange="changeRiderStatus(${item.id}, this.value)">
                        <option value="">Update Status</option>
                        <option value="Picked Up">Picked Up</option>
                        <option value="On the Way">On the Way</option>
                        <option value="Delivered">Delivered</option>
                    </select>
                </td>
            </tr>
        `).join("");

    } catch (error) {
        assignmentList.innerHTML =
            `<tr><td colspan="6">${escapeHTML(error.message)}</td></tr>`;
    }
}


// Accept Customer Order
async function acceptCustomerOrder(orderId) {
    if (!confirm("Do you want to accept this order?")) return;

    try {
        await apiRequest(`${API.orders}/${orderId}/accept`, {
            method: "PATCH"
        });

        alert("Order accepted successfully!");
        await loadOrders();

    } catch (error) {
        alert(error.message);
    }
}


// Assign Rider to Order
async function assignRiderToOrder(orderId) {
    try {
        const data = await apiRequest(API.riders);
        const riders = (data.riders || []).filter(
            rider => (rider.status || "Available") === "Available"
        );

        if (riders.length === 0) {
            alert("No available riders. Please add a rider first.");
            return;
        }

        const riderOptions = riders.map(rider =>
            `${rider.id}: ${rider.name} (${rider.phone})`
        ).join("\n");

        const selectedId = prompt(
            "Enter Rider ID from the available list:\n\n" + riderOptions
        );

        if (!selectedId) return;

        const riderId = Number(selectedId);

        if (!riders.some(rider => Number(rider.id) === riderId)) {
            alert("Invalid Rider ID.");
            return;
        }

        await apiRequest(API.assignments, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                order_id: orderId,
                rider_id: riderId
            })
        });

        alert("Rider assigned successfully!");
        await loadRiderAssignments();
        await loadRiders();
        await loadOrders();

    } catch (error) {
        alert(error.message);
    }
}


// Update Delivery Status
async function changeRiderStatus(assignmentId, status) {
    if (!status) return;

    try {
        await apiRequest(`${API.assignments}/${assignmentId}/status`, {
            method: "PATCH",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ status: status })
        });

        alert("Delivery status updated!");
        await loadRiderAssignments();
        await loadRiders();

    } catch (error) {
        alert(error.message);
    }
}
