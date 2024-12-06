# %%


import tkinter as tk
from tkinter import messagebox
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.ticker import FuncFormatter
import wrds


# Global variable declarations
selected_stocks_data = []  # Stores the selected stocks globally
current_allocation = {"Stocks": 0, "Bonds": 0}  # Default allocation
current_value = 0  # Tracks the current portfolio value
goal_value = 100000  # Default goal value


# WRDS connection
db = wrds.Connection()

# Functions for Data Fetching and Visualization
def fetch_data(ticker, start="2020-01-01", end="2024-11-01"):
    data = yf.download(ticker, start=start, end=end)
    return data["Adj Close"]


def fetch_fama_french():
    ff_data = db.get_table('ff', 'factors_daily')
    ff_data['date'] = pd.to_datetime(ff_data['date'], format='%Y%m%d')
    ff_data = ff_data.set_index('date')
    return ff_data[['mktrf', 'smb', 'hml', 'rf']]

def calculate_performance(stock_data, bond_data, ff_data, allocation):
    stock_returns = stock_data.pct_change().dropna()
    bond_returns = bond_data.pct_change().dropna()
    weighted_returns = allocation["Stocks"] * stock_returns.mean() + allocation["Bonds"] * bond_returns.mean()
    avg_rf = ff_data['rf'].mean() / 100
    portfolio_return = weighted_returns - avg_rf
    return portfolio_return

def calculate_monthly_contribution(goal_value, current_value, time_horizon):
    """
    Calculate the monthly contribution needed to reach the goal value within the given time horizon.
    """
    remaining_value = max(goal_value - current_value, 0)
    months = time_horizon * 12
    if months > 0:
        return remaining_value / months
    return 0


def update_goal_based_on_type():
    """
    Update the investment goal based on the selected goal type or manual input.
    The most recent input (dropdown or manual) is always reflected.
    """
    goal_type = goal_type_var.get()
    default_goals = {
        "House": 300000,
        "Retirement": 1000000,
        "Business": 500000,
        "Vacation": 20000,
        "College": 100000,
    }

    # Get the goal value based on the dropdown
    new_goal = default_goals.get(goal_type, 100000)

    # Update the input box and status label with the dropdown selection
    goal_var.set(str(new_goal))
    status_label.config(
        text=f"Updated goal to {goal_type}: ${new_goal:,}",
        fg="blue"
    )


def manual_goal_update(*args):
    """
    Handle manual updates to the goal and ensure they take precedence until the dropdown is changed.
    """
    manual_goal = goal_var.get().strip()

    if manual_goal.isdigit():
        # Update the status label with the manually entered goal
        status_label.config(
            text=f"Custom goal entered: ${int(manual_goal):,}",
            fg="blue"
        )
    elif manual_goal == "":
        # If the field is cleared, fallback to the dropdown selection
        update_goal_based_on_type()
    else:
        # Handle invalid input
        status_label.config(
            text="Invalid input. Please enter a valid numeric goal.",
            fg="red"
        )



# Stock Selection Functions
def open_stock_selection(category, stock_list, selected_var):
    """
    Opens a popup to allow the user to select stocks from the given category.
    """
    popup = tk.Toplevel(root)
    popup.title(f"Select {category} Stocks")
    tk.Label(popup, text=f"Select {category} Stocks:", font=("Arial", 12)).pack(pady=10)

    for stock in stock_list:
        var = tk.BooleanVar()
        checkbox = tk.Checkbutton(popup, text=stock, variable=var)
        checkbox.pack(anchor="w")
        selected_var[stock] = var

    tk.Button(popup, text="Done", command=lambda: [popup.destroy(), update_selected_stocks()]).pack(pady=10)


def get_selected_stocks_from_checkboxes(selected_var):
    """
    Retrieves the list of selected stocks from the checkboxes.
    """
    return [stock for stock, var in selected_var.items() if var.get()]


