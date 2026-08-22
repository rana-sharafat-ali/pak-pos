# 🚀 PakPOS — Modern Retail & Restaurant Point of Sale System

**PakPOS** is an enterprise-grade, offline-first Point of Sale (POS) and business intelligence platform built with **Django (Python)** and **Modern Vanilla CSS/JS**. Designed specifically for retail stores, supermarkets, restaurants, and food outlets, PakPOS provides high-speed billing, daily cash drawer shifts, expense tracking, and real-time cloud synchronization to a standalone **Owner Web Portal**.

---

## 🌟 Key Features

### 1. ⚡ High-Speed Point of Sale (POS)
- **Instant Item Scanning & Search**: Barcode scanner ready with fast category filters.
- **Multi-Channel Order Routing**: Support for **Walk-In / Counter**, **Dine-In**, **Takeaway**, and **Delivery**.
- **Dynamic Surcharges & Discounts**: Percentage/Flat line discounts, government sales tax, and customizable service charges.
- **Flexible Payment Methods**: Cash, Card (Debit/Credit), and Digital Mobile Wallets (EasyPaisa, JazzCash, Bank Transfer).
- **Thermal Receipt Printing**: 80mm & 58mm POS thermal receipt generation.

### 2. 💵 Daily Shift & Cash Drawer Reconciliation
- **Shift Timing Window**: Configurable operational shift hours.
- **Accurate Cash Drawer Formula**: $\text{Net Cash in Drawer} = \text{Cash Collected} - \text{Shift Outflows (Expenses)}$.
- **Live Deficit Protection**: Automatic visual warnings when expense outflows exceed cash sales.
- **Itemized Shift Outflows**: Complete real-time ledger of all expenses logged during the active shift.
- **Hourly Sales Velocity**: Visual hourly timeline displaying peak revenue hours.

### 3. 📊 Executive Analytics Dashboard
- **6-Metric KPI Grid**: Total Sales Inflow, Net Business Profit, Operating Expenses, Govt Tax & Charges, Payment Split, and Discounts/Refunds.
- **Interactive Visual Charts**:
  - 📈 **Sales Revenue Timeline**: Hourly and daily revenue velocity.
  - 🍽️ **Order Channels Share**: Channel distribution doughnut chart.
  - 🏆 **Top 5 Best-Selling Products**: Volume-based bestsellers.
  - 💳 **Payment Methods Split**: Settlement breakdown by channel.
  - 🍩 **Expense Outflows Breakdown**: Category-wise expense doughnut chart.

### 4. 📦 Products, Variants & Inventory Health
- **Simple & Variant Products**: Manage single items or multi-sized items (Small, Medium, Large, etc.).
- **Profitability Tracking**: Automatic Cost of Goods Sold (COGS) and profit margin calculations.
- **Low Stock & Depletion Warnings**: Real-time alerts for items nearing minimum stock levels.

### 5. 💸 Expense & Outflow Ledger
- Categorized expense logging (Salaries, Utilities, Raw Materials, Rent, Maintenance).
- Cashier and operator audit tracking with timestamp and descriptive notes.

### 6. 🌐 Standalone Owner Web Portal (`owner_portal/`)
- Lightweight, responsive executive mobile & desktop web application.
- Real-time cloud sync via Google Sheets / Webhook infrastructure.
- Instant access to revenue, profit, shift drawers, top sellers, and thermal receipts from anywhere in the world.

---

## 📁 Project Architecture

```text
pak pos/
├── manage.py                     # Django CLI entrypoint
├── run.bat                       # One-click Windows starter script
├── .env.example                  # Environment configuration template
├── .gitignore                    # Git ignore specifications
├── README.md                     # Comprehensive project documentation
├── db.sqlite3                    # Local SQLite database
├── venv/                         # Python Virtual Environment
├── owner_portal/                 # Standalone Executive Owner Web Portal (SPA)
│   ├── index.html                # Portal markup & layout
│   ├── style.css                 # Modern CSS design system
│   ├── app.js                    # Portal state, calculations & Chart.js engine
│   └── config.js                 # API & Webhook connection configuration
├── templates/                    # Django HTML5 Templates
│   ├── base.html                 # Master layout template
│   ├── core/                     # Executive Dashboard & Settings
│   ├── products/                 # Inventory & Variant management
│   ├── sales/                    # POS billing, shift summaries & receipts
│   ├── expenses/                 # Expense ledger & category management
│   └── users/                    # Authentication, profiles & user management
├── static/                       # Static Assets
│   ├── css/                      # Stylesheets (retailos.css, pos.css, etc.)
│   ├── js/                       # Local offline-ready libraries (chart.umd.min.js, etc.)
│   └── images/                   # Branding icons & avatars
└── pakpos_project/               # Main Django Application Package
    ├── settings.py               # Global project configuration
    ├── urls.py                   # Master URL routing
    ├── wsgi.py / asgi.py
    └── apps/                     # Modular Django Apps
        ├── core/                 # Dashboard, system settings, and cloud sync worker
        ├── products/             # Products, categories, and inventory models
        ├── users/                # Custom User model, RBAC roles, and auth
        ├── sales/                # POS, invoices, line items, and shifts
        └── expenses/             # Expense logs, categories, and ledgers
```

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.10+** installed
- Modern Web Browser (Chrome, Edge, Firefox, Safari)

### 2. Quick Start (Windows)
Double-click `run.bat` or run:
```cmd
run.bat
```

### 3. Manual Installation

1. **Clone the repository and enter the directory**:
   ```bash
   cd "pak pos"
   ```

2. **Create and activate a virtual environment**:
   ```powershell
   # Windows PowerShell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up Environment Variables**:
   Copy `.env.example` to `.env`:
   ```powershell
   copy .env.example .env
   ```

5. **Run database migrations**:
   ```bash
   python manage.py migrate
   ```

6. **Create an administrator account**:
   ```bash
   python manage.py createsuperuser
   ```

7. **Start the Development Server**:
   ```bash
   python manage.py runserver
   ```

8. **Access the application**:
   - **Executive Dashboard**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
   - **Point of Sale (POS)**: [http://127.0.0.1:8000/sales/pos/](http://127.0.0.1:8000/sales/pos/)
   - **Daily Shift Summary**: [http://127.0.0.1:8000/sales/shift/](http://127.0.0.1:8000/sales/shift/)
   - **Django Admin**: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)
   - **Owner Web Portal**: Open `owner_portal/index.html` in any browser or host on GitHub Pages/Netlify.

---

## 🛡️ License & Copyright
Developed for high-performance retail and restaurant environments.
All rights reserved © 2026 **PakPOS**.
