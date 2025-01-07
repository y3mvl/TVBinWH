import json
import os
import traceback
import logging
import pandas as pd
from binance.client import Client
from flask import Flask, request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),  # Logs to a file
        logging.StreamHandler()           # Logs to console
    ]
)


API_KEY = f'{os.environ["API_KEY"]}'
API_SECRET = f'{os.environ["API_SECRET"]}'
FREEBALANCE = float(f'{os.environ["FREEBALANCE"]}')
SECRET_KEY = f'{os.environ["SECRET_KEY"]}'
ORDER_ENABLE = True if f'{os.environ["ORDER_ENABLE"]}' == "TRUE" else False
app = Flask(__name__)
BINANCE_ENV = os.environ.get("BINANCE_ENV", "TESTNET").upper()

client = Client(API_KEY, API_SECRET)

if BINANCE_ENV == "TESTNET":
    client.API_URL = "https://testnet.binancefuture.com"
    logging.info("Running on Binance Testnet")
else:
    logging.info("Running on Binance Mainnet")

def validate_symbol(symbol: str) -> bool:
    try:
        valid_symbols = [s["symbol"] for s in client.futures_exchange_info()["symbols"]]
        if symbol in valid_symbols:
            return True
        else:
            logging.warning(f"Invalid symbol: {symbol}")
            return False
    except Exception as e:
        logging.error(f"Failed to fetch symbol list: {e}")
        return False


def change_leverage(data) -> dict:
    try:
        current_leverage = client.futures_position_information(symbol=data["symbol"])[0]["leverage"]
        if int(current_leverage) != data["leverage"]:
            client.futures_change_leverage(symbol=data["symbol"], leverage=data["leverage"])
        else:
            logging.info(f"Leverage for {data['symbol']} already set to {data['leverage']}")
        return data
    except Exception as e:
        logging.error(f"Error changing leverage for {data['symbol']}: {e}")
        positions = client.futures_position_information(symbol=data["symbol"])
        data["leverage"] = float(positions[0]["leverage"]) if positions else 1
        return data


def check_actions(actions) -> str:
    if actions == "CloseLong" or actions == "OpenShort":
        return "SELL"
    elif actions == "CloseShort" or actions == "OpenLong":
        return "BUY"
    elif actions == "test":
        return "test"
    else:
        return "test"


def get_position_size(symbol) -> pd.DataFrame:
    positions = client.futures_position_information(symbol=symbol)
    current_position = [
        position
        for position in positions
        if float(position["positionAmt"]) != 0
    ]
    if not current_position:
        logging.warning(f"No open positions for {symbol}")
        return pd.DataFrame()  # Return empty DataFrame to handle gracefully
    position_data = pd.DataFrame(
        current_position,
        columns=[
            "symbol",
            "entryPrice",
            "markPrice",
            "positionAmt",
            "unRealizedProfit",
            "positionSide",
            "leverage",
        ],
    )
    return position_data



def check_amount(symbol, order_amount, position_amount, action) -> float:
    qty_precision = 0
    m = len(order_amount)
    bids = float(client.futures_orderbook_ticker(symbol=symbol)["bidPrice"])
    asks = float(client.futures_orderbook_ticker(symbol=symbol)["askPrice"])
    bidask = bids if action == "SELL" else asks
    qty_precision = next(
        (int(precision["quantityPrecision"]) for precision in client.futures_exchange_info()["symbols"] if precision["symbol"] == symbol),
        0
    )

    if order_amount[0] == "%":
        percent = float(order_amount[1:m])
        return round(percent / 100 * position_amount, qty_precision)
    elif order_amount[0] == "@":
        fiat = float(order_amount[1:m])
        return round(fiat, qty_precision)
    elif order_amount[0] == "$":
        usd = float(order_amount[1:m])
        return round(usd / bidask, qty_precision)
    else:
        return 0


def check_balance(fiat) -> float:
    balances = client.futures_account_balance()
    balance = next(
        (float(asset["balance"]) for asset in balances if asset["asset"] == fiat),
        0  # Default to 0 if no matching asset is found
    )
    if balance == 0:
        logging.warning(f"No balance found for {fiat}")
    return round(balance, 2)


def close_order(data, position_data, side):
    if data["amount"] > 0:
        order = client.futures_create_order(
            symbol=data["symbol"],
            positionSide=side,
            side=data["order_side"],
            type="MARKET",
            quantity=abs(data["amount"]),
        )
        logging.info(f"Order Closed: {order}")
        position_size = float(position_data["positionAmt"][data["symbol"]])
        position_entry = float(position_data["entryPrice"][data["symbol"]])
        position_lev = int(position_data["leverage"][data["symbol"]])
        margin = position_entry * position_size / position_lev
        balance = check_balance("USDT")
        profit_loss = float(
            position_data["unRealizedProfit"][data["symbol"]]
        ) * abs(float(data["amount"]) / position_size)

        message = (
            f"Binance Bot\n"
            + f"Coin       : {data['symbol']}\n"
            + f"Order      : {data['action']}\n"
            + f"Amount     : {data['amount']}\n"
            + f"Margin     : {round(margin, 2)}USDT\n"
            + f"P/L        : {round(profit_loss, 2)} USDT\n"
            + f"Leverage   : X{position_lev}\n"
            + f"Balance    : {round(balance, 2)} USDT"
        )
        logging.info(message)
        return {"message": message}
    else:
        return {"error": "Invalid order amount."}


