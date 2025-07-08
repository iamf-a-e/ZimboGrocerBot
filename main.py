import os
import logging
import requests
import random
import string
from datetime import datetime
from flask import Flask, request, jsonify, render_template
import redis
import json
import traceback
from orders import OrderSystem
from products import Category, Product

logging.basicConfig(level=logging.INFO)

# Environment variables
wa_token = os.environ.get("WA_TOKEN")
phone_id = os.environ.get("PHONE_ID")
gen_api = os.environ.get("GEN_API")
owner_phone = os.environ.get("OWNER_PHONE")
redis_url = os.environ.get("REDIS_URL")

# Redis client setup
redis_client = redis.StrictRedis.from_url(redis_url, decode_responses=True)

class User:
    def __init__(self, payer_name, payer_phone):
        self.payer_name = payer_name
        self.payer_phone = payer_phone
        self.cart = []
        self.checkout_data = {}

    def add_to_cart(self, product, quantity):
        for item in self.cart:
            if item['product'].name == product.name:
                item['quantity'] += quantity
                return
        self.cart.append({"product": product, "quantity": quantity})

    def remove_from_cart(self, product_name):
        self.cart = [item for item in self.cart if item["product"].name.lower() != product_name.lower()]

    def clear_cart(self):
        self.cart = []

    def get_cart_contents(self):
        return [(item["product"], item["quantity"]) for item in self.cart]

    def get_cart_total(self):
        return sum(item["product"].price * item["quantity"] for item in self.cart)

    def to_dict(self):
        return {
            "payer_name": self.payer_name,
            "payer_phone": self.payer_phone,
            "cart": [{
                "product": {
                    "name": item["product"].name,
                    "price": item["product"].price,
                    "description": item["product"].description
                },
                "quantity": item["quantity"]
            } for item in self.cart],
            "checkout_data": self.checkout_data
        }

    @classmethod
    def from_dict(cls, data):
        user = cls(data["payer_name"], data["payer_phone"])
        user.cart = [{
            "product": Product(
                item["product"]["name"],
                float(item["product"]["price"]),
                item["product"].get("description", "")
            ),
            "quantity": int(item["quantity"])
        } for item in data.get("cart", [])]
        user.checkout_data = data.get("checkout_data", {})
        return user

# Redis state functions
def get_user_state(phone_number):
    state_json = redis_client.get(f"user_state:{phone_number}")
    if state_json:
        return json.loads(state_json)
    return {'step': 'ask_name', 'sender': phone_number}

def update_user_state(phone_number, updates):
    updates['phone_number'] = phone_number
    if 'sender' not in updates:
        updates['sender'] = phone_number
    redis_client.setex(f"user_state:{phone_number}", 86400, json.dumps(updates))

# Utility

def list_categories():
    order_system = OrderSystem()
    return "\n".join([f"{chr(65+i)}. {cat}" for i, cat in enumerate(order_system.list_categories())])

def list_products(category_name):
    order_system = OrderSystem()
    products = order_system.list_products(category_name)
    return "\n".join([f"{i+1}. {p.name} - R{p.price:.2f}" for i, p in enumerate(products)])

def show_cart(user):
    cart = user.get_cart_contents()
    if not cart:
        return "Your cart is empty."
    lines = [f"{p.name} x{q} = R{p.price*q:.2f}" for p, q in cart]
    total = sum(p.price*q for p, q in cart)
    return "\n".join(lines) + f"\n\nTotal: R{total:.2f}"

def list_delivery_areas(delivery_areas):
    return "\n".join([f"{k} - R{v:.2f}" for k, v in delivery_areas.items()])

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
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to send message: {e}")

# Handlers
def handle_ask_name(prompt, user_data, phone_id):
    send("Hello! Welcome to Zimbogrocer. What's your name?", user_data['sender'], phone_id)
    update_user_state(user_data['sender'], {'step': 'save_name'})
    return {'step': 'save_name'}

def handle_save_name(prompt, user_data, phone_id):
    user = User(prompt.title(), user_data['sender'])
    order_system = OrderSystem()
    categories_products = order_system.get_products_by_category()
    category_names = list(categories_products.keys())
    first_category = category_names[0]
    first_products = categories_products[first_category]

    update_user_state(user_data['sender'], {
        'step': 'choose_product',
        'user': user.to_dict(),
        'category_names': category_names,
        'current_category_index': 0
    })

    send(
        f"Thanks {user.payer_name}! Here are products from {first_category}:
{first_products}

Reply 'more' to see next category.",
        user_data['sender'], phone_id
    )
    return {'step': 'choose_product', 'user': user.to_dict()}

