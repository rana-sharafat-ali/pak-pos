/**
 * PakPOS Client-Side Point of Sale (POS) Controller & Cart Engine
 * Includes High-Speed Barcode Scanner Interceptor & Multi-Tab Order Queues
 */

(function () {
    'use strict';

    // State Variables
    let catalog = window.POS_CATALOG || [];
    let currentCategoryId = 0;
    let searchQuery = '';

    // Multi-Tab Cart State
    const isRestaurantMode = (window.POS_MODE === 'restaurant' || window.POS_MODE === 'cafe' || window.POS_MODE === 'food' || window.POS_MODE === 'fast_food');

    let tabs = [
        {
            id: 'tab-1',
            label: 'Order 1',
            items: [],
            customer: { name: 'Walk-in Customer', phone: 'walk_in', email: '', address: '' },
            discount: { type: 'none', value: 0 },
            paymentMethod: 'cash',
            orderType: isRestaurantMode ? 'dine_in' : 'walk_in',
            tableNumber: '',
            notes: '',
        }
    ];
    let activeTabId = 'tab-1';

    // Temp selection states
    let activeProductForVariantModal = null;
    let discountModalType = 'fixed';
    let customerSearchTimeout = null;

    // Hardware Barcode Scanner Buffer
    let barcodeScannerBuffer = '';
    let lastKeyStrokeTime = Date.now();

    // DOM Elements
    const productGrid = document.getElementById('pos-product-grid');
    const searchInput = document.getElementById('pos-search-input');
    const tabBar = document.getElementById('pos-tab-bar');
    const cartContainer = document.getElementById('pos-cart-items-container');
    const customerDisplay = document.getElementById('pos-customer-display');
    const btnOpenPayment = document.getElementById('btn-open-payment');

    // Financial Displays
    const calcSubtotal = document.getElementById('pos-calc-subtotal');
    const calcDiscount = document.getElementById('pos-calc-discount');
    const calcTax = document.getElementById('pos-calc-tax');
    const calcService = document.getElementById('pos-calc-service');
    const calcTotal = document.getElementById('pos-calc-total');
    const discountBadge = document.getElementById('pos-discount-badge');

    // ================= 1. INITIALIZATION =================
    document.addEventListener('DOMContentLoaded', () => {
        renderProductGrid();
        renderTabs();
        renderActiveCart();

        // Search Input Handlers
        if (searchInput) {
            searchInput.focus();

            searchInput.addEventListener('input', (e) => {
                searchQuery = e.target.value.toLowerCase().trim();
                renderProductGrid();
            });

            // Fast Barcode Scanner / Enter Key Handler
            searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    const code = searchInput.value.trim();
                    if (code) {
                        const handled = handleBarcodeScan(code);
                        if (handled) {
                            searchInput.value = '';
                            searchQuery = '';
                            renderProductGrid();
                        }
                    }
                }
            });
        }

        // Global Hardware Barcode Scanner Listener
        setupGlobalBarcodeListener();
    });

    // ================= 2. AUDIO & VISUAL FEEDBACK =================
    function playBeepSound() {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(1400, ctx.currentTime);
            gain.gain.setValueAtTime(0.12, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.09);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.09);
        } catch (e) {
            // Audio context not allowed or blocked
        }
    }

    function showScanFeedbackToast(message) {
        let toast = document.getElementById('pos-scan-toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'pos-scan-toast';
            toast.style.cssText = 'position: fixed; bottom: 25px; left: 50%; transform: translateX(-50%); background: #0f172a; color: #38bdf8; padding: 0.65rem 1.25rem; border-radius: 9999px; font-size: 0.88rem; font-weight: 700; box-shadow: 0 10px 25px rgba(0,0,0,0.3); z-index: 99999; display: flex; align-items: center; gap: 0.5rem; border: 1px solid #38bdf8; transition: all 0.2s ease; opacity: 0; pointer-events: none;';
            document.body.appendChild(toast);
        }
        toast.innerHTML = `<span>⚡ ${message}</span>`;
        toast.style.opacity = '1';
        toast.style.transform = 'translateX(-50%) translateY(-5px)';

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(-50%) translateY(0)';
        }, 1600);
    }

    // ================= 3. BARCODE SCANNING & MATCHING ENGINE =================
    function setupGlobalBarcodeListener() {
        window.addEventListener('keydown', (e) => {
            // Ignore special keys
            if (['Shift', 'Control', 'Alt', 'Meta', 'CapsLock', 'Tab'].includes(e.key)) return;

            // If user is actively typing in a form modal (like customer phone, address, notes, cash amount), skip global intercept
            const activeEl = document.activeElement;
            const isModalInput = activeEl && (
                activeEl.id === 'customer-name-field' ||
                activeEl.id === 'customer-phone-field' ||
                activeEl.id === 'customer-address-field' ||
                activeEl.id === 'discount-value-input' ||
                activeEl.id === 'cash-tendered-input' ||
                activeEl.id === 'order-notes-input'
            );
            if (isModalInput) return;

            const now = Date.now();
            const timeDiff = now - lastKeyStrokeTime;
            lastKeyStrokeTime = now;

            if (e.key === 'Enter') {
                const scannedCode = barcodeScannerBuffer.trim();
                if (scannedCode.length >= 2) {
                    e.preventDefault();
                    const handled = handleBarcodeScan(scannedCode);
                    barcodeScannerBuffer = '';
                    if (handled && searchInput) {
                        searchInput.value = '';
                        searchQuery = '';
                        renderProductGrid();
                    }
                }
            } else if (e.key.length === 1) {
                // If keys arrive with standard typing delay (>120ms), clear buffer
                if (timeDiff > 120) {
                    barcodeScannerBuffer = '';
                }
                barcodeScannerBuffer += e.key;
            }
        });
    }

    function handleBarcodeScan(rawCode) {
        if (!rawCode) return false;
        const code = rawCode.trim();
        const codeLower = code.toLowerCase();

        // -------------------------------------------------------------
        // STEP A: Match Specific Product Variant by Barcode (800 + ProdId + VarId)
        // -------------------------------------------------------------
        for (const prod of catalog) {
            if (prod.has_variants && prod.variants) {
                const matchedVar = prod.variants.find(v => {
                    if (v.barcode && v.barcode === code) return true;
                    // Check standard 8-digit Code128 pattern: 800 + ProdId(3 digits) + VarId(2 digits)
                    if (code.startsWith('800') && code.length >= 8) {
                        const parsedPId = parseInt(code.substring(3, 6), 10);
                        const parsedVId = parseInt(code.substring(6, 8), 10);
                        return prod.id === parsedPId && v.id === parsedVId;
                    }
                    return false;
                });

                if (matchedVar) {
                    addToCart(prod.id, matchedVar.id, prod.name, matchedVar.name, matchedVar.selling_price);
                    playBeepSound();
                    showScanFeedbackToast(`Added ${prod.name} (${matchedVar.name})`);
                    return true;
                }
            }
        }

        // -------------------------------------------------------------
        // STEP B: Match Standard Product by Barcode (800 + ProdId + 00)
        // -------------------------------------------------------------
        const matchedByProdBarcode = catalog.find(prod => {
            if (prod.barcode && prod.barcode === code) return true;
            if (code.startsWith('800') && code.length >= 8) {
                const parsedPId = parseInt(code.substring(3, 6), 10);
                const parsedVId = parseInt(code.substring(6, 8), 10);
                return prod.id === parsedPId && parsedVId === 0;
            }
            return false;
        });

        if (matchedByProdBarcode) {
            if (matchedByProdBarcode.has_variants) {
                openVariantModal(matchedByProdBarcode);
            } else {
                addToCart(matchedByProdBarcode.id, null, matchedByProdBarcode.name, '', matchedByProdBarcode.base_price);
                playBeepSound();
                showScanFeedbackToast(`Added ${matchedByProdBarcode.name}`);
            }
            return true;
        }

        // -------------------------------------------------------------
        // STEP C: Match by Numeric Product ID (e.g. '1', '2', '001')
        // -------------------------------------------------------------
        const numericId = parseInt(code, 10);
        if (!isNaN(numericId)) {
            const matchedById = catalog.find(p => p.id === numericId);
            if (matchedById) {
                if (matchedById.has_variants) {
                    openVariantModal(matchedById);
                } else {
                    addToCart(matchedById.id, null, matchedById.name, '', matchedById.base_price);
                    playBeepSound();
                    showScanFeedbackToast(`Added ${matchedById.name}`);
                }
                return true;
            }
        }

        // -------------------------------------------------------------
        // STEP D: Match by Exact Product Name
        // -------------------------------------------------------------
        const matchedByName = catalog.find(p => p.name.toLowerCase() === codeLower);
        if (matchedByName) {
            if (matchedByName.has_variants) {
                openVariantModal(matchedByName);
            } else {
                addToCart(matchedByName.id, null, matchedByName.name, '', matchedByName.base_price);
                playBeepSound();
                showScanFeedbackToast(`Added ${matchedByName.name}`);
            }
            return true;
        }

        // -------------------------------------------------------------
        // STEP E: If single product matches filtered search query
        // -------------------------------------------------------------
        const filtered = catalog.filter(p => p.name.toLowerCase().includes(codeLower));
        if (filtered.length === 1) {
            const single = filtered[0];
            if (single.has_variants) {
                openVariantModal(single);
            } else {
                addToCart(single.id, null, single.name, '', single.base_price);
                playBeepSound();
                showScanFeedbackToast(`Added ${single.name}`);
            }
            return true;
        }

        return false;
    }

    // ================= 4. PRODUCT CATALOG & GRID =================
    window.filterByCategory = function (catId, btnEl) {
        currentCategoryId = parseInt(catId, 10);
        document.querySelectorAll('.pos-cat-pill').forEach(btn => btn.classList.remove('active'));
        if (btnEl) btnEl.classList.add('active');
        renderProductGrid();
    };

    function renderProductGrid() {
        if (!productGrid) return;
        productGrid.innerHTML = '';

        const filtered = catalog.filter(p => {
            const matchesCat = currentCategoryId === 0 || p.category_id === currentCategoryId;
            const matchesSearch = !searchQuery || p.name.toLowerCase().includes(searchQuery) || (p.barcode && p.barcode.includes(searchQuery));
            return matchesCat && matchesSearch;
        });

        if (filtered.length === 0) {
            productGrid.innerHTML = `
                <div style="grid-column: 1 / -1; text-align: center; padding: 3rem 1rem; color: var(--muted-text);">
                    <div style="font-size: 2rem; margin-bottom: 0.5rem;">🔍</div>
                    <p style="font-size: 0.9rem; font-weight: 600;">No matching products found.</p>
                </div>
            `;
            return;
        }

        filtered.forEach(prod => {
            const card = document.createElement('div');
            card.className = 'pos-item-card';
            card.onclick = () => handleProductClick(prod);

            let variantBadgeHtml = '';
            if (prod.has_variants) {
                variantBadgeHtml = `<span class="pos-variant-tag">${prod.variants.length} Sizes</span>`;
            }

            card.innerHTML = `
                <div>
                    <div class="pos-card-icon-box">${prod.category_icon || '📦'}</div>
                    <div class="pos-card-name" title="${prod.name}">${prod.name}</div>
                </div>
                <div>
                    <div class="pos-card-price">${prod.price_display}</div>
                    ${variantBadgeHtml}
                </div>
            `;
            productGrid.appendChild(card);
        });
    }

    function handleProductClick(product) {
        if (product.has_variants && product.variants && product.variants.length > 0) {
            openVariantModal(product);
        } else {
            addToCart(product.id, null, product.name, '', product.base_price);
            playBeepSound();
        }
    }

    // ================= 5. MULTI-TAB ORDER QUEUE =================
    function getActiveTab() {
        let tab = tabs.find(t => t.id === activeTabId);
        if (!tab) {
            activeTabId = tabs[0].id;
            tab = tabs[0];
        }
        return tab;
    }

    function renderTabs() {
        if (!tabBar) return;
        tabBar.innerHTML = '';

        tabs.forEach((tab) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = `pos-tab-btn ${tab.id === activeTabId ? 'active' : ''}`;
            btn.onclick = () => switchTab(tab.id);

            const countBadge = tab.items.length > 0 ? `(${tab.items.length})` : '';

            let closeBtn = '';
            if (tabs.length > 1) {
                closeBtn = `<span class="pos-tab-close" onclick="event.stopPropagation(); closeTab('${tab.id}')">✕</span>`;
            }

            btn.innerHTML = `<span>${tab.label} ${countBadge}</span>${closeBtn}`;
            tabBar.appendChild(btn);
        });

        // Add Tab Button
        const addBtn = document.createElement('button');
        addBtn.type = 'button';
        addBtn.className = 'pos-tab-add';
        addBtn.onclick = addNewTab;
        addBtn.innerHTML = `<span>+ New Tab</span>`;
        tabBar.appendChild(addBtn);
    }

    window.switchTab = function (tabId) {
        activeTabId = tabId;
        renderTabs();
        renderActiveCart();
    };

    window.addNewTab = function () {
        const nextNum = tabs.length + 1;
        const newTab = {
            id: `tab-${Date.now()}`,
            label: `Order ${nextNum}`,
            items: [],
            customer: { name: 'Walk-in Customer', phone: 'walk_in', email: '', address: '' },
            discount: { type: 'none', value: 0 },
            paymentMethod: 'cash',
            orderType: isRestaurantMode ? 'dine_in' : 'walk_in',
            tableNumber: '',
            notes: '',
        };
        tabs.push(newTab);
        activeTabId = newTab.id;
        renderTabs();
        renderActiveCart();
    };

    window.closeTab = function (tabId) {
        if (tabs.length <= 1) return;
        tabs = tabs.filter(t => t.id !== tabId);
        if (activeTabId === tabId) {
            activeTabId = tabs[0].id;
        }
        renderTabs();
        renderActiveCart();
    };

    // ================= 6. CART OPERATIONS & MATH =================
    function addToCart(productId, variantId, name, variantName, unitPrice) {
        const currentTab = getActiveTab();
        const existing = currentTab.items.find(i => i.productId === productId && i.variantId === variantId);

        if (existing) {
            existing.quantity += 1;
        } else {
            currentTab.items.push({
                productId,
                variantId,
                name,
                variantName,
                unitPrice: parseFloat(unitPrice),
                quantity: 1,
            });
        }

        renderTabs();
        renderActiveCart();
    }

    window.changeItemQty = function (index, delta) {
        const currentTab = getActiveTab();
        const item = currentTab.items[index];
        if (!item) return;

        item.quantity += delta;
        if (item.quantity <= 0) {
            currentTab.items.splice(index, 1);
        }

        renderTabs();
        renderActiveCart();
    };

    window.removeItem = function (index) {
        const currentTab = getActiveTab();
        currentTab.items.splice(index, 1);
        renderTabs();
        renderActiveCart();
    };

    window.clearCurrentCart = function () {
        const currentTab = getActiveTab();
        if (currentTab.items.length === 0) return;
        if (confirm('Clear all items from this active order?')) {
            currentTab.items = [];
            currentTab.discount = { type: 'none', value: 0 };
            renderTabs();
            renderActiveCart();
        }
    };

    function calculateCartTotals() {
        const currentTab = getActiveTab();
        let subtotal = 0;

        currentTab.items.forEach(i => {
            subtotal += i.unitPrice * i.quantity;
        });

        // Discount
        let discountAmount = 0;
        if (currentTab.discount.type === 'fixed') {
            discountAmount = Math.min(currentTab.discount.value, subtotal);
        } else if (currentTab.discount.type === 'percentage') {
            discountAmount = subtotal * (Math.min(100, currentTab.discount.value) / 100);
        }

        const netAfterDiscount = Math.max(0, subtotal - discountAmount);

        // Taxes & Service / Delivery Charges
        const taxRate = window.DEFAULT_TAX_RATE || 0;
        const taxAmount = taxRate > 0 ? (netAfterDiscount * (taxRate / 100)) : 0;

        const orderType = currentTab.orderType || (isRestaurantMode ? 'dine_in' : 'walk_in');
        let serviceRate = 0;
        let serviceAmount = 0;
        let chargeLabel = 'Service Charges';

        if (orderType === 'takeaway' || orderType === 'walk_in') {
            serviceRate = 0;
            serviceAmount = 0;
            chargeLabel = 'Service Charges';
        } else if (orderType === 'delivery') {
            chargeLabel = 'Delivery Charges';
            serviceRate = 0;
            serviceAmount = (currentTab.customCharges !== null && currentTab.customCharges !== undefined) 
                ? currentTab.customCharges 
                : (window.DEFAULT_DELIVERY_CHARGES !== undefined ? window.DEFAULT_DELIVERY_CHARGES : 150);
        } else { // dine_in
            const isCustom = (currentTab.customCharges !== null && currentTab.customCharges !== undefined);
            if (isCustom) {
                chargeLabel = 'Service Charges';
                serviceRate = 0;
                serviceAmount = currentTab.customCharges;
            } else {
                serviceRate = window.DEFAULT_SERVICE_CHARGE_RATE || 0;
                chargeLabel = serviceRate > 0 ? `Service Charges (${serviceRate}%)` : 'Service Charges';
                serviceAmount = serviceRate > 0 ? (netAfterDiscount * (serviceRate / 100)) : 0;
            }
        }

        const totalAmount = netAfterDiscount + taxAmount + serviceAmount;

        return {
            subtotal,
            discountAmount,
            taxAmount,
            serviceAmount,
            totalAmount,
            taxRate,
            serviceRate,
            chargeLabel,
            orderType,
        };
    }

    function renderActiveCart() {
        const currentTab = getActiveTab();

        // Update Customer Display
        if (customerDisplay) {
            customerDisplay.textContent = currentTab.customer.name || 'Walk-in Customer';
        }

        // Render Cart Items
        if (!cartContainer) return;
        cartContainer.innerHTML = '';

        if (currentTab.items.length === 0) {
            cartContainer.innerHTML = `
                <div style="text-align: center; padding: 4rem 1rem; color: var(--muted-text);">
                    <div style="font-size: 2.2rem; margin-bottom: 0.5rem; opacity: 0.6;">🛒</div>
                    <p style="font-size: 0.88rem; font-weight: 600;">Active order is empty.</p>
                    <span style="font-size: 0.78rem; opacity: 0.8;">Click products on the left or scan barcodes to add.</span>
                </div>
            `;
        } else {
            currentTab.items.forEach((item, idx) => {
                const lineTotal = item.unitPrice * item.quantity;
                const row = document.createElement('div');
                row.className = 'pos-cart-item-row';

                let variantSub = item.variantName ? `<span style="font-size: 0.74rem; color: #2563eb; font-weight: 600;">[${item.variantName}]</span> • ` : '';

                row.innerHTML = `
                    <div class="pos-item-title-box">
                        <div class="pos-item-title" title="${item.name}">${item.name}</div>
                        <div class="pos-item-sub">${variantSub}PKR ${item.unitPrice.toFixed(2)}</div>
                    </div>
                    <div class="pos-qty-control">
                        <button type="button" class="pos-qty-btn" onclick="changeItemQty(${idx}, -1)">−</button>
                        <span class="pos-qty-num">${item.quantity}</span>
                        <button type="button" class="pos-qty-btn" onclick="changeItemQty(${idx}, 1)">+</button>
                    </div>
                    <div class="pos-item-price-box">
                        <div class="pos-item-total">PKR ${lineTotal.toFixed(2)}</div>
                    </div>
                    <button type="button" class="pos-item-remove" onclick="removeItem(${idx})" title="Remove item">✕</button>
                `;
                cartContainer.appendChild(row);
            });
        }

        // Calculations Display
        const totals = calculateCartTotals();

        if (calcSubtotal) calcSubtotal.textContent = `PKR ${totals.subtotal.toFixed(2)}`;
        if (calcDiscount) calcDiscount.textContent = `- PKR ${totals.discountAmount.toFixed(2)}`;
        if (calcTax) calcTax.textContent = `PKR ${totals.taxAmount.toFixed(2)}`;
        if (calcService) calcService.textContent = `PKR ${totals.serviceAmount.toFixed(2)}`;
        if (calcTotal) calcTotal.textContent = `PKR ${totals.totalAmount.toFixed(2)}`;
        const chargesLabelEl = document.getElementById('pos-charges-label');
        const chargesRowEl = document.getElementById('pos-charges-row');
        if (chargesLabelEl) {
            chargesLabelEl.textContent = totals.chargeLabel;
        }

        if (discountBadge) {
            discountBadge.textContent = currentTab.discount.type !== 'none' && currentTab.discount.value > 0 ? `(${currentTab.discount.type === 'percentage' ? currentTab.discount.value + '%' : 'PKR ' + currentTab.discount.value})` : '(Edit)';
        }

        const quickDiscBtn = document.getElementById('btn-quick-apply-discount');
        const defaultPercent = window.DEFAULT_DISCOUNT_PERCENT || 0;
        if (quickDiscBtn && defaultPercent > 0) {
            if (currentTab.discount.type === 'percentage' && currentTab.discount.value === defaultPercent) {
                quickDiscBtn.classList.add('active');
                quickDiscBtn.textContent = `${defaultPercent}% Applied ✓`;
            } else {
                quickDiscBtn.classList.remove('active');
                quickDiscBtn.textContent = `Apply ${defaultPercent}%`;
            }
        }

        if (btnOpenPayment) {
            btnOpenPayment.disabled = currentTab.items.length === 0;
        }

        // Sync Restaurant Mode Controls
        const orderType = currentTab.orderType || (isRestaurantMode ? 'dine_in' : 'walk_in');
        document.querySelectorAll('.pos-type-pill').forEach(el => el.classList.remove('active'));
        const activePill = document.getElementById(`btn-type-${orderType}`);
        if (activePill) activePill.classList.add('active');

        const tableBox = document.getElementById('restaurant-table-box');
        if (tableBox) {
            tableBox.style.display = (orderType === 'dine_in') ? 'flex' : 'none';
        }
        const tableSelect = document.getElementById('restaurant-table-select');
        if (tableSelect) {
            tableSelect.value = currentTab.tableNumber || '';
        }
    }

    // ================= RESTAURANT MODE HANDLERS =================
    window.selectOrderType = function (type) {
        const currentTab = getActiveTab();
        currentTab.orderType = type;

        // Reset custom charges on type change so type defaults take effect
        currentTab.customCharges = null;

        document.querySelectorAll('.pos-type-pill').forEach(el => el.classList.remove('active'));
        const activePill = document.getElementById(`btn-type-${type}`);
        if (activePill) activePill.classList.add('active');

        const tableBox = document.getElementById('restaurant-table-box');
        if (tableBox) {
            tableBox.style.display = (type === 'dine_in') ? 'flex' : 'none';
        }

        renderActiveCart();
    };

    window.updateTableSelection = function (table) {
        const currentTab = getActiveTab();
        currentTab.tableNumber = table;
    };

    window.printKitchenOrderTicket = function () {
        const currentTab = getActiveTab();
        if (currentTab.items.length === 0) {
            showScanFeedbackToast('❌ Cart is empty. Add items for KOT.');
            return;
        }

        const now = new Date();
        const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const dateStr = now.toLocaleDateString();

        let itemsRows = '';
        currentTab.items.forEach((item) => {
            const variantText = item.variantName ? `<span style="font-weight: bold;">[${item.variantName}]</span>` : '';
            itemsRows += `
                <tr>
                    <td style="font-size: 16px; font-weight: 900; padding: 6px 0; vertical-align: top;">${item.quantity}x</td>
                    <td style="font-size: 15px; font-weight: 800; padding: 6px 0;">
                        ${item.name} ${variantText}
                    </td>
                </tr>
            `;
        });

        const orderTypeLabel = (currentTab.orderType || 'dine_in').toUpperCase().replace('_', '-');
        const tableLabel = currentTab.tableNumber ? `TABLE: ${currentTab.tableNumber}` : `TYPE: ${orderTypeLabel}`;

        const kotHtml = `
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    @page { margin: 0; size: auto; }
                    body { font-family: monospace; padding: 10px; width: 75mm; margin: 0; color: #000; font-size: 13px; }
                    .kot-header { text-align: center; border-bottom: 2px dashed #000; padding-bottom: 8px; margin-bottom: 8px; }
                    .kot-title { font-size: 18px; font-weight: 900; letter-spacing: 1px; }
                    .kot-table-badge { font-size: 16px; font-weight: 900; background: #000; color: #fff; padding: 4px 8px; margin: 6px 0; display: inline-block; }
                    .kot-meta { font-size: 12px; margin-bottom: 6px; border-bottom: 1px dashed #000; padding-bottom: 6px; }
                    table { width: 100%; border-collapse: collapse; border-bottom: 2px dashed #000; margin-bottom: 8px; }
                    .kot-footer { text-align: center; font-size: 11px; font-weight: bold; }
                </style>
            </head>
            <body>
                <div class="kot-header">
                    <div class="kot-title">🍳 KITCHEN TICKET (KOT)</div>
                    <div class="kot-table-badge">${tableLabel}</div>
                    <div style="font-size: 12px; font-weight: bold;">Order: ${currentTab.label} • ${orderTypeLabel}</div>
                </div>
                <div class="kot-meta">
                    <div>Time: ${timeStr} • Date: ${dateStr}</div>
                    <div>Customer: ${currentTab.customer.name || 'Walk-in'}</div>
                </div>
                <table>
                    <thead>
                        <tr style="border-bottom: 1px solid #000; text-align: left;">
                            <th style="width: 25%;">Qty</th>
                            <th style="width: 75%;">Item Description</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${itemsRows}
                    </tbody>
                </table>
                <div class="kot-footer">
                    *** Send immediately to Kitchen ***
                </div>
            </body>
            </html>
        `;

        let printFrame = document.getElementById('receipt-print-frame');
        if (!printFrame) {
            printFrame = document.createElement('iframe');
            printFrame.id = 'receipt-print-frame';
            printFrame.style.cssText = 'position: fixed; right: 0; bottom: 0; width: 0; height: 0; border: 0; opacity: 0; pointer-events: none;';
            document.body.appendChild(printFrame);
        }

        const doc = printFrame.contentWindow.document;
        doc.open();
        doc.write(kotHtml);
        doc.close();

        setTimeout(() => {
            try {
                printFrame.contentWindow.focus();
                printFrame.contentWindow.print();
            } catch (e) {}
        }, 200);

        playBeepSound();
        showScanFeedbackToast('🍳 KOT sent to Kitchen Printer!');
    };

    // ================= 7. VARIANT SELECTOR MODAL =================
    window.openVariantModal = function (product) {
        activeProductForVariantModal = product;
        const modal = document.getElementById('modal-variant-selector');
        const titleEl = document.getElementById('variant-modal-product-name');
        const listEl = document.getElementById('variant-options-list');

        if (!modal || !listEl) return;

        titleEl.textContent = `Select Size: ${product.name}`;
        listEl.innerHTML = '';

        product.variants.forEach(v => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'pos-cat-pill';
            btn.style.cssText = 'width: 100%; justify-content: space-between; padding: 0.75rem 1rem; border-radius: 8px; font-size: 0.9rem;';
            btn.innerHTML = `
                <strong style="color: var(--secondary);">${v.name}</strong>
                <span style="color: var(--primary); font-weight: 800;">PKR ${v.selling_price.toFixed(2)}</span>
            `;
            btn.onclick = () => {
                addToCart(product.id, v.id, product.name, v.name, v.selling_price);
                playBeepSound();
                showScanFeedbackToast(`Added ${product.name} (${v.name})`);
                closeVariantModal();
            };
            listEl.appendChild(btn);
        });

        modal.style.display = 'flex';
    };

    window.closeVariantModal = function () {
        const modal = document.getElementById('modal-variant-selector');
        if (modal) modal.style.display = 'none';
        activeProductForVariantModal = null;
        if (searchInput) searchInput.focus();
    };

    // ================= 8. CUSTOMER MANAGEMENT MODAL =================
    window.openCustomerModal = function () {
        const modal = document.getElementById('modal-customer');
        const currentTab = getActiveTab();
        if (!modal) return;

        const nameField = document.getElementById('customer-name-field');
        const phoneField = document.getElementById('customer-phone-field');
        const addressField = document.getElementById('customer-address-field');

        if (nameField) nameField.value = currentTab.customer.phone !== 'walk_in' ? currentTab.customer.name : '';
        if (phoneField) phoneField.value = currentTab.customer.phone !== 'walk_in' ? currentTab.customer.phone : '';
        if (addressField) addressField.value = currentTab.customer.address || '';

        modal.style.display = 'flex';
    };

    window.closeCustomerModal = function () {
        const modal = document.getElementById('modal-customer');
        if (modal) modal.style.display = 'none';
        if (searchInput) searchInput.focus();
    };

    window.handleCustomerSearch = function (query) {
        clearTimeout(customerSearchTimeout);
        const resultsBox = document.getElementById('customer-search-results');
        if (!resultsBox) return;

        if (!query.trim()) {
            resultsBox.style.display = 'none';
            return;
        }

        customerSearchTimeout = setTimeout(() => {
            fetch(`${window.CUSTOMER_SEARCH_API_URL}?q=${encodeURIComponent(query)}`)
                .then(r => r.json())
                .then(data => {
                    resultsBox.innerHTML = '';
                    if (data.customers && data.customers.length > 0) {
                        resultsBox.style.display = 'block';
                        data.customers.forEach(c => {
                            const item = document.createElement('div');
                            item.style.cssText = 'padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border-subtle); cursor: pointer; background: #fff; font-size: 0.82rem;';
                            item.innerHTML = `<strong>${c.name}</strong> • <span style="color: var(--muted-text);">${c.phone}</span> <span style="float: right; color: var(--primary); font-size: 0.74rem;">(${c.total_orders} Orders)</span>`;
                            item.onclick = () => {
                                selectCustomerFromList(c);
                                resultsBox.style.display = 'none';
                            };
                            resultsBox.appendChild(item);
                        });
                    } else {
                        resultsBox.style.display = 'none';
                    }
                });
        }, 250);
    };

    function selectCustomerFromList(c) {
        const nameField = document.getElementById('customer-name-field');
        const phoneField = document.getElementById('customer-phone-field');
        const addressField = document.getElementById('customer-address-field');

        if (nameField) nameField.value = c.name;
        if (phoneField) phoneField.value = c.phone;
        if (addressField) addressField.value = c.address;
    }

    window.setWalkinCustomer = function () {
        const currentTab = getActiveTab();
        currentTab.customer = { name: 'Walk-in Customer', phone: 'walk_in', email: '', address: '' };
        renderActiveCart();
        closeCustomerModal();
    };

    window.saveCustomerModalSelection = function () {
        const currentTab = getActiveTab();
        const nameField = document.getElementById('customer-name-field');
        const phoneField = document.getElementById('customer-phone-field');
        const addressField = document.getElementById('customer-address-field');

        const name = nameField ? nameField.value.trim() : '';
        const phone = phoneField ? phoneField.value.trim() : '';
        const address = addressField ? addressField.value.trim() : '';

        if (!phone) {
            setWalkinCustomer();
            return;
        }

        currentTab.customer = {
            name: name || 'Valued Customer',
            phone: phone,
            email: '',
            address: address,
        };

        renderActiveCart();
        closeCustomerModal();
    };

    // ================= 9. DISCOUNT MODAL & QUICK TOGGLE =================
    window.toggleQuickDiscount = function () {
        const currentTab = getActiveTab();
        const defaultPercent = window.DEFAULT_DISCOUNT_PERCENT || 0;
        if (defaultPercent <= 0) return;

        if (currentTab.discount.type === 'percentage' && currentTab.discount.value === defaultPercent) {
            // Remove discount
            currentTab.discount = { type: 'none', value: 0 };
            showScanFeedbackToast('Discount removed');
        } else {
            // Apply default percent
            currentTab.discount = { type: 'percentage', value: defaultPercent };
            playBeepSound();
            showScanFeedbackToast(`✓ Applied ${defaultPercent}% Discount`);
        }
        renderActiveCart();
    };

    window.openDiscountModal = function () {
        const modal = document.getElementById('modal-discount');
        const currentTab = getActiveTab();
        if (!modal) return;

        const currentType = currentTab.discount.type === 'percentage' ? 'percentage' : (currentTab.discount.type === 'fixed' ? 'fixed' : 'percentage');
        setDiscountType(currentType);

        const valInput = document.getElementById('discount-value-input');
        if (valInput) {
            valInput.value = currentTab.discount.value > 0 ? currentTab.discount.value : '';
            setTimeout(() => valInput.focus(), 50);
        }

        modal.style.display = 'flex';
    };

    window.closeDiscountModal = function () {
        const modal = document.getElementById('modal-discount');
        if (modal) modal.style.display = 'none';
        if (searchInput) searchInput.focus();
    };

    window.setDiscountType = function (type) {
        discountModalType = type;
        const btnFixed = document.getElementById('btn-disc-fixed');
        const btnPercent = document.getElementById('btn-disc-percent');
        const label = document.getElementById('discount-input-label');
        const presetsPercent = document.getElementById('disc-presets-percent');
        const presetsFixed = document.getElementById('disc-presets-fixed');

        if (type === 'fixed') {
            if (btnFixed) {
                btnFixed.classList.remove('btn-outline');
                btnFixed.classList.add('btn-primary');
                btnFixed.style.background = 'var(--primary)';
                btnFixed.style.color = '#fff';
            }
            if (btnPercent) {
                btnPercent.classList.remove('btn-primary');
                btnPercent.classList.add('btn-outline');
                btnPercent.style.background = '#fff';
                btnPercent.style.color = 'var(--secondary)';
            }
            if (label) label.textContent = 'Flat Discount Amount (PKR)';
            if (presetsPercent) presetsPercent.style.display = 'none';
            if (presetsFixed) presetsFixed.style.display = 'flex';
        } else {
            if (btnPercent) {
                btnPercent.classList.remove('btn-outline');
                btnPercent.classList.add('btn-primary');
                btnPercent.style.background = 'var(--primary)';
                btnPercent.style.color = '#fff';
            }
            if (btnFixed) {
                btnFixed.classList.remove('btn-primary');
                btnFixed.classList.add('btn-outline');
                btnFixed.style.background = '#fff';
                btnFixed.style.color = 'var(--secondary)';
            }
            if (label) label.textContent = 'Discount Percentage (%)';
            if (presetsPercent) presetsPercent.style.display = 'flex';
            if (presetsFixed) presetsFixed.style.display = 'none';
        }
    };

    window.setDiscountPreset = function (val) {
        const valInput = document.getElementById('discount-value-input');
        if (valInput) {
            valInput.value = val;
            applyDiscount();
        }
    };

    window.applyDiscount = function () {
        const currentTab = getActiveTab();
        const valInput = document.getElementById('discount-value-input');
        const val = parseFloat(valInput ? valInput.value : 0) || 0;

        if (val > 0) {
            currentTab.discount = {
                type: discountModalType,
                value: val,
            };
            showScanFeedbackToast(`✓ Applied ${discountModalType === 'percentage' ? val + '%' : 'PKR ' + val} Discount`);
        } else {
            currentTab.discount = { type: 'none', value: 0 };
        }

        renderActiveCart();
        closeDiscountModal();
    };

    window.clearDiscount = function () {
        const currentTab = getActiveTab();
        currentTab.discount = { type: 'none', value: 0 };
        showScanFeedbackToast('Discount removed');
        renderActiveCart();
        closeDiscountModal();
    };

    // ================= 9B. SERVICE & DELIVERY CHARGES MODAL =================
    window.openChargesModal = function () {
        const modal = document.getElementById('modal-charges');
        const currentTab = getActiveTab();
        const totals = calculateCartTotals();
        if (!modal) return;

        const titleEl = document.getElementById('modal-charges-title');
        const inputLabel = document.getElementById('modal-charges-input-label');
        const valInput = document.getElementById('charges-value-input');

        if (currentTab.orderType === 'delivery') {
            if (titleEl) titleEl.textContent = 'Edit Delivery Charges';
            if (inputLabel) inputLabel.textContent = 'Delivery Fee (PKR)';
        } else if (currentTab.orderType === 'takeaway' || currentTab.orderType === 'walk_in') {
            if (titleEl) titleEl.textContent = 'Add Service Fee (Optional)';
            if (inputLabel) inputLabel.textContent = 'Service Fee (PKR)';
        } else {
            if (titleEl) titleEl.textContent = 'Edit Dine-In Service Fee';
            if (inputLabel) inputLabel.textContent = 'Service Fee (PKR)';
        }

        if (valInput) {
            valInput.value = totals.serviceAmount.toFixed(2);
            setTimeout(() => valInput.focus(), 50);
        }

        modal.style.display = 'flex';
    };

    window.closeChargesModal = function () {
        const modal = document.getElementById('modal-charges');
        if (modal) modal.style.display = 'none';
        if (searchInput) searchInput.focus();
    };

    window.saveChargesModalSelection = function () {
        const currentTab = getActiveTab();
        const valInput = document.getElementById('charges-value-input');
        const val = parseFloat(valInput ? valInput.value : 0) || 0;

        currentTab.customCharges = Math.max(0, val);
        showScanFeedbackToast(`✓ Charges updated to PKR ${currentTab.customCharges.toFixed(2)}`);

        renderActiveCart();
        closeChargesModal();
    };

    window.resetChargesToDefault = function () {
        const currentTab = getActiveTab();
        currentTab.customCharges = null;
        showScanFeedbackToast('Charges reset to default');

        renderActiveCart();
        closeChargesModal();
    };

    // ================= 10. PAYMENT & CASH TENDER ASSISTANT =================
    window.openPaymentModal = function () {
        const currentTab = getActiveTab();
        if (currentTab.items.length === 0) return;

        const modal = document.getElementById('modal-payment');
        const totalDisplay = document.getElementById('pay-modal-total-display');
        const totals = calculateCartTotals();

        if (totalDisplay) {
            totalDisplay.textContent = `Total Payable: PKR ${totals.totalAmount.toFixed(2)}`;
        }

        selectPaymentMethod(currentTab.paymentMethod || 'cash');

        // Setup cash tender inputs & quick notes
        const cashInput = document.getElementById('cash-tendered-input');
        if (cashInput) {
            cashInput.value = totals.totalAmount.toFixed(2);
        }

        renderQuickNotes(totals.totalAmount);
        calculateChangeReturned();

        if (modal) modal.style.display = 'flex';
    };

    window.closePaymentModal = function () {
        const modal = document.getElementById('modal-payment');
        if (modal) modal.style.display = 'none';
        if (searchInput) searchInput.focus();
    };

    window.selectPaymentMethod = function (method) {
        const currentTab = getActiveTab();
        currentTab.paymentMethod = method;

        document.querySelectorAll('.payment-method-pill').forEach(el => el.classList.remove('active'));
        const activePill = document.getElementById(`pay-method-${method}`);
        if (activePill) activePill.classList.add('active');

        const cashSection = document.getElementById('cash-tender-section');
        if (cashSection) {
            cashSection.style.display = method === 'cash' ? 'block' : 'none';
        }
    };

    function renderQuickNotes(total) {
        const container = document.getElementById('cash-quick-notes');
        if (!container) return;
        container.innerHTML = '';

        const exactBtn = document.createElement('button');
        exactBtn.type = 'button';
        exactBtn.className = 'cash-note-btn';
        exactBtn.textContent = `Exact: PKR ${total.toFixed(0)}`;
        exactBtn.onclick = () => setTenderedAmount(total);
        container.appendChild(exactBtn);

        const presets = [500, 1000, 5000];
        presets.forEach(p => {
            if (p >= total) {
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'cash-note-btn';
                btn.textContent = `PKR ${p}`;
                btn.onclick = () => setTenderedAmount(p);
                container.appendChild(btn);
            }
        });
    }

    function setTenderedAmount(amount) {
        const cashInput = document.getElementById('cash-tendered-input');
        if (cashInput) {
            cashInput.value = amount.toFixed(2);
            calculateChangeReturned();
        }
    }

    window.calculateChangeReturned = function () {
        const cashInput = document.getElementById('cash-tendered-input');
        const changeDisplay = document.getElementById('change-returned-display');
        const totals = calculateCartTotals();

        const tendered = parseFloat(cashInput ? cashInput.value : 0) || 0;
        const change = Math.max(0, tendered - totals.totalAmount);

        if (changeDisplay) {
            changeDisplay.textContent = `PKR ${change.toFixed(2)}`;
        }
    };

    // ================= 11. AJAX CHECKOUT SUBMISSION =================
    window.submitCheckout = function () {
        const currentTab = getActiveTab();
        if (currentTab.items.length === 0) return;

        const totals = calculateCartTotals();
        const cashInput = document.getElementById('cash-tendered-input');
        const notesInput = document.getElementById('order-notes-input');
        const submitBtn = document.getElementById('btn-complete-checkout');

        const tendered = parseFloat(cashInput ? cashInput.value : totals.totalAmount) || totals.totalAmount;

        let finalNotes = notesInput ? notesInput.value.trim() : '';
        if (currentTab.tableNumber) {
            finalNotes = finalNotes ? `${finalNotes} (Table: ${currentTab.tableNumber})` : `Table: ${currentTab.tableNumber}`;
        }

        // Build Payload
        const payload = {
            customer_name: currentTab.customer.name,
            customer_phone: currentTab.customer.phone,
            customer_email: currentTab.customer.email,
            customer_address: currentTab.customer.address,
            payment_method: currentTab.paymentMethod,
            order_type: currentTab.orderType || 'walk_in',
            amount_tendered: tendered,
            discount_type: currentTab.discount.type,
            discount_value: currentTab.discount.value,
            tax_rate: totals.taxRate,
            service_charge_rate: totals.serviceRate,
            service_charge_amount: totals.serviceAmount,
            notes: finalNotes,
            items: currentTab.items.map(i => ({
                product_id: i.productId,
                variant_id: i.variantId,
                quantity: i.quantity,
            })),
        };

        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = 'Processing...';
        }

        function getCookie(name) {
            let cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                const cookies = document.cookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = cookies[i].trim();
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        }

        fetch(window.POS_CHECKOUT_API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: JSON.stringify(payload),
        })
            .then(res => res.json())
            .then(data => {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = '✓ Complete & Print Receipt';
                }

                if (data.success) {
                    closePaymentModal();

                    // Print thermal receipt automatically
                    let printFrame = document.getElementById('receipt-print-frame');
                    if (!printFrame) {
                        printFrame = document.createElement('iframe');
                        printFrame.id = 'receipt-print-frame';
                        printFrame.style.cssText = 'position: fixed; right: 0; bottom: 0; width: 0; height: 0; border: 0; opacity: 0; pointer-events: none;';
                        document.body.appendChild(printFrame);
                    }

                    if (data.receipt_url) {
                        printFrame.onload = function () {
                            try {
                                printFrame.contentWindow.focus();
                                printFrame.contentWindow.print();
                            } catch (e) {}
                        };
                        printFrame.src = data.receipt_url;
                    }

                    // Reset Current Tab
                    currentTab.items = [];
                    currentTab.discount = { type: 'none', value: 0 };
                    currentTab.customer = { name: 'Walk-in Customer', phone: 'walk_in', email: '', address: '' };

                    renderTabs();
                    renderActiveCart();

                    // Silent Non-Blocking Toast Notification (No alert popup!)
                    showScanFeedbackToast(`✓ Order Completed: ${data.invoice_number} (Change: PKR ${data.change_returned.toFixed(2)})`);
                } else {
                    showScanFeedbackToast(`❌ Error: ${data.error || 'Failed to process sale'}`);
                }
            })
            .catch(err => {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = '✓ Complete & Print Receipt';
                }
                showScanFeedbackToast(`❌ Network error while completing checkout: ${err}`);
            });
    };

})();