def open_order(data, side):
    data = change_leverage(data)
    if data["amount"] > 0:
        order = client.futures_create_order(
            symbol=data["symbol"],
            positionSide=side,
            side=data["order_side"],
            type="MARKET",
            quantity=data["amount"],
        )
        logging.info(f"Order opened: {order}")
        position_data = get_position_size(data["symbol"])
        if data["mode"] and len(position_data.index) > 1:
            if data["action"] == "CloseLong":
                position_data.drop(index=1, inplace=True)
            if data["action"] == "OpenLong":
                position_data.drop(index=0, inplace=True)
            if data["action"] == "CloseShort":
                position_data.drop(index=0, inplace=True)
            if data["action"] == "OpenShort":
                position_data.drop(index=1, inplace=True)
        position_data = position_data.set_index("symbol")
        position_size = float(position_data["positionAmt"][data["symbol"]])
        position_entry = float(position_data["entryPrice"][data["symbol"]])
        position_lev = int(position_data["leverage"][data["symbol"]])
        margin = position_entry * position_size / position_lev
        balance = check_balance("USDT")

        message = (
            f"Binance Bot\n"
            + f"Coin       : {data['symbol']}\n"
            + f"Order      : {data['action']}\n"
            + f"Amount     : {position_size}\n"
            + f"Margin     : {round(margin, 2)}USDT\n"
            + f"Price      : {position_entry}\n"
            + f"Leverage   : X{position_lev}\n"
            + f"Balance    : {round(balance, 2)} USDT"
        )

        logging.info(message)
        return {"message": message}
    else:
        return {"error": "Invalid order amount."}


def closeall_order(data, position_data, side):
    position_size = abs(float(position_data["positionAmt"][data["symbol"]]))
    position_entry = float(position_data["entryPrice"][data["symbol"]])
    position_lev = int(position_data["leverage"][data["symbol"]])

    order = client.futures_create_order(
        symbol=data["symbol"],
        positionSide=side,
        side=data["order_side"],
        type="MARKET",
        quantity=position_size,
    )
    logging.info(f"All order closed: {order}")
    margin = position_entry * position_size / position_lev
    balance = check_balance("USDT")
    profit_loss = float(position_data["unRealizedProfit"][data["symbol"]])

    message = (
        f"Binance Bot\n"
        + f"Coin       : {data['symbol']}\n"
        + "Order      : CloseAll\n"
        + f"Amount     : {position_size}\n"
        + f"Margin     : {round(margin, 2)}USDT\n"
        + f"P/L        : {round(profit_loss, 2)} USDT\n"
        + f"Leverage   : X{position_lev}\n"
        + f"Balance    : {round(balance, 2)} USDT"
    )
    logging.info(message)
    return  {"message": message}


def OpenLong(data):
    if data["amount_type"] == "%":
        return {"error":"Invalid amount"}
    return open_order(data, data["LongSide"])


def OpenShort(data):
    if data["amount_type"] == "%":
        return {"error":"Invalid amount"}
    return open_order(data, data["ShortSide"])


def CloseLong(data, position_data):
    return close_order(data, position_data, data["LongSide"])


def CloseShort(data, position_data):
    return close_order(data, position_data, data["ShortSide"])


def CloseAllLong(data, position_data):
    return closeall_order(data, position_data, data["LongSide"])


def CloseAllShort(data, position_data):
    return closeall_order(data, position_data, data["ShortSide"])