def get_selected_stocks():
    """
    Combine all manually selected stocks and globally stored recommended stocks.
    """
    global selected_stocks_data  # Declare global variable
    # Fetch stocks from checkboxes
    selected_risky = get_selected_stocks_from_checkboxes(risky_selected)
    selected_medium = get_selected_stocks_from_checkboxes(medium_selected)
    selected_stable = get_selected_stocks_from_checkboxes(stable_selected)
    
    # Combine with global selected_stocks_data
    all_selected = list(set(selected_risky + selected_medium + selected_stable + selected_stocks_data))
    
    # Update global selected stocks
    selected_stocks_data = all_selected

    return all_selected


def update_selected_stocks():
    """
    Updates the displayed list of selected stocks on the dashboard.
    Combines manually selected stocks and globally stored recommended stocks.
    """
    global selected_stocks_data  # Declare global variable
    selected_stocks = get_selected_stocks()  # Fetch all stocks (manual + recommended)
    selected_stocks_label.config(
        text=f"Selected Stocks: {', '.join(selected_stocks) if selected_stocks else 'None'}",
        fg="blue"
    )


# Visualization Functions
def display_pie_chart(frame):
    for widget in frame.winfo_children():
        widget.destroy()
    labels = list(current_allocation.keys())
    sizes = list(current_allocation.values())
    fig, ax = plt.subplots(figsize=(4, 4))
    ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
    ax.set_title("Portfolio Allocation")
    canvas = FigureCanvasTkAgg(fig, frame)
    canvas.get_tk_widget().pack(pady=10)
    add_back_to_dashboard_button(frame)

def display_goal_progress(frame):
    for widget in frame.winfo_children():
        widget.destroy()
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.bar(["Goal", "Current Value"], [goal_value, current_value], color=["green", "blue"])
    ax.set_title("Progress Toward Investment Goal", fontsize=14)
    ax.set_ylabel("Value ($)", fontsize=12)

    for bar, value in zip(ax.patches, [goal_value, current_value]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() / 2,
            f"${int(value):,}",
            ha="center",
            va="center",
            fontsize=12,
            color="white" if value > goal_value * 0.7 else "black"
        )

    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"${int(x):,}"))
    plt.tight_layout()
    canvas = FigureCanvasTkAgg(fig, frame)
    canvas.get_tk_widget().pack(pady=10)
    add_back_to_dashboard_button(frame)



def display_risk_return(frame):
    for widget in frame.winfo_children():
        widget.destroy()

    # Fetch data for all selected stocks
    risk_return_data = []
    for ticker in selected_stocks_data:
        try:
            stock_prices = fetch_data(ticker)
            if stock_prices.empty:
                print(f"Warning: No data available for {ticker}. Skipping.")
                continue
            returns = stock_prices.pct_change().dropna()
            avg_return = returns.mean()
            volatility = returns.std()
            risk_return_data.append((ticker, avg_return, volatility))
        except Exception as e:
            print(f"Error fetching data for {ticker}: {e}")

    if not risk_return_data:
        tk.Label(frame, text="No valid data for selected stocks.", font=("Arial", 12), fg="red").pack(pady=10)
        return

    # Sort data for visualization
    risk_return_data.sort(key=lambda x: x[1], reverse=True)
    tickers = [data[0] for data in risk_return_data]
    returns = [data[1] for data in risk_return_data]
    volatilities = [data[2] for data in risk_return_data]

    # Create horizontal bar chart
    fig, ax = plt.subplots(figsize=(6, 4))
    bar_width = 0.4
    x_positions = range(len(tickers))

    ax.barh(x_positions, returns, height=bar_width, label="Return", color="blue")
    ax.barh(x_positions, volatilities, height=bar_width, label="Volatility (Risk)", color="orange", alpha=0.7)

    ax.set_yticks(x_positions)
    ax.set_yticklabels(tickers)
    ax.set_title("Risk vs Return for Selected Stocks", fontsize=14)
    ax.set_xlabel("Value")

    # Format X-axis to show percentages
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x * 100:.1f}%"))
    ax.legend()
    plt.tight_layout()
    canvas = FigureCanvasTkAgg(fig, frame)
    canvas.get_tk_widget().pack(pady=10)
    add_back_to_dashboard_button(frame)


