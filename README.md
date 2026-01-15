# Restaurant Tip Distribution App

A desktop application built with Python to automate the calculation and distribution of tips for restaurant staff. It replaces manual Excel calculations with a secure, database-driven system. It was used in a real restaurant where I worked last summer.

## 🚀 Features
* **Fair Distribution Algorithm:** Automatically calculates tip shares based on staff points (roles) and daily collected tips.
* **Local Database:** Uses SQLite to store staff details and daily logs securely, replacing fragile Excel files.
* **PDF Reporting:** Generates professional financial reports (Daily, Weekly, Monthly) for accounting and transparency.
* **Manager Security:** Sensitive actions (like editing staff points) are protected by a password gate.
* **User-Friendly GUI:** Built with Tkinter for a native, fast, and easy-to-use Windows interface.

## 🛠️ Technology Stack
* **Language:** Python 3.12
* **GUI:** Tkinter
* **Database:** SQLite3
* **Data Processing:** Pandas
* **Reporting:** ReportLab (PDF Generation)
* **Packaging:** PyInstaller & Inno Setup

## ⚙️ Setup & Installation
1. Download the latest installer from the [Releases](https://github.com/dimitris-detsirapis/Restaurant-Tip-App/releases) page.
2. Run `RestaurantTipApp_Setup.exe` to install the app.
3. Launch via the Desktop shortcut.

## 🔒 Security Note for Developers
The application includes a manager authentication system.
* **Default Password:** `1234` (for testing/demo purposes).
* In a production environment, this should be configured via the `MANAGER_PASSWORD` environment variable.

