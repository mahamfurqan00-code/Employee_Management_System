import os
import re
from collections import Counter
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from werkzeug.security import generate_password_hash, check_password_hash
from textblob import TextBlob

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-key-change-me")

# Database: SQLite by default (zero setup). To use MySQL (e.g. WAMP + MySQL 5.6 as in
# the project document) set DATABASE_URL, for example:
#   mysql+pymysql://root:@localhost/fraud_detection
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///fraud_detection.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

IP_DUPLICATE_THRESHOLD = 3          # same IP, same app, this many comments -> flagged
ADMIN_SIGNUP_CODE = os.environ.get("ADMIN_SIGNUP_CODE", "")

# Sentiment thresholds on a -1 (very negative) .. +1 (very positive) scale
POSITIVE_AT = 0.10
NEGATIVE_AT = -0.10


# --- Database Models ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)      # salted hash, never plain text
    role = db.Column(db.String(10), default='user')

    reviews = db.relationship('Review', backref='author', lazy=True)
    feedbacks = db.relationship('Feedback', backref='author', lazy=True)


class Application(db.Model):
    """Admin > Add New Application: Name, Link, Description, Rating, Category, App Image."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    link = db.Column(db.String(255))
    description = db.Column(db.Text)
    category = db.Column(db.String(50))
    image_url = db.Column(db.String(255))
    rating = db.Column(db.Float)                  # listed rating, 0-5, entered by the admin
    verdict = db.Column(db.String(20))            # admin decision: 'Genuine', 'Fraud' or None (pending)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reviews = db.relationship('Review', backref='application', lazy=True,
                               cascade="all, delete-orphan")

    @property
    def verdict_label(self):
        return self.verdict or "Pending"

    @property
    def verdict_class(self):
        return {"Genuine": "status-genuine", "Fraud": "status-fraud"}.get(self.verdict, "status-neutral")

    def stats(self):
        """Opinion-mining summary of all comments on this app."""
        revs = self.reviews
        total = len(revs)
        pos = sum(1 for r in revs if r.sentiment == "Positive")
        neg = sum(1 for r in revs if r.sentiment == "Negative")
        neu = total - pos - neg
        scores = [r.sentiment_score for r in revs if r.sentiment_score is not None]
        avg = sum(scores) / len(scores) if scores else 0.0
        # sentiment rating: average score (-1..+1) mapped to a 0..5 scale
        sentiment_rating = round((avg + 1) / 2 * 5, 1) if scores else None
        ip_counts = Counter(r.ip_address for r in revs)
        repeat_ip = sum(1 for r in revs if ip_counts[r.ip_address] >= IP_DUPLICATE_THRESHOLD)
        neg_share = neg / total if total else 0.0

        reasons = []
        if total == 0:
            suggestion, tone = "No comments yet", "status-neutral"
        else:
            if neg_share > 0.5 or avg <= -0.2:
                suggestion, tone = "Likely Fraud", "status-fraud"
            elif avg >= 0.1 and neg_share < 0.3:
                suggestion, tone = "Likely Genuine", "status-genuine"
            else:
                suggestion, tone = "Needs review", "status-neutral"
            reasons.append(f"{neg} of {total} comment(s) are negative ({neg_share:.0%}).")
            reasons.append(f"Average sentiment score is {avg:+.2f} (sentiment rating {sentiment_rating} / 5).")
            if repeat_ip:
                reasons.append(f"{repeat_ip} comment(s) share an IP address with {IP_DUPLICATE_THRESHOLD - 1}+ other "
                               f"comments on this app, a possible sign of fake reviews.")
        return dict(total=total, positive=pos, negative=neg, neutral=neu, avg_score=avg,
                    sentiment_rating=sentiment_rating, repeat_ip=repeat_ip,
                    suggestion=suggestion, suggestion_class=tone, reasons=reasons)


class Review(db.Model):
    """A user's comment on an application, analysed with opinion mining."""
    id = db.Column(db.Integer, primary_key=True)
    app_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    review_text = db.Column(db.Text, nullable=False)
    sentiment = db.Column(db.String(20))          # Positive / Negative / Neutral
    sentiment_score = db.Column(db.Float)         # -1 .. +1
    ip_address = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def sentiment_class(self):
        return {"Positive": "status-genuine", "Negative": "status-fraud"}.get(self.sentiment, "status-neutral")

    @property
    def is_ip_suspicious(self):
        count = Review.query.filter_by(app_id=self.app_id, ip_address=self.ip_address).count()
        return count >= IP_DUPLICATE_THRESHOLD