# Summary Page
def display_summary():
    """
    Updates and displays the summary page with user inputs and calculated results.
    """
    for widget in summary_frame.winfo_children():
        widget.destroy()

    # Title
    tk.Label(summary_frame, text="Summary", font=("Arial", 16)).pack(pady=10)

    # Display User Inputs
    tk.Label(summary_frame, text=f"Goal Type: {goal_type_var.get()}", font=("Arial", 12)).pack(anchor="w", padx=20)
    tk.Label(summary_frame, text=f"Investment Goal: ${goal_var.get()}", font=("Arial", 12)).pack(anchor="w", padx=20)
    tk.Label(summary_frame, text=f"Risk Tolerance: {risk_var.get()}", font=("Arial", 12)).pack(anchor="w", padx=20)
    tk.Label(summary_frame, text=f"Time Horizon: {time_var.get()} years", font=("Arial", 12)).pack(anchor="w", padx=20)
    tk.Label(summary_frame, text=f"Selected Stocks: {', '.join(selected_stocks_data) if selected_stocks_data else 'None'}", font=("Arial", 12)).pack(anchor="w", padx=20)

    # Display Results
    tk.Label(summary_frame, text=f"Current Portfolio Value: ${current_value:,.2f}", font=("Arial", 12)).pack(anchor="w", padx=20)
    tk.Label(summary_frame, text=f"Monthly Contribution Needed: ${calculate_monthly_contribution(goal_value, current_value, int(time_var.get())):,.2f}", font=("Arial", 12)).pack(anchor="w", padx=20)

    # Display Portfolio Allocation
    allocation_text = f"Portfolio Allocation: {current_allocation['Stocks']}% Stocks, {current_allocation['Bonds']}% Bonds"
    tk.Label(summary_frame, text=allocation_text, font=("Arial", 12)).pack(anchor="w", padx=20)

    # Suggested Adjustments (if necessary)
    if current_value < goal_value * 0.5:
        tk.Label(summary_frame, text="Suggestion: Consider increasing your time horizon or lowering your goal.", font=("Arial", 10), fg="red").pack(anchor="w", padx=20)

    # Back to Dashboard Button
    tk.Button(summary_frame, text="Back to Dashboard", command=lambda: show_frame(robo_advisor_frame)).pack(pady=10)

    # Navigation Buttons for Other Pages
    tk.Button(summary_frame, text="Portfolio Allocation", command=lambda: [show_frame(pie_chart_frame), display_pie_chart(pie_chart_frame)]).pack(pady=5)
    tk.Button(summary_frame, text="Goal Progress", command=lambda: [show_frame(goal_progress_frame), display_goal_progress(goal_progress_frame)]).pack(pady=5)
    tk.Button(summary_frame, text="Risk vs Return", command=lambda: [show_frame(risk_return_frame), display_risk_return(risk_return_frame)]).pack(pady=5)

    # Navigate to Summary Page
    show_frame(summary_frame)


def add_back_to_dashboard_button(frame):
    tk.Button(frame, text="Back to Dashboard", command=lambda: show_frame(robo_advisor_frame)).pack(pady=10)
    tk.Button(frame, text="Go to Summary Page", command=display_summary).pack(pady=5)


