from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
from sqlalchemy import func
import json

app = Flask(__name__)
app.secret_key = "secret123"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expenses.db'
db = SQLAlchemy(app)

# ---------------- Models ----------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    mobile = db.Column(db.String(15), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    job = db.Column(db.String(100))
    daily_earning = db.Column(db.Float)
    photo = db.Column(db.String(200))
    signup_time = db.Column(db.DateTime, default=datetime.utcnow)

class UserData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    total_income = db.Column(db.Float, default=0)
    total_expenses = db.Column(db.Float, default=0)
    monthly_budget = db.Column(db.Float, default=0)
    savings_goal = db.Column(db.Float, default=0)
    suggestion = db.Column(db.String(200), default="")

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    note = db.Column(db.String(200))
    date = db.Column(db.Date, default=date.today)

# ✅ Income Model
class Income(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=datetime.utcnow)
    source = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

# ✅ Updated Repay Model with status
class Repay(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow)
    status = db.Column(db.String(20), default="Unpaid")   # ✅ New field

# ---------------- Routes ----------------
@app.route('/')
def home():
    return redirect(url_for("login"))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        mobile = request.form['mobile']
        password = request.form['password']
        job = request.form['job']
        daily_earning = request.form['daily_earning']

        user = User(
            name=name,
            mobile=mobile,
            password=password,
            job=job,
            daily_earning=daily_earning,
            photo="https://via.placeholder.com/100"
        )
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        mobile = request.form['mobile']
        password = request.form['password']
        user = User.query.filter_by(mobile=mobile, password=password).first()
        if user:
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        else:
            return "Invalid mobile or password"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ✅ UPDATED: Dashboard now includes all-time lists while keeping all previous logic
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])

    # ✅ Ensure UserData exists
    user_data = UserData.query.filter_by(user_id=session['user_id']).first()
    if not user_data:
        user_data = UserData(user_id=session['user_id'])
        db.session.add(user_data)
        db.session.commit()

    # ✅ Calculate totals
    total_income = db.session.query(func.sum(Income.amount)).filter_by(user_id=user.id).scalar() or 0
    total_expenses = db.session.query(func.sum(Expense.amount)).filter_by(user_id=user.id).scalar() or 0
    balance = total_income - total_expenses

    # ✅ Budget & savings defaults
    monthly_budget = user_data.monthly_budget or 50000
    savings_goal = user_data.savings_goal or 200000

    # ✅ Suggestion logic
    suggestion = user_data.suggestion
    if not suggestion:
        suggestion = "Good job! You're saving well." if balance > (0.2 * total_income) else "Try to cut down expenses."

    today = date.today()

    # ✅ Today’s income list
    today_income = Income.query.filter_by(user_id=user.id, date=today).all()

    # ✅ Today’s expenses list
    expenses_today = Expense.query.filter(
        Expense.user_id == user.id,
        func.date(Expense.date) == today
    ).all()

    # ✅ History of incomes
    history = Income.query.filter(
        Income.user_id == user.id,
        Income.date < today
    ).order_by(Income.date.desc()).all()

    # ✅ Repayments list
    repayments = Repay.query.filter_by(user_id=user.id).all()

    # ✅ Payments list
    payments = Payment.query.filter_by(user_id=user.id).all()

    # ✅ NEW: All-time income & expenses lists for dashboard
    alltime_income = Income.query.filter_by(user_id=user.id).all()
    expenses_alltime = Expense.query.filter_by(user_id=user.id).all()

    return render_template(
        "dashboard.html",
        user=user,
        user_data=user_data,
        total_income=total_income,
        total_expenses=total_expenses,
        expenses_today=expenses_today,
        balance=balance,
        monthly_budget=monthly_budget,
        savings_goal=savings_goal,
        suggestion=suggestion,
        today_income=today_income,
        history=history,
        repayments=repayments,
        payments=payments,                # ✅ available in template
        alltime_income=alltime_income,    # ✅ new
        expenses_alltime=expenses_alltime,# ✅ new
        now=datetime.now()
    )

