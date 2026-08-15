// RetailOS / PakPOS - Main Client Scripts

function toggleSidebar() {
    document.body.classList.toggle('sidebar-collapsed');
    const isCollapsed = document.body.classList.contains('sidebar-collapsed');
    localStorage.setItem('retailos_sidebar_collapsed', isCollapsed ? 'true' : 'false');
}

// Restore user sidebar preference on load
document.addEventListener('DOMContentLoaded', () => {
    const isCollapsed = localStorage.getItem('retailos_sidebar_collapsed');
    if (isCollapsed === 'true') {
        document.body.classList.add('sidebar-collapsed');
    }
});

// ================= GLOBAL DELETE CONFIRMATION MODAL =================
function openDeleteModal(name, type, deleteUrl, warningText = '') {
    const modal = document.getElementById('global-delete-modal');
    const title = document.getElementById('delete-modal-title');
    const msg = document.getElementById('delete-modal-message');
    const form = document.getElementById('global-delete-form');
    const warningBox = document.getElementById('delete-modal-warning');
    const warningMsg = document.getElementById('delete-modal-warning-text');

    if (!modal) return;

    if (title) title.textContent = `Delete ${type}?`;
    if (msg) msg.innerHTML = `Are you sure you want to permanently delete <strong>"${name}"</strong>? This action cannot be undone.`;
    if (form) {
        form.action = deleteUrl;
        form.querySelectorAll('input[name="selected_ids"]').forEach(el => el.remove());
    }

    if (warningBox && warningMsg) {
        if (warningText) {
            warningMsg.textContent = warningText;
            warningBox.style.display = 'flex';
        } else {
            warningBox.style.display = 'none';
        }
    }

    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
}

function closeDeleteModal() {
    const modal = document.getElementById('global-delete-modal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = '';
    }
}

// ================= BULK ACTIONS & MULTI-SELECT CONTROLLER =================
function getSelectedCheckboxIds() {
    const checkedBoxes = document.querySelectorAll('.item-select-checkbox:checked');
    // Use Set to get unique IDs (prevents double counting between table and grid views)
    const uniqueValues = Array.from(new Set(Array.from(checkedBoxes).map(cb => cb.value)));
    return uniqueValues;
}

function syncCheckbox(changedCb) {
    if (!changedCb || !changedCb.value) return;
    const val = changedCb.value;
    const isChecked = changedCb.checked;
    document.querySelectorAll(`.item-select-checkbox[value="${val}"]`).forEach(cb => {
        cb.checked = isChecked;
    });
}

function handleItemSelect(event) {
    if (event && event.target && event.target.classList.contains('item-select-checkbox')) {
        syncCheckbox(event.target);
    }

    const selectedIds = getSelectedCheckboxIds();
    const toolbar = document.getElementById('bulk-actions-bar');
    const countBadge = document.getElementById('bulk-selected-count');
    
    // Get unique item checkboxes count
    const allItemBoxes = document.querySelectorAll('.item-select-checkbox');
    const uniqueTotalItems = new Set(Array.from(allItemBoxes).map(cb => cb.value)).size;

    if (countBadge) {
        countBadge.textContent = `${selectedIds.length} Selected`;
    }

    if (toolbar) {
        if (selectedIds.length > 0) {
            toolbar.classList.add('active');
        } else {
            toolbar.classList.remove('active');
        }
    }

    // Sync master checkboxes (both table & grid)
    const masterCheckboxes = document.querySelectorAll('#select-all-checkbox, .select-all-master-checkbox');
    masterCheckboxes.forEach(master => {
        if (uniqueTotalItems > 0) {
            master.checked = (selectedIds.length === uniqueTotalItems);
            master.indeterminate = (selectedIds.length > 0 && selectedIds.length < uniqueTotalItems);
        }
    });
}

function toggleSelectAll(masterCheckbox) {
    const isChecked = masterCheckbox.checked;
    const checkboxes = document.querySelectorAll('.item-select-checkbox');
    checkboxes.forEach(cb => {
        cb.checked = isChecked;
    });
    handleItemSelect();
}

function clearAllSelections() {
    const checkboxes = document.querySelectorAll('.item-select-checkbox');
    checkboxes.forEach(cb => {
        cb.checked = false;
    });
    const masterCheckboxes = document.querySelectorAll('#select-all-checkbox, .select-all-master-checkbox');
    masterCheckboxes.forEach(master => {
        master.checked = false;
        master.indeterminate = false;
    });
    handleItemSelect();
}

function openBulkDeleteModal(itemType, bulkDeleteUrl, warningText = '') {
    const selectedIds = getSelectedCheckboxIds();
    if (selectedIds.length === 0) {
        alert('Please select at least one item to delete.');
        return;
    }

    const modal = document.getElementById('global-delete-modal');
    const title = document.getElementById('delete-modal-title');
    const msg = document.getElementById('delete-modal-message');
    const form = document.getElementById('global-delete-form');
    const warningBox = document.getElementById('delete-modal-warning');
    const warningMsg = document.getElementById('delete-modal-warning-text');

    if (!modal) return;

    if (title) title.textContent = `Delete ${selectedIds.length} ${itemType}s?`;
    if (msg) msg.innerHTML = `Are you sure you want to permanently delete <strong>${selectedIds.length} selected ${itemType.toLowerCase()}(s)</strong>? This action cannot be undone.`;
    if (form) {
        form.action = bulkDeleteUrl;
        form.querySelectorAll('input[name="selected_ids"]').forEach(el => el.remove());
        const hiddenInput = document.createElement('input');
        hiddenInput.type = 'hidden';
        hiddenInput.name = 'selected_ids';
        hiddenInput.value = selectedIds.join(',');
        form.appendChild(hiddenInput);
    }

    if (warningBox && warningMsg) {
        if (warningText) {
            warningMsg.textContent = warningText;
            warningBox.style.display = 'flex';
        } else {
            warningBox.style.display = 'none';
        }
    }

    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
}

// Close delete modal on backdrop click or ESC key
document.addEventListener('DOMContentLoaded', () => {
    const modal = document.getElementById('global-delete-modal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeDeleteModal();
            }
        });
    }

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeDeleteModal();
        }
    });

    // Auto-dismiss ALL Flash Alert Messages after 2.5 seconds
    const allAlerts = document.querySelectorAll('.alert, .auto-dismiss-alert');
    allAlerts.forEach((alert) => {
        setTimeout(() => {
            alert.classList.add('fade-out');
            setTimeout(() => {
                alert.remove();
                const container = document.getElementById('flash-messages-container');
                if (container && container.children.length === 0) {
                    container.style.display = 'none';
                }
            }, 450);
        }, 2500);
    });
});