# Robo-Advisor Functions
def calculate_results():
    """
    Calculate portfolio performance, update monthly contribution, and enable visualizations.
    """
    status_label.config(text="Calculations in Progress...", fg="orange")
    root.update_idletasks()

    # Get all selected stocks (manual + recommended)
    selected_stocks = get_selected_stocks()  # Fetch all stocks
    investment_goal = float(goal_var.get() or 100000)
    time_horizon = int(time_var.get() or 10)

    if not selected_stocks:
        status_label.config(text="No stocks selected. Please select stocks.", fg="red")
        return

    try:
        # Fetch stock and bond data
        stock_data = pd.DataFrame()
        for ticker in selected_stocks:
            data = fetch_data(ticker)
            if data.empty:
                print(f"Warning: No data found for {ticker}. Skipping.")
                continue
            stock_data[ticker] = data

        if stock_data.empty:
            status_label.config(text="Error: No valid stock data found.", fg="red")
            return

        stock_data = stock_data.mean(axis=1)  # Average performance across selected stocks
        bond_data = fetch_data("BND")
        ff_data = fetch_fama_french()

        # Calculate performance
        allocation = recommend_allocation(risk_var.get())
        performance = calculate_performance(stock_data, bond_data, ff_data, allocation)

        # Update global variables
        global current_allocation, current_value, goal_value
        current_allocation = allocation
        current_value = (1 + performance) ** time_horizon * 100000  # Compound growth
        goal_value = investment_goal

        # Calculate monthly contribution
        monthly_contribution = calculate_monthly_contribution(goal_value, current_value, time_horizon)
        monthly_contribution_label.config(
            text=f"Monthly Contribution Needed: ${monthly_contribution:,.2f}"
        )

        # Update the selected stocks display
        update_selected_stocks()

        status_label.config(text="Calculations Complete!", fg="green")
        enable_visualization_buttons()
    except Exception as e:
        status_label.config(text=f"Error: {str(e)}", fg="red")


def enable_visualization_buttons():
    for button in [pie_chart_button, goal_progress_button, risk_return_button]:
        button.config(state=tk.NORMAL)
    summary_button.config(state=tk.NORMAL)  # Enable the summary button


def recommend_stocks():
    """
    Suggest stocks based on the user's risk tolerance and goal type,
    and display the recommendations on the dashboard.
    """
    risk_tolerance = risk_var.get()
    goal_type = goal_type_var.get()

    # Define stock recommendations by risk tolerance
    stock_pool = {
        "Low": ["KO", "JNJ", "WMT", "HD", "PG"],
        "Medium": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"],
        "High": ["TSLA", "PLTR", "GME", "AMC", "COIN"],
    }

    # Define goal-specific stocks
    goal_specific_stocks = {
        "House": ["HD", "LOW", "TOL"],
        "Retirement": ["VTI", "VOO", "SPY"],
        "Business": ["CRM", "ADBE", "MSFT"],
        "Vacation": ["DAL", "BKNG", "ABNB"],
        "College": ["SCHD", "QQQ", "VOO"],
    }

    # Get recommendations
    recommendations = stock_pool.get(risk_tolerance, [])
    goal_recommendations = goal_specific_stocks.get(goal_type, [])
    final_recommendations = list(set(recommendations + goal_recommendations))

    # Update the dashboard with recommendations
    if final_recommendations:
        recommended_stocks_label.config(
            text=f"Recommended Stocks: {', '.join(final_recommendations)}", fg="blue"
        )
    else:
        recommended_stocks_label.config(
            text="No recommendations available.", fg="red"
        )

def add_recommended_stocks_to_selection():
    """
    Add recommended stocks to the selection and update the dashboard.
    """
    # Extract recommended stocks from the label
    recommended_stocks = recommended_stocks_label.cget("text").replace("Recommended Stocks: ", "").split(", ")
    if recommended_stocks and recommended_stocks[0] != "None":
        global selected_stocks_data
        # Merge recommended stocks with existing selection
        selected_stocks_data = list(set(selected_stocks_data + recommended_stocks))  # Deduplicate
        update_selected_stocks()  # Update display
        status_label.config(text="Recommended stocks added to your selection!", fg="green")
    else:
        status_label.config(text="No recommended stocks to add.", fg="red")



def recommend_allocation(risk_tolerance):
    if risk_tolerance == "Low":
        return {"Stocks": 30, "Bonds": 70}
    elif risk_tolerance == "Medium":
        return {"Stocks": 60, "Bonds": 40}
    elif risk_tolerance == "High":
        return {"Stocks": 80, "Bonds": 20}

