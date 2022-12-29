import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?",
                          request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # return apology("TODO")
    if request.method == "POST":
        print("post")
        username = request.form.get("username")
        password = request.form.get("password")
        password_confirmation = request.form.get("confirmation")
        # Ensure username was submitted
        if not username:
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not password:
            return apology("must provide password", 403)

        elif not password_confirmation:
            return apology(" password confirmation is required", 403)

        if password != password_confirmation:
            return apology("passwrods do not match!")

        # generate password hash:
        hash = generate_password_hash(password=password)

        # Insert username and hash to Database:

        try:
            user = db.execute(
                "INSERT INTO users(username, hash) VALUES(?, ?)", username, hash)
            print(user)
        except:  # if username already taken return apology:
            return apology("username has already been taken", 403)

        # Remember which user has logged in

        session["user_id"] = user

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)

    else:
        return render_template("register.html")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_id = session['user_id']
    user = db.execute("SELECT * FROM users WHERE id = ?", user_id)[0]
    stocks = db.execute(
        "SELECT symbol, name, price, SUM(shares) as total_shares FROM transactions WHERE user_id= ? GROUP BY symbol", user_id)

    cash = db.execute("SELECT cash from users WHERE id = ?", user_id)[
        0]['cash']

    total = cash
    for stock in stocks:
        total += stock['price'] * stock['total_shares']
    return render_template("index.html", user=user,  stocks=stocks, cash=cash, usd=usd, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # return apology("TODO")
    if request.method == "POST":
        symbol = request.form.get('symbol')
        shares = request.form.get('shares')
        item = lookup(symbol=symbol)

        if not symbol:
            return apology("Enter a symbol")
        elif not item:
            return apology("Invalid symbol")

        try:
            shares = int(shares)
        except:
            return apology("shares most be an Integer")

        if shares <= 0:
            return apology("shares must be a positive Integer")

        user_id = session["user_id"]
        cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[
            0]['cash']
        item_name = item["name"]
        item_price = item["price"]
        total_price = int(item_price) * int(shares)
        if cash < total_price:
            return apology("credit is not enough")
        else:
            db.execute("UPDATE users SET cash = ? WHERE id = ?",
                       cash - total_price, user_id)
            db.execute("INSERT INTO transactions (user_id, name, shares, price, type, symbol) VALUES (?, ?, ?, ?, ?, ?)",
                       user_id, item_name, shares, item_price, 'buy', symbol)
        print(f'\n\n{cash}\n\n')
        return redirect('/')
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    user_id= session["user_id"]
    transactions = db.execute("SELECT type, symbol, price, shares, time FROM transactions WHERE user_id = ? ", user_id)
    user = db.execute("SELECT * FROM users WHERE id = ?", user_id)[0]
    return render_template("history.html", transactions=transactions, user=user,usd=usd)


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    # return apology("TODO")
    if request.method == "POST":
        symbol = request.form.get('symbol')
        if not symbol:
            return apology("please provide a simple")
        result = lookup(symbol=symbol)
        return render_template("quoted.html", name=result['name'], price=usd(result['price']), symbol=result['symbol'])
    else:
        return render_template('quote.html')


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":
        user_id = session['user_id']
        symbol = request.form.get('symbol')
        shares = int(request.form.get("shares"))
        if shares <= 0:
            return apology("shares must be a positive number")

        item_price = int(lookup(symbol=symbol)["price"])
        item_name = lookup(symbol=symbol)["name"]
        price = shares * item_price

        shares_owned = db.execute(
            "SELECT SUM(shares) as total_shares from transactions WHERE user_id = ? and symbol = ?", user_id, symbol)[0]["total_shares"]

        if int(shares_owned) < shares:
            return apology(" you have no shares get your shit togagher")

        current_cash = db.execute(
            "SELECT cash FROM users WHERE id = ?", user_id)[0]['cash']
        db.execute("UPDATE users SET cash = ? WHERE id = ?",
                   current_cash + price, user_id)
        db.execute("INSERT INTO transactions (user_id, name, shares, price, type, symbol) VALUES(?, ?, ?, ?, ?, ?)",
                   user_id, item_name, -shares, item_price, "sell", symbol)

        return redirect("/")

    else:
        user_id = session['user_id']
        symbols = db.execute(
            "SELECT symbol FROM transactions WHERE user_id = ? GROUP BY symbol", user_id)
        return render_template("sell.html", symbols=symbols)
