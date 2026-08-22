/**
 * PakPOS Owner Portal Configuration
 * Standalone Client-Side Portal (Zero Server Dependency)
 */

window.PORTAL_CONFIG = {
    // Default Cloud Database Webhook URL for Database Sync
    DEFAULT_WEBHOOK_URL: "https://script.google.com/macros/s/AKfycbxiTjw3CU_dFFOfEZ0xizJHt-_Cd1Y2vogkB-1E9DdD4tlsGhaqdDjBFj-NFDzu070N/exec",
    
    // Auto-refresh interval in seconds (default: 60s)
    AUTO_REFRESH_SECONDS: 60,
    
    // Default Currency
    DEFAULT_CURRENCY: "PKR",
    
    // Default Store Name
    DEFAULT_APP_NAME: "PakPOS Store",
    
    // Storage Keys
    STORAGE_KEYS: {
        WEBHOOK_URL: "pakpos_owner_webhook_url",
        CACHED_DATA: "pakpos_owner_cached_data",
        LAST_SYNC: "pakpos_owner_last_sync",
        THEME: "pakpos_owner_theme"
    },
    
    // Get Active Webhook URL (from localStorage or default)
    getWebhookUrl: function() {
        return localStorage.getItem(this.STORAGE_KEYS.WEBHOOK_URL) || this.DEFAULT_WEBHOOK_URL;
    },
    
    // Set Custom Webhook URL
    setWebhookUrl: function(url) {
        if (url && url.trim()) {
            localStorage.setItem(this.STORAGE_KEYS.WEBHOOK_URL, url.trim());
        } else {
            localStorage.removeItem(this.STORAGE_KEYS.WEBHOOK_URL);
        }
    }
};