class Feedback(db.Model):
    """User > Write Feedback (about the system). Admin is notified via an unread counter."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# --- Helpers ---

def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if 'user_id' not in session:
                flash("Please log in to continue.", "error")
                return redirect(url_for('login'))
            if role and session.get('role') != role:
                flash("You don't have access to that page.", "error")
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return wrapped
    return decorator


def get_client_ip():
    """IP address of the visitor. Behind Apache/Nginx (as in the project document) set
    TRUST_PROXY=1 so the address forwarded by the web server is used instead of the proxy's."""
    if os.environ.get("TRUST_PROXY") == "1":
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.remote_addr


# ---- Opinion mining: SentiWordNet (project document) with TextBlob as automatic fallback ----

_NEGATIONS = {"not", "no", "never", "cannot", "without", "hardly"}
_SKIP_WORDS = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "am", "it", "its", "this", "that",
               "these", "those", "i", "me", "my", "we", "you", "your", "he", "she", "they", "them", "of", "to",
               "in", "on", "at", "by", "for", "with", "and", "or", "but", "as", "so", "very", "too", "really",
               "has", "have", "had", "do", "does", "did", "will", "would", "can", "could", "app", "apps"}
_swn = None      # lazy: the SentiWordNet corpus, or False if it is not available


def _load_sentiwordnet():
    global _swn
    if _swn is None:
        try:
            from nltk.corpus import sentiwordnet
            list(sentiwordnet.senti_synsets("good"))     # raises LookupError if corpus not downloaded
            _swn = sentiwordnet
        except Exception:
            _swn = False
    return _swn


def sentiwordnet_polarity(text_value, lexicon=None):
    """Average positive-minus-negative SentiWordNet score of the opinion words in the text (-1..+1).
    Handles simple negation ('not good'). Returns None when SentiWordNet is not available."""
    swn = lexicon or _load_sentiwordnet()
    if not swn:
        return None
    scores, negate_left = [], 0
    for token in re.findall(r"[a-z']+", text_value.lower()):
        if token in _NEGATIONS or token.endswith("n't"):
            negate_left = 3
            continue
        if token in _SKIP_WORDS:
            negate_left = max(0, negate_left - 1)
            continue
        senses = list(swn.senti_synsets(token))[:4]
        if senses:
            weights = [1 / (i + 1) for i in range(len(senses))]      # commoner senses count more
            s = sum(w * (x.pos_score() - x.neg_score()) for w, x in zip(weights, senses)) / sum(weights)
            if abs(s) >= 0.05:
                scores.append(-s if negate_left else s)
        negate_left = max(0, negate_left - 1)
    return max(-1.0, min(1.0, sum(scores) / len(scores))) if scores else 0.0


def sentiment_engine_name():
    wanted = os.environ.get("SENTIMENT_ENGINE", "sentiwordnet").lower()
    if wanted == "sentiwordnet" and _load_sentiwordnet():
        return "SentiWordNet"
    return "TextBlob (SentiWordNet not available)" if wanted == "sentiwordnet" else "TextBlob"


def analyze_sentiment(text_value):
    """Returns (label, score): label is Positive, Negative or Neutral; score is -1..+1."""
    score = None
    if os.environ.get("SENTIMENT_ENGINE", "sentiwordnet").lower() == "sentiwordnet":
        score = sentiwordnet_polarity(text_value)
    if score is None:
        score = TextBlob(text_value).sentiment.polarity
    score = round(score, 3)
    if score >= POSITIVE_AT:
        return "Positive", score
    if score <= NEGATIVE_AT:
        return "Negative", score
    return "Neutral", score


def parse_rating(raw):
    try:
        return max(0.0, min(5.0, round(float(raw), 1)))
    except (TypeError, ValueError):
        return None


