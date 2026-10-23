# 🥚 CHEREMO EGG DEPOT | MANAGEMENT SYSTEM

> A comprehensive, production-ready Django web application for managing egg sales, dynamic bundle pricing, real-time stock levels, supplier restock deliveries, operating expenses, and transparent profit accounting.

- **Business Owner:** Japhet
- **Default Username:** `japhet`
- **Timezone:** `Africa/Nairobi`
- **Currency:** `KES (Kenyan Shillings)`

---

## 🌟 Key Features

1. **Smart Dynamic Pricing Engine:**
   - Automatically calculates the **cheapest combination of offers** for any quantity using dynamic programming (Unbounded Knapsack algorithm).
   - Configurable offers in Settings:
     - 1 Single Egg = KSh 20.00
     - 2 Eggs Offer = KSh 35.00
     - 3 Eggs Offer = KSh 55.00
     - Half Tray (15 eggs) = KSh 240.00
     - Full Tray (30 eggs) = KSh 480.00
   - Examples automatically computed:
     - 4 eggs = KSh 70.00 (2 × 2 eggs)
     - 5 eggs = KSh 90.00 (3 eggs + 2 eggs)
     - 10 eggs = KSh 175.00 (5 × 2 eggs)
     - 16 eggs = KSh 260.00 (15 eggs + 1 egg)
     - 31 eggs = KSh 500.00 (30 eggs + 1 egg)
   - Real-time client-side price preview via AJAX with server-side re-validation before saving.
   - Historical sales preserve the exact price applied at the time of sale.

2. **Accurate Inventory & Stock Movement Audit:**
   - Standard 30-egg trays (1 full tray = 30 eggs, 1 half tray = 15 eggs).
   - Tracks **Total Eggs**, **Full Trays Available**, and **Loose Eggs Remaining**.
   - Database row-locking (`select_for_update`) within transactions prevents overselling and negative inventory.
   - Immutable audit trail logs every stock movement (Opening stock, Sales, Deliveries, Breakage losses, Count corrections, and Cancellations).
   - Safe opening stock initialization: 30 trays = 900 eggs established once, protected against duplication.

3. **Restocking Calculator & Supplier Deliveries:**
   - Full tray purchases with automatic conversion (e.g., 10 trays @ KSh 400 = 300 eggs, KSh 4,000 cost).
   - Smart Restocking Calculator calculates shortfall, rounds up to whole trays, and projects post-delivery stock.
   - Weighted Average Cost (WAC) tracking automatically recalculates egg asset valuation on each restock.
   - Optional supplier receipt/invoice upload stored securely via Cloudinary in production.

4. **Transparent Accounting & Profit Management:**
   - **Cost of Goods Sold (COGS):** Quantity sold × WAC per egg.
   - **Gross Profit:** Revenue − COGS.
   - **Net Profit:** Gross Profit − Operating Expenses − Egg Losses.
   - Capital inventory purchases are strictly separated from operating expenses to prevent double-counting.
   - Comprehensive reports: Daily, Weekly, Monthly, All-Time, and Custom Date Ranges.

5. **Security & Deployment Ready:**
   - Django built-in authentication (`@login_required` on all management routes).
   - CSRF protection enabled across all forms.
   - WhiteNoise for high-performance static asset compression and delivery.
   - Environment-variable configuration with SQLite local fallback and PostgreSQL production support via `dj-database-url`.
   - Cloudinary integration with modern Django `STORAGES` configuration.

---

## 🛠️ Technology Stack

- **Backend:** Python 3.13+, Django 5.1+ / 6.0+
- **Database:** SQLite (local development), PostgreSQL (production)
- **Database Config:** `dj-database-url`
- **Static Assets:** WhiteNoise (`CompressedManifestStaticFilesStorage`)
- **Media Storage:** Cloudinary & `django-cloudinary-storage`
- **WSGI Server:** Gunicorn
- **Environment Management:** `python-dotenv`
- **Frontend:** HTML5, Modern CSS3 (CSS Variables, Flexbox, CSS Grid), JavaScript (Vanilla ES6)