def clear_transactions():
    """
    Reset all user selections and calculations to start fresh.
    """
    # Reset global variables
    global selected_stocks_data, current_allocation, current_value, goal_value
    selected_stocks_data = []
    current_allocation = {"Stocks": 0, "Bonds": 0}
    current_value = 0
    goal_value = float(goal_var.get() or 100000)

    # Reset input variables
    goal_type_var.set("Retirement")
    goal_var.set("100000")
    risk_var.set("Medium")
    time_var.set("10")

    # Clear stock selections
    for stock_var in risky_selected.values():
        stock_var.set(False)
    for stock_var in medium_selected.values():
        stock_var.set(False)
    for stock_var in stable_selected.values():
        stock_var.set(False)

    # Update labels
    selected_stocks_label.config(text="Selected Stocks: None", fg="blue")
    recommended_stocks_label.config(text="Recommended Stocks: None", fg="blue")
    monthly_contribution_label.config(text="Monthly Contribution Needed: $0", fg="green")
    status_label.config(text="Waiting for input...", fg="blue")

    # Disable visualization buttons
    for button in [pie_chart_button, goal_progress_button, risk_return_button, summary_button]:
        button.config(state=tk.DISABLED)


# GUI Setup
root = tk.Tk()
root.title("SmartInvest: Your Personal Robo Advisor")

# Frames for GUI
main_menu = tk.Frame(root)
robo_advisor_frame = tk.Frame(root)
pie_chart_frame = tk.Frame(root)
goal_progress_frame = tk.Frame(root)
risk_return_frame = tk.Frame(root)
summary_frame = tk.Frame(root)
summary_frame.grid(row=0, column=0, sticky="nsew")


for frame in (main_menu, robo_advisor_frame, pie_chart_frame, goal_progress_frame, risk_return_frame):
    frame.grid(row=0, column=0, sticky="nsew")

# Main Menu
tk.Label(main_menu, text="Welcome to SmartInvest: Your Personal Robo Advisor!", font=("Arial", 16)).pack(pady=20)
tk.Button(main_menu, text="Dashboard", command=lambda: show_frame(robo_advisor_frame)).pack(pady=10)

# Robo-Advisor Frame
tk.Label(robo_advisor_frame, text="Dashboard", font=("Arial", 14)).grid(row=0, column=0, columnspan=3, pady=10)
status_label = tk.Label(robo_advisor_frame, text="Waiting for input...", font=("Arial", 10), fg="blue")
status_label.grid(row=1, column=0, columnspan=3, pady=5)


# Goal Type Dropdown
tk.Label(robo_advisor_frame, text="Goal Type:").grid(row=2, column=0, padx=10, pady=5)
goal_type_var = tk.StringVar(value="Retirement")
goal_types = ["House", "Retirement", "Business", "Vacation", "College"]
tk.OptionMenu(robo_advisor_frame, goal_type_var, *goal_types, command=lambda _: update_goal_based_on_type()).grid(row=2, column=1, padx=10, pady=5)

# Investment Goal Input
tk.Label(robo_advisor_frame, text="Investment Goal ($):").grid(row=3, column=0, padx=10, pady=5)
goal_var = tk.StringVar(value="100000")
goal_var.trace_add("write", manual_goal_update)
tk.Entry(robo_advisor_frame, textvariable=goal_var).grid(row=3, column=1, padx=10, pady=5)

# Risk Tolerance Input
tk.Label(robo_advisor_frame, text="Risk Tolerance:").grid(row=4, column=0, padx=10, pady=5)
risk_var = tk.StringVar(value="Medium")
tk.OptionMenu(robo_advisor_frame, risk_var, "Low", "Medium", "High").grid(row=4, column=1, padx=10, pady=5)

