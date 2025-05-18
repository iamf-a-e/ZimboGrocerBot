import os
import logging
import requests
import random
import string
from datetime import datetime
from flask import Flask, request, jsonify, render_template

logging.basicConfig(level=logging.INFO)

wa_token = os.environ.get("WA_TOKEN")
app = Flask(__name__)

user_states = {}

# Models
class User:
    def __init__(self, payer_name, payer_phone):
        self.payer_name = payer_name
        self.payer_phone = payer_phone
        self.cart = []

    def add_to_cart(self, product, quantity):
        self.cart.append((product, quantity))

    def clear_cart(self):
        self.cart = []

    def get_cart_contents(self):
        return self.cart

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
        fresh = Category("Fresh Groceries")
        fresh.add_product(Product("Beef", 147.99, "Economy steak on bone beef cuts 1kg"))
        fresh.add_product(Product("Chicken", 179.99, "Ivines Mixed Portions 2kg"))
        self.add_category(fresh)

        bev = Category("Beverages")
        bev.add_product(Product("Coca cola", 39.99, "Coca cola 2L"))
        self.add_category(bev)

    def add_category(self, category):
        self.categories[category.name] = category

    def list_categories(self):
        return list(self.categories.keys())

    def list_products(self, category_name):
        return self.categories[category_name].products if category_name in self.categories else []

# Helper Functions
def send(message, sender, phone_id):
    url = f"https://graph.facebook.com/v19.0/{phone_id}/messages"
    headers = {
        'Authorization': f'Bearer {wa_token}',
        'Content-Type': 'application/json'
    }
    data = {
        "messaging_product": "whatsapp",
        "to": sender,
        "type": "text",
        "text": {"body": message}
    }
    requests.post(url, headers=headers, json=data)

def generate_order_number():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

# Web Routes
@app.route("/", methods=["GET"])
def index():
    return render_template("connected.html")

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        return challenge if token == "BOT" else "Failed", 200 if token == "BOT" else 403

    elif request.method == "POST":
        data = request.get_json()["entry"][0]["changes"][0]["value"]["messages"][0]
        phone_id = request.get_json()["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"]
        message_handler(data, phone_id)
        return jsonify({"status": "ok"}), 200

# Chat Flow Logic
def message_handler(data, phone_id):
    sender = data["from"]
    if data["type"] != "text":
        send("This format is not supported ☹", sender, phone_id)
        return

    prompt = data["text"]["body"].strip()
    state = user_states.get(sender, {})
    order_system = state.get("order_system", OrderSystem())
    user = state.get("user")

    if not user:
        if "awaiting_name" not in state:
            send("Hello! Welcome to Zimbogrocer online service. What's your name?", sender, phone_id)
            state["awaiting_name"] = True
        else:
            user = User(prompt.title(), sender)
            state["user"] = user
            state.pop("awaiting_name", None)
            state["order_system"] = order_system
            categories = order_system.list_categories()
            category_list = "\n".join([f"{chr(65 + idx)}. {category}" for idx, category in enumerate(categories)])
            send(f"Thank you, {user.payer_name}! Available categories:\n{category_list}\nPlease select a category (A, B, ...):", sender, phone_id)

    elif "selected_category" not in state:
        if prompt.isalpha() and len(prompt) == 1:
            index = ord(prompt.upper()) - 65
            categories = order_system.list_categories()
            if 0 <= index < len(categories):
                selected_category = categories[index]
                state["selected_category"] = selected_category
                products = order_system.list_products(selected_category)
                product_list = "\n".join([f"{i+1}. {p.name} - R{p.price} ({p.description})" for i, p in enumerate(products)])
                send(f"Products in {selected_category}:\n{product_list}\nSelect a product by number:", sender, phone_id)
            else:
                send("Invalid category. Please choose a letter from the list.", sender, phone_id)
        else:
            send("Please select a category using A, B, C...", sender, phone_id)

    elif "selected_product" not in state:
        if prompt.isdigit():
            idx = int(prompt) - 1
            selected_category = state["selected_category"]
            products = order_system.list_products(selected_category)
            if 0 <= idx < len(products):
                product = products[idx]
                state["selected_product"] = product
                send(f"You selected: {product.name} - R{product.price}\nHow many would you like to add?", sender, phone_id)
            else:
                send("Invalid product number. Try again.", sender, phone_id)
        else:
            send("Please choose a product using the number.", sender, phone_id)

    elif "awaiting_quantity" not in state:
        if prompt.isdigit():
            quantity = int(prompt)
            product = state["selected_product"]
            user.add_to_cart(product, quantity)
            state["awaiting_quantity"] = True
            cart = user.get_cart_contents()
            cart_str = "\n".join([f"{p.name} x{q} - R{p.price*q:.2f}" for p, q in cart])
            total = sum(p.price * q for p, q in cart)
            send(f"Added {product.name} x{quantity}.\nCart:\n{cart_str}\nTotal: R{total:.2f}", sender, phone_id)
            send("Would you like to checkout? (yes/no)", sender, phone_id)
        else:
            send("Please enter quantity as a number.", sender, phone_id)

    elif state.get("awaiting_quantity") and "checkout_decision" not in state:
        if prompt.lower() == "yes":
            state["checkout_decision"] = True
            send("Enter the receiver's full name:", sender, phone_id)
            state["awaiting_receiver"] = "name"
        elif prompt.lower() == "no":
            send("Okay. Say 'hi' to start again anytime.", sender, phone_id)
            user_states.pop(sender, None)
        else:
            send("Please respond with 'yes' or 'no'.", sender, phone_id)

    elif "awaiting_receiver" in state:
        receiver_info = state.get("receiver_info", {})
        step = state["awaiting_receiver"]

        if step == "name":
            receiver_info["name"] = prompt
            state["awaiting_receiver"] = "address"
            send("Enter home address:", sender, phone_id)
        elif step == "address":
            receiver_info["address"] = prompt
            state["awaiting_receiver"] = "id"
            send("Enter ID number:", sender, phone_id)
        elif step == "id":
            receiver_info["id"] = prompt
            state["awaiting_receiver"] = "phone"
            send("Enter phone number:", sender, phone_id)
        elif step == "phone":
            receiver_info["phone"] = prompt
            order_id = generate_order_number()
            cart = user.get_cart_contents()
            cart_str = "\n".join([f"{p.name} x{q} - R{p.price*q:.2f}" for p, q in cart])
            total = sum(p.price * q for p, q in cart)
            summary = (
                f"Order #{order_id}\n"
                f"Receiver: {receiver_info['name']}\n"
                f"Address: {receiver_info['address']}\n"
                f"Phone: {receiver_info['phone']}\n"
                f"Cart:\n{cart_str}\nTotal: R{total:.2f}\n\nThank you for shopping with Zimbogrocer!"
            )
            send(summary, sender, phone_id)
            user.clear_cart()
            user_states.pop(sender, None)
            return

        state["receiver_info"] = receiver_info

    user_states[sender] = state

if __name__ == "__main__":
    app.run(debug=True, port=8000)
