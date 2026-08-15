# PakPOS - Point of Sale System

PakPOS is a modern Point of Sale (POS) application built with **Django** and Python, designed for business and retail management.

---

## 📁 Project Structure

```text
pak pos/
├── manage.py
├── run.bat                     # Quick starter script to activate venv
├── .env                        # Environment variables (secret keys, debug mode)
├── .env.example                # Sample environment template
├── .gitignore
├── README.md
├── venv/                       # Virtual Environment
└── pakpos_project/             # Main Django Project Directory
    ├── settings.py
    ├── urls.py
    ├── wsgi.py
    ├── asgi.py
    └── apps/                   # Project Applications
        ├── __init__.py
        ├── core/               # Core / Dashboard App
        └── products/           # Products Management App
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+ installed
- Git (optional)

### 2. Environment Setup

If you are on Windows, you can simply run:
```bat
run.bat
```
Or manually activate the virtual environment:
```powershell
# Windows
.\venv\Scripts\activate
```

### 3. Environment Variables
Create a `.env` file in the root directory (or copy from `.env.example`):
```env
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
```

### 4. Database Migrations
Run the initial migrations to set up the database:
```bash
python manage.py migrate
```

### 5. Create Superuser (Admin)
Create an administrative account:
```bash
python manage.py createsuperuser
```

### 6. Run Development Server
Start the Django development server:
```bash
python manage.py runserver
```

Open your browser and navigate to:
- **Home / Core**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Products**: [http://127.0.0.1:8000/products/](http://127.0.0.1:8000/products/)
- **Admin Panel**: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

---

## 📦 Installed Apps
- **`core`** (`pakpos_project.apps.core`): Base application and dashboard.
- **`products`** (`pakpos_project.apps.products`): Product catalog and inventory management.