# Time Horizon Input
tk.Label(robo_advisor_frame, text="Time Horizon (Years):").grid(row=5, column=0, padx=10, pady=5)
time_var = tk.StringVar(value="10")
tk.Entry(robo_advisor_frame, textvariable=time_var).grid(row=5, column=1, padx=10, pady=5)

# Stock Selection Buttons
risky_stocks = ["TSLA", "GME", "AMC", "PLTR", "COIN", "SPCE", "NIO"]
medium_risk_stocks = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "CRM", "ADBE"]
stable_stocks = ["JNJ", "PG", "KO", "WMT", "HD", "VTI", "VOO", "SPY"]


risky_selected = {}
medium_selected = {}
stable_selected = {}


# Stock Selection Buttons
tk.Button(robo_advisor_frame, text="Select Risky Stocks", command=lambda: open_stock_selection("Risky", risky_stocks, risky_selected)).grid(row=6, column=0, padx=10, pady=5)
tk.Button(robo_advisor_frame, text="Select Medium Risk Stocks", command=lambda: open_stock_selection("Medium Risk", medium_risk_stocks, medium_selected)).grid(row=6, column=1, padx=10, pady=5)
tk.Button(robo_advisor_frame, text="Select Stable Stocks", command=lambda: open_stock_selection("Stable", stable_stocks, stable_selected)).grid(row=6, column=2, padx=10, pady=5)

# Display Selected Stocks
selected_stocks_label = tk.Label(robo_advisor_frame, text="Selected Stocks: None", font=("Arial", 10), fg="blue")
selected_stocks_label.grid(row=7, column=0, columnspan=3, pady=5)

# Calculate Button
tk.Button(robo_advisor_frame, text="Calculate", command=calculate_results).grid(row=8, column=0, columnspan=3, pady=10)

# Monthly Contribution Display
monthly_contribution_label = tk.Label(robo_advisor_frame, text="Monthly Contribution Needed: $0", font=("Arial", 10), fg="green")
monthly_contribution_label.grid(row=9, column=0, columnspan=3, pady=5)

# Clear Transactions Button
tk.Button(robo_advisor_frame, text="Clear Transactions", command=clear_transactions).grid(row=11, column=0, columnspan=3, pady=10)

# Recommended Stocks Section
recommended_stocks_label = tk.Label(robo_advisor_frame, text="Recommended Stocks: None", font=("Arial", 10), fg="blue")
recommended_stocks_label.grid(row=10, column=0, columnspan=3, pady=5)
tk.Button(robo_advisor_frame, text="Get Stock Recommendations", command=recommend_stocks).grid(row=13, column=0, columnspan=3, pady=5)
tk.Button(robo_advisor_frame, text="Add Recommended Stocks", command=add_recommended_stocks_to_selection).grid(row=14, column=0, columnspan=3, pady=5)

# Visualization Buttons Section
pie_chart_button = tk.Button(robo_advisor_frame, text="Portfolio Allocation", command=lambda: [show_frame(pie_chart_frame), display_pie_chart(pie_chart_frame)], state=tk.DISABLED)
pie_chart_button.grid(row=16, column=0, columnspan=3, pady=5)

goal_progress_button = tk.Button(robo_advisor_frame, text="Goal Progress", command=lambda: [show_frame(goal_progress_frame), display_goal_progress(goal_progress_frame)], state=tk.DISABLED)
goal_progress_button.grid(row=17, column=0, columnspan=3, pady=5)

risk_return_button = tk.Button(robo_advisor_frame, text="Risk vs Return", command=lambda: [show_frame(risk_return_frame), display_risk_return(risk_return_frame)], state=tk.DISABLED)
risk_return_button.grid(row=18, column=0, columnspan=3, pady=5)

# Summary Button
summary_button = tk.Button(robo_advisor_frame, text="View Summary", command=display_summary, state=tk.DISABLED)
summary_button.grid(row=19, column=0, columnspan=3, pady=10)



# Start with Main Menu
def show_frame(frame):
    frame.tkraise()

show_frame(main_menu)
root.mainloop()




# %%


