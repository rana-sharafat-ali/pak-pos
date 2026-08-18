/**
 * PakPOS Client-Side Point of Sale (POS) Controller & Cart Engine
 * Upgraded All-in-One Single-Screen POS Flow with Instant Zero-Modal Billing
 * Features: High-Speed Barcode Scanning, Persistent Search Focus, Inline Customer / Discount / Cash Tender
 */

(function () {
    'use strict';

    // State Variables
    let catalog = window.POS_CATALOG || [];
    let currentCategoryId = 0;
    let searchQuery = '';

    // Multi-Tab Cart State
    const isRestaurantMode = (window.POS_MODE === 'restaurant' || window.POS_MODE === 'cafe' || window.POS_MODE === 'food' || window.POS_MODE === 'fast_food');
    const defaultDiscountPercent = parseFloat(window.DEFAULT_DISCOUNT_PERCENT) || 0;

    let tabs = [
        {
            id: 'tab-1',
            label: 'Order 1',
            items: [],
            customer: { name: 'Walk-in Customer', phone: 'walk_in', email: '', address: '' },
            discount: { 
                type: defaultDiscountPercent > 0 ? 'percentage' : 'none', 
                value: defaultDiscountPercent 
            },
            paymentMethod: 'cash',
            orderType: isRestaurantMode ? 'dine_in' : 'walk_in',
            tableNumber: '',
            customCharges: null,
            notes: '',
            amountTendered: null,
        }
    ];
    let activeTabId = 'tab-1';

    // Temp selection states
    let activeProductForVariantModal = null;
    let customerSearchTimeout = null;

    // Hardware Barcode Scanner Buffer
    let barcodeScannerBuffer = '';
    let lastKeyStrokeTime = Date.now();

    // DOM Elements
    const productGrid = document.getElementById('pos-product-grid');
    const searchInput = document.getElementById('pos-search-input');
    const tabBar = document.getElementById('pos-tab-bar');
    const cartContainer = document.getElementById('pos-cart-items-container');
    const customerInput = document.getElementById('pos-customer-input');
    const customerDropdown = document.getElementById('customer-search-results');
    const btnClearCustomer = document.getElementById('btn-clear-customer');
    const btnCompleteSale = document.getElementById('btn-complete-sale');

    // Financial Displays
    const calcSubtotal = document.getElementById('pos-calc-subtotal');
    const calcDiscount = document.getElementById('pos-calc-discount');
    const calcTax = document.getElementById('pos-calc-tax');
    const calcService = document.getElementById('pos-calc-service');
    const calcTotal = document.getElementById('pos-calc-total');
    const inlineDiscValInput = document.getElementById('pos-inline-disc-val');
    const inlineDiscTypeSelect = document.getElementById('pos-inline-disc-type');
    const inlineChargesInput = document.getElementById('pos-inline-charges-input');
    const inlineCashInput = document.getElementById('pos-inline-cash-input');
    const inlineChangeDisplay = document.getElementById('pos-inline-change-display');
    const inlineCashSection = document.getElementById('pos-inline-cash-section');

    // ================= 1. INITIALIZATION & FOCUS ENGINE =================
    document.addEventListener('DOMContentLoaded', () => {
        // Auto-collapse sidebar on smaller screens / laptops (< 1280px) to maximize POS horizontal space
        if (window.innerWidth < 1280) {
            document.body.classList.add('sidebar-collapsed');
        }

        renderProductGrid();
        renderTabs();
        renderActiveCart();
        focusSearchInput();

        // Search Input Handlers
        if (searchInput) {
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
                    } else {
                        // Empty enter on search bar: if cart has items, proceed with checkout
                        const currentTab = getActiveTab();
                        if (currentTab.items.length > 0) {
                            submitInlineCheckout();
                        }
                    }
                }
            });
        }

        // Global Hardware Barcode Scanner Listener
        setupGlobalBarcodeListener();

        // Global Click & Hotkey Listener for Persistent Search Focus & Shortcuts
        setupGlobalFocusAndHotkeys();
    });

    // Mobile / Tablet Tab Switcher (< 880px)
    window.switchMobileView = function (view) {
        const catalogPane = document.getElementById('pos-pane-catalog');
        const cartPane = document.getElementById('pos-pane-cart');
        const btnCatalog = document.getElementById('btn-tab-catalog');
        const btnCart = document.getElementById('btn-tab-cart');

        if (view === 'catalog') {
            if (catalogPane) catalogPane.classList.remove('pos-tab-view-hidden');
            if (cartPane) cartPane.classList.add('pos-tab-view-hidden');
            if (btnCatalog) btnCatalog.classList.add('active');
            if (btnCart) btnCart.classList.remove('active');
            focusSearchInput();
        } else {
            if (catalogPane) catalogPane.classList.add('pos-tab-view-hidden');
            if (cartPane) cartPane.classList.remove('pos-tab-view-hidden');
            if (btnCatalog) btnCatalog.classList.remove('active');
            if (btnCart) btnCart.classList.add('active');
        }
    };

    /**
     * Helper to determine if user is intentionally typing in another input/select or if a modal is active
     */
    function isSpecialFieldFocused() {
        const active = document.activeElement;
        if (!active) return false;
        const tag = active.tagName.toLowerCase();
        if (tag === 'textarea' || tag === 'select') return true;
        if (tag === 'input' && active !== searchInput) return true;
        const modal = document.getElementById('modal-variant-selector');
        if (modal && modal.style.display === 'flex') return true;
        return false;
    }

    /**
     * Always ensures the pointer/keyboard focus returns to the product/barcode search input
     * and auto-selects (highlights) existing text so any new typing replaces it instantly.
     */
    function focusSearchInput(selectAll = true) {
        if (!searchInput) return;
        setTimeout(() => {
            if (!isSpecialFieldFocused()) {
                searchInput.focus();
                if (selectAll && searchInput.value.length > 0) {
                    searchInput.select();
                }
            }
        }, 10);
    }

    function setupGlobalFocusAndHotkeys() {
        // Refocus search bar on any mouse/pointer click anywhere on the page
        document.addEventListener('pointerdown', (e) => {
            const isOtherInput = e.target.closest('input:not(#pos-search-input), select, textarea, #modal-variant-selector, #customer-search-results');
            if (!isOtherInput) {
                setTimeout(() => focusSearchInput(true), 10);
            }
        });

        // Refocus search bar when switching back to this browser window / tab
        window.addEventListener('focus', () => {
            focusSearchInput(true);
        });

        // UNIVERSAL KEYBOARD INTERCEPTOR:
        // Any keystroke typed anywhere on the POS screen immediately types into the search/barcode bar!
        window.addEventListener('keydown', (e) => {
            // Allow system shortcuts (Ctrl+C, Ctrl+V, Ctrl+R, F5, etc.)
            if (e.ctrlKey || e.altKey || e.metaKey) return;
            if (['Control', 'Alt', 'Meta', 'Shift', 'CapsLock', 'Tab', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Home', 'End', 'PageUp', 'PageDown'].includes(e.key)) return;

            // Global Hotkeys: F10 to complete sale
            if (e.key === 'F10') {
                e.preventDefault();
                submitInlineCheckout();
                return;
            }

            // Escape clears search and closes dropdowns
            if (e.key === 'Escape') {
                if (customerDropdown) customerDropdown.style.display = 'none';
                closeVariantModal();
                if (searchInput) {
                    searchInput.value = '';
                    searchQuery = '';
                    renderProductGrid();
                    searchInput.focus();
                }
                return;
            }

            // If user is actively typing in customer, cash tender, discount or modal, let them type normally
            if (isSpecialFieldFocused()) {
                return;
            }

            // If focus is NOT already on search bar, redirect keystroke straight into search bar!
            if (document.activeElement !== searchInput && searchInput) {
                const hadFullSelection = (searchInput.selectionStart === 0 && searchInput.selectionEnd === searchInput.value.length && searchInput.value.length > 0);
                searchInput.focus();
                if (e.key.length === 1) {
                    e.preventDefault();
                    if (hadFullSelection) {
                        searchInput.value = e.key;
                    } else {
                        searchInput.value += e.key;
                    }
                    searchQuery = searchInput.value.toLowerCase().trim();
                    renderProductGrid();
                } else if (e.key === 'Backspace') {
                    e.preventDefault();
                    if (hadFullSelection) {
                        searchInput.value = '';
                    } else {
                        searchInput.value = searchInput.value.slice(0, -1);
                    }
                    searchQuery = searchInput.value.toLowerCase().trim();
                    renderProductGrid();
                } else if (e.key === 'Enter') {
                    e.preventDefault();
                    const code = searchInput.value.trim();
                    if (code) {
                        const handled = handleBarcodeScan(code);
                        if (handled) {
                            searchInput.value = '';
                            searchQuery = '';
                            renderProductGrid();
                        }
                    } else {
                        const currentTab = getActiveTab();
                        if (currentTab.items.length > 0) {
                            submitInlineCheckout();
                        }
                    }
                }
            }
        });
    }

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
            // Audio context blocked or not available
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

    // ================= 3. HARDWARE BARCODE SCANNER INTERCEPTOR =================
    function setupGlobalBarcodeListener() {
        window.addEventListener('keydown', (e) => {
            if (['Shift', 'Control', 'Alt', 'Meta', 'CapsLock', 'Tab'].includes(e.key)) return;

            const activeEl = document.activeElement;
            const isEditingField = activeEl && (
                activeEl === customerInput ||
                activeEl === inlineDiscValInput ||
                activeEl === inlineChargesInput ||
                activeEl === inlineCashInput
            );
            if (isEditingField) return;

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

        // 1. Check Product Variant by Barcode (800 + ProdId + VarId)
        for (const prod of catalog) {
            if (prod.has_variants && prod.variants) {
                const matchedVar = prod.variants.find(v => {
                    if (v.barcode && v.barcode === code) return true;
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
                    focusSearchInput();
                    return true;
                }
            }
        }

        // 2. Check Standard Product by Barcode (800 + ProdId + 00)
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
                focusSearchInput();
            }
            return true;
        }

        // 3. Match by Numeric Product ID (e.g. '1', '2')
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
                    focusSearchInput();
                }
                return true;
            }
        }

        // 4. Match by Exact Product Name
        const matchedByName = catalog.find(p => p.name.toLowerCase() === codeLower);
        if (matchedByName) {
            if (matchedByName.has_variants) {
                openVariantModal(matchedByName);
            } else {
                addToCart(matchedByName.id, null, matchedByName.name, '', matchedByName.base_price);
                playBeepSound();
                showScanFeedbackToast(`Added ${matchedByName.name}`);
                focusSearchInput();
            }
            return true;
        }

        // 5. If single match in query
        const filtered = catalog.filter(p => p.name.toLowerCase().includes(codeLower));
        if (filtered.length === 1) {
            const single = filtered[0];
            if (single.has_variants) {
                openVariantModal(single);
            } else {
                addToCart(single.id, null, single.name, '', single.base_price);
                playBeepSound();
                showScanFeedbackToast(`Added ${single.name}`);
                focusSearchInput();
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
        focusSearchInput();
    };

    function renderProductGrid() {
        if (!productGrid) return;
        productGrid.innerHTML = '';

        const filtered = catalog.filter(p => {
            const matchesCat = currentCategoryId === 0 || p.category_id === currentCategoryId;
            const matchesSearch = !searchQuery || p.name.toLowerCase().includes(searchQuery) || (p.barcode && p.barcode.includes(searchQuery));
            return matchesCat && matchesSearch;
        });

        const mobCatCount = document.getElementById('mob-catalog-count');
        if (mobCatCount) mobCatCount.textContent = filtered.length;

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
            focusSearchInput();
        }
    }

    // ================= 5. MULTI-TAB ORDER QUEUES =================
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

        tabs.forEach((tab, index) => {
            const tabBtn = document.createElement('button');
            tabBtn.type = 'button';
            tabBtn.className = `pos-tab-btn ${tab.id === activeTabId ? 'active' : ''}`;
            tabBtn.onclick = () => switchTab(tab.id);

            const itemCount = tab.items.reduce((sum, item) => sum + item.quantity, 0);
            const badgeHtml = itemCount > 0 ? `<span style="background: var(--primary); color: #fff; border-radius: 9999px; padding: 0.1rem 0.4rem; font-size: 0.7rem; font-weight: 800;">${itemCount}</span>` : '';

            let closeBtnHtml = '';
            if (tabs.length > 1) {
                closeBtnHtml = `<span class="pos-tab-close" onclick="event.stopPropagation(); closeTab('${tab.id}')">✕</span>`;
            }

            tabBtn.innerHTML = `
                <span>${tab.label}</span>
                ${badgeHtml}
                ${closeBtnHtml}
            `;
            tabBar.appendChild(tabBtn);
        });

        // Add Tab Button
        const addBtn = document.createElement('button');
        addBtn.type = 'button';
        addBtn.className = 'pos-tab-add';
        addBtn.innerHTML = '<span>+ New</span>';
        addBtn.onclick = addNewTab;
        tabBar.appendChild(addBtn);
    }

    window.switchTab = function (tabId) {
        activeTabId = tabId;
        renderTabs();
        renderActiveCart();
        focusSearchInput();
    };

    window.addNewTab = function () {
        const newIndex = tabs.length + 1;
        const newTab = {
            id: `tab-${Date.now()}`,
            label: `Order ${newIndex}`,
            items: [],
            customer: { name: 'Walk-in Customer', phone: 'walk_in', email: '', address: '' },
            discount: { 
                type: defaultDiscountPercent > 0 ? 'percentage' : 'none', 
                value: defaultDiscountPercent 
            },
            paymentMethod: 'cash',
            orderType: isRestaurantMode ? 'dine_in' : 'walk_in',
            tableNumber: '',
            customCharges: null,
            notes: '',
            amountTendered: null,
        };
        tabs.push(newTab);
        activeTabId = newTab.id;
        renderTabs();
        renderActiveCart();
        focusSearchInput();
    };

    window.closeTab = function (tabId) {
        if (tabs.length <= 1) return;
        tabs = tabs.filter(t => t.id !== tabId);
        if (activeTabId === tabId) {
            activeTabId = tabs[0].id;
        }
        renderTabs();
        renderActiveCart();
        focusSearchInput();
    };

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

        currentTab.hasCustomCashTender = false;
        currentTab.amountTendered = null;

        renderTabs();
        renderActiveCart();
        focusSearchInput();
    }

    window.changeItemQty = function (index, delta) {
        const currentTab = getActiveTab();
        const item = currentTab.items[index];
        if (!item) return;

        item.quantity += delta;
        if (item.quantity <= 0) {
            currentTab.items.splice(index, 1);
        }

        currentTab.hasCustomCashTender = false;
        currentTab.amountTendered = null;

        renderTabs();
        renderActiveCart();
        focusSearchInput();
    };

    window.removeItem = function (index) {
        const currentTab = getActiveTab();
        currentTab.items.splice(index, 1);
        currentTab.hasCustomCashTender = false;
        currentTab.amountTendered = null;
        renderTabs();
        renderActiveCart();
        focusSearchInput();
    };

    window.clearCurrentCart = function () {
        const currentTab = getActiveTab();
        if (currentTab.items.length === 0) return;
        if (confirm('Clear all items from this active order?')) {
            currentTab.items = [];
            currentTab.discount = { 
                type: defaultDiscountPercent > 0 ? 'percentage' : 'none', 
                value: defaultDiscountPercent 
            };
            currentTab.customCharges = null;
            currentTab.amountTendered = null;
            currentTab.hasCustomCashTender = false;
            renderTabs();
            renderActiveCart();
            focusSearchInput();
        }
    };

    function calculateCartTotals() {
        const currentTab = getActiveTab();
        let subtotal = 0;

        currentTab.items.forEach(i => {
            subtotal += i.unitPrice * i.quantity;
        });

        // 1. Taxes (calculated on Subtotal)
        const taxRate = window.DEFAULT_TAX_RATE || 0;
        const taxAmount = taxRate > 0 ? (subtotal * (taxRate / 100)) : 0;

        // 2. Service / Delivery Charges (calculated on Subtotal)
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
                serviceAmount = serviceRate > 0 ? (subtotal * (serviceRate / 100)) : 0;
            }
        }

        // 3. Gross Total before Discount
        const grossTotal = subtotal + taxAmount + serviceAmount;

        // 4. Discount Calculation (Subtracted from Total: Subtotal + Tax + Service Charges)
        let discountAmount = 0;
        if (currentTab.discount.type === 'fixed') {
            discountAmount = Math.min(currentTab.discount.value, grossTotal);
        } else if (currentTab.discount.type === 'percentage') {
            discountAmount = subtotal * (Math.min(100, currentTab.discount.value) / 100);
        }

        // 5. Final Net Payable Amount
        const totalAmount = Math.max(0, grossTotal - discountAmount);

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
        const totals = calculateCartTotals();

        // 1. Customer Input Display
        if (customerInput) {
            customerInput.value = (currentTab.customer && currentTab.customer.name && currentTab.customer.name !== 'Walk-in Customer') 
                ? `${currentTab.customer.name} (${currentTab.customer.phone || ''})` 
                : '';
            if (btnClearCustomer) {
                btnClearCustomer.style.display = (currentTab.customer && currentTab.customer.name && currentTab.customer.name !== 'Walk-in Customer') ? 'block' : 'none';
            }
        }

        // 2. Render Cart Items List
        if (cartContainer) {
            cartContainer.innerHTML = '';

            if (currentTab.items.length === 0) {
                cartContainer.innerHTML = `
                    <div style="text-align: center; padding: 2.5rem 1rem; color: var(--muted-text);">
                        <div style="font-size: 1.8rem; margin-bottom: 0.35rem; opacity: 0.6;">🛒</div>
                        <strong style="font-size: 0.85rem; color: var(--secondary); display: block;">Cart is Empty</strong>
                        <span style="font-size: 0.74rem;">Scan a barcode or click items to add</span>
                    </div>
                `;
            } else {
                currentTab.items.forEach((item, index) => {
                    const row = document.createElement('div');
                    row.className = 'pos-cart-item-row';
                    const itemTotal = (item.unitPrice * item.quantity).toFixed(2);
                    const variantDisplay = item.variantName ? `<div class="pos-item-sub">${item.variantName}</div>` : '';

                    row.innerHTML = `
                        <div class="pos-item-title-box">
                            <div class="pos-item-title" title="${item.name}">${item.name}</div>
                            ${variantDisplay}
                        </div>

                        <div class="pos-item-unit-price">PKR ${item.unitPrice.toFixed(2)}</div>

                        <div class="pos-qty-control">
                            <button type="button" class="pos-qty-btn" onclick="changeItemQty(${index}, -1)">−</button>
                            <span class="pos-qty-num">${item.quantity}</span>
                            <button type="button" class="pos-qty-btn" onclick="changeItemQty(${index}, 1)">+</button>
                        </div>

                        <div class="pos-item-price-box">
                            <div class="pos-item-total">PKR ${itemTotal}</div>
                        </div>

                        <button type="button" class="pos-item-remove" onclick="removeItem(${index})" title="Remove item">✕</button>
                    `;
                    cartContainer.appendChild(row);
                });
            }
        }

        // 3. Update Financial Numbers
        if (calcSubtotal) calcSubtotal.textContent = `PKR ${totals.subtotal.toFixed(2)}`;
        if (calcDiscount) calcDiscount.textContent = `- PKR ${totals.discountAmount.toFixed(2)}`;
        if (calcTax) calcTax.textContent = `PKR ${totals.taxAmount.toFixed(2)}`;
        if (calcService) calcService.textContent = `PKR ${totals.serviceAmount.toFixed(2)}`;
        if (calcTotal) calcTotal.textContent = `PKR ${totals.totalAmount.toFixed(2)}`;

        // Update Service Label
        const chargesLabelEl = document.getElementById('pos-charges-label');
        if (chargesLabelEl) chargesLabelEl.textContent = totals.chargeLabel;

        // Update Inline Discount Inputs
        if (inlineDiscValInput && document.activeElement !== inlineDiscValInput) {
            inlineDiscValInput.value = currentTab.discount.value || '';
        }
        if (inlineDiscTypeSelect) {
            inlineDiscTypeSelect.value = currentTab.discount.type === 'fixed' ? 'fixed' : 'percentage';
        }

        // Update Inline Charges Input
        if (inlineChargesInput && document.activeElement !== inlineChargesInput) {
            inlineChargesInput.value = totals.serviceAmount > 0 ? totals.serviceAmount.toFixed(0) : '';
        }

        // 4. Update Payment Method Active State
        const method = currentTab.paymentMethod || 'cash';
        ['cash', 'card', 'online'].forEach(m => {
            const btn = document.getElementById(`inline-pay-${m}`);
            if (btn) {
                if (m === method) {
                    btn.classList.add('active');
                    btn.style.background = '#eff6ff';
                    btn.style.borderColor = '#2563eb';
                    btn.style.color = '#1d4ed8';
                } else {
                    btn.classList.remove('active');
                    btn.style.background = '#ffffff';
                    btn.style.borderColor = 'var(--border-card)';
                    btn.style.color = 'var(--secondary)';
                }
            }
        });

        // 5. Update Cash Tender Section
        if (inlineCashSection) {
            inlineCashSection.style.display = method === 'cash' ? 'block' : 'none';
        }

        if (inlineCashInput && document.activeElement !== inlineCashInput) {
            if (currentTab.hasCustomCashTender && currentTab.amountTendered !== null && currentTab.amountTendered !== undefined) {
                inlineCashInput.value = parseFloat(currentTab.amountTendered).toFixed(2);
            } else if (totals.totalAmount > 0) {
                inlineCashInput.value = totals.totalAmount.toFixed(2);
            } else {
                inlineCashInput.value = '';
            }
        }
        calculateInlineChange();

        // 6. Enable / Disable Complete Sale Button
        if (btnCompleteSale) {
            btnCompleteSale.disabled = (currentTab.items.length === 0);
        }

        // 7. Update Mobile/Tablet Cart Tab Badge
        const totalItemQty = currentTab.items.reduce((sum, item) => sum + item.quantity, 0);
        const mobCartBadge = document.getElementById('mob-cart-badge');
        if (mobCartBadge) {
            mobCartBadge.textContent = `${totalItemQty} items (PKR ${totals.totalAmount.toFixed(0)})`;
        }

        // 8. Update Discount Unit Button Indicator
        const discUnitBtn = document.getElementById('pos-disc-unit-btn');
        if (discUnitBtn) {
            discUnitBtn.textContent = (currentTab.discount && currentTab.discount.type === 'fixed') ? 'PKR' : '%';
        }

        // 9. Update Restaurant Order Type and Table Selectors
        const orderTypeSelect = document.getElementById('restaurant-order-type-select');
        if (orderTypeSelect) {
            orderTypeSelect.value = currentTab.orderType || 'dine_in';
        }
        const tableSelect = document.getElementById('restaurant-table-select');
        if (tableSelect) {
            tableSelect.value = currentTab.tableNumber || '';
            tableSelect.style.display = (currentTab.orderType === 'dine_in' || !currentTab.orderType) ? 'inline-block' : 'none';
        }
    }

    // ================= 7. INLINE CUSTOMER LOOKUP =================
    window.handleCustomerInlineSearch = function (query) {
        if (!customerDropdown) return;
        const q = query.trim();

        if (customerSearchTimeout) clearTimeout(customerSearchTimeout);

        if (q.length < 2) {
            customerDropdown.style.display = 'none';
            return;
        }

        customerSearchTimeout = setTimeout(() => {
            fetch(`${window.CUSTOMER_SEARCH_API_URL}?q=${encodeURIComponent(q)}`)
                .then(res => res.json())
                .then(data => {
                    if (data.results && data.results.length > 0) {
                        customerDropdown.innerHTML = '';
                        data.results.forEach(cust => {
                            const opt = document.createElement('div');
                            opt.className = 'pos-cust-opt';
                            opt.style.cssText = 'padding: 0.45rem 0.75rem; font-size: 0.8rem; border-bottom: 1px solid #f1f5f9; cursor: pointer; display: flex; align-items: center; justify-content: space-between;';
                            opt.innerHTML = `
                                <div>
                                    <strong style="color: var(--secondary);">${cust.name}</strong>
                                    <div style="font-size: 0.72rem; color: var(--muted-text);">${cust.phone || 'No phone'}</div>
                                </div>
                                <span style="font-size: 0.72rem; color: #2563eb; font-weight: 700;">Select</span>
                            `;
                            opt.onclick = () => selectInlineCustomer(cust);
                            customerDropdown.appendChild(opt);
                        });
                        customerDropdown.style.display = 'block';
                    } else {
                        // Quick create option
                        customerDropdown.innerHTML = `
                            <div style="padding: 0.6rem 0.75rem; font-size: 0.8rem; color: var(--muted-text);">
                                <div>No customer found for "<strong>${q}</strong>"</div>
                                <button type="button" onclick="quickRegisterInlineCustomer('${q}')" style="margin-top: 0.35rem; padding: 0.25rem 0.65rem; font-size: 0.75rem; font-weight: 700; background: #eff6ff; border: 1px solid #bfdbfe; color: #1d4ed8; border-radius: 4px; cursor: pointer;">
                                    + Add as New Customer (${q})
                                </button>
                            </div>
                        `;
                        customerDropdown.style.display = 'block';
                    }
                })
                .catch(() => {
                    customerDropdown.style.display = 'none';
                });
        }, 150);
    };

    function selectInlineCustomer(cust) {
        const currentTab = getActiveTab();
        currentTab.customer = {
            name: cust.name,
            phone: cust.phone || '',
            email: cust.email || '',
            address: cust.address || '',
        };
        if (customerDropdown) customerDropdown.style.display = 'none';
        showScanFeedbackToast(`👤 Customer: ${cust.name}`);
        renderActiveCart();
        focusSearchInput();
    }

    window.quickRegisterInlineCustomer = function (identifier) {
        const currentTab = getActiveTab();
        const isNumeric = /^\d+$/.test(identifier);
        currentTab.customer = {
            name: isNumeric ? `Customer ${identifier}` : identifier,
            phone: isNumeric ? identifier : '',
            email: '',
            address: '',
        };
        if (customerDropdown) customerDropdown.style.display = 'none';
        showScanFeedbackToast(`👤 Customer set to ${currentTab.customer.name}`);
        renderActiveCart();
        focusSearchInput();
    };

    window.clearCustomerSelection = function () {
        const currentTab = getActiveTab();
        currentTab.customer = { name: 'Walk-in Customer', phone: 'walk_in', email: '', address: '' };
        if (customerDropdown) customerDropdown.style.display = 'none';
        renderActiveCart();
        focusSearchInput();
    };

    // ================= 8. INLINE DISCOUNT HANDLERS =================
    window.setInlineDiscountPreset = function (val, type) {
        const currentTab = getActiveTab();
        currentTab.discount = {
            type: val > 0 ? (type || 'percentage') : 'none',
            value: parseFloat(val) || 0,
        };
        showScanFeedbackToast(`Discount: ${val > 0 ? val + (type === 'fixed' ? ' PKR' : '%') : 'None'}`);
        renderActiveCart();
        focusSearchInput();
    };

    window.updateInlineDiscountMode = function (mode) {
        const currentTab = getActiveTab();
        currentTab.discount.type = mode;
        renderActiveCart();
    };

    window.onInlineDiscountInputChange = function (val) {
        const currentTab = getActiveTab();
        const num = parseFloat(val) || 0;
        const type = inlineDiscTypeSelect ? inlineDiscTypeSelect.value : 'percentage';

        currentTab.discount = {
            type: num > 0 ? type : 'none',
            value: num,
        };
        renderActiveCart();
    };

    window.toggleDiscountUnit = function () {
        const currentTab = getActiveTab();
        const currentType = currentTab.discount.type;
        const nextType = (currentType === 'fixed') ? 'percentage' : 'fixed';
        currentTab.discount.type = nextType;
        if (inlineDiscTypeSelect) inlineDiscTypeSelect.value = nextType;
        renderActiveCart();
        focusSearchInput();
    };

    // ================= 9. INLINE CHARGES HANDLERS =================
    window.onInlineChargesInputChange = function (val) {
        const currentTab = getActiveTab();
        const num = parseFloat(val);
        currentTab.customCharges = isNaN(num) ? null : Math.max(0, num);
        renderActiveCart();
    };

    window.clearCurrentCart = function () {
        const currentTab = getActiveTab();
        currentTab.items = [];
        currentTab.discount = { 
            type: defaultDiscountPercent > 0 ? 'percentage' : 'none', 
            value: defaultDiscountPercent 
        };
        currentTab.customer = { name: 'Walk-in Customer', phone: 'walk_in', email: '', address: '' };
        currentTab.customCharges = null;
        currentTab.amountTendered = null;
        currentTab.hasCustomCashTender = false;
        renderTabs();
        renderActiveCart();
        focusSearchInput();
    };

    // ================= 10. INLINE PAYMENT & CASH TENDER =================
    window.selectInlinePaymentMethod = function (method) {
        const currentTab = getActiveTab();
        currentTab.paymentMethod = method;
        renderActiveCart();
        focusSearchInput();
    };

    window.onInlineCashInputChange = function (val) {
        const currentTab = getActiveTab();
        const totals = calculateCartTotals();
        currentTab.hasCustomCashTender = (val.trim() !== '');
        const tendered = parseFloat(val) || 0;
        currentTab.amountTendered = tendered;
        const change = Math.max(0, tendered - totals.totalAmount);
        if (inlineChangeDisplay) {
            inlineChangeDisplay.textContent = `PKR ${change.toFixed(2)}`;
        }
    };

    window.setInlineExactCash = function () {
        const currentTab = getActiveTab();
        const totals = calculateCartTotals();
        currentTab.hasCustomCashTender = false;
        currentTab.amountTendered = totals.totalAmount;
        if (inlineCashInput) inlineCashInput.value = totals.totalAmount > 0 ? totals.totalAmount.toFixed(2) : '';
        calculateInlineChange();
        focusSearchInput();
    };

    window.setInlineCashNote = function (noteAmount) {
        const currentTab = getActiveTab();
        
        let currentBase = 0;
        if (currentTab.hasCustomCashTender) {
            // Already accumulated note or typed custom amount -> add to it! (e.g. 500 + 500 = 1000)
            currentBase = parseFloat(inlineCashInput ? inlineCashInput.value : 0) || 0;
        } else {
            // First time clicking currency note -> clear exact default bill and start fresh from 0!
            currentBase = 0;
            currentTab.hasCustomCashTender = true;
        }

        const nextAmount = currentBase + noteAmount;
        currentTab.amountTendered = nextAmount;
        if (inlineCashInput) inlineCashInput.value = nextAmount.toFixed(2);
        calculateInlineChange();
        focusSearchInput();
    };

    window.calculateInlineChange = function () {
        const currentTab = getActiveTab();
        const totals = calculateCartTotals();
        let tendered = 0;
        if (currentTab.hasCustomCashTender) {
            tendered = parseFloat(inlineCashInput ? inlineCashInput.value : (currentTab.amountTendered || 0)) || 0;
        } else {
            tendered = totals.totalAmount;
        }
        currentTab.amountTendered = tendered;
        const change = Math.max(0, tendered - totals.totalAmount);

        if (inlineChangeDisplay) {
            inlineChangeDisplay.textContent = `PKR ${change.toFixed(2)}`;
        }
    };

    // ================= 11. RESTAURANT ORDER TYPE & TABLE =================
    window.selectOrderType = function (type) {
        const currentTab = getActiveTab();
        currentTab.orderType = type;

        const selectEl = document.getElementById('restaurant-order-type-select');
        if (selectEl) selectEl.value = type;

        const tableSelect = document.getElementById('restaurant-table-select');
        if (tableSelect) {
            tableSelect.style.display = type === 'dine_in' ? 'inline-block' : 'none';
        }

        renderActiveCart();
        focusSearchInput();
    };

    window.updateTableSelection = function (val) {
        const currentTab = getActiveTab();
        currentTab.tableNumber = val;
        focusSearchInput();
    };

    window.printKitchenOrderTicket = function () {
        const currentTab = getActiveTab();
        if (currentTab.items.length === 0) {
            showScanFeedbackToast('Cannot print KOT for an empty order');
            return;
        }
        showScanFeedbackToast('🍳 KOT Sent to Kitchen Printer');
        focusSearchInput();
    };

    // ================= 12. VARIANT MODAL HANDLERS =================
    function openVariantModal(product) {
        activeProductForVariantModal = product;
        const modal = document.getElementById('modal-variant-selector');
        const nameEl = document.getElementById('variant-modal-product-name');
        const listEl = document.getElementById('variant-options-list');

        if (!modal || !listEl) return;

        if (nameEl) nameEl.textContent = product.name;
        listEl.innerHTML = '';

        if (product.variants && product.variants.length > 0) {
            product.variants.forEach(variant => {
                const priceFormatted = variant.selling_price_display || `PKR ${parseFloat(variant.selling_price || 0).toFixed(2)}`;
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'btn btn-outline';
                btn.style.cssText = 'display: flex; align-items: center; justify-content: space-between; padding: 0.75rem 1rem; font-weight: 700; width: 100%; text-align: left; border-radius: 8px; margin-bottom: 0.4rem; transition: all 0.15s ease;';
                btn.innerHTML = `
                    <span style="font-size: 0.9rem; color: var(--secondary);">${variant.name}</span>
                    <strong style="color: var(--primary); font-size: 0.95rem;">${priceFormatted}</strong>
                `;
                btn.onmouseover = () => { btn.style.borderColor = 'var(--primary)'; btn.style.background = '#f0fdf4'; };
                btn.onmouseout = () => { btn.style.borderColor = 'var(--border-card)'; btn.style.background = '#ffffff'; };
                btn.onclick = () => {
                    addToCart(product.id, variant.id, product.name, variant.name, variant.selling_price);
                    playBeepSound();
                    closeVariantModal();
                };
                listEl.appendChild(btn);
            });
        }

        modal.style.display = 'flex';
    }

    window.closeVariantModal = function () {
        const modal = document.getElementById('modal-variant-selector');
        if (modal) modal.style.display = 'none';
        activeProductForVariantModal = null;
        focusSearchInput();
    };

    // ================= 13. SEAMLESS INLINE AJAX CHECKOUT =================
    window.submitInlineCheckout = function () {
        const currentTab = getActiveTab();
        if (currentTab.items.length === 0) {
            showScanFeedbackToast('⚠️ Cart is empty. Add items first.');
            focusSearchInput();
            return;
        }

        const totals = calculateCartTotals();
        const tendered = parseFloat(inlineCashInput ? inlineCashInput.value : totals.totalAmount) || totals.totalAmount;

        let finalNotes = currentTab.notes || '';
        if (currentTab.tableNumber) {
            finalNotes = finalNotes ? `${finalNotes} (Table: ${currentTab.tableNumber})` : `Table: ${currentTab.tableNumber}`;
        }

        const payload = {
            customer_name: currentTab.customer.name,
            customer_phone: currentTab.customer.phone,
            customer_email: currentTab.customer.email,
            customer_address: currentTab.customer.address,
            payment_method: currentTab.paymentMethod || 'cash',
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

        if (btnCompleteSale) {
            btnCompleteSale.disabled = true;
            btnCompleteSale.innerHTML = '<span>⚡ Processing...</span>';
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
                if (btnCompleteSale) {
                    btnCompleteSale.disabled = false;
                    btnCompleteSale.innerHTML = `
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="20 6 9 17 4 12"></polyline>
                        </svg>
                        <span>Charge & Print (F10)</span>
                    `;
                }

                if (data.success) {
                    playBeepSound();

                    // Print thermal receipt automatically via silent hidden iframe
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

                    // Reset Active Tab Order
                    currentTab.items = [];
                    currentTab.discount = { 
                        type: defaultDiscountPercent > 0 ? 'percentage' : 'none', 
                        value: defaultDiscountPercent 
                    };
                    currentTab.customer = { name: 'Walk-in Customer', phone: 'walk_in', email: '', address: '' };
                    currentTab.customCharges = null;
                    currentTab.amountTendered = null;

                    renderTabs();
                    renderActiveCart();

                    // Display Feedback Toast
                    const changeInfo = (data.change_returned > 0) ? ` • Baqaya: PKR ${data.change_returned.toFixed(2)}` : '';
                    showScanFeedbackToast(`✓ Invoice ${data.invoice_number} Completed!${changeInfo}`);

                    // Retain pointer focus on barcode/product search input
                    focusSearchInput();
                } else {
                    showScanFeedbackToast(`❌ Error: ${data.error || 'Checkout failed'}`);
                    focusSearchInput();
                }
            })
            .catch(err => {
                if (btnCompleteSale) {
                    btnCompleteSale.disabled = false;
                    btnCompleteSale.innerHTML = `
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="20 6 9 17 4 12"></polyline>
                        </svg>
                        <span>Charge & Print (F10)</span>
                    `;
                }
                showScanFeedbackToast(`❌ Network Error: ${err}`);
                focusSearchInput();
            });
    };

})();
