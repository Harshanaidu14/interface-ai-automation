
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI(title="BankOps Demo")

# Fictional customer data for testing
customers = {
    "12345": {
        "name": "Alex Morgan",
        "account": "Savings",
        "balance": "$8,450.00",
        "status": "Active"
    },
    "67890": {
        "name": "Jordan Lee",
        "account": "Savings",
        "balance": "$12,750.00",
        "status": "Active"
    },
    "11223": {
        "name": "Taylor Smith",
        "account": "Checking",
        "balance": "$3,200.00",
        "status": "Inactive"
    }
}

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
    <head>
        <title>BankOps Demo</title>
        <style>
            body {
                font-family: Arial;
                background: #f3f5f9;
                padding: 50px;
            }
            .card {
                background: white;
                padding: 30px;
                max-width: 500px;
                margin: auto;
                border-radius: 10px;
                box-shadow: 0 2px 10px #ddd;
            }
            input, button {
                padding: 12px;
                margin-top: 10px;
                width: 100%;
                box-sizing: border-box;
            }
            button {
                background: #174ea6;
                color: white;
                border: none;
                cursor: pointer;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>BankOps - Customer Lookup</h2>
            <form action="/customer" method="get">
                <label>Customer ID</label>
                <input name="customer_id"
                       placeholder="Enter customer ID"
                       required>
                <button type="submit">
                    Search Customer
                </button>
            </form>
        </div>
    </body>
    </html>
    """

@app.get("/customer", response_class=HTMLResponse)
def customer_details(customer_id: str):
    customer = customers.get(customer_id)

    if not customer:
        return """
        <h2>Customer Not Found</h2>
        <p>No matching customer record exists.</p>
        <a href="/">Back to Search</a>
        """

    return f"""
    <html>
    <body style="font-family:Arial;padding:50px">
        <h2>Customer Details</h2>
        <p><b>Customer ID:</b> {customer_id}</p>
        <p><b>Name:</b> {customer['name']}</p>
        <p><b>Account Type:</b> {customer['account']}</p>
        <p><b>Balance:</b> {customer['balance']}</p>
        <p><b>Status:</b> {customer['status']}</p>
        <a href="/">Back to Search</a>
    </body>
    </html>
    """

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