# Each app gets its own badge color + icon. Colors follow each app's
# well-known brand color; icons are generic symbols (not logo artwork), so
# no external image files are needed and everything works offline.
BADGE_STYLES = {
    "WhatsApp":        {"color": "#25D366", "icon": "💬"},
    "Snapchat":        {"color": "#FFFC00", "icon": "📸", "text": "#111318"},
    "Facebook":        {"color": "#1877F2", "icon": "👥"},
    "Twitter (X)":     {"color": "#000000", "icon": "𝕏"},
    "Bitcoin Wallet":  {"color": "#F7931A", "icon": "₿"},
    "Binance":         {"color": "#F0B90B", "icon": "🪙", "text": "#111318"},
    "Coinbase":        {"color": "#0052FF", "icon": "🪙"},
    "PUBG Mobile":     {"color": "#5B6F44", "icon": "🎮"},
    "Free Fire":       {"color": "#FF5722", "icon": "🔥"},
    "Ludo King":       {"color": "#D32F2F", "icon": "🎲"},
    "QuickPay Wallet": {"color": "#1D4ED8", "icon": "💳"},
    "ChatterBox":      {"color": "#6366F1", "icon": "🗨️"},
    "FitTrack Pro":    {"color": "#10B981", "icon": "🏃"},
    "CryptoLeap":      {"color": "#F59E0B", "icon": "📈", "text": "#111318"},
    "StudyBuddy":      {"color": "#8B5CF6", "icon": "📚"},
    "SnapDeal Rewards": {"color": "#EC4899", "icon": "🛍️"},
    "RideNow":         {"color": "#0EA5E9", "icon": "🚗"},
    "MoodJournal":     {"color": "#F97316", "icon": "📓"},
}
_FALLBACK_COLORS = ["#1D4ED8", "#DC2626", "#F5B700", "#111318", "#7C3AED", "#0EA5E9"]


def get_app_badge(application):
    """Returns {color, icon, text} for an app. Known apps use the curated
    style above; any app an admin adds later gets a stable color (based on
    its name) with its first letter as the icon."""
    style = BADGE_STYLES.get(application.name)
    if style:
        return {"color": style["color"], "icon": style["icon"], "text": style.get("text", "#FFFFFF")}
    color = _FALLBACK_COLORS[sum(ord(c) for c in application.name) % len(_FALLBACK_COLORS)]
    text = "#111318" if color == "#F5B700" else "#FFFFFF"
    return {"color": color, "icon": application.name[:1].upper(), "text": text}


app.jinja_env.globals["get_app_badge"] = get_app_badge


@app.context_processor
def inject_unread_feedback():
    """Number of unread feedback messages, shown as a badge on the admin's Feedback tab."""
    if session.get('role') == 'admin':
        return {'unread_feedback': Feedback.query.filter_by(is_read=False).count()}
    return {'unread_feedback': 0}


# --- Public Routes ---