@app.route('/income', methods=['GET', 'POST'])
def income_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    today = date.today()

    if request.method == 'POST':
        source = request.form['source']
        amount = float(request.form['amount'])
        income_date = request.form.get('date')
        if income_date:
            income_date = datetime.strptime(income_date, "%Y-%m-%d").date()
        else:
            income_date = today

        new_income = Income(
            user_id=session['user_id'],
            source=source,
            amount=amount,
            date=income_date
        )
        db.session.add(new_income)
        db.session.commit()
        return redirect(url_for('income_page'))

    today_income = Income.query.filter_by(
        user_id=session['user_id'], date=today
    ).all()

    history = Income.query.filter(
        Income.user_id == session['user_id'],
        Income.date < today
    ).order_by(Income.date.desc()).all()

    return render_template(
        "income.html",
        today_income=today_income,
        history=history,
        now=today
    )

@app.route('/edit_income/<int:income_id>', methods=['GET', 'POST'])
def edit_income(income_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    income = Income.query.get_or_404(income_id)

    if income.user_id != session['user_id']:
        return "Unauthorized", 403

    if request.method == 'POST':
        income.source = request.form['source']
        income.amount = float(request.form['amount'])
        income.date = datetime.strptime(request.form['date'], "%Y-%m-%d").date()
        db.session.commit()
        return redirect(url_for('income_page'))

    return render_template("edit_income.html", income=income)

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        user.name = request.form['name']
        user.job = request.form['job']
        user.daily_earning = request.form['daily_earning']
        db.session.commit()
        return redirect(url_for('dashboard'))

    return render_template('edit_profile.html', user=user)

@app.route('/update/<field>', methods=['GET', 'POST'])
def update_field(field):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_data = UserData.query.filter_by(user_id=session['user_id']).first()
    if not user_data:
        user_data = UserData(user_id=session['user_id'])
        db.session.add(user_data)
        db.session.commit()

    if request.method == 'POST':
        value = request.form['value']
        if field == "income":
            user_data.total_income = float(value)
        elif field == "expenses":
            user_data.total_expenses = float(value)
        elif field == "budget":
            user_data.monthly_budget = float(value)
        elif field == "savings":
            user_data.savings_goal = float(value)
        elif field == "suggestion":
            user_data.suggestion = value
        db.session.commit()
        return redirect(url_for('dashboard'))

    return render_template("update_field.html", field=field, user_data=user_data)

# ✅ Monthly Income Route
@app.route('/monthly_income')
def monthly_income():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    today = date.today()
    start_date = today - timedelta(days=30)

    incomes = Income.query.filter(
        Income.user_id == user_id,
        Income.date >= start_date,
        Income.date <= today
    ).order_by(Income.date).all()

    chart_data = [
        {"date": inc.date.strftime("%Y-%m-%d"), "amount": inc.amount}
        for inc in incomes
    ]

    return render_template(
        "monthly_income.html",
        incomes=incomes,
        chart_data=json.dumps(chart_data)
    )

# ✅ Savings Route
@app.route('/savings', methods=['GET', 'POST'])
def savings_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    if request.method == 'POST':
        name = request.form['name']
        amount = float(request.form['amount'])
        repay_date = request.form.get('date')

        if repay_date:
            repay_date = datetime.strptime(repay_date, "%Y-%m-%d").date()
        else:
            repay_date = date.today()

        new_repay = Repay(
            user_id=user_id,
            name=name,
            amount=amount,
            date=repay_date,
            status="Unpaid"
        )
        db.session.add(new_repay)
        db.session.commit()
        return redirect(url_for('savings_page'))

    repayments = Repay.query.filter_by(user_id=user_id).order_by(Repay.date.desc()).all()

    return render_template("savings.html", repayments=repayments)

# ✅ Edit Repay Route
@app.route('/edit_repay/<int:repay_id>', methods=['GET', 'POST'])
def edit_repay(repay_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    repay = Repay.query.get_or_404(repay_id)
    if repay.user_id != session['user_id']:
        return "Unauthorized", 403

    if request.method == 'POST':
        repay.name = request.form['name']
        repay.amount = float(request.form['amount'])
        repay.date = datetime.strptime(request.form['date'], "%Y-%m-%d").date()
        repay.status = request.form['status']
        db.session.commit()
        return redirect(url_for('savings_page'))

    return render_template("edit_repay.html", repay=repay)

# ✅ Delete Repay Route
@app.route('/delete_repay/<int:repay_id>', methods=['POST'])
def delete_repay(repay_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    repay = Repay.query.get_or_404(repay_id)
    if repay.user_id != session['user_id']:
        return "Unauthorized", 403

    db.session.delete(repay)
    db.session.commit()
    return redirect(url_for('savings_page'))

# ✅ Today’s Income & Expenses (Add + View)
@app.route("/expenses_today", methods=["GET", "POST"])
def expenses_today():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    today = date.today()

    # Handle form submission (Add new expense)
    if request.method == "POST":
        amount = request.form.get("amount")
        source = request.form.get("source")
        note = request.form.get("note")
        if amount and source:
            expense = Expense(
                user_id=user_id,
                amount=float(amount),
                category=source,   # using 'category' as 'source'
                note=note,
                date=today
            )
            db.session.add(expense)
            db.session.commit()
            flash("Expense added!", "success")
        return redirect(url_for("expenses_today"))

    # Get only today’s expenses
    expenses_today_list = Expense.query.filter(
        Expense.user_id == user_id,
        func.date(Expense.date) == today
    ).all()

    return render_template("expenses_today.html", expenses=expenses_today_list, today=today)

# ✅ Edit Expense
@app.route("/edit_expense/<int:expense_id>", methods=["GET", "POST"])
def edit_expense(expense_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    expense = Expense.query.get_or_404(expense_id)
    if expense.user_id != session["user_id"]:
        return "Unauthorized", 403

    if request.method == "POST":
        expense.amount = float(request.form["amount"])
        expense.category = request.form["category"]
        db.session.commit()
        flash("Expense updated!", "success")
        return redirect(url_for("expenses_today"))

    return render_template("edit_expense.html", expense=expense)

@app.route("/balance_today")
def balance_today():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    today = date.today()

    # Get today's incomes & expenses
    today_income = Income.query.filter(
        Income.user_id == user.id,
        func.date(Income.date) == today
    ).all()

    today_expenses = Expense.query.filter(
        Expense.user_id == user.id,
        func.date(Expense.date) == today
    ).all()

    # Calculate sums
    income_sum = sum(i.amount for i in today_income)
    expense_sum = sum(e.amount for e in today_expenses)
    balance = income_sum - expense_sum

    return render_template(
        "balance_today.html",
        today_income=today_income,
        today_expenses=today_expenses,
        income_sum=income_sum,
        expense_sum=expense_sum,
        balance=balance,
        today=today
    )

@app.route("/delete_income/<int:id>")
def delete_income(id):
    income = Income.query.get_or_404(id)
    db.session.delete(income)
    db.session.commit()
    return redirect(url_for("monthly_income"))

@app.route("/delete_expense/<int:id>")
def delete_expense(id):
    expense = Expense.query.get_or_404(id)
    db.session.delete(expense)
    db.session.commit()
    return redirect(url_for("monthly_expenses"))  # or wherever you want to go back

@app.route('/monthly_expenses')
def monthly_expenses():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    today = date.today()
    start_date = today - timedelta(days=30)

    # Raw records for table (last 30 days)
    expenses = (Expense.query
                .filter(Expense.user_id == user_id,
                        Expense.date >= start_date,
                        Expense.date <= today)
                .order_by(Expense.date.desc())
                .all())

    # Aggregate per day for the chart
    daily_totals = {}
    for e in expenses:
        k = e.date  # already a date
        daily_totals[k] = daily_totals.get(k, 0) + (e.amount or 0)

    # Build chart data sorted by date
    chart_data = [
        {"date": d.strftime("%Y-%m-%d"), "amount": daily_totals[d]}
        for d in sorted(daily_totals.keys())
    ]

    return render_template(
        "monthly_expenses.html",
        expenses=expenses,
        chart_data=json.dumps(chart_data),
        start_date=start_date,
        end_date=today
    )

@app.route("/last30")
def last30():
    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    # Income (last 30 days)
    incomes = Income.query.filter(Income.date.between(start_date, end_date)).all()
    income_sum = sum(i.amount for i in incomes)

    # Expenses (last 30 days)
    expenses = Expense.query.filter(Expense.date.between(start_date, end_date)).all()
    expense_sum = sum(e.amount for e in expenses)

    # Balance
    balance = income_sum - expense_sum

    return render_template(
        "last30.html",
        today=end_date,
        start_date=start_date,
        end_date=end_date,
        incomes=incomes,
        expenses=expenses,
        income_sum=income_sum,
        expense_sum=expense_sum,
        balance=balance
    )

# ---------------- Payment Model ----------------
class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    name = db.Column(db.String(150), nullable=False)        # who/what
    purpose = db.Column(db.String(250))                     # purpose/notes
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, default=date.today)
    status = db.Column(db.String(20), default="Unpaid")     # Paid / Unpaid

# ---------------- Payments Routes ----------------
@app.route('/payments', methods=['GET', 'POST'])
def payments_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    if request.method == 'POST':
        name = request.form.get('name')
        purpose = request.form.get('purpose')
        amount = request.form.get('amount')
        date_str = request.form.get('date')
        status = request.form.get('status') or "Unpaid"

        if not name or not amount:
            flash("Name and amount are required", "danger")
            return redirect(url_for('payments_page'))

        try:
            amt = float(amount)
        except ValueError:
            flash("Invalid amount", "danger")
            return redirect(url_for('payments_page'))

        pay_date = None
        if date_str:
            try:
                pay_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                pay_date = date.today()
        else:
            pay_date = date.today()

        p = Payment(
            user_id=user_id,
            name=name,
            purpose=purpose,
            amount=amt,
            date=pay_date,
            status=status
        )
        db.session.add(p)
        db.session.commit()
        flash("Payment added!", "success")
        return redirect(url_for('payments_page'))

    payments = Payment.query.filter_by(user_id=user_id).order_by(Payment.date.desc()).all()
    return render_template('payments.html', payments=payments)

@app.route('/edit_payment/<int:pay_id>', methods=['GET', 'POST'])
def edit_payment(pay_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    payment = Payment.query.get_or_404(pay_id)
    if payment.user_id != session['user_id']:
        return "Unauthorized", 403

    if request.method == 'POST':
        payment.name = request.form.get('name')
        payment.purpose = request.form.get('purpose')
        try:
            payment.amount = float(request.form.get('amount'))
        except (TypeError, ValueError):
            flash("Invalid amount", "danger")
            return redirect(url_for('edit_payment', pay_id=pay_id))

        date_str = request.form.get('date')
        if date_str:
            try:
                payment.date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                payment.date = date.today()

        payment.status = request.form.get('status') or payment.status
        db.session.commit()
        flash("Payment updated!", "success")
        return redirect(url_for('payments_page'))

    return render_template('edit_payment.html', payment=payment)

@app.route('/delete_payment/<int:pay_id>', methods=['POST'])
def delete_payment(pay_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    payment = Payment.query.get_or_404(pay_id)
    if payment.user_id != session['user_id']:
        return "Unauthorized", 403

    db.session.delete(payment)
    db.session.commit()
    flash("Payment deleted.", "success")
    return redirect(url_for('payments_page'))

@app.route('/all_time')
def all_time():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    # Fetch all incomes and expenses
    all_income = Income.query.filter_by(user_id=user_id).order_by(Income.date.asc()).all()
    all_expenses = Expense.query.filter_by(user_id=user_id).order_by(Expense.date.asc()).all()

    # Prepare data for charts
    income_data = [{"date": inc.date.strftime("%Y-%m-%d"), "amount": inc.amount} for inc in all_income]
    expense_data = [{"date": exp.date.strftime("%Y-%m-%d"), "amount": exp.amount} for exp in all_expenses]

    return render_template(
        "all_time.html",
        all_income=all_income,
        all_expenses=all_expenses,
        income_data=income_data,
        expense_data=expense_data
    )

@app.route('/track')
def track_page():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("track.html")

@app.route('/monthly_tracker')
def monthly_tracker():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    # Fetch all expenses of the user
    expenses = Expense.query.filter_by(user_id=user_id).order_by(Expense.date.desc()).all()

    # Organize by category → month-year → total
    tracker = {}
    for e in expenses:
        month_year = e.date.strftime("%B %Y")  # e.g., "July 2025"
        category = e.category
        if category not in tracker:
            tracker[category] = {}
        if month_year not in tracker[category]:
            tracker[category][month_year] = 0
        tracker[category][month_year] += e.amount

    return render_template("monthly_tracker.html", tracker=tracker)


# ---------------- Run ----------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
