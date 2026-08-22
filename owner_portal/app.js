/**
 * PakPOS Standalone Owner Web Portal
 * Pure Client-Side Application (Zero Python / Django Dependency)
 * 100% Read-Only Live Database Visualizer (Crisp Modern Light Theme)
 * Security: Master Password Guard, Payment Notice Integration
 */

window.OwnerPortal = (function() {
    let state = {
        data: {
            Sales: [],
            SaleItems: [],
            Expenses: [],
            ExpenseCategories: [],
            Shifts: [],
            SystemSettings: {},
            Customers: [],
            Tables: []
        },
        currentTab: 'dashboard',
        salesFilter: {
            dateRange: 'all', // 'all', 'today', 'yesterday', '7days', 'month'
            orderType: 'all',
            search: ''
        },
        expenseFilter: {
            dateRange: 'all',
            search: ''
        },
        shiftFilter: {
            dateRange: 'today', // 'today', 'yesterday', 'all', or specific 'YYYY-MM-DD'
            customDate: null
        },
        charts: {},
        isLoading: false,
        lastSyncTime: null,
        isAuthenticated: false,
        activePassword: null
    };

    // Default Fallback Password (matched against Google Apps Script)
    const DEFAULT_MASTER_PASSWORD = "7860";

    // Initialize Application
    function init() {
        checkAuthentication();
        loadCachedData();
        setupNavigation();
        setupEventListeners();
    }

    // =========================================================================
    // 1. MASTER PASSWORD SECURITY & AUTHENTICATION
    // =========================================================================
    function checkAuthentication() {
        const savedSession = sessionStorage.getItem('owner_auth_session');
        const lockOverlay = document.getElementById('lock-screen-overlay');
        
        if (savedSession) {
            state.isAuthenticated = true;
            state.activePassword = savedSession;
            if (lockOverlay) lockOverlay.classList.add('hidden');
            fetchLiveDatabaseData();
        } else {
            state.isAuthenticated = false;
            if (lockOverlay) lockOverlay.classList.remove('hidden');
            const passInput = document.getElementById('master-password-input');
            if (passInput) setTimeout(() => passInput.focus(), 200);
        }
    }

    function togglePasswordVisibility() {
        const passInput = document.getElementById('master-password-input');
        const eyeIcon = document.getElementById('eye-icon');
        if (!passInput) return;

        if (passInput.type === 'password') {
            passInput.type = 'text';
            if (eyeIcon) {
                eyeIcon.innerHTML = '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line>';
            }
        } else {
            passInput.type = 'password';
            if (eyeIcon) {
                eyeIcon.innerHTML = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle>';
            }
        }
    }

    function clearPasswordError() {
        const errorEl = document.getElementById('pin-error-msg');
        if (errorEl) errorEl.classList.remove('show');
    }

    function showPasswordError(msg = "Incorrect Password. Please try again.") {
        const errorEl = document.getElementById('pin-error-msg');
        if (errorEl) {
            errorEl.innerText = msg;
            errorEl.classList.add('show');
        }
        const passInput = document.getElementById('master-password-input');
        if (passInput) {
            passInput.focus();
            passInput.select();
        }
    }

    async function submitPassword() {
        const passInput = document.getElementById('master-password-input');
        const enteredPass = (passInput ? passInput.value : '').trim();

        if (!enteredPass) {
            showPasswordError("Please enter your Master Password");
            return;
        }

        const submitBtn = document.querySelector('#master-password-form button[type="submit"]');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span>Verifying...</span>';
        }

        try {
            const webhookUrl = PORTAL_CONFIG.getWebhookUrl();
            const authParam = `&pin=${encodeURIComponent(enteredPass)}&password=${encodeURIComponent(enteredPass)}`;
            
            const response = await fetch(webhookUrl + '?action=fetch_all' + authParam, {
                method: 'GET',
                headers: { 'Accept': 'application/json' }
            });

            if (response && response.ok) {
                const result = await response.json();
                
                if (result && result.success !== false && result.data) {
                    state.isAuthenticated = true;
                    state.activePassword = enteredPass;
                    sessionStorage.setItem('owner_auth_session', enteredPass);

                    // Clean Fresh State Assignment (Never keep stale deleted data)
                    setFreshCloudData(result.data);

                    const lockOverlay = document.getElementById('lock-screen-overlay');
                    if (lockOverlay) lockOverlay.classList.add('hidden');

                    updateSyncBadge(true);
                    renderAllViews();
                    checkPaymentAlertStatus();
                    return;
                } else if (result && result.error && String(result.error).toLowerCase().includes('denied')) {
                    showPasswordError("Access Denied: Incorrect Master Password");
                    return;
                }
            }

            // Fallback check against local cache
            const settingsPass = (state.data.SystemSettings && (state.data.SystemSettings.owner_password || state.data.SystemSettings.owner_master_pin)) || DEFAULT_MASTER_PASSWORD;
            if (enteredPass === settingsPass || enteredPass === DEFAULT_MASTER_PASSWORD) {
                state.isAuthenticated = true;
                state.activePassword = enteredPass;
                sessionStorage.setItem('owner_auth_session', enteredPass);

                const lockOverlay = document.getElementById('lock-screen-overlay');
                if (lockOverlay) lockOverlay.classList.add('hidden');

                fetchLiveDatabaseData();
            } else {
                showPasswordError("Incorrect Password. Access Denied.");
            }
        } catch (err) {
            const settingsPass = (state.data.SystemSettings && (state.data.SystemSettings.owner_password || state.data.SystemSettings.owner_master_pin)) || DEFAULT_MASTER_PASSWORD;
            if (enteredPass === settingsPass || enteredPass === DEFAULT_MASTER_PASSWORD) {
                state.isAuthenticated = true;
                state.activePassword = enteredPass;
                sessionStorage.setItem('owner_auth_session', enteredPass);
                const lockOverlay = document.getElementById('lock-screen-overlay');
                if (lockOverlay) lockOverlay.classList.add('hidden');
                renderAllViews();
            } else {
                showPasswordError("Verification failed. Please check password.");
            }
        } finally {
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<span>Unlock Portal</span>';
            }
        }
    }

    function lockPortal() {
        state.isAuthenticated = false;
        state.activePassword = null;
        sessionStorage.removeItem('owner_auth_session');

        const lockOverlay = document.getElementById('lock-screen-overlay');
        if (lockOverlay) lockOverlay.classList.remove('hidden');

        const passInput = document.getElementById('master-password-input');
        if (passInput) {
            passInput.value = '';
            setTimeout(() => passInput.focus(), 150);
        }
        clearPasswordError();
    }

    // Clean Fresh Data Setter
    function setFreshCloudData(cloudData) {
        if (!cloudData || typeof cloudData !== 'object') return;
        state.data = {
            Sales: Array.isArray(cloudData.Sales) ? cloudData.Sales : [],
            SaleItems: Array.isArray(cloudData.SaleItems) ? cloudData.SaleItems : [],
            Expenses: Array.isArray(cloudData.Expenses) ? cloudData.Expenses : [],
            ExpenseCategories: Array.isArray(cloudData.ExpenseCategories) ? cloudData.ExpenseCategories : [],
            Shifts: Array.isArray(cloudData.Shifts) ? cloudData.Shifts : [],
            SystemSettings: (cloudData.SystemSettings && typeof cloudData.SystemSettings === 'object') ? cloudData.SystemSettings : {},
            Actions: (cloudData.Actions && typeof cloudData.Actions === 'object') ? cloudData.Actions : {},
            Customers: Array.isArray(cloudData.Customers) ? cloudData.Customers : [],
            Tables: Array.isArray(cloudData.Tables) ? cloudData.Tables : []
        };
        state.lastSyncTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        localStorage.setItem(PORTAL_CONFIG.STORAGE_KEYS.CACHED_DATA, JSON.stringify(state.data));
        localStorage.setItem(PORTAL_CONFIG.STORAGE_KEYS.LAST_SYNC, state.lastSyncTime);
    }

    // =========================================================================
    // 2. PAYMENT ALERT & SUBSCRIPTION NOTICE
    // =========================================================================
    function checkPaymentAlertStatus() {
        const actions = state.data.Actions || {};
        const settings = state.data.SystemSettings || {};
        const banner = document.getElementById('payment-alert-banner');
        if (!banner) return;

        // Check if payment alert is active in Actions tab or SystemSettings
        const actVal = actions.payment_alert_active || actions.payment_alert || actions.alert_active;
        const isAlertActive = (actVal && ["TRUE", "1", "YES", "T", "ON", "ENABLE", "ENABLED"].includes(String(actVal).toUpperCase().trim())) ||
                              settings.payment_alert === true || 
                              String(settings.payment_alert).toLowerCase() === 'true' ||
                              String(settings.payment_status).toLowerCase() === 'overdue' ||
                              String(settings.payment_status).toLowerCase() === 'pending';

        if (isAlertActive) {
            banner.classList.add('show');
            const titleEl = document.getElementById('pay-banner-title');
            const descEl = document.getElementById('pay-banner-desc');
            
            const title = actions.payment_alert_title || actions.alert_title || settings.payment_alert_title || 'Software Subscription Renewal Due';
            const month = actions.payment_pending_month || actions.payment_month || actions.pending_month || '';
            const amount = actions.payment_pending_amount || actions.payment_amount || actions.pending_amount || '';
            const dueDate = actions.payment_due_date || actions.due_date || '';
            const accInfo = actions.payment_account_info || actions.account_info || '';
            const contact = actions.payment_contact_info || actions.contact_info || '';
            const customMsg = actions.payment_alert_message || actions.alert_message || settings.payment_alert_message;

            let descParts = [];
            if (customMsg) {
                descParts.push(customMsg);
            } else {
                let billPart = 'Payment';
                if (month) billPart += ` for ${month}`;
                if (amount) billPart += ` (PKR ${amount})`;
                if (dueDate) billPart += ` - Due Date: ${dueDate}`;
                descParts.push(billPart + '.');
            }
            if (accInfo) descParts.push(`Bank Details: ${accInfo}`);
            if (contact) descParts.push(`Contact: ${contact}`);

            if (titleEl) titleEl.innerText = title;
            if (descEl) descEl.innerText = descParts.join(' | ');
        } else {
            banner.classList.remove('show');
        }
    }

    // =========================================================================
    // 3. DATA FETCH & CACHE ENGINE
    // =========================================================================
    function loadCachedData() {
        const cached = localStorage.getItem(PORTAL_CONFIG.STORAGE_KEYS.CACHED_DATA);
        if (cached) {
            try {
                const parsed = JSON.parse(cached);
                if (parsed && typeof parsed === 'object') {
                    state.data = {
                        Sales: Array.isArray(parsed.Sales) ? parsed.Sales : [],
                        SaleItems: Array.isArray(parsed.SaleItems) ? parsed.SaleItems : [],
                        Expenses: Array.isArray(parsed.Expenses) ? parsed.Expenses : [],
                        ExpenseCategories: Array.isArray(parsed.ExpenseCategories) ? parsed.ExpenseCategories : [],
                        Shifts: Array.isArray(parsed.Shifts) ? parsed.Shifts : [],
                        SystemSettings: (parsed.SystemSettings && typeof parsed.SystemSettings === 'object') ? parsed.SystemSettings : {},
                        Actions: (parsed.Actions && typeof parsed.Actions === 'object') ? parsed.Actions : {},
                        Customers: Array.isArray(parsed.Customers) ? parsed.Customers : [],
                        Tables: Array.isArray(parsed.Tables) ? parsed.Tables : []
                    };
                    state.lastSyncTime = localStorage.getItem(PORTAL_CONFIG.STORAGE_KEYS.LAST_SYNC);
                    updateSyncBadge();
                    if (state.isAuthenticated) {
                        renderAllViews();
                        checkPaymentAlertStatus();
                    }
                }
            } catch (e) {
                console.error("Cache load error:", e);
            }
        }
    }

    async function fetchLiveDatabaseData(isManual = false) {
        // If manual click, unlock stuck state
        if (isManual) {
            state.isLoading = false;
        }

        // Ensure session password exists
        if (!state.isAuthenticated) {
            const savedSession = sessionStorage.getItem('owner_auth_session');
            if (savedSession) {
                state.isAuthenticated = true;
                state.activePassword = savedSession;
                const lockOverlay = document.getElementById('lock-screen-overlay');
                if (lockOverlay) lockOverlay.classList.add('hidden');
            } else {
                const lockOverlay = document.getElementById('lock-screen-overlay');
                if (lockOverlay) lockOverlay.classList.remove('hidden');
                return;
            }
        }

        if (state.isLoading) return;
        state.isLoading = true;

        const refreshBtn = document.getElementById('global-refresh-btn');
        const syncBtnText = document.getElementById('sync-btn-text');
        if (refreshBtn) refreshBtn.classList.add('spinning');
        if (syncBtnText) syncBtnText.innerText = 'Syncing...';

        const webhookUrl = PORTAL_CONFIG.getWebhookUrl();
        const currentPass = state.activePassword || sessionStorage.getItem('owner_auth_session') || DEFAULT_MASTER_PASSWORD;

        try {
            let response = null;
            const authParam = `&pin=${encodeURIComponent(currentPass)}&password=${encodeURIComponent(currentPass)}`;
            try {
                response = await fetch(webhookUrl + '?action=fetch_all' + authParam, {
                    method: 'GET',
                    headers: { 'Accept': 'application/json' }
                });
            } catch (err) {
                response = await fetch(webhookUrl, {
                    method: 'POST',
                    body: JSON.stringify({ fetch_all: true, table: 'all', pin: currentPass, password: currentPass })
                });
            }

            if (response && response.ok) {
                const result = await response.json();
                if (result && result.data) {
                    setFreshCloudData(result.data);
                    updateSyncBadge(true);
                    renderAllViews();
                    checkPaymentAlertStatus();
                } else if (result && result.error && String(result.error).toLowerCase().includes('denied')) {
                    console.warn("Auth check failed:", result.error);
                    updateSyncBadge(false);
                }
            } else {
                updateSyncBadge(false);
            }
        } catch (error) {
            console.warn("Live Database fetch notice:", error);
            updateSyncBadge(false);
        } finally {
            state.isLoading = false;
            if (refreshBtn) refreshBtn.classList.remove('spinning');
            if (syncBtnText) syncBtnText.innerText = 'Sync';
        }
    }

    function updateSyncBadge(isSuccess = null) {
        const syncText = document.getElementById('sync-status-time');
        const syncDot = document.getElementById('sync-pulse-dot');
        const storeNameEl = document.getElementById('portal-store-name');

        if (syncText) {
            syncText.innerText = state.lastSyncTime ? `Last Synced: ${state.lastSyncTime}` : 'Connecting...';
        }

        if (syncDot) {
            if (isSuccess === false) {
                syncDot.style.background = 'var(--danger)';
                syncDot.style.boxShadow = '0 0 8px var(--danger)';
            } else {
                syncDot.style.background = 'var(--success)';
                syncDot.style.boxShadow = '0 0 8px var(--success)';
            }
        }

        const settings = state.data.SystemSettings || {};
        if (storeNameEl) {
            storeNameEl.innerText = settings.app_name || PORTAL_CONFIG.DEFAULT_APP_NAME;
        }
    }

    // =========================================================================
    // 4. NAVIGATION
    // =========================================================================
    function setupNavigation() {
        const navItems = document.querySelectorAll('.nav-item');
        navItems.forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const tab = item.getAttribute('data-tab');
                switchTab(tab);
            });
        });
    }

    function switchTab(tabName) {
        state.currentTab = tabName;

        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.toggle('active', item.getAttribute('data-tab') === tabName);
        });

        document.querySelectorAll('.tab-page').forEach(page => {
            page.classList.toggle('active', page.id === `view-${tabName}`);
        });

        const titles = {
            'dashboard': 'Executive Dashboard',
            'invoices': 'Invoices & Sales Explorer',
            'expenses': 'Expenses & Outflows',
            'shifts': 'Daily Shift & Cash Reconciliation'
        };
        const titleEl = document.getElementById('current-page-title');
        if (titleEl) titleEl.innerText = titles[tabName] || 'Dashboard';

        renderActiveTab();
    }

    function renderActiveTab() {
        if (!state.isAuthenticated) return;
        switch (state.currentTab) {
            case 'dashboard':
                renderDashboard();
                break;
            case 'invoices':
                renderInvoices();
                break;
            case 'expenses':
                renderExpenses();
                break;
            case 'shifts':
                renderShifts();
                break;
        }
    }

    function renderAllViews() {
        if (state.isAuthenticated) renderActiveTab();
    }

    // =========================================================================
    // Helper Formatting Functions
    // =========================================================================
    function parseDate(dateStr) {
        if (!dateStr) return null;
        const d = new Date(dateStr);
        return isNaN(d.getTime()) ? null : d;
    }

    function isDateInRange(dateStr, rangeType, customDateStr = null) {
        if (!dateStr || rangeType === 'all') return true;
        const d = parseDate(dateStr);
        if (!d) return true;

        const now = new Date();
        const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());

        if (rangeType === 'today') {
            return d >= startOfDay;
        } else if (rangeType === 'yesterday') {
            const yesterdayStart = new Date(startOfDay);
            yesterdayStart.setDate(yesterdayStart.getDate() - 1);
            return d >= yesterdayStart && d < startOfDay;
        } else if (rangeType === '7days') {
            const sevenDaysAgo = new Date(startOfDay);
            sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
            return d >= sevenDaysAgo;
        } else if (rangeType === 'month') {
            const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
            return d >= startOfMonth;
        } else if (rangeType === 'specific' && customDateStr) {
            const dateOnly = d.toISOString().split('T')[0];
            return dateOnly === customDateStr;
        }
        return true;
    }

    function formatCurrency(amount) {
        const num = parseFloat(amount) || 0;
        const curr = (state.data.SystemSettings && state.data.SystemSettings.app_currency) || PORTAL_CONFIG.DEFAULT_CURRENCY;
        return `${curr} ${num.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
    }

    function formatDateTime(dateStr) {
        const d = parseDate(dateStr);
        if (!d) return dateStr || '-';
        return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) + ', ' +
               d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    function formatTimeOnly(dateStr) {
        const d = parseDate(dateStr);
        if (!d) return '-';
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    // =========================================================================
    // 1. DASHBOARD VIEW
    // =========================================================================
    function renderDashboard() {
        const sales = state.data.Sales || [];
        const saleItems = state.data.SaleItems || [];
        const expenses = state.data.Expenses || [];

        let totalRevenue = 0;
        let todayOrdersCount = 0;
        sales.forEach(s => {
            totalRevenue += parseFloat(s.total_amount) || 0;
            if (isDateInRange(s.created_at, 'today')) todayOrdersCount++;
        });

        let totalExpense = 0;
        expenses.forEach(e => totalExpense += parseFloat(e.amount) || 0);

        const netProfit = totalRevenue - totalExpense;

        document.getElementById('dash-total-sales').innerText = formatCurrency(totalRevenue);
        document.getElementById('dash-total-orders').innerText = sales.length.toLocaleString();
        document.getElementById('dash-total-expenses').innerText = formatCurrency(totalExpense);
        document.getElementById('dash-expense-count').innerText = expenses.length.toLocaleString();
        document.getElementById('dash-total-profit').innerText = formatCurrency(netProfit);
        document.getElementById('dash-shift-orders-today').innerText = todayOrdersCount.toLocaleString();

        renderDashboardCharts(sales, saleItems, expenses);

        const recentSales = sales.slice().reverse().slice(0, 6);
        const tbody = document.getElementById('dash-recent-sales-tbody');
        if (tbody) {
            tbody.innerHTML = recentSales.length ? recentSales.map(s => `
                <tr>
                    <td><strong>#${s.invoice_number || s.id}</strong></td>
                    <td>${formatDateTime(s.created_at)}</td>
                    <td>${s.customer || 'Walk-in Customer'}</td>
                    <td><span class="badge ${s.order_type === 'dine_in' ? 'badge-blue' : s.order_type === 'delivery' ? 'badge-amber' : 'badge-green'}">${s.order_type || 'Takeaway'}</span></td>
                    <td>${s.payment_method || 'Cash'}</td>
                    <td><strong>${formatCurrency(s.total_amount)}</strong></td>
                    <td>
                        <button class="btn btn-sm" onclick="OwnerPortal.viewReceipt('${s.invoice_number || s.id}')">
                            <span>Receipt</span>
                        </button>
                    </td>
                </tr>
            `).join('') : `<tr><td colspan="7" style="text-align:center; padding: 24px; color: var(--text-muted);">No sales recorded in database yet</td></tr>`;
        }
    }

    function renderDashboardCharts(sales, saleItems, expenses) {
        if (typeof Chart === 'undefined') return;

        // Line Chart: Revenue Trend
        const daysMap = {};
        sales.forEach(s => {
            const d = parseDate(s.created_at);
            if (d) {
                const key = d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
                daysMap[key] = (daysMap[key] || 0) + (parseFloat(s.total_amount) || 0);
            }
        });

        if (Object.keys(daysMap).length < 2) {
            for (let i = 4; i >= 0; i--) {
                const d = new Date();
                d.setDate(d.getDate() - i);
                const key = d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
                if (!daysMap[key]) daysMap[key] = 0;
            }
        }

        const ctxTrend = document.getElementById('chart-sales-trend');
        if (ctxTrend) {
            if (state.charts.trend) state.charts.trend.destroy();
            state.charts.trend = new Chart(ctxTrend, {
                type: 'line',
                data: {
                    labels: Object.keys(daysMap),
                    datasets: [{
                        label: 'Sales Revenue',
                        data: Object.values(daysMap),
                        borderColor: '#2563eb',
                        backgroundColor: 'rgba(37, 99, 235, 0.08)',
                        fill: true,
                        tension: 0.35,
                        pointRadius: 5,
                        pointBackgroundColor: '#2563eb',
                        pointBorderColor: '#ffffff',
                        pointBorderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        y: { grid: { color: '#f1f5f9' }, ticks: { font: { size: 11 } } },
                        x: { grid: { display: false }, ticks: { font: { size: 11 } } }
                    }
                }
            });
        }

        // Bar Chart: Top Products
        const itemQtyMap = {};
        saleItems.forEach(it => {
            const name = it.product_name || it.product || 'Product';
            itemQtyMap[name] = (itemQtyMap[name] || 0) + (parseFloat(it.quantity) || 1);
        });

        const sortedItems = Object.entries(itemQtyMap).sort((a, b) => b[1] - a[1]).slice(0, 5);
        const topLabels = sortedItems.map(x => x[0]);
        const topQtys = sortedItems.map(x => x[1]);

        const ctxTop = document.getElementById('chart-top-products');
        if (ctxTop) {
            if (state.charts.topProducts) state.charts.topProducts.destroy();
            state.charts.topProducts = new Chart(ctxTop, {
                type: 'bar',
                data: {
                    labels: topLabels.length ? topLabels : ['No items sold yet'],
                    datasets: [{
                        label: 'Quantity Sold',
                        data: topQtys.length ? topQtys : [0],
                        backgroundColor: '#10b981',
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        y: { grid: { color: '#f1f5f9' }, ticks: { stepSize: 1, font: { size: 11 } } },
                        x: { grid: { display: false }, ticks: { font: { size: 11 } } }
                    }
                }
            });
        }

        // Doughnut Chart: Expenses
        const expCatMap = {};
        expenses.forEach(e => {
            const cat = e.category || 'General';
            expCatMap[cat] = (expCatMap[cat] || 0) + (parseFloat(e.amount) || 0);
        });

        const ctxExp = document.getElementById('chart-expense-breakdown');
        if (ctxExp) {
            if (state.charts.expenses) state.charts.expenses.destroy();
            const labels = Object.keys(expCatMap);
            const data = Object.values(expCatMap);
            state.charts.expenses = new Chart(ctxExp, {
                type: 'doughnut',
                data: {
                    labels: labels.length ? labels : ['No Expenses'],
                    datasets: [{
                        data: data.length ? data : [1],
                        backgroundColor: ['#ef4444', '#f59e0b', '#10b981', '#2563eb', '#8b5cf6', '#ec4899'],
                        borderWidth: 2,
                        borderColor: '#ffffff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } } }
                }
            });
        }

        // Pie Chart: Payment Methods
        const payMap = { 'Cash': 0, 'Card': 0, 'Online/Other': 0 };
        sales.forEach(s => {
            const method = String(s.payment_method || '').toLowerCase();
            if (method.includes('cash')) payMap['Cash']++;
            else if (method.includes('card')) payMap['Card']++;
            else payMap['Online/Other']++;
        });

        const ctxPay = document.getElementById('chart-payment-methods');
        if (ctxPay) {
            if (state.charts.payments) state.charts.payments.destroy();
            state.charts.payments = new Chart(ctxPay, {
                type: 'pie',
                data: {
                    labels: Object.keys(payMap),
                    datasets: [{
                        data: Object.values(payMap),
                        backgroundColor: ['#2563eb', '#8b5cf6', '#f59e0b'],
                        borderWidth: 2,
                        borderColor: '#ffffff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } } }
                }
            });
        }
    }

    // =========================================================================
    // 2. INVOICES / SALES VIEW
    // =========================================================================
    function renderInvoices() {
        const sales = state.data.Sales || [];
        const filter = state.salesFilter;

        let filtered = sales.filter(s => {
            if (!isDateInRange(s.created_at, filter.dateRange)) return false;
            if (filter.orderType !== 'all' && String(s.order_type).toLowerCase() !== filter.orderType) return false;
            if (filter.search) {
                const q = filter.search.toLowerCase();
                const inv = String(s.invoice_number || s.id).toLowerCase();
                const cashier = String(s.cashier || '').toLowerCase();
                const cust = String(s.customer || '').toLowerCase();
                if (!inv.includes(q) && !cashier.includes(q) && !cust.includes(q)) return false;
            }
            return true;
        });

        let totalRevenue = 0;
        filtered.forEach(s => totalRevenue += parseFloat(s.total_amount) || 0);
        const avgOrder = filtered.length ? (totalRevenue / filtered.length) : 0;

        document.getElementById('inv-total-rev').innerText = formatCurrency(totalRevenue);
        document.getElementById('inv-total-count').innerText = filtered.length.toLocaleString();
        document.getElementById('inv-avg-val').innerText = formatCurrency(avgOrder);

        const tbody = document.getElementById('invoices-tbody');
        if (tbody) {
            tbody.innerHTML = filtered.length ? filtered.slice().reverse().map(s => `
                <tr>
                    <td><strong>#${s.invoice_number || s.id}</strong></td>
                    <td>${formatDateTime(s.created_at)}</td>
                    <td>${s.customer || 'Walk-in Customer'}</td>
                    <td><span class="badge ${s.order_type === 'dine_in' ? 'badge-blue' : s.order_type === 'delivery' ? 'badge-amber' : 'badge-green'}">${s.order_type || 'Takeaway'}</span></td>
                    <td>${s.payment_method || 'Cash'}</td>
                    <td>${formatCurrency(s.subtotal || s.total_amount)}</td>
                    <td>${formatCurrency(s.discount_amount || 0)}</td>
                    <td><strong>${formatCurrency(s.total_amount)}</strong></td>
                    <td>
                        <button class="btn btn-sm" onclick="OwnerPortal.viewReceipt('${s.invoice_number || s.id}')">
                            <span>Receipt</span>
                        </button>
                    </td>
                </tr>
            `).join('') : `<tr><td colspan="9" style="text-align:center; padding: 32px; color: var(--text-muted);">No invoices found for selected filter</td></tr>`;
        }
    }

    function viewReceipt(invoiceNo) {
        const sale = (state.data.Sales || []).find(s => String(s.invoice_number || s.id) === String(invoiceNo));
        if (!sale) return;

        const saleItems = (state.data.SaleItems || []).filter(item => {
            const saleRef = String(item.sale || item.sale_id || '');
            return saleRef.includes(String(sale.invoice_number)) || saleRef === String(sale.id);
        });

        const settings = state.data.SystemSettings || {};

        document.getElementById('rec-store-name').innerText = settings.app_name || PORTAL_CONFIG.DEFAULT_APP_NAME;
        document.getElementById('rec-store-sub').innerText = settings.app_subtitle || 'Sales Receipt';
        document.getElementById('rec-invoice-no').innerText = `#${sale.invoice_number || sale.id}`;
        document.getElementById('rec-date').innerText = formatDateTime(sale.created_at);
        document.getElementById('rec-order-type').innerText = sale.order_type || 'Takeaway';
        document.getElementById('rec-cashier').innerText = sale.cashier || 'Cashier';
        document.getElementById('rec-customer').innerText = sale.customer || 'Walk-in Customer';

        const itemsBody = document.getElementById('rec-items-tbody');
        if (itemsBody) {
            itemsBody.innerHTML = saleItems.length ? saleItems.map(it => `
                <tr>
                    <td style="padding: 6px 0;">${it.product_name || it.product || 'Item'} x ${it.quantity}</td>
                    <td style="text-align: right; padding: 6px 0;">${formatCurrency(it.total_price || (it.unit_price * it.quantity))}</td>
                </tr>
            `).join('') : `<tr><td colspan="2" style="padding: 10px 0; color: #64748b;">Items breakdown not itemized</td></tr>`;
        }

        document.getElementById('rec-subtotal').innerText = formatCurrency(sale.subtotal || sale.total_amount);
        document.getElementById('rec-tax').innerText = formatCurrency(sale.tax_amount || 0);
        document.getElementById('rec-discount').innerText = formatCurrency(sale.discount_amount || 0);
        document.getElementById('rec-total').innerText = formatCurrency(sale.total_amount);
        document.getElementById('rec-payment-method').innerText = sale.payment_method || 'Cash';

        const modal = document.getElementById('receipt-modal');
        if (modal) modal.classList.add('show');
    }

    function closeReceiptModal() {
        const modal = document.getElementById('receipt-modal');
        if (modal) modal.classList.remove('show');
    }

    // =========================================================================
    // 3. EXPENSES VIEW
    // =========================================================================
    function renderExpenses() {
        const expenses = state.data.Expenses || [];
        const filter = state.expenseFilter;

        let filtered = expenses.filter(e => {
            const expDate = e.date || e.created_at;
            if (!isDateInRange(expDate, filter.dateRange)) return false;
            if (filter.search) {
                const q = filter.search.toLowerCase();
                const desc = String(e.description || '').toLowerCase();
                const cat = String(e.category || '').toLowerCase();
                if (!desc.includes(q) && !cat.includes(q)) return false;
            }
            return true;
        });

        let total = 0;
        filtered.forEach(e => total += parseFloat(e.amount) || 0);
        document.getElementById('exp-total-amount').innerText = formatCurrency(total);
        document.getElementById('exp-total-count').innerText = filtered.length.toLocaleString();

        const tbody = document.getElementById('expenses-tbody');
        if (tbody) {
            tbody.innerHTML = filtered.length ? filtered.slice().reverse().map(e => `
                <tr>
                    <td><span class="badge badge-amber">${e.category || 'General'}</span></td>
                    <td><strong>${e.description || 'Expense Entry'}</strong></td>
                    <td>${formatDateTime(e.date || e.created_at)}</td>
                    <td>${e.logged_by || 'Admin'}</td>
                    <td><strong style="color: var(--danger); font-size: 14px;">${formatCurrency(e.amount)}</strong></td>
                </tr>
            `).join('') : `<tr><td colspan="5" style="text-align:center; padding: 32px; color: var(--text-muted);">No expenses recorded for this period</td></tr>`;
        }
    }

    // =========================================================================
    // 4. DAILY SHIFTS VIEW (REAL-TIME CASH RECONCILIATION REPORT)
    // =========================================================================
    function renderShifts() {
        const sales = state.data.Sales || [];
        const expenses = state.data.Expenses || [];
        const filter = state.shiftFilter;

        const shiftSales = sales.filter(s => {
            return isDateInRange(s.created_at, filter.dateRange, filter.customDate);
        });

        const shiftExpenses = expenses.filter(e => {
            const expDate = e.date || e.created_at;
            return isDateInRange(expDate, filter.dateRange, filter.customDate);
        });

        let grossSales = 0;
        let cashSales = 0;
        let cardSales = 0;
        let onlineSales = 0;

        const cashierMap = {};
        const orderTypeMap = {
            'dine_in': { label: '🍽️ Dine-in', orders: 0, revenue: 0 },
            'takeaway': { label: '📦 Takeaway', orders: 0, revenue: 0 },
            'delivery': { label: '🛵 Delivery', orders: 0, revenue: 0 },
            'walk_in': { label: '🛍️ Walk-in', orders: 0, revenue: 0 }
        };

        shiftSales.forEach(s => {
            const amount = parseFloat(s.total_amount) || 0;
            grossSales += amount;

            const method = String(s.payment_method || '').toLowerCase();
            if (method.includes('cash')) cashSales += amount;
            else if (method.includes('card')) cardSales += amount;
            else onlineSales += amount;

            const cName = s.cashier || 'Cashier (Admin)';
            if (!cashierMap[cName]) {
                cashierMap[cName] = { cashier: cName, orders: 0, cash: 0, card: 0, total: 0 };
            }
            cashierMap[cName].orders++;
            cashierMap[cName].total += amount;
            if (method.includes('cash')) cashierMap[cName].cash += amount;
            else if (method.includes('card')) cashierMap[cName].card += amount;

            const oType = String(s.order_type || 'takeaway').toLowerCase();
            if (!orderTypeMap[oType]) {
                orderTypeMap[oType] = { label: oType.charAt(0).toUpperCase() + oType.slice(1), orders: 0, revenue: 0 };
            }
            orderTypeMap[oType].orders++;
            orderTypeMap[oType].revenue += amount;
        });

        let totalShiftExpenses = 0;
        shiftExpenses.forEach(e => totalShiftExpenses += parseFloat(e.amount) || 0);

        const totFloat = grossSales > 0 ? grossSales : 1;
        const cashPct = Math.round((cashSales / totFloat) * 100);
        const cardPct = Math.round((cardSales / totFloat) * 100);
        const onlinePct = Math.round((onlineSales / totFloat) * 100);

        document.getElementById('shift-kpi-gross').innerText = formatCurrency(grossSales);
        document.getElementById('shift-kpi-orders').innerText = shiftSales.length.toLocaleString();
        document.getElementById('shift-kpi-cash').innerText = formatCurrency(cashSales);
        document.getElementById('shift-kpi-cash-pct').innerText = `${cashPct}%`;
        document.getElementById('shift-kpi-card').innerText = formatCurrency(cardSales);
        document.getElementById('shift-kpi-card-pct').innerText = `${cardPct}%`;
        document.getElementById('shift-kpi-online').innerText = formatCurrency(onlineSales);
        document.getElementById('shift-kpi-online-pct').innerText = `${onlinePct}%`;
        document.getElementById('shift-kpi-expenses').innerText = formatCurrency(totalShiftExpenses);

        const cashierTbody = document.getElementById('shift-cashier-tbody');
        const cashierList = Object.values(cashierMap);
        if (cashierTbody) {
            cashierTbody.innerHTML = cashierList.length ? cashierList.map(c => `
                <tr>
                    <td><strong>${c.cashier}</strong></td>
                    <td><span class="badge badge-blue">${c.orders} Orders</span></td>
                    <td>${formatCurrency(c.cash)}</td>
                    <td>${formatCurrency(c.card)}</td>
                    <td><strong style="color: var(--primary);">${formatCurrency(c.total)}</strong></td>
                </tr>
            `).join('') : `<tr><td colspan="5" style="text-align:center; padding: 20px; color: var(--text-muted);">No cashier activity in this shift</td></tr>`;
        }

        const orderTypesTbody = document.getElementById('shift-ordertypes-tbody');
        const orderTypeList = Object.values(orderTypeMap).filter(ot => ot.orders > 0);
        if (orderTypesTbody) {
            orderTypesTbody.innerHTML = orderTypeList.length ? orderTypeList.map(ot => {
                const pct = Math.round((ot.revenue / totFloat) * 100);
                return `
                    <tr>
                        <td><strong>${ot.label}</strong></td>
                        <td>${ot.orders}</td>
                        <td><strong>${formatCurrency(ot.revenue)}</strong></td>
                        <td><span class="badge badge-green">${pct}%</span></td>
                    </tr>
                `;
            }).join('') : `<tr><td colspan="4" style="text-align:center; padding: 20px; color: var(--text-muted);">No orders in this shift</td></tr>`;
        }

        const shiftInvoicesTbody = document.getElementById('shift-invoices-tbody');
        const countBadge = document.getElementById('shift-table-count-badge');
        if (countBadge) countBadge.innerText = `${shiftSales.length} Invoices`;

        if (shiftInvoicesTbody) {
            shiftInvoicesTbody.innerHTML = shiftSales.length ? shiftSales.slice().reverse().map(s => `
                <tr>
                    <td><strong>#${s.invoice_number || s.id}</strong></td>
                    <td>${formatTimeOnly(s.created_at)}</td>
                    <td>${s.customer || 'Walk-in'}</td>
                    <td>${s.cashier || 'Admin'}</td>
                    <td><span class="badge ${s.order_type === 'dine_in' ? 'badge-blue' : s.order_type === 'delivery' ? 'badge-amber' : 'badge-green'}">${s.order_type || 'Takeaway'}</span></td>
                    <td>${s.payment_method || 'Cash'}</td>
                    <td><strong>${formatCurrency(s.total_amount)}</strong></td>
                    <td>
                        <button class="btn btn-sm" onclick="OwnerPortal.viewReceipt('${s.invoice_number || s.id}')">
                            <span>Receipt</span>
                        </button>
                    </td>
                </tr>
            `).join('') : `<tr><td colspan="8" style="text-align:center; padding: 32px; color: var(--text-muted);">No invoices processed during this shift</td></tr>`;
        }
    }

    // =========================================================================
    // Event Listeners Setup
    // =========================================================================
    function setupEventListeners() {
        const refreshBtn = document.getElementById('global-refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => fetchLiveDatabaseData());
        }

        document.querySelectorAll('#invoices-pills .pill-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('#invoices-pills .pill-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                state.salesFilter.dateRange = btn.getAttribute('data-range');
                renderInvoices();
            });
        });

        const invSearch = document.getElementById('inv-search-input');
        if (invSearch) {
            invSearch.addEventListener('input', (e) => {
                state.salesFilter.search = e.target.value;
                renderInvoices();
            });
        }

        const invType = document.getElementById('inv-type-select');
        if (invType) {
            invType.addEventListener('change', (e) => {
                state.salesFilter.orderType = e.target.value;
                renderInvoices();
            });
        }

        document.querySelectorAll('#expenses-pills .pill-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('#expenses-pills .pill-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                state.expenseFilter.dateRange = btn.getAttribute('data-range');
                renderExpenses();
            });
        });

        const expSearch = document.getElementById('exp-search-input');
        if (expSearch) {
            expSearch.addEventListener('input', (e) => {
                state.expenseFilter.search = e.target.value;
                renderExpenses();
            });
        }

        document.querySelectorAll('#shift-pills .pill-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('#shift-pills .pill-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const range = btn.getAttribute('data-range');
                state.shiftFilter.dateRange = range;
                state.shiftFilter.customDate = null;
                const picker = document.getElementById('shift-date-picker');
                if (picker) picker.value = '';
                renderShifts();
            });
        });

        const shiftPicker = document.getElementById('shift-date-picker');
        if (shiftPicker) {
            shiftPicker.addEventListener('change', (e) => {
                if (e.target.value) {
                    document.querySelectorAll('#shift-pills .pill-btn').forEach(b => b.classList.remove('active'));
                    state.shiftFilter.dateRange = 'specific';
                    state.shiftFilter.customDate = e.target.value;
                    renderShifts();
                }
            });
        }
    }

    // Public API
    return {
        init,
        viewTab: switchTab,
        viewReceipt,
        closeReceiptModal,
        fetchLiveDatabaseData,
        submitPassword,
        togglePasswordVisibility,
        lockPortal
    };
})();

// Auto-run on DOM Ready
document.addEventListener('DOMContentLoaded', () => {
    OwnerPortal.init();
});
