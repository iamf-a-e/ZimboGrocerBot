import os
import logging
import requests
import random
import string
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO)

wa_token = os.environ.get("WA_TOKEN")
gen_api = os.environ.get("GEN_API")
owner_phone_1 = os.environ.get("OWNER_PHONE")
owner_phone_1 = os.environ.get("OWNER_PHONE_1")
owner_phone_1 = os.environ.get("OWNER_PHONE_2")
owner_phone_1 = os.environ.get("OWNER_PHONE_3")
owner_phone_1 = os.environ.get("OWNER_PHONE_4")

app = Flask(__name__)
user_states = {}

# User, Product, Category, OrderSystem classes as before

class User:
    def __init__(self, payer_name, payer_phone):
        self.payer_name = payer_name
        self.payer_phone = payer_phone
        self.cart = []
        self.checkout_data = {}

    def add_to_cart(self, product, quantity):
        self.cart.append((product, quantity))

    def remove_from_cart(self, product_name):
        self.cart = [item for item in self.cart if item[0].name.lower() != product_name.lower()]

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

        beverages = Category("Beverages")
        beverages.add_product(Product("Coca Cola", 39.99, "Coca cola 2L"))
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
    requests.post(url, headers=headers, json=data)

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
    prompt = data["text"]["body"].strip()
    user_data = user_states.setdefault(sender, {"step": "ask_name", "order_system": OrderSystem()})

    step = user_data["step"]
    order_system = user_data["order_system"]
    user = user_data.get("user")

    def list_categories():
        return "\n".join([f"{chr(65+i)}. {cat}" for i, cat in enumerate(order_system.list_categories())])

    def list_products(category_name):
        products = order_system.list_products(category_name)
        return "\n".join([f"{i+1}. {p.name} - R{p.price:.2f}: {p.description}" for i, p in enumerate(products)])

    def show_cart(user):
        cart = user.get_cart_contents()
        if not cart:
            return "Your cart is empty."
        lines = [f"{p.name} x{q} = R{p.price*q:.2f}" for p, q in cart]
        total = sum(p.price*q for p, q in cart)
        return "\n".join(lines) + f"\n\nTotal: R{total:.2f}"

    if step == "ask_name":
        send("Hello! Welcome to Zimbogrocer. What's your name?", sender, phone_id)
        user_data["step"] = "save_name"

    elif step == "save_name":
        user = User(prompt.title(), sender)
        user_data["user"] = user
        send(f"Thanks {user.payer_name}! Please select a category:\n{list_categories()}", sender, phone_id)
        user_data["step"] = "choose_category"

    elif step == "choose_category":
        idx = ord(prompt.upper()) - 65
        categories = order_system.list_categories()
        if 0 <= idx < len(categories):
            cat = categories[idx]
            user_data["selected_category"] = cat
            send(f"Products in {cat}:\n{list_products(cat)}\nSelect a product by number.", sender, phone_id)
            user_data["step"] = "choose_product"
        else:
            send("Invalid category. Try again:\n" + list_categories(), sender, phone_id)

    elif step == "choose_product":
        try:
            index = int(prompt) - 1
            cat = user_data["selected_category"]
            products = order_system.list_products(cat)
            if 0 <= index < len(products):
                user_data["selected_product"] = products[index]
                send(f"You selected {products[index].name}. How many would you like to add?", sender, phone_id)
                user_data["step"] = "ask_quantity"
            else:
                send("Invalid product number. Try again.", sender, phone_id)
        except:
            send("Please enter a valid number.", sender, phone_id)

    elif step == "ask_quantity":
        try:
            qty = int(prompt)
            prod = user_data["selected_product"]
            user.add_to_cart(prod, qty)
            send(f"{prod.name} x{qty} added.\n{show_cart(user)}\nWould you like to checkout? (yes/no)", sender, phone_id)
            user_data["step"] = "ask_checkout"
        except:
            send("Please enter a valid number for quantity.", sender, phone_id)

    elif step == "ask_checkout":
        if prompt.lower() in ["yes", "y"]:
            send("Please enter the receiver’s full name.", sender, phone_id)
            user_data["step"] = "get_receiver_name"
        else:
            send("What would you like to do next?\n- View cart\n- Clear cart\n- Remove <item>\n- Select another category", sender, phone_id)
            user_data["step"] = "post_add_menu"

    elif step == "post_add_menu":
        if prompt.lower() == "view cart":
            send(show_cart(user), sender, phone_id)
        elif prompt.lower() == "clear cart":
            user.clear_cart()
            send("Cart cleared.", sender, phone_id)
        elif prompt.lower().startswith("remove "):
            item = prompt[7:].strip()
            user.remove_from_cart(item)
            send(f"{item} removed from cart.\n{show_cart(user)}", sender, phone_id)
        else:
            send("Let's continue. Choose a category:\n" + list_categories(), sender, phone_id)
            user_data["step"] = "choose_category"

    elif step == "get_receiver_name":
        user.checkout_data["receiver_name"] = prompt
        send("Enter the delivery address.", sender, phone_id)
        user_data["step"] = "get_address"

    elif step == "get_address":
        user.checkout_data["address"] = prompt
        send("Enter receiver’s ID number.", sender, phone_id)
        user_data["step"] = "get_id"

    elif step == "get_id":
        user.checkout_data["id_number"] = prompt
        send("Enter receiver’s phone number.", sender, phone_id)
        user_data["step"] = "get_phone"

    elif step == "get_phone":
        user.checkout_data["phone"] = prompt
        order_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        send(f"Order placed! 🛒\nOrder ID: {order_id}\n\n{show_cart(user)}\n\nReceiver: {user.checkout_data['receiver_name']}\nAddress: {user.checkout_data['address']}\nPhone: {user.checkout_data['phone']}", sender, phone_id)
        user.clear_cart()
        user_data["step"] = "choose_category"
        send("Would you like to place another order? Select a category:\n" + list_categories(), sender, phone_id)

    else:
        send("Sorry, I didn't understand that. Please start again with 'Hi'", sender, phone_id)

if __name__ == "__main__":
    app.run(debug=True, port=8000)