def handle_choose_product(prompt, user_data, phone_id):
    try:
        index = int(prompt) - 1
        order_system = OrderSystem()
        products = order_system.get_all_products()
        if 0 <= index < len(products):
            selected_product = products[index]
            update_user_state(user_data['sender'], {
                'selected_product': selected_product.__dict__,
                'step': 'ask_quantity'
            })
            send(f"You selected {selected_product.name}. How many would you like to add?", user_data['sender'], phone_id)
            return {'step': 'ask_quantity', 'selected_product': selected_product.__dict__}
        else:
            send("Invalid product number. Try again.", user_data['sender'], phone_id)
            return {'step': 'choose_product'}
    except:
        send("Please enter a valid product number.", user_data['sender'], phone_id)
        return {'step': 'choose_product'}

def handle_ask_quantity(prompt, user_data, phone_id):
    try:
        qty = int(prompt.strip())
        if qty < 1:
            raise ValueError
    except:
        send("Please enter a valid number for quantity (e.g., 1, 2, 3).", user_data['sender'], phone_id)
        return {'step': 'ask_quantity', 'selected_product': user_data.get("selected_product", {})}

    user = User.from_dict(user_data['user'])
    pd = user_data['selected_product']
    product = Product(pd['name'], pd['price'], pd.get('description', ''))
    user.add_to_cart(product, qty)

    update_user_state(user_data['sender'], {
        'user': user.to_dict(),
        'step': 'post_add_menu'
    })
    send("Item added to your cart.
What would you like to do next?
1. View cart
2. Clear cart
3. Remove <item>
4. Add Item", user_data['sender'], phone_id)
    return {'step': 'post_add_menu', 'user': user.to_dict()}

# ... (Add all other handlers from your original main.py file here) ...

# Action mapping
action_mapping = {
    "ask_name": handle_ask_name,
    "save_name": handle_save_name,
    "choose_product": handle_choose_product,
    "ask_quantity": handle_ask_quantity,
    "post_add_menu": handle_post_add_menu,
    "get_area": handle_get_area,
    "ask_checkout": handle_ask_checkout,
    "get_receiver_name": handle_get_receiver_name,
    "get_address": handle_get_address,
    "get_id": handle_get_id,
    "get_phone": handle_get_phone,
    "confirm_details": handle_confirm_details,
    "await_payment_selection": handle_payment_selection,
    "ask_place_another_order": handle_ask_place_another_order,
    "choose_delivery_or_pickup": handle_choose_delivery_or_pickup,
    "get_receiver_name_pickup": handle_get_receiver_name_pickup,
    "get_id_pickup": handle_get_id_pickup,
}

def get_action(current_state, prompt, user_data, phone_id):
    handler = action_mapping.get(current_state, handle_default)
    return handler(prompt, user_data, phone_id)

# Message handler
def message_handler(prompt, sender, phone_id):
    text = prompt.strip().lower()

    if text in ["hi", "hey", "hie"]:
        user_state = {'step': 'ask_name', 'sender': sender}
        updated_state = get_action('ask_name', prompt, user_state, phone_id)
        update_user_state(sender, updated_state)
        return

    user_state = get_user_state(sender)
    user_state['sender'] = sender

    if text == "more" and user_state.get('step') == 'choose_product':
        updated_state = handle_next_category(user_state, phone_id)
        update_user_state(sender, updated_state)
        return

    updated_state = get_action(user_state['step'], prompt, user_state, phone_id)
    update_user_state(sender, updated_state)

# Flask app
app = Flask(__name__)

@app.route("/", methods=["GET"])
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
        data = request.get_json()
        logging.info(f"Incoming webhook data: {data}")

        try:
            entry = data["entry"][0]
            changes = entry["changes"][0]
            value = changes["value"]
            phone_id = value["metadata"]["phone_number_id"]

            messages = value.get("messages", [])
            if messages:
                message = messages[0]
                sender = message["from"]

                if "text" in message:
                    prompt = message["text"]["body"].strip()
                    message_handler(prompt, sender, phone_id)
                else:
                    send("Please send a text message", sender, phone_id)
        except Exception as e:
            logging.error(f"Error processing webhook: {e}", exc_info=True)

        return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(debug=True, port=8000)
