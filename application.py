import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # Store user id
    user_id = session.get("user_id")

    # Store user portfolio into a dictionary
    portfolio = db.execute("SELECT * FROM portfolio WHERE user_id=?", user_id)

    # store user's cash into a variable
    cash = db.execute("SELECT cash FROM users WHERE id=?", user_id)
    cash = cash[0]['cash']

    # Store user portfolio into a dictionary
    stock_list = []
    for stock in portfolio:
        stock_list.append(stock['comp_symbol'])

    # if stock list was not empty
    if len(stock_list) > 0:
        # for each symbol in user's portfolio
        for symbol in stock_list:
            # get company information
            company = lookup(symbol)
            # update shares prices
            db.execute("UPDATE portfolio SET price=? WHERE user_id=? AND comp_symbol=?",
                        company['price'], user_id, company['symbol'])

    # Store user shares and shares' prices into a dictionary
    user_property = db.execute("SELECT price, shares FROM portfolio WHERE user_id=?", user_id)

    # Calculate the value of user shares
    stock_values = 0
    for item in user_property:
        stock_values += (item['price'] * item['shares'])

    # Calculate user's total property
    total_property = stock_values + cash

    return render_template("index.html", portfolio=portfolio, cash=cash, total_property=total_property)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Store user inputes into variables
        shares = request.form.get('shares')
        symbol = request.form.get('symbol')

        # store user id
        user_id = session.get("user_id")

        # Ensure the symbol was submitted
        if not symbol:
            return apology("must provide symbol", 403)

        if not shares:
            return apology("must provide number of shares you want to buy")

        # Ensure shares is digit
        if not shares.isdigit():
            return apology("You cannot purchase partial shares.", 400)

        # store the result of lookup funtion in a dictionary
        company = lookup(symbol)

        # Ensure the symbol exists
        if company == None:
            return apology("Symbol does not exists.", 400)

        # Render an apology if the input is not a positive integer.
        shares = int(shares)
        if shares < 1:
            return apology("You have to provide a positive integer", 400)

        # Calculate transaction total price
        total = shares * company['price']

        # Get user cash from database
        cash = db.execute("SELECT cash FROM users WHERE id=?", user_id)
        cash = cash[0]['cash']

        # Calculate new cash
        new_cash = cash - total

        # Ensure user have enough money to buy share
        if new_cash >= 0:
            # Update user cash
            db.execute("UPDATE users SET cash=? WHERE id=?", new_cash, user_id)

            # Get date and time
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Insert buy info into transactions database
            db.execute("INSERT INTO transactions (user_id, comp_symbol, comp_name, shares, price, time, action) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        user_id, company['symbol'], company['name'], shares, company['price'], now, "buy")

            # Get user portfolio
            user_stocks = db.execute("SELECT comp_symbol FROM portfolio WHERE user_id=?", user_id)
            # append user's portfolio shares symbol into a list
            portfolio_symbols = []
            for stock in user_stocks:
                portfolio_symbols.append(stock['comp_symbol'])

            # if user not owed shares of the company insert number of shares into user portfolio
            if company['symbol'] not in portfolio_symbols:
                db.execute("INSERT INTO portfolio (user_id, comp_symbol, comp_name, shares, price) VALUES (?, ?, ?, ?, ?)",
                            user_id, company['symbol'], company['name'], shares, company['price'])
            # else user owed shares of the company update number of shares
            else:
                old_shares = db.execute("SELECT shares FROM portfolio WHERE user_id=? AND comp_symbol=?",
                                        user_id, company['symbol'])

                new_shares = old_shares[0]['shares'] + shares
                db.execute("UPDATE portfolio SET shares=? WHERE user_id=? AND comp_symbol=?",
                            new_shares, user_id, company['symbol'])
                db.execute("UPDATE portfolio SET price=? WHERE user_id=? AND comp_symbol=?",
                            company['price'], user_id, company['symbol'])

        # Render an apology if user don't have enough cash
        else:
            return apology("Sorry you cannot afford the number of shares at the current price.")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template('buy.html')

    return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Store user id
    user_id = session.get("user_id")

    # Store user transactions into a dictionary
    portfolio = db.execute("SELECT * FROM transactions WHERE user_id=?", user_id)

    # Display user transactions
    return render_template("history.html", portfolio=portfolio)


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

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


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # store the symbol in a variable
        symbol = request.form.get("symbol")

        # Ensure username was submitted
        if not symbol:
            return apology("must provide symbol", 400)

        else:
            # store the result of lookup funtion in a temp dictionary
            company = lookup(symbol)

            # Ensure the symbol exists
            if company == None:
                return apology("Symbol does not exists.", 400)

            # if symbol exists show symbol price
            return render_template("quoted.html", company=company)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")

    return apology("TODO")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # store user input in variables
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # registered = False

        # Ensure username was submitted
        if not username:
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not password:
            return apology("must provide password", 400)

        # Ensure password confirmation was submitted
        elif not confirmation:
            return apology("must provide confirmation", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        if len(rows) != 0:
            return apology("username is taken", 400)
        elif password != confirmation:
            return apology("password and confirmation must match", 400)
        else:
            password_hash = generate_password_hash(password)
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, password_hash)
            # registered = True

        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # Store user id
    user_id = session.get("user_id")

    # Get user portfolio
    user_stocks = db.execute("SELECT comp_symbol FROM portfolio WHERE user_id=?", user_id)

    # append user's portfolio shares symbol into a list
    portfolio_symbols = []
    for stock in user_stocks:
        portfolio_symbols.append(stock['comp_symbol'])

    if request.method == "POST":
        symbol = request.form.get("symbol")
        sell_shares = request.form.get("shares")

        if not symbol:
            return apology("you have to provide symbol", 404)
        elif symbol not in portfolio_symbols:
            return apology("you don't have any shares of this symbol", 404)

        if not sell_shares:
            return apology("you have to provide number of shares you want to sell", 404)

        sell_shares = int(sell_shares)
        if sell_shares < 1:
            return apology("You have to provide a positive integer", 403)

        selected_symbol = db.execute("SELECT shares from portfolio WHERE user_id=? AND comp_symbol=?", user_id, symbol)

        if selected_symbol[0]['shares'] < sell_shares:
            return apology("you don't own that many shares of the stock", 400)
        else:
            # Calculate new value of company shares that user have
            shares_new_value = selected_symbol[0]['shares'] - sell_shares

            # Store company information into a dictionary
            company = lookup(symbol)

            # Request for date and time
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Calculate total price
            total = company['price'] * sell_shares

            # Get user old cash
            old_cash = db.execute("SELECT cash FROM users WHERE id=?", user_id)
            old_cash = old_cash[0]['cash']

            # Calculate new cash
            new_cash = old_cash + total

            # Update user cash
            db.execute("UPDATE users SET cash=? WHERE id=?", new_cash, user_id)

            # Update portfolio table
            db.execute("UPDATE portfolio SET shares=? WHERE user_id=? AND comp_symbol=?",
                        shares_new_value, user_id, company['symbol'])
            db.execute("UPDATE portfolio SET price=? WHERE user_id=? AND comp_symbol=?",
                        company['price'], user_id, company['symbol'])

            # Insert action into transactions table
            db.execute("INSERT INTO transactions (user_id, comp_symbol, comp_name, shares, price, time, action) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        user_id, company['symbol'], company['name'], sell_shares, company['price'], now, "sell")
    else:
        return render_template("sell.html", portfolio_symbols=portfolio_symbols)

    return redirect('/')
    # return apology("TODO")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