@app.route('/')
def welcome():
    return render_template('welcome.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        role = request.form.get('role', 'user')
        if role not in ('user', 'admin'):
            role = 'user'

        if not username or not email or not password:
            flash("All fields are required.", "error")
            return render_template('register.html')

        if role == 'admin' and (
                not ADMIN_SIGNUP_CODE or request.form.get('admin_code', '') != ADMIN_SIGNUP_CODE):
            flash("Incorrect Admin Access Code.", "error")
            return render_template('register.html')

        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists — please log in instead.", "error")
            return render_template('register.html')

        db.session.add(User(username=username, email=email,
                            password=generate_password_hash(password), role=role))
        db.session.commit()
        flash(f"{'Admin' if role == 'admin' else 'User'} account created successfully. Please log in.", "success")
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        role = request.form.get('role', 'user')

        user = User.query.filter_by(email=email, role=role).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            return redirect(url_for('admin_dashboard' if user.role == 'admin' else 'user_dashboard'))

        flash("Invalid email, password, or role selection.", "error")
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash("You've been logged out.", "success")
    return redirect(url_for('welcome'))


# --- User Routes ---

@app.route('/user_dashboard')
@login_required(role='user')
def user_dashboard():
    """User > View Applications (from various categories)."""
    apps = Application.query.order_by(Application.name).all()
    categories = sorted({a.category for a in apps if a.category})
    return render_template('user_dashboard.html', apps=apps, categories=categories)


@app.route('/app/<int:app_id>', methods=['GET', 'POST'])
@login_required(role='user')
def app_detail(app_id):
    """User > View Selected Application Details, and Comment on Application."""
    application = Application.query.get_or_404(app_id)
    if request.method == 'POST':
        comment = request.form.get('review', '').strip()
        if comment:
            label, score = analyze_sentiment(comment)
            db.session.add(Review(app_id=application.id, user_id=session['user_id'], review_text=comment,
                                  sentiment=label, sentiment_score=score, ip_address=get_client_ip()))
            db.session.commit()
            flash("Comment posted and analysed.", "success")
        return redirect(url_for('app_detail', app_id=application.id))
    reviews = Review.query.filter_by(app_id=application.id).order_by(Review.created_at.desc()).all()
    return render_template('app_detail.html', app=application, reviews=reviews, stats=application.stats())


@app.route('/write_feedback', methods=['GET', 'POST'])
@login_required(role='user')
def write_feedback():
    if request.method == 'POST':
        message = request.form.get('message', '').strip()
        if message:
            db.session.add(Feedback(user_id=session['user_id'], message=message, is_read=False))
            db.session.commit()
            flash("Thanks for your feedback — the admin has been notified.", "success")
        return redirect(url_for('write_feedback'))
    return render_template('write_feedback.html')


# --- Admin Routes ---

@app.route('/admin_dashboard')
@login_required(role='admin')
def admin_dashboard():
    """Admin > Review Monitoring (Opinion Mining): every comment with sentiment + ranking of apps."""
    reviews = Review.query.order_by(Review.created_at.desc()).all()
    ranking = sorted((a for a in Application.query.all() if a.reviews),
                     key=lambda a: a.stats()['avg_score'], reverse=True)
    return render_template('admin_dashboard.html', reviews=reviews, ranking=ranking,
                           ip_threshold=IP_DUPLICATE_THRESHOLD, engine=sentiment_engine_name())


@app.route('/admin/apps', methods=['GET', 'POST'])
@login_required(role='admin')
def admin_apps():
    """Admin > Add New Application."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash("App name is required.", "error")
            return redirect(url_for('admin_apps'))
        db.session.add(Application(
            name=name,
            link=request.form.get('link', '').strip(),
            description=request.form.get('description', '').strip(),
            category=request.form.get('category', '').strip(),
            image_url=request.form.get('image_url', '').strip(),
            rating=parse_rating(request.form.get('rating'))))
        db.session.commit()
        flash(f'"{name}" added.', "success")
        return redirect(url_for('admin_apps'))
    apps = Application.query.order_by(Application.name).all()
    return render_template('admin_apps.html', apps=apps)


@app.route('/admin/apps/delete/<int:app_id>')
@login_required(role='admin')
def delete_app(app_id):
    application = Application.query.get_or_404(app_id)
    name = application.name
    db.session.delete(application)
    db.session.commit()
    flash(f'"{name}" and its comments were removed.', "success")
    return redirect(url_for('admin_apps'))


@app.route('/admin/detect')
@login_required(role='admin')
def admin_detect():
    """Admin > Detect Fraud Applications: overview of every application with its analysis."""
    apps = Application.query.order_by(Application.name).all()
    return render_template('admin_detect.html', apps=apps)


@app.route('/admin/apps/<int:app_id>')
@login_required(role='admin')
def admin_app_detail(app_id):
    """Application details + all its comments + analysis, so the admin can decide Genuine or Fraud."""
    application = Application.query.get_or_404(app_id)
    reviews = Review.query.filter_by(app_id=app_id).order_by(Review.created_at.desc()).all()
    return render_template('admin_app_detail.html', app=application, reviews=reviews,
                           stats=application.stats(), ip_threshold=IP_DUPLICATE_THRESHOLD)


@app.route('/admin/apps/<int:app_id>/verdict', methods=['POST'])
@login_required(role='admin')
def set_verdict(app_id):
    application = Application.query.get_or_404(app_id)
    choice = request.form.get('verdict', '')
    application.verdict = choice if choice in ('Genuine', 'Fraud') else None
    db.session.commit()
    flash(f'"{application.name}" marked as {application.verdict_label}.', "success")
    return redirect(url_for('admin_app_detail', app_id=app_id))


@app.route('/admin/users')
@login_required(role='admin')
def admin_users():
    users = User.query.filter_by(role='user').order_by(User.username).all()
    return render_template('admin_users.html', users=users)


@app.route('/admin/feedback')
@login_required(role='admin')
def admin_feedback():
    items = Feedback.query.order_by(Feedback.created_at.desc()).all()
    new_ids = {f.id for f in items if not f.is_read}
    if new_ids:
        Feedback.query.filter(Feedback.id.in_(new_ids)).update({Feedback.is_read: True}, synchronize_session=False)
        db.session.commit()
    return render_template('admin_feedback.html', items=items, new_ids=new_ids)


@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required(role='admin')
def edit_review(id):
    review = Review.query.get_or_404(id)
    if request.method == 'POST':
        review.review_text = request.form.get('review_text', review.review_text)
        review.sentiment, review.sentiment_score = analyze_sentiment(review.review_text)
        db.session.commit()
        flash("Comment updated and re-analysed.", "success")
        return redirect(url_for('admin_dashboard'))
    return render_template('edit_review.html', review=review)


@app.route('/delete/<int:id>')
@login_required(role='admin')
def delete_review(id):
    review = Review.query.get_or_404(id)
    db.session.delete(review)
    db.session.commit()
    flash("Comment deleted.", "success")
    return redirect(url_for('admin_dashboard'))


# --- Admin seeding from the terminal (alternative to the Register page) ---
@app.cli.command("create-admin")
def create_admin():
    """Create an admin account directly in the database."""
    import getpass
    with app.app_context():
        username = input("Admin username: ").strip()
        email = input("Admin email: ").strip().lower()
        password = getpass.getpass("Admin password: ")
        if not username or not email or not password:
            print("All fields are required. No account created.")
            return
        if User.query.filter_by(email=email).first():
            print("An account with that email already exists.")
            return
        db.session.add(User(username=username, email=email,
                            password=generate_password_hash(password), role='admin'))
        db.session.commit()
        print(f"Admin account created for {email}.")


# --- Database setup / upgrade ---

def ensure_schema():
    """Adds columns introduced in newer versions to tables that already exist, so an older
    fraud_detection.db keeps working without being deleted."""
    inspector = inspect(db.engine)
    wanted = {
        'application': {'rating': 'FLOAT', 'verdict': 'VARCHAR(20)'},
        'review': {'sentiment_score': 'FLOAT'},
        'feedback': {'is_read': 'BOOLEAN DEFAULT 0'},
    }
    with db.engine.begin() as conn:
        for table, columns in wanted.items():
            existing = {c['name'] for c in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in existing:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}'))


def backfill_sentiment():
    """Re-analyses comments saved by older versions (which had only 'Genuine'/'Fraud Suspect')."""
    pending = Review.query.filter(Review.sentiment_score.is_(None)).all()
    for r in pending:
        r.sentiment, r.sentiment_score = analyze_sentiment(r.review_text)
    if pending:
        db.session.commit()


SAMPLE_APPS = [
    # (name, category, description, listed rating). Ratings are demo values for this project.
    ("QuickPay Wallet", "Finance", "A mobile wallet for peer-to-peer payments and bill splitting.", 4.2),
    ("ChatterBox", "Social", "A group messaging app with disappearing messages and voice rooms.", 4.0),
    ("FitTrack Pro", "Health & Fitness", "Step counter, workout logging, and calorie tracking.", 4.4),
    ("CryptoLeap", "Crypto", "A crypto trading app promising high daily returns.", 2.1),
    ("StudyBuddy", "Education", "Flashcards and spaced-repetition study planner for students.", 4.6),
    ("SnapDeal Rewards", "Shopping", "Cashback and rewards app for online shopping.", 3.9),
    ("RideNow", "Travel", "On-demand ride booking with fare estimates.", 4.1),
    ("MoodJournal", "Health & Fitness", "A daily mood and habit tracking journal.", 4.3),
    ("WhatsApp", "Social", "Cross-platform messaging and voice/video calling app.", 4.3),
    ("Snapchat", "Social", "Photo and video messaging app known for disappearing content.", 4.0),
    ("Facebook", "Social", "Social networking platform for posts, groups, and marketplace.", 3.9),
    ("Twitter (X)", "Social", "Short-form public posting and real-time discussion platform.", 3.7),
    ("Bitcoin Wallet", "Crypto", "A wallet app for storing, sending, and receiving Bitcoin.", 3.8),
    ("Binance", "Crypto", "Cryptocurrency exchange app for trading a wide range of coins.", 4.1),
    ("Coinbase", "Crypto", "Platform for buying, selling, and storing cryptocurrency.", 3.9),
    ("PUBG Mobile", "Gaming", "Battle royale mobile game with squad-based matches.", 4.0),
    ("Free Fire", "Gaming", "Fast-paced battle royale mobile game.", 4.1),
    ("Ludo King", "Gaming", "Multiplayer mobile adaptation of the classic board game Ludo.", 4.2),
]


def seed_sample_apps():
    """Adds any sample app that is missing (by name) and fills in a missing rating.
    Never removes or duplicates anything."""
    existing = {a.name: a for a in Application.query.all()}
    changed = False
    for name, category, description, rating in SAMPLE_APPS:
        if name not in existing:
            db.session.add(Application(name=name, category=category, description=description,
                                       link="https://example.com/" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"),
                                       rating=rating))
            changed = True
        elif existing[name].rating is None:
            existing[name].rating = rating
            changed = True
    if changed:
        db.session.commit()


def init_db():
    db.create_all()
    ensure_schema()
    backfill_sentiment()
    seed_sample_apps()


if __name__ == '__main__':
    with app.app_context():
        init_db()
        print("Sentiment engine:", sentiment_engine_name())
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")
