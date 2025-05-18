import os
import logging
import requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Logging configuration
logging.basicConfig(level=logging.INFO)

# Environment variables
wa_token = os.environ.get("WA_TOKEN")
gen_api = os.environ.get("GEN_API")
owner_phone_1 = os.environ.get("OWNER_PHONE_1")
owner_phone_2 = os.environ.get("OWNER_PHONE_2")
owner_phone_3 = os.environ.get("OWNER_PHONE_3")
owner_phone_4 = os.environ.get("OWNER_PHONE_4")

app = Flask(__name__)

user_states = {}

# Database setup (disabled)
db = False
if db:
    db_url = os.environ.get("DB_URL")
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    Base = declarative_base()

    class Chat(Base):
        __tablename__ = 'chats'
        Chat_no = Column(Integer, primary_key=True)
        Sender = Column(String(255), nullable=False)
        Message = Column(String, nullable=False)
        Chat_time = Column(DateTime, default=datetime.utcnow)

    Base.metadata.create_all(engine)

class User:
    def __init__(self, payer_name, payer_phone):
        self.payer_name = payer_name
        self.payer_phone = payer_phone
        self.cart = []

    def add_to_cart(self, product, quantity):
        for i, (item, qty) in enumerate(self.cart):
            if item.name == product.name:
                self.cart[i] = (item, qty + quantity)
                return
        self.cart.append((product, quantity))

    def get_cart_contents(self):
        return self.cart

    def remove_item(self, product_name):
        self.cart = [(item, qty) for item, qty in self.cart if item.name.lower() != product_name.lower()]

    def clear_cart(self):
        self.cart.clear()

class Product:
    def __init__(self, name, price, description):
        self.name = name
        self.price = price
        self.description = description

class Category:
    def __init__(self, name):
        self.name = name
        self.products = []

    def add_product(self, product):
        self.products.append(product)

class OrderSystem:
    def __init__(self):
        self.categories = {}
        self.populate_products()

    def populate_products(self):
        fresh_groceries = Category("Fresh Groceries")
        fresh_groceries.add_product(Product("Beef", 147.99, "Economy steak on bone beef cuts 1kg"))
        fresh_groceries.add_product(Product("Chicken", 179.99, "Ivines Mixed Portions 2kg"))
        self.add_category(fresh_groceries)

        beverages = Category("Beverages")
        beverages.add_product(Product("Coca cola", 39.99, "Coca cola 2l"))
        self.add_category(beverages)

    def add_category(self, category):
        self.categories[category.name] = category

    def list_categories(self):
        return list(self.categories.keys())

    def list_products(self, category_name):
        return self.categories[category_name].products if category_name in self.categories else []

def send(answer, sender, phone_id):
    url = f"https://graph.facebook.com/v19.0/{phone_id}/messages"
    headers = {
        'Authorization': f'Bearer {wa_token}',
        'Content-Type': 'application/json'
    }
    data = {
        "messaging_product": "whatsapp",
        "to": sender,
        "type": "text",
        "text": {"body": answer}
    }
    response = requests.post(url, headers=headers, json=data)
    return response

@app.route("/", methods=["GET", "POST"])
def index():
    return render_template("connected.html")

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == "BOT":
            return challenge, 200
        return "Failed", 403

    elif request.method == "POST":
        data = request.get_json()["entry"][0]["changes"][0]["value"]["messages"][0]
        phone_id = request.get_json()["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"]
        message_handler(data, phone_id)
        return jsonify({"status": "ok"}), 200