---

## 💻 Local Setup Instructions (Windows PowerShell)

Follow these exact step-by-step commands in **Windows PowerShell**:

### 1. Open PowerShell and Navigate to the Project

```powershell
cd C:\Users\Administrator\.gemini\antigravity\scratch\cheremo_egg_depot
```

### 2. Create and Activate the Virtual Environment

```powershell
# Create virtual environment with access to system site packages
python -m venv --system-site-packages venv

# Activate the virtual environment in PowerShell
.\venv\Scripts\Activate.ps1
```

*(Note: If PowerShell displays an `ExecutionPolicy` restriction, run `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` once).*

### 3. Install Dependencies

```powershell
python -m pip install -r requirements.txt
```

### 4. Set Up Local Environment Variables

A `.env` file has been provided. If creating from scratch:

```powershell
Copy-Item .env.example .env
```

Ensure `.env` contains:
```ini
SECRET_KEY=cheremo-egg-depot-dev-secret-key-348912739182379
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,testserver
CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
```

### 5. Run Database Migrations

```powershell
python manage.py migrate
```

### 6. Initialize Depot Settings, Opening Stock & Create Japhet's Account

Run the custom management command:

```powershell
python manage.py setup_depot --username japhet --password "CheremoDepot2026!"
```

This command will:
- Establish the business profile for **Cheremo Egg Depot** (Owner: **Japhet**).
- Establish the initial opening stock of **30 trays (900 eggs) @ KSh 400.00/tray** with an auditable transaction log.
- Create the superuser account `japhet` with the password `CheremoDepot2026!`.

*(Alternatively, you can run `python manage.py createsuperuser` if you prefer to type your own password interactively).*

### 7. Run Automated Tests

To verify that all 13 automated tests pass (including pricing combinations, inventory overselling protection, accounting formulas, and security):

```powershell
python manage.py test management
```

### 8. Start the Local Development Server

```powershell
python manage.py runserver
```

Now open your web browser and visit:
👉 **http://127.0.0.1:8000/**

Log in with:
- **Username:** `japhet`
- **Password:** `CheremoDepot2026!` (or the password you set)

---

## ☁️ Cloudinary Configuration & Deployment Guide

> **IMPORTANT:** Cloudinary is used to store uploaded media files (such as supplier receipts, invoices, and the business logo). PostgreSQL stores your business database records (sales, inventory movements, expenses).

