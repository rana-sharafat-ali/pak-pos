/**
 * PakPOS Standalone Owner Web Portal
 * Pure Client-Side Application (Zero Python / Django Dependency)
 * 100% Read-Only Live Database Visualizer (Crisp Modern Light Theme)
 * Security: Master Password Guard, Payment Notice Integration
 * Audited & Logically Calibrated KPI & Graph Engine
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
            Actions: {},
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

    // Default Fallback Password
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
        if (isManual) {
            state.isLoading = false;
        }

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
    // Helper Formatting & Validation Functions
    // =========================================================================
    function isValidSale(s) {
        if (!s) return false;
        const st = String(s.status || 'completed').toLowerCase().trim();
        return st !== 'cancelled' && st !== 'void';
    }

    function parseDate(dateStr) {
        if (!dateStr) return null;
        let str = String(dateStr).trim();
        // Safe parsing for YYYY-MM-DD to avoid UTC midnight rollover
        if (/^\d{4}-\d{2}-\d{2}$/.test(str)) {
            const parts = str.split('-');
            return new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
        }
        if (str.includes(' ') && !str.includes('T')) {
            str = str.replace(' ', 'T');
        }
        const d = new Date(str);
        return isNaN(d.getTime()) ? null : d;
    }

    function isDateInRange(dateStr, rangeType, customDateStr = null) {
        if (!dateStr || rangeType === 'all') return true;
        const d = parseDate(dateStr);
        if (!d) return true;

        const now = new Date();
        const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const endOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59, 999);

        if (rangeType === 'today') {
            return d >= startOfDay && d <= endOfDay;
        } else if (rangeType === 'yesterday') {
            const yesterdayStart = new Date(startOfDay);
            yesterdayStart.setDate(yesterdayStart.getDate() - 1);
            return d >= yesterdayStart && d < startOfDay;
        } else if (rangeType === '7days') {
            const sevenDaysAgo = new Date(startOfDay);
            sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 6);
            return d >= sevenDaysAgo && d <= endOfDay;
        } else if (rangeType === 'month') {
            const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
            return d >= startOfMonth && d <= endOfDay;
        } else if (rangeType === 'specific' && customDateStr) {
            const target = parseDate(customDateStr);
            if (!target) return true;
            return d.getFullYear() === target.getFullYear() &&
                   d.getMonth() === target.getMonth() &&
                   d.getDate() === target.getDate();
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
        const allSales = state.data.Sales || [];
        const saleItems = state.data.SaleItems || [];
        const expenses = state.data.Expenses || [];

        // Filter valid completed sales
        const completedSales = allSales.filter(isValidSale);

        let totalRevenue = 0;
        let totalTax = 0;
        let totalCharges = 0;
        let totalDiscounts = 0;
        let todayOrdersCount = 0;

        completedSales.forEach(s => {
            totalRevenue += parseFloat(s.total_amount) || 0;
            totalTax += parseFloat(s.tax_amount) || 0;
            totalCharges += parseFloat(s.service_charge_amount) || 0;
            totalDiscounts += parseFloat(s.discount_amount) || 0;
            if (isDateInRange(s.created_at, 'today')) todayOrdersCount++;
        });

        let totalExpense = 0;
        expenses.forEach(e => totalExpense += parseFloat(e.amount) || 0);

        const totalSurcharges = totalTax + totalCharges;
        // Net Profit = Total Revenue Inflow - Tax - Service Charges - Operating Expenses
        const netProfit = totalRevenue - totalTax - totalCharges - totalExpense;

        document.getElementById('dash-total-sales').innerText = formatCurrency(totalRevenue);
        document.getElementById('dash-total-orders').innerText = completedSales.length.toLocaleString();
        document.getElementById('dash-total-expenses').innerText = formatCurrency(totalExpense);
        document.getElementById('dash-expense-count').innerText = expenses.length.toLocaleString();
        
        const taxEl = document.getElementById('dash-total-tax-charges');
        const taxSubEl = document.getElementById('dash-tax-charges-sub');
        if (taxEl) taxEl.innerText = `+${formatCurrency(totalSurcharges)}`;
        if (taxSubEl) taxSubEl.innerText = `Tax: ${formatCurrency(totalTax)} • Service: ${formatCurrency(totalCharges)}`;

        document.getElementById('dash-total-profit').innerText = formatCurrency(netProfit);
        const profitSub = document.getElementById('dash-profit-sub');
        if (profitSub) profitSub.innerText = `Sales (${formatCurrency(totalRevenue)}) − Tax/Fees (${formatCurrency(totalSurcharges)}) − Exp (${formatCurrency(totalExpense)})`;
        document.getElementById('dash-shift-orders-today').innerText = todayOrdersCount.toLocaleString();

        renderDashboardCharts(completedSales, saleItems, expenses);

        const recentSales = completedSales.slice().reverse().slice(0, 6);
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

        // 1. Line Chart: Daily Sales Revenue Trend (Past -> Today Ascending Chronological Order)
        const timelineDays = [];
        for (let i = 6; i >= 0; i--) {
            const d = new Date();
            d.setDate(d.getDate() - i);
            const dateKey = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
            const label = d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
            timelineDays.push({ key: dateKey, label: label, revenue: 0 });
        }

        sales.forEach(s => {
            const d = parseDate(s.created_at);
            if (d) {
                const sKey = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
                const slot = timelineDays.find(t => t.key === sKey);
                if (slot) {
                    slot.revenue += parseFloat(s.total_amount) || 0;
                }
            }
        });

        const ctxTrend = document.getElementById('chart-sales-trend');
        if (ctxTrend) {
            if (state.charts.trend) state.charts.trend.destroy();
            state.charts.trend = new Chart(ctxTrend, {
                type: 'line',
                data: {
                    labels: timelineDays.map(t => t.label),
                    datasets: [{
                        label: 'Sales Revenue',
                        data: timelineDays.map(t => t.revenue),
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

        // 2. Bar Chart: Top Selling Products (Net Quantity Sold)
        const validSaleIds = new Set();
        sales.forEach(s => {
            if (s.id !== undefined && s.id !== null) validSaleIds.add(String(s.id).trim());
            if (s.invoice_number) validSaleIds.add(String(s.invoice_number).trim());
        });

        const itemQtyMap = {};
        
        saleItems.forEach(it => {
            const saleRef = String(it.sale || it.sale_id || '').trim();
            const itInv = String(it.invoice_number || '').trim();

            let belongsToValidSale = false;
            if (!saleRef && !itInv) {
                // If items aren't tagged to a specific sale, consider valid
                belongsToValidSale = true;
            } else if (validSaleIds.has(saleRef) || (itInv && validSaleIds.has(itInv))) {
                belongsToValidSale = true;
            } else {
                for (const s of sales) {
                    if (matchItemToSale(it, s)) {
                        belongsToValidSale = true;
                        break;
                    }
                }
            }

            if (belongsToValidSale) {
                let baseName = String(it.product_name || it.product || 'Product').trim();
                // Clean up string representations like "Product - PKR 100 (Active)"
                if (baseName.includes(' - ')) baseName = baseName.split(' - ')[0].trim();
                const fullName = it.variant_name ? `${baseName} (${it.variant_name})` : baseName;
                const netQty = Math.max(0, (parseFloat(it.quantity) || 1) - (parseFloat(it.refunded_quantity) || 0));
                if (netQty > 0) {
                    itemQtyMap[fullName] = (itemQtyMap[fullName] || 0) + netQty;
                }
            }
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

        // 3. Doughnut Chart: Expense Categories Breakdown
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
            const hasData = labels.length > 0 && data.some(v => v > 0);

            state.charts.expenses = new Chart(ctxExp, {
                type: 'doughnut',
                data: {
                    labels: hasData ? labels : ['No Outflows Recorded'],
                    datasets: [{
                        data: hasData ? data : [1],
                        backgroundColor: hasData ? ['#ef4444', '#f59e0b', '#10b981', '#2563eb', '#8b5cf6', '#ec4899'] : ['#e2e8f0'],
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

        // 4. Pie Chart: Payment Methods Distribution (Revenue Share)
        const payRevenueMap = { 'Cash': 0, 'Card': 0, 'Online / Digital': 0 };
        sales.forEach(s => {
            const amount = parseFloat(s.total_amount) || 0;
            const method = String(s.payment_method || '').toLowerCase();
            if (method.includes('cash')) payRevenueMap['Cash'] += amount;
            else if (method.includes('card')) payRevenueMap['Card'] += amount;
            else payRevenueMap['Online / Digital'] += amount;
        });

        const ctxPay = document.getElementById('chart-payment-methods');
        if (ctxPay) {
            if (state.charts.payments) state.charts.payments.destroy();
            const payLabels = Object.keys(payRevenueMap);
            const payData = Object.values(payRevenueMap);
            const hasPayData = payData.some(v => v > 0);

            state.charts.payments = new Chart(ctxPay, {
                type: 'pie',
                data: {
                    labels: hasPayData ? payLabels : ['No Payments Recorded'],
                    datasets: [{
                        data: hasPayData ? payData : [1],
                        backgroundColor: hasPayData ? ['#2563eb', '#8b5cf6', '#f59e0b'] : ['#e2e8f0'],
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

        // 5. Doughnut Chart: Order Channels Distribution (Dine-in vs Takeaway vs Delivery vs Walk-in)
        const orderChannelMap = {
            'walk_in': { label: 'Walk-In / Counter', revenue: 0, count: 0 },
            'dine_in': { label: 'Dine-In', revenue: 0, count: 0 },
            'takeaway': { label: 'Takeaway', revenue: 0, count: 0 },
            'delivery': { label: 'Delivery', revenue: 0, count: 0 }
        };
        sales.forEach(s => {
            const ot = String(s.order_type || 'walk_in').toLowerCase();
            const amount = parseFloat(s.total_amount) || 0;
            if (orderChannelMap[ot]) {
                orderChannelMap[ot].revenue += amount;
                orderChannelMap[ot].count++;
            } else {
                orderChannelMap[ot] = { label: ot.charAt(0).toUpperCase() + ot.slice(1), revenue: amount, count: 1 };
            }
        });

        const ctxChannels = document.getElementById('chart-order-channels');
        if (ctxChannels) {
            if (state.charts.orderChannels) state.charts.orderChannels.destroy();
            const channelLabels = Object.values(orderChannelMap).map(c => c.label);
            const channelRevenues = Object.values(orderChannelMap).map(c => c.revenue);
            const hasChannelData = channelRevenues.some(v => v > 0);

            state.charts.orderChannels = new Chart(ctxChannels, {
                type: 'doughnut',
                data: {
                    labels: hasChannelData ? channelLabels : ['No Orders Recorded'],
                    datasets: [{
                        data: hasChannelData ? channelRevenues : [1],
                        backgroundColor: hasChannelData ? ['#2563eb', '#10b981', '#f59e0b', '#8b5cf6'] : ['#e2e8f0'],
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
        const allSales = state.data.Sales || [];
        const filter = state.salesFilter;

        let filtered = allSales.filter(s => {
            if (!isValidSale(s)) return false;
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
            tbody.innerHTML = filtered.length ? filtered.slice().reverse().map(s => {
                const subtotal = parseFloat(s.subtotal) || (parseFloat(s.total_amount) + (parseFloat(s.discount_amount) || 0) - (parseFloat(s.tax_amount) || 0));
                return `
                    <tr>
                        <td><strong>#${s.invoice_number || s.id}</strong></td>
                        <td>${formatDateTime(s.created_at)}</td>
                        <td>${s.customer || 'Walk-in Customer'}</td>
                        <td><span class="badge ${s.order_type === 'dine_in' ? 'badge-blue' : s.order_type === 'delivery' ? 'badge-amber' : 'badge-green'}">${s.order_type || 'Takeaway'}</span></td>
                        <td>${s.payment_method || 'Cash'}</td>
                        <td>${formatCurrency(subtotal)}</td>
                        <td>${formatCurrency(s.discount_amount || 0)}</td>
                        <td><strong>${formatCurrency(s.total_amount)}</strong></td>
                        <td>
                            <button class="btn btn-sm" onclick="OwnerPortal.viewReceipt('${s.invoice_number || s.id}')">
                                <span>Receipt</span>
                            </button>
                        </td>
                    </tr>
                `;
            }).join('') : `<tr><td colspan="9" style="text-align:center; padding: 32px; color: var(--text-muted);">No invoices found for selected filter</td></tr>`;
        }
    }

    function matchItemToSale(item, sale) {
        if (!item || !sale) return false;
        const saleIdStr = String(sale.id).trim();
        const invoiceStr = String(sale.invoice_number || '').trim();
        const itemSaleRef = String(item.sale || item.sale_id || '').trim();
        const itemInv = String(item.invoice_number || '').trim();

        if (itemInv && invoiceStr && itemInv.toLowerCase() === invoiceStr.toLowerCase()) return true;
        if (itemSaleRef && saleIdStr && itemSaleRef === saleIdStr) return true;
        if (invoiceStr && itemSaleRef && itemSaleRef.includes(invoiceStr)) return true;
        if (saleIdStr && itemSaleRef && (itemSaleRef.startsWith(saleIdStr + ' ') || itemSaleRef.startsWith(saleIdStr + '-') || itemSaleRef.startsWith(saleIdStr + ':'))) return true;
        return false;
    }

    function viewReceipt(invoiceNo) {
        const sale = (state.data.Sales || []).find(s => String(s.invoice_number || s.id) === String(invoiceNo));
        if (!sale) return;

        const saleItems = (state.data.SaleItems || []).filter(item => matchItemToSale(item, sale));

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
            itemsBody.innerHTML = saleItems.length ? saleItems.map(it => {
                const itemName = it.product_name || it.product || 'Item';
                const varName = it.variant_name ? ` (${it.variant_name})` : '';
                const qty = it.quantity || 1;
                const lineTotal = parseFloat(it.total_price) || (parseFloat(it.unit_price || 0) * qty);
                return `
                    <tr>
                        <td style="padding: 6px 0;">${itemName}${varName} x ${qty}</td>
                        <td style="text-align: right; padding: 6px 0;">${formatCurrency(lineTotal)}</td>
                    </tr>
                `;
            }).join('') : `<tr><td colspan="2" style="padding: 10px 0; color: #64748b;">Items breakdown not itemized</td></tr>`;
        }

        const subtotal = parseFloat(sale.subtotal) || (parseFloat(sale.total_amount) + (parseFloat(sale.discount_amount) || 0) - (parseFloat(sale.tax_amount) || 0));
        document.getElementById('rec-subtotal').innerText = formatCurrency(subtotal);
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
        const allSales = state.data.Sales || [];
        const expenses = state.data.Expenses || [];
        const settings = state.data.SystemSettings || {};
        const filter = state.shiftFilter;

        // Shift Timing Badge from SystemSettings
        const startHour = settings.pos_shift_start_hour !== undefined ? String(settings.pos_shift_start_hour).padStart(2, '0') : '00';
        const endHour = settings.pos_shift_end_hour !== undefined ? String(settings.pos_shift_end_hour).padStart(2, '0') : '23';
        const timingBadge = document.getElementById('shift-timing-badge');
        if (timingBadge) {
            timingBadge.innerText = `Shift Hours: ${startHour}:00 – ${endHour}:00`;
        }

        const shiftSales = allSales.filter(s => {
            if (!isValidSale(s)) return false;
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
            let isCash = false;
            let isCard = false;
            let isOnline = false;

            if (method.includes('cash')) {
                cashSales += amount;
                isCash = true;
            } else if (method.includes('card')) {
                cardSales += amount;
                isCard = true;
            } else {
                onlineSales += amount;
                isOnline = true;
            }

            const cName = s.cashier || 'Cashier (Admin)';
            if (!cashierMap[cName]) {
                cashierMap[cName] = { cashier: cName, orders: 0, cash: 0, card: 0, online: 0, total: 0 };
            }
            cashierMap[cName].orders++;
            cashierMap[cName].total += amount;
            if (isCash) cashierMap[cName].cash += amount;
            else if (isCard) cashierMap[cName].card += amount;
            else if (isOnline) cashierMap[cName].online += amount;

            const oType = String(s.order_type || 'takeaway').toLowerCase();
            if (!orderTypeMap[oType]) {
                orderTypeMap[oType] = { label: oType.charAt(0).toUpperCase() + oType.slice(1), orders: 0, revenue: 0 };
            }
            orderTypeMap[oType].orders++;
            orderTypeMap[oType].revenue += amount;
        });

        let totalShiftExpenses = 0;
        shiftExpenses.forEach(e => totalShiftExpenses += parseFloat(e.amount) || 0);

        const netCashInDrawer = cashSales - totalShiftExpenses;
        const totFloat = grossSales > 0 ? grossSales : 1;
        const cashPct = Math.round((cashSales / totFloat) * 100);
        const cardPct = Math.round((cardSales / totFloat) * 100);
        const onlinePct = Math.round((onlineSales / totFloat) * 100);

        document.getElementById('shift-kpi-gross').innerText = formatCurrency(grossSales);
        document.getElementById('shift-kpi-orders').innerText = shiftSales.length.toLocaleString();
        
        const cashCardEl = document.getElementById('shift-kpi-cash');
        const cashSubEl = document.getElementById('shift-kpi-cash-pct');
        if (cashCardEl) {
            cashCardEl.innerText = formatCurrency(netCashInDrawer);
            if (netCashInDrawer < 0) {
                cashCardEl.style.color = 'var(--danger)';
                if (cashSubEl) cashSubEl.innerHTML = `<span style="color: var(--danger); font-weight: 700;">⚠️ Deficit (Outflows exceed cash)</span>`;
            } else {
                cashCardEl.style.color = 'var(--success)';
                if (cashSubEl) cashSubEl.innerText = `Cash Sales (${formatCurrency(cashSales)}) − Outflows`;
            }
        }

        document.getElementById('shift-kpi-card').innerText = formatCurrency(cardSales);
        document.getElementById('shift-kpi-card-pct').innerText = `${cardPct}% of shift`;
        document.getElementById('shift-kpi-online').innerText = formatCurrency(onlineSales);
        document.getElementById('shift-kpi-online-pct').innerText = `${onlinePct}% of shift`;
        document.getElementById('shift-kpi-expenses').innerText = formatCurrency(totalShiftExpenses);

        // Render Shift Hourly Sales Velocity Chart
        const ctxHourly = document.getElementById('chart-hourly-shift');
        if (ctxHourly) {
            if (state.charts.hourlyShift) state.charts.hourlyShift.destroy();

            const startH = settings.pos_shift_start_hour !== undefined ? parseInt(settings.pos_shift_start_hour, 10) : 9;
            const endH = settings.pos_shift_end_hour !== undefined ? parseInt(settings.pos_shift_end_hour, 10) : 23;

            const shiftHourSlots = [];
            if (startH <= endH) {
                for (let h = startH; h <= endH; h++) shiftHourSlots.push(h);
            } else {
                for (let h = startH; h < 24; h++) shiftHourSlots.push(h);
                for (let h = 0; h <= endH; h++) shiftHourSlots.push(h);
            }

            const hourlyRevenueMap = {};
            shiftHourSlots.forEach(h => hourlyRevenueMap[h] = 0);

            let peakHourLabel = 'None';
            let peakHourRev = 0;

            shiftSales.forEach(s => {
                const d = parseDate(s.created_at);
                if (d) {
                    const hr = d.getHours();
                    const amt = parseFloat(s.total_amount) || 0;
                    if (hourlyRevenueMap[hr] !== undefined) {
                        hourlyRevenueMap[hr] += amt;
                    }
                }
            });

            const hourlyLabels = shiftHourSlots.map(h => {
                const period = h < 12 ? 'AM' : 'PM';
                const disp = h % 12 || 12;
                const label = `${disp} ${period}`;
                const rev = hourlyRevenueMap[h] || 0;
                if (rev > peakHourRev) {
                    peakHourRev = rev;
                    peakHourLabel = label;
                }
                return label;
            });
            const hourlyData = shiftHourSlots.map(h => hourlyRevenueMap[h] || 0);

            const peakBadge = document.getElementById('shift-peak-hour-badge');
            if (peakBadge) {
                peakBadge.innerText = peakHourRev > 0 ? `⭐ Peak: ${peakHourLabel} (${formatCurrency(peakHourRev)})` : 'Shift Timeline';
            }

            state.charts.hourlyShift = new Chart(ctxHourly, {
                type: 'bar',
                data: {
                    labels: hourlyLabels,
                    datasets: [{
                        label: 'Hourly Revenue',
                        data: hourlyData,
                        backgroundColor: '#3b82f6',
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => ` Revenue: ${formatCurrency(ctx.parsed.y)}`
                            }
                        }
                    },
                    scales: {
                        y: { beginAtZero: true, grid: { color: '#f1f5f9' }, ticks: { font: { size: 10 } } },
                        x: { grid: { display: false }, ticks: { font: { size: 10 } } }
                    }
                }
            });
        }

        // Render Shift Expenses Table
        const expTbody = document.getElementById('shift-expenses-tbody');
        const expBadge = document.getElementById('shift-expenses-count-badge');
        if (expBadge) expBadge.innerText = `${shiftExpenses.length} Outflows`;
        if (expTbody) {
            expTbody.innerHTML = shiftExpenses.length ? shiftExpenses.slice().reverse().map(e => `
                <tr>
                    <td><span class="badge badge-amber">${e.category || 'General'}</span></td>
                    <td><strong>${e.description || 'Expense Entry'}</strong></td>
                    <td>${formatTimeOnly(e.date || e.created_at)}</td>
                    <td>${e.logged_by || 'Admin'}</td>
                    <td><strong style="color: var(--danger); font-size: 14px;">-${formatCurrency(e.amount)}</strong></td>
                </tr>
            `).join('') : `<tr><td colspan="5" style="text-align:center; padding: 20px; color: var(--text-muted);">No expense outflows recorded during this shift</td></tr>`;
        }

        const cashierTbody = document.getElementById('shift-cashier-tbody');
        const cashierList = Object.values(cashierMap);
        if (cashierTbody) {
            cashierTbody.innerHTML = cashierList.length ? cashierList.map(c => `
                <tr>
                    <td><strong>${c.cashier}</strong></td>
                    <td><span class="badge badge-blue">${c.orders} Orders</span></td>
                    <td>${formatCurrency(c.cash)}</td>
                    <td>${formatCurrency(c.card)}</td>
                    <td>${formatCurrency(c.online)}</td>
                    <td><strong style="color: var(--primary);">${formatCurrency(c.total)}</strong></td>
                </tr>
            `).join('') : `<tr><td colspan="6" style="text-align:center; padding: 20px; color: var(--text-muted);">No cashier activity in this shift</td></tr>`;
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
            refreshBtn.addEventListener('click', () => fetchLiveDatabaseData(true));
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