def message_handler(data, phone_id):
    sender = data["from"]
    if data["type"] != "text":
        send("This format is not supported by the bot \u2639", sender, phone_id)
        return

    prompt = data["text"]["body"].strip().lower()
    user_state = user_states.setdefault(sender, {"order_system": OrderSystem(), "user": None})
    order_system = user_state["order_system"]
    user = user_state["user"]

    if prompt in ["hi", "hello", "hey"]:
        if user:
            send(f"Hi {user.payer_name}, welcome back! Would you like to place an order? (yes/no)", sender, phone_id)
        else:
            send("Hello! Welcome to Zimbogrocer online service. What's your name?", sender, phone_id)

    elif user is None:
        payer_name = prompt.title()
        payer_phone = sender
        user = User(payer_name, payer_phone)
        user_state["user"] = user
        categories = order_system.list_categories()
        cat_list = "\n".join([f"{chr(65+i)}. {cat}" for i, cat in enumerate(categories)])
        send(f"Thanks {payer_name}! Available categories:\n{cat_list}", sender, phone_id)

    elif prompt in ["yes", "sure"] and "selected_product" not in user_state:
        categories = order_system.list_categories()
        cat_list = "\n".join([f"{chr(65+i)}. {cat}" for i, cat in enumerate(categories)])
        send(f"Available categories:\n{cat_list}", sender, phone_id)

    elif prompt in ["no", "not now"]:
        send("Alright! Let me know if you change your mind.", sender, phone_id)

    elif prompt.isalpha() and len(prompt) == 1:
        index = ord(prompt.upper()) - 65
        categories = order_system.list_categories()
        if 0 <= index < len(categories):
            selected_category = categories[index]
            user_state["selected_category"] = selected_category
            products = order_system.list_products(selected_category)
            prod_list = "\n".join([f"{i+1}. {p.name} - R{p.price}: {p.description}" for i, p in enumerate(products)])
            send(f"Products in {selected_category}:\n{prod_list}\nChoose a product by number.", sender, phone_id)
        else:
            send("Invalid category letter.", sender, phone_id)

    elif prompt.isdigit() and "selected_category" in user_state:
        products = order_system.list_products(user_state["selected_category"])
        index = int(prompt) - 1
        if 0 <= index < len(products):
            user_state["selected_product"] = products[index]
            send(f"How many of {products[index].name} would you like to add to your cart?", sender, phone_id)
        else:
            send("Invalid product number.", sender, phone_id)

    elif prompt.isdigit() and "selected_product" in user_state:
        quantity = int(prompt)
        if quantity <= 0:
            send("Quantity must be a positive number.", sender, phone_id)
            return
        product = user_state["selected_product"]
        user.add_to_cart(product, quantity)
        user_state.pop("selected_product", None)
        user_state.pop("selected_category", None)
        cart_msg = "\n".join([f"{item.name} x{qty} - R{item.price*qty:.2f}" for item, qty in user.get_cart_contents()])
        send(f"{product.name} x{quantity} added to your cart.\nCurrent cart:\n{cart_msg}\nWould you like to add more? (yes/no)", sender, phone_id)

    elif prompt == "view cart":
        if not user.cart:
            send("Your cart is empty.", sender, phone_id)
        else:
            cart_msg = "\n".join([f"{item.name} x{qty} - R{item.price*qty:.2f}" for item, qty in user.get_cart_contents()])
            send(f"Your cart:\n{cart_msg}", sender, phone_id)

    elif prompt.startswith("remove "):
        prod_name = prompt.replace("remove ", "").strip()
        user.remove_item(prod_name)
        send(f"{prod_name} removed from your cart.", sender, phone_id)

    elif prompt == "clear cart":
        user.clear_cart()
        send("Your cart has been cleared.", sender, phone_id)

    elif prompt == "checkout":
        if not user.cart:
            send("Your cart is empty. Add some items before checking out.", sender, phone_id)
        else:
            cart_msg = "\n".join([f"{item.name} x{qty} - R{item.price*qty:.2f}" for item, qty in user.get_cart_contents()])
            total = sum(item.price * qty for item, qty in user.get_cart_contents())
            send(f"Checkout summary:\n{cart_msg}\nTotal: R{total:.2f}\nThank you for shopping with Zimbogrocer!", sender, phone_id)
            user.clear_cart()

    else:
        send("Sorry, I didn't understand that. Type 'view cart', 'checkout', 'remove <item>', or 'clear cart'.", sender, phone_id)

if __name__ == "__main__":
    app.run(debug=True, port=8000)
