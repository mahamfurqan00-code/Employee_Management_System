# PeopleOps – Employment Management System

## About the Project

PeopleOps is a web-based Employment Management System developed using Python and Flask. The main purpose of this project is to make employee management easier, faster, and more organized.

In many organizations, managing employee records manually can become time-consuming, especially when the number of employees increases. PeopleOps provides a simple platform where an administrator can manage employee information, keep track of employment details, and view important workforce information from one place.

I developed this project to practice my Python development skills and understand how a real-world web application works, including database management, backend development, and frontend integration.

## Main Features

- **Dashboard:** Displays an overview of the organization, including total employees, active employees, departments, and average salary.
- **Add Employees:** Allows new employee records to be added to the system.
- **Update Employee Details:** Existing employee information can be edited whenever changes are needed.
- **Delete Employees:** Removes employee records that are no longer required.
- **Search Employees:** Makes it easy to find employees using their name, employee ID, email, or job title.
- **Filter Employees:** Employees can be filtered by department and employment status.
- **Employee Status:** Keeps track of whether an employee is Active, Inactive, or On Leave.
- **Salary Management:** Stores employee salary information.
- **CSV Export:** Allows employee records to be downloaded in CSV format.
- **REST API:** Provides employee information in JSON format through an API endpoint.

## Technologies Used

- Python – Main programming language
- Flask – Backend web framework
- Flask-SQLAlchemy – Database integration and ORM
- SQLite – Database for storing employee records
- HTML – Page structure
- CSS – Styling and responsive layout
- JavaScript – Basic frontend interactions
- Jinja2 – Dynamic HTML templates

## Project Structure

PeopleOps-Employment-Management-System/

- app.py – Main application file containing routes, database models, and backend logic.
- requirements.txt – List of Python packages required to run the project.
- README.md – Project documentation.
- templates/ – HTML templates used by the application.
- static/css/ – CSS files for the user interface.
- static/js/ – JavaScript files.
- tests/ – Basic application tests.

## How to Run the Project

Follow these steps to run PeopleOps on your computer.

### Step 1: Install Python

Make sure Python 3.10 or a newer version is installed.

### Step 2: Extract the ZIP File

Extract the downloaded project ZIP file to your computer.

### Step 3: Open the Project Folder

Open the project folder in VS Code or another code editor.

### Step 4: Create a Virtual Environment

Run this command in the terminal:

python -m venv venv

Activate it on Windows:

venv\Scripts\activate

### Step 5: Install Required Packages

Run:

pip install -r requirements.txt

### Step 6: Start the Application

Run:

python app.py

### Step 7: Open the Website

Open your browser and visit:

http://127.0.0.1:5000

The application will create its SQLite database automatically and add sample employee records on the first run.

## Deploying on Vercel

Import this repository into Vercel and deploy it from the project root. Vercel detects the Flask application in `app.py` and installs the packages listed in `requirements.txt`; no custom start command is needed.

To persist employee records with Neon:

1. Create a PostgreSQL project in Neon and copy its pooled connection string. Use the pooled host and keep `sslmode=require` in the URL.
2. In Vercel, open the project's **Settings → Environment Variables** and add `DATABASE_URL` with the Neon connection string. Do not commit the URL to this repository.
3. Add a unique `SECRET_KEY` environment variable in the same Vercel settings.
4. Redeploy the project so the new environment variables take effect.

The app converts standard PostgreSQL URLs to use the included Psycopg driver. On startup it creates the employee table and sample records if the database is empty. Existing records in the local SQLite database are not automatically copied to Neon.

Vercel's application filesystem is not persistent. Without `DATABASE_URL`, the app uses a temporary SQLite database to display the dashboard, but data saved there may disappear and is not shared reliably between serverless instances.

Keep `SECRET_KEY` private and set it in Vercel's environment variables before using the app beyond a demo.

## API Endpoints

The project also includes two simple API endpoints:

- GET /api/employees – Returns employee records in JSON format.
- GET /health – Checks whether the application is running.

## Sample Data

The application includes fictional employee records so that users can explore the dashboard and test its features without entering data manually.

You can add, edit, search, filter, and delete employee records through the interface.

## Future Improvements

There are several features that could make this project even better in the future:

- Admin login and authentication
- Different access levels for HR staff and administrators
- Employee profile pictures
- Attendance management
- Leave request management
- Monthly salary reports
- PDF report generation
- Improved security and data backup

## Important Note

This project was developed for educational and portfolio purposes. It demonstrates employee record management using Python, Flask, and SQLite. Before using it in a real organization, additional security features such as authentication, authorization, CSRF protection, and secure configuration should be implemented.

---

**Project Name:** PeopleOps – Employment Management System

**Developed Using:** Python, Flask, SQLite, HTML, CSS, and JavaScript

**Project Type:** Web-Based Application