from datetime import datetime
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-secret-key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///telesupport.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="customer")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tickets = db.relationship("Ticket", foreign_keys="Ticket.customer_id", backref="customer")
    assigned_tickets = db.relationship("Ticket", foreign_keys="Ticket.assigned_to_id", backref="assigned_to")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    priority = db.Column(db.String(20), nullable=False, default="Medium")
    status = db.Column(db.String(30), nullable=False, default="Open")
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(160), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    client_name = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="Planned")
    priority = db.Column(db.String(20), nullable=False, default="Medium")
    start_date = db.Column(db.Date)
    deadline = db.Column(db.Date)
    description = db.Column(db.Text, nullable=False)
    manager_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    manager = db.relationship("User", backref="managed_projects")


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return User.query.get(user_id)


@app.context_processor
def inject_current_user():
    return {"current_user": current_user()}


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not current_user():
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            user = current_user()
            if not user or user.role not in roles:
                flash("You do not have permission to access that page.", "danger")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)

        return wrapped_view

    return decorator


@app.route("/")
def index():
    if current_user():
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "danger")
            return redirect(url_for("register"))

        user = User(name=name, email=email, role="customer")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Account created. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            session["user_id"] = user.id
            flash(f"Welcome back, {user.name}.", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()

    if user.role == "customer":
        tickets = Ticket.query.filter_by(customer_id=user.id).order_by(Ticket.created_at.desc()).all()
    elif user.role == "agent":
        tickets = Ticket.query.filter_by(assigned_to_id=user.id).order_by(Ticket.created_at.desc()).all()
    else:
        tickets = Ticket.query.order_by(Ticket.created_at.desc()).all()

    stats = {
        "total": len(tickets),
        "open": sum(1 for ticket in tickets if ticket.status == "Open"),
        "progress": sum(1 for ticket in tickets if ticket.status == "In Progress"),
        "closed": sum(1 for ticket in tickets if ticket.status == "Closed"),
    }

    projects = []
    if user.role in ["admin", "project_manager"]:
        projects = Project.query.order_by(Project.created_at.desc()).all()

    return render_template("dashboard.html", tickets=tickets, stats=stats, projects=projects)


@app.route("/projects/new", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def create_project():
    if request.method == "POST":
        start_date = request.form.get("start_date") or None
        deadline = request.form.get("deadline") or None
        project = Project(
            name=request.form["name"].strip(),
            client_name=request.form["client_name"].strip(),
            status=request.form["status"],
            priority=request.form["priority"],
            start_date=datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None,
            deadline=datetime.strptime(deadline, "%Y-%m-%d").date() if deadline else None,
            description=request.form["description"].strip(),
            manager_id=current_user().id,
        )
        db.session.add(project)
        db.session.commit()
        flash("Project created successfully.", "success")
        return redirect(url_for("dashboard"))

    return render_template("project_form.html")


@app.route("/tickets/new", methods=["GET", "POST"])
@login_required
def create_ticket():
    user = current_user()
    if request.method == "POST":
        ticket = Ticket(
            title=request.form["title"].strip(),
            category=request.form["category"],
            priority=request.form["priority"],
            description=request.form["description"].strip(),
            location=request.form["location"].strip(),
            customer_id=user.id,
        )
        db.session.add(ticket)
        db.session.commit()
        flash("Support ticket created successfully.", "success")
        return redirect(url_for("dashboard"))

    return render_template("ticket_form.html")


@app.route("/tickets/<int:ticket_id>")
@login_required
def ticket_detail(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    user = current_user()
    if user.role == "customer" and ticket.customer_id != user.id:
        flash("You can view only your own tickets.", "danger")
        return redirect(url_for("dashboard"))
    if user.role == "agent" and ticket.assigned_to_id != user.id:
        flash("This ticket is not assigned to you.", "danger")
        return redirect(url_for("dashboard"))
    agents = User.query.filter(User.role.in_(["agent", "technician"])).order_by(User.name).all()
    return render_template("ticket_detail.html", ticket=ticket, agents=agents)


@app.route("/tickets/<int:ticket_id>/update", methods=["POST"])
@login_required
@roles_required("admin", "agent", "technician")
def update_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    user = current_user()

    if user.role in ["agent", "technician"] and ticket.assigned_to_id != user.id:
        flash("You can update only assigned tickets.", "danger")
        return redirect(url_for("dashboard"))

    ticket.status = request.form["status"]
    ticket.priority = request.form["priority"]

    assigned_to_id = request.form.get("assigned_to_id")
    if user.role == "admin" and assigned_to_id:
        ticket.assigned_to_id = int(assigned_to_id)

    db.session.commit()
    flash("Ticket updated.", "success")
    return redirect(url_for("ticket_detail", ticket_id=ticket.id))


@app.route("/admin/users")
@login_required
@roles_required("admin")
def users():
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template("users.html", users=all_users)


def seed_data():
    users = [
        ("Admin User", "admin@telesupport.com", "admin123", "admin"),
        ("Project Manager", "manager@telesupport.com", "manager123", "project_manager"),
        ("Support Agent", "agent@telesupport.com", "agent123", "agent"),
        ("Field Technician", "tech@telesupport.com", "tech123", "technician"),
        ("Demo Customer", "customer@telesupport.com", "customer123", "customer"),
    ]
    created_users = {}
    for name, email, password, role in users:
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(name=name, email=email, role=role)
            user.set_password(password)
            db.session.add(user)
        created_users[role] = user

    db.session.flush()
    if Ticket.query.first():
        db.session.commit()
        return

    db.session.add(
        Ticket(
            title="Broadband connection down",
            category="Internet",
            priority="High",
            status="In Progress",
            description="Internet service has been unavailable since morning.",
            location="Sector 12, Customer Premises",
            customer_id=created_users["customer"].id,
            assigned_to_id=created_users["agent"].id,
        )
    )
    db.session.commit()


@app.cli.command("init-db")
def init_db_command():
    db.create_all()
    seed_data()
    print("Database initialized with demo users.")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_data()
    app.run(debug=True)
