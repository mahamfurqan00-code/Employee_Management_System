Project Name: Detecting Fraud Apps using Sentiment Analysis

1. Project Overview
--------------------
A web-based application that identifies suspicious mobile app reviews using
opinion mining (sentiment analysis) and repeat-IP tracking.

2. Key Features
-----------------
- Registration & Login: separate User and Admin login, with hashed passwords.
- Applications: Admin adds apps (name, link, description, category, image);
  users browse them before reviewing.
- Reviews: Users submit reviews per app. TextBlob sentiment analysis flags
  negative reviews as "Fraud Suspect".
- Repeat-IP flagging: reviews are flagged in the admin dashboard when 3+
  reviews for the same app come from the same IP address — a common sign of
  fake review farming.
- Feedback: Users can send general platform feedback to the admin, separate
  from app reviews.
- Admin tools: view/edit/delete reviews, manage applications, view
  registered users, view feedback.

3. Technologies Used
----------------------
Backend: Python (Flask, Flask-SQLAlchemy)
Frontend: HTML5, CSS (Jinja2 templates)
Database: SQLite
AI Tool: TextBlob (opinion mining)
Security: Werkzeug password hashing

4. How to Run the Project
----------------------------
1. Extract the folder.
2. (Recommended) Create and activate a virtual environment:
     python -m venv venv
     venv\Scripts\activate      (Windows)
     source venv/bin/activate   (Mac/Linux)
3. Install required libraries:
     pip install -r requirements.txt
4. TextBlob needs its language corpora the first time you use it:
     python -m textblob.download_corpora
4b. The default sentiment engine is SentiWordNet (the dictionary named in
    the project document), via NLTK. Download it once:
     python -m nltk.downloader sentiwordnet wordnet omw-1.4
    If this step is skipped, or the download fails, the app automatically
    falls back to TextBlob - nothing crashes either way. To force TextBlob
    on purpose, set SENTIMENT_ENGINE=textblob before running the app.
5. Create an admin account. You have two options:
   a) On the Register page in the browser, choose "Register as: Admin" from
      the dropdown and enter the Admin Access Code. Set a unique
      ADMIN_SIGNUP_CODE environment variable before starting the app:
        PowerShell: $env:ADMIN_SIGNUP_CODE = "your-unique-long-code"
        macOS/Linux: export ADMIN_SIGNUP_CODE="your-unique-long-code"
      Admin registration is disabled if this variable is not set.
   b) From the terminal, without needing the code:
        flask --app app.py create-admin
      You'll be prompted for an admin username, email, and password.
6. Run the application:
     python app.py
7. Open the browser and go to: http://127.0.0.1:5000
8. Log in as Admin (the account from step 5) and add a few applications
   under "Applications" before users start submitting reviews.
9. Register a normal user account from the Register page, log in, and
   submit reviews to see the sentiment analysis and IP-flagging in action.

5. Notes on Test Credentials
--------------------------------
Earlier versions of this project shipped pre-seeded plaintext test logins.
Passwords are now hashed, so those old credentials no longer work — use the
`flask create-admin` command (step 5 above) to create your own admin
account, and the Register page for user accounts.

6. Changes From the Original Submission
-------------------------------------------
- Passwords are hashed (werkzeug) instead of stored in plain text.
- Login and Register pages now clearly separate User and Admin: Login has
  User/Admin tabs, and Register has a "Register as" dropdown. Choosing
  Admin on Register requires an Admin Access Code (see setup step 5) so
  the option is visible without letting just anyone grant themselves
  admin access.
- Added an Application model so apps are real, manageable records instead
  of free-text typed into the review form (matches the original proposal's
  "Add New Application" / "View Applications" modules).
- Added a Feedback model and "Write Feedback" page (matches the proposal's
  feedback module).
- Added an admin "View Users" page.
- Implemented IP-based repeat-review flagging, which the original README
  described but the code never actually used.
- Replaced the raw "Invalid Credentials!" HTML string and silent failures
  with flashed messages shown in the normal page layout.
- Config, secret key, and debug mode now read from environment variables
  instead of being hardcoded.
- UI redesign: black / blue / red / yellow theme (blue = actions and
  "Genuine", red = fraud and danger, yellow = warnings and highlights,
  black = navigation and headers). Space Grotesk + Inter typography.
- Every app now has its own colored icon badge (WhatsApp green, Snapchat
  yellow, Bitcoin orange, etc.), generated in code - no external image
  files needed, works offline. Apps an admin adds later automatically get
  a badge color and their first letter.
- Login and Register use a round, animated 3D card that tilts with the
  mouse (disabled automatically for users who prefer reduced motion).
- Added 10 trending apps (WhatsApp, Snapchat, Facebook, Twitter (X),
  Bitcoin Wallet, Binance, Coinbase, PUBG Mobile, Free Fire, Ludo King).
  No database change is needed for this version.
- Second UI redesign based on a reference design: deep navy / indigo /
  plum / rose / blush palette, thin geometric headings (Josefin Sans),
  outlined italic buttons, glass-style cards, and an app-style
  floating bottom navigation dock (icon + label tabs, active page
  highlighted, different tabs for visitors, users and admins).
- Welcome page now has a hero section. Login/Register keep the round
  animated 3D card, restyled in the new palette.
- The admin "Image URL" field now actually displays on the app tile and
  detail page (with the colored icon badge as the fallback).
- Closed the gaps against the instructor's project document, without
  touching the colour theme, typography, or any existing styling:
  * Rating field added to Add New Application, shown on app tiles, the
    app detail page, and in the admin tables.
  * New "Detect Fraud Applications" admin section (Detect tab): every
    app's comments and rating are summarised with a suggested verdict,
    and the admin can mark an app Genuine, Fraud, or reset it to
    Pending. The verdict is shown to users on the app tile and detail
    page.
  * Sentiment is now Positive / Negative / Neutral (previously a binary
    Genuine / Fraud Suspect label), with a numeric score (-1 to +1)
    shown next to every comment.
  * Applications are ranked by average sentiment score on the admin
    Reviews page, as the project document asks for.
  * Sentiment engine is SentiWordNet by default (matching the project
    document's "Senti WordNet Dictionary"), with an automatic,
    silent fallback to TextBlob if the corpus isn't downloaded.
  * IP capture now works correctly behind a reverse proxy (Apache/
    Nginx) when TRUST_PROXY=1 is set, closing the project document's
    "capture IP addresses" requirement for a real deployment.
  * The exact project title, "Detecting Fraud Apps using Sentiment
    Analysis", now appears on the Welcome page and in the browser tab
    title. The Welcome page itself was kept - it was not in the
    instructor's document, but was requested separately and is being
    kept intentionally.
  * The database upgrades itself automatically (ensure_schema) when
    these new columns are missing, and re-scores any old comments
    (backfill_sentiment) - you do NOT need to delete fraud_detection.db
    for this version.
- NOT changed, on purpose - flag these with your supervisor if it
  matters for grading:
  * Database: still SQLite, not MySQL 5.6/WAMP as listed in the
    project document. Set DATABASE_URL to use MySQL instead (see the
    comment above SQLALCHEMY_DATABASE_URI in app.py).
  * Some module names differ in wording from the project document
    (e.g. the nav says "Apps"/"Reviews" rather than the full module
    names) - the Mismatch Report spreadsheet lists every wording
    difference if you want to match them exactly.
  * Admin self-registration (with an access code) is still on the
    Register page; the project document only describes a single
    registration form for users.