def ordering(order_data, position_data, position_size):
    isin_position = True if position_size != 0.0 else False
    if order_data["action"] == "CloseLong":
        if position_size > 0.0 and isin_position:
            CloseLong(order_data, position_data)
            return "Order Done"
        else:
            logging.warning(f"Attempted to close long but no position for {order_data['symbol']}")
            return "No Position : Do Nothing"
    elif order_data["action"] == "CloseShort":
        if position_size < 0.0 and isin_position:
            CloseShort(order_data, position_data)
            return "Order Done"
        else:
            logging.warning(f"Attempted to close short but no position for {order_data['symbol']}")
            return "No Position : Do Nothing"
    elif order_data["action"] == "OpenLong":
        if not order_data["mode"] and position_size < 0.0 and isin_position:
            CloseAllShort(order_data, position_data)
            OpenLong(order_data)
            return "Order Done"
        elif position_size > 0.0 and isin_position:
            logging.warning(f"Attempted to open long but already in position {order_data['symbol']}")
            return "Already in position : Do Nothing"
        else:
            OpenLong(order_data)
            return "Order Done"
    elif order_data["action"] == "OpenShort":
        if not order_data["mode"] and position_size > 0.0 and isin_position:
            CloseAllLong(order_data, position_data)
            OpenShort(order_data)
            return "Order Done"
        elif position_size < 0.0 and isin_position:
            logging.warning(f"Attempted to open short but already in position {order_data['symbol']}")
            return "Already in position : Do Nothing"
        else:
            OpenShort(order_data)
            return "Order Done"
    elif order_data["action"] == "test":
        return "test"
    else:
        return "Nothin to do"


def signal_handle(data) -> str:
    """
    Sample payload =  '{"side":"OpenShort","amount":"@0.006","symbol":"BTCUSDTPERP","passphrase":"1945","leverage":"125"}' # noqa:
    """
    if not data["passphrase"].isalnum() or data["passphrase"] != SECRET_KEY:
        logging.warning("Invalid passphrase attempt.")
        return "Nice try!! :P"

    balance = check_balance("USDT")

    if float(balance) < FREEBALANCE:
        logging.warning(f"Insufficient balance: {balance} USDT (Required: {FREEBALANCE})")
        return "Insufficient balance"

    symbol = data["symbol"]
    if not validate_symbol(symbol):
        logging.error(f"Invalid trading symbol {symbol}")
        return "Invalid symbol: Order rejected"
    if symbol.endswith("PERP"):
        symbol = symbol[:-4]

    position_mode = client.futures_get_position_mode()
    position_data = get_position_size(symbol)
    position_size = 0.0
    if position_mode["dualSidePosition"] and len(position_data.index) > 1:
        if data["side"] == "CloseLong":
            position_data.drop(index=1, inplace=True)
        if data["side"] == "OpenLong":
            position_data.drop(index=0, inplace=True)
        if data["side"] == "CloseShort":
            position_data.drop(index=0, inplace=True)
        if data["side"] == "OpenShort":
            position_data.drop(index=1, inplace=True)
        if data["side"] == "test":
            return "test"
    position_data = position_data.set_index("symbol")
    if not position_data.empty and symbol in position_data.index:
        position_size = float(position_data["positionAmt"].get(symbol, 0))
    actions = check_actions((data["side"] if ORDER_ENABLE is True else "test"))
    amount = check_amount(symbol, data["amount"], position_size, actions)
    if amount <= 0:
        logging.warning(f"Invalid order amount: {data['amount']}")
        return "Invalid order amount: Order rejected"

    order_data = {
        "amount_type": data["amount"][0],
        "amount": amount,
        "symbol": symbol,
        "leverage": int(data["leverage"]),
        "action": (data["side"] if ORDER_ENABLE is True else "test"),
        "order_side": actions,
        "mode": position_mode["dualSidePosition"],
        "LongSide": ("LONG" if position_mode["dualSidePosition"] else "BOTH"),
        "ShortSide": (
            "SHORT" if position_mode["dualSidePosition"] else "BOTH"
        ),
        "balance": balance,
    }

    if not (1 <= order_data['leverage'] <= 125):  # Binance leverage typically ranges from 1x to 125x
        logging.warning(f"Invalid leverage: {order_data['leverage']}")
        return "Invalid leverage: Order rejected"

    try:
        message = ordering(order_data, position_data, position_size)
        return message
    except Exception as e:
        logging.error(f"Ordering failed for {order_data['symbol']}: {e}")
        return f"Error occurred\n{e}"


@app.route("/")
def first_pages():
    return "hello"


@app.route("/webhook", methods=["POST"])
def webhook():
    data = json.loads(request.data)

    #if BINANCE_ENV == "TESTNET" and "PERP" not in data["symbol"]:
    #    logging.warning("Testnet orders must use PERP symbols")
    #    notify.send(f"{BOT_NAME}: Testnet orders must use PERP symbols.")
    #    return {"error": "Invalid symbol for testnet"}

    response = signal_handle(data)
    logging.info(f"Webhook triggered. Response: {response}")
    return {"OK": "Done"}


if __name__ == "__main__":
    logging.info(f"Binance BOT is starting in {BINANCE_ENV}...")
    app.run(debug=os.environ.get("FLASK_DEBUG", "False").lower() == "true")
    # print(get_position_size("OCEANUSDT"))
    #
    # test = signal_handle(
    #     data={
    #         "side": "OpenLong",
    #         "amount": "@574",
    #         "symbol": "OCEANUSDT",
    #         "passphrase": "8888",
    #         "leverage": "20",
    #     }
    # )
    # print(test)
