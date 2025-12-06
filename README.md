# Restaurant Management System （Backend）

A comprehensive restaurant management system built on **Flask + Vue.js**. This project adopts a decoupled architecture (Frontend imports Vue and Element UI via CDN) and implements core functionalities including user management, inventory control, order processing, and employee payroll calculation.

## Project Structure
To ensure Flask renders pages correctly, please ensure the directory structure is as follows (Note: index.html must be inside the templates folder):
```bash
/Project Root
  ├── app.py              # Backend entry file
  ├── templates/
  │   └── index.html      # Frontend entry page
  ├── static/             # Default static assets/images
  ├── uploads/            # (Auto-created)
  └── food_images/        # (Auto-created)
```

## Dependencies

* **Backend:** Python 3, Flask, SQLAlchemy (ORM)
* **Frontend:** Vue.js 2, Element UI, Axios
* **Database:** SQLite (Managed/Viewed via DB Browser for SQLite)

## Features

This project includes the following modules:

### 1. Dashboard
* **Data Visualization:** Visualizes core data including total users, total orders, and total sales revenue.
* **Real-time Analytics:** Backend performs aggregate queries to calculate statistical indicators in real-time.

### 2. User Module
* **CRUD Operations:** Implements Create, Read, Update, and Delete functionality for users.
* **Avatar Upload:** Supports local image uploads for user avatars. The backend automatically saves files to the `uploads/avatars` directory and generates access URLs.
* **Balance System:** Simulates logic for top-ups and consumption. Administrators can manually modify user balances.

### 3. Food Inventory
* **Image Management:** Supports uploading and previewing food images (JPG/PNG/WebP formats).
* **Inventory Control:** Automatically checks stock levels during order placement. Creation of orders is blocked if stock is insufficient to prevent overselling.

### 4. Order System
* **Transaction Processing:**
    * Automatically deducts the user's balance upon ordering.
    * Simultaneously deducts the stock of the corresponding food items.
    * **Atomic Transactions:** Includes a full rollback mechanism. If the balance or stock is insufficient, the operation is automatically cancelled to ensure data consistency.
* **Search:** Supports multi-condition searching (by Order ID, Username).

### 5. Employee & Salary
* **Modeling:** Designed data models for employee roles and salaries.
* **Auto-Calculation:** The frontend automatically calculates the daily rate and total monthly payable salary based on the input "Monthly Salary" and "Actual Working Days," facilitating financial accounting.

## How to Run

### 1. Environment Setup
Ensure **Python 3.8+** is installed locally.
It is recommended to create a virtual environment, then install dependencies:

```bash
pip install flask flask-sqlalchemy flask-cors

```

### 2. Start the Server
```bash
python app.py
```
Note: On the first run, the system will automatically generate the restaurant.db database file and initialize test data.

Special Note for macOS Users: macOS Monterey and newer versions occupy port 5000 by default (AirPlay Receiver). If you encounter an Address already in use error, please modify the code at the bottom of app.py to use port 5001 or another free port: app.run(host='0.0.0.0', port=5001, debug=True)

### 3. Access
- Default Address: http://127.0.0.1:5000

- If Port Modified: http://127.0.0.1:5001 (or your custom port)

- LAN Access: To access from other devices on the same WiFi, use your machine's IP address (e.g., http://10.34.xx.xx:5001).