### Step 1: Create a Cloudinary Account
Sign up for a free account at [Cloudinary.com](https://cloudinary.com/).

### Step 2: Retrieve Your API Credentials
1. Log in to the [Cloudinary Console](https://console.cloudinary.com/).
2. On your Dashboard / API Keys page, copy the three credentials:
   - **Cloud Name** (e.g. `dxy82kdla`)
   - **API Key** (e.g. `839217482910482`)
   - **API Secret** (e.g. `kdf9_sd02jkdf92kd84js82kd`)

### Step 3: Configure Environment Variables on Your Hosting Platform
When deploying to **Render**, **Railway**, or any other hosting provider:

1. Open your web service dashboard.
2. Navigate to **Environment Variables** (or **Settings > Environment**).
3. Add the following keys with your private credentials:
   ```env
   CLOUDINARY_CLOUD_NAME=your_actual_cloud_name
   CLOUDINARY_API_KEY=your_actual_api_key
   CLOUDINARY_API_SECRET=your_actual_api_secret
   ```
4. Also set:
   ```env
   DEBUG=False
   SECRET_KEY=a-long-random-secret-key-for-production
   ALLOWED_HOSTS=.onrender.com,your-custom-domain.com
   CSRF_TRUSTED_ORIGINS=https://your-service.onrender.com,https://your-custom-domain.com
   DATABASE_URL=postgresql://user:password@hostname:5432/dbname
   ```

### Step 4: Storage Architecture Verification
In `depot/settings.py`, the modern Django `STORAGES` setting is configured as:
- When `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, and `CLOUDINARY_API_SECRET` are provided, the default file storage automatically connects to `cloudinary_storage.storage.MediaCloudinaryStorage`.
- Uploaded supplier receipts and depot logos receive persistent, CDN-accelerated URLs (e.g. `https://res.cloudinary.com/...`).
- Uploads remain available and persistent across application redeployments and container restarts.
- During local development with empty Cloudinary keys, the application gracefully defaults to `django.core.files.storage.FileSystemStorage`, preventing crashes when working offline.
- CSS, JavaScript, and font assets are served via **WhiteNoise** directly from your web server, ensuring high-speed delivery without wasting Cloudinary bandwidth.

---

## 🚀 Online Deployment Guide (e.g. Render)

### Step 1: Push Code to GitHub

```powershell
git init
git add .
git commit -m "Initial commit: Cheremo Egg Depot Management System"
git branch -M main
git remote add origin https://github.com/japhetcheremo-cloud/cheremo-egg-deport.git
git push -u origin main
```

*(Note: `.env`, virtual environment directories, and `.sqlite3` files are listed in `.gitignore` and will never be committed).*

### Step 2: Create a PostgreSQL Database on Render
1. Log in to [Render.com](https://render.com/).
2. Click **New +** and select **PostgreSQL**.
3. Name it `cheremo-depot-db`.
4. Once provisioned, copy the **Internal Database URL** (or **External Database URL**).

### Step 3: Create a Web Service on Render
1. Click **New +** and select **Web Service**.
2. Connect your GitHub repository `cheremo-egg-deport`.
3. Configure the following:
   - **Environment:** `Python 3`
   - **Build Command:** `./build.sh` (or `pip install -r requirements.txt && python manage.py collectstatic --no-input && python manage.py migrate`)
   - **Start Command:** `gunicorn depot.wsgi --log-file -`
4. In the **Environment Variables** tab, add:
   - `DATABASE_URL` = *(Your PostgreSQL URL from Step 2)*
   - `SECRET_KEY` = *(A secure 50+ character string)*
   - `DEBUG` = `False`
   - `ALLOWED_HOSTS` = `.onrender.com`
   - `CSRF_TRUSTED_ORIGINS` = `https://your-app-name.onrender.com`
   - `CLOUDINARY_CLOUD_NAME` = *(Your Cloudinary Cloud Name)*
   - `CLOUDINARY_API_KEY` = *(Your Cloudinary API Key)*
   - `CLOUDINARY_API_SECRET` = *(Your Cloudinary API Secret)*

### Step 4: Run Initial Setup in Render Shell
After the deployment finishes:
1. In the Render service dashboard, click **Shell**.
2. Run:
   ```bash
   python manage.py setup_depot --username japhet --password "YourProductionPassword123!"
   ```
3. Open `https://your-app-name.onrender.com/` and log in with username `japhet`.

---

## 🔧 Troubleshooting Guide

| Issue | Cause | Solution |
|---|---|---|
| **Invalid HTTP_HOST header / 400 Bad Request** | The deployed domain or host is not in `ALLOWED_HOSTS`. | In your hosting platform settings, set `ALLOWED_HOSTS=.onrender.com` (or your domain). |
| **CSRF verification failed (403)** | Missing deployed HTTPS domain in trusted origins. | Set `CSRF_TRUSTED_ORIGINS=https://your-domain.onrender.com` in environment variables. |
| **Static files (CSS/JS) not styling on production** | `collectstatic` was not run during build. | Ensure `build.sh` executes `python manage.py collectstatic --no-input` and WhiteNoise is in middleware. |
| **Missing staticfiles manifest entry** | Manifest was queried before static files were collected. | Run `python manage.py collectstatic` to generate `staticfiles.json`. |
| **Cloudinary upload fails / Unauthorized error** | Incorrect `CLOUDINARY_API_KEY` or `CLOUDINARY_API_SECRET`. | Double-check Cloudinary credentials in your hosting platform dashboard. Ensure no trailing spaces exist. |
| **Database connection error** | Invalid or unreachable `DATABASE_URL`. | Check the PostgreSQL service status on your hosting provider and verify credentials in the connection string. |
| **Duplicate Opening Stock error** | Initial stock was already initialized. | Opening stock can only be established once. Use the **Deliveries** page for restocks or the **Inventory Adjustments** page for corrections. |

---

## 📁 Project Structure

```
cheremo_egg_depot/
│
├── manage.py                   # Django management utility
├── requirements.txt            # Python dependencies (Django, Cloudinary, WhiteNoise, etc.)
├── .env.example                # Example environment variable template
├── .gitignore                  # Git ignore rules for secrets, DB, and venv
├── build.sh                    # Automated deployment build script
├── Procfile                    # Web process command for Gunicorn
├── README.md                   # Comprehensive system documentation
│
├── depot/                      # Core Django project configuration
│   ├── __init__.py
│   ├── settings.py             # Settings (Cloudinary STORAGES, WhiteNoise, dj-database-url, KES, Nairobi TZ)
│   ├── urls.py                 # Top-level URL routing
│   ├── wsgi.py                 # WSGI application entrypoint
│   └── asgi.py                 # ASGI application entrypoint
│
├── management/                 # Cheremo Egg Depot core application
│   ├── __init__.py
│   ├── admin.py                # Admin registration with audit-log protections
│   ├── apps.py                 # Application configuration
│   ├── context_processors.py   # Global business info & low-stock banner context
│   ├── forms.py                # Forms for Sales, Deliveries, Expenses, Adjustments, Settings
│   ├── models.py               # BusinessSettings, Inventory, Sale, Delivery, Expense, Movements
│   ├── services.py             # Pricing algorithm (Knapsack DP), Inventory, Restocking Calculator, Accounting
│   ├── tests.py                # Automated test suite (13 test cases)
│   ├── urls.py                 # Route definitions for all views and APIs
│   ├── views.py                # View handlers (Dashboard, Sales, Deliveries, Expenses, Reports, CSV)
│   └── management/
│       └── commands/
│           ├── __init__.py
│           └── setup_depot.py  # First-time setup command for japhet superuser & opening stock
│
├── templates/                  # Responsive HTML5 templates (Egg branding, sunshine yellow & orange)
│   ├── base.html               # Master layout with sidebar and mobile navigation
│   ├── login.html              # Clean, branded login page
│   ├── dashboard.html          # Operational dashboard with live metrics and 7-day trend
│   ├── sales.html              # Point-of-Sale with live price preview and sale history
│   ├── deliveries.html         # Supplier restock intake and Restocking Calculator
│   ├── expenses.html           # Operating expenses log and monthly summary
│   ├── inventory.html          # Live stock breakdown and egg loss / count adjustment form
│   ├── transactions.html       # Full audit trail with date filters, search, and CSV export
│   ├── reports.html            # P&L statement, COGS, Net Profit, and documented accounting rules
│   ├── settings.html           # Configurable retail pricing and one-time opening stock initialization
│   ├── confirm_delete.html     # Confirmation dialog for safe sale cancellations
│   └── registration/
│       └── login.html          # Fallback auth template
│
└── static/                     # Static styling and JavaScript
    ├── css/
    │   └── style.css           # Custom styling with brand palette (#FFC928, #FF8A00, #FFF9EC)
    └── js/
        └── script.js           # Live pricing preview AJAX, mobile menu toggle, double-submit protection
```

---

## 🥚 Brand Colors Reference

- **Sunshine Yellow:** `#FFC928`
- **Vibrant Orange:** `#FF8A00`
- **Orange Hover:** `#E87500`
- **Cream Background:** `#FFF9EC`
- **Surface White:** `#FFFFFF`
- **Dark Text:** `#292929`
- **Success Green:** `#21865B`
- **Error Red:** `#D93636`
