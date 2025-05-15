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
wa_token = os.environ.get("WA_TOKEN")  # WhatsApp API Key
gen_api = os.environ.get("GEN_API")  # Gemini API Key
owner_phone = os.environ.get("OWNER_PHONE")  # Owner's phone number with country code
owner_phone = os.environ.get("OWNER_PHONE_1")
owner_phone = os.environ.get("OWNER_PHONE_2")
owner_phone = os.environ.get("OWNER_PHONE_3")
owner_phone = os.environ.get("OWNER_PHONE_4")


app = Flask(__name__)

# User state management
user_states = {}

# Database setup
db = False
if db:
    db_url = os.environ.get("DB_URL")  # Database URL
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

# User class for handling user information
class User:
    def __init__(self, payer_name, payer_phone):
        self.payer_name = payer_name
        self.payer_phone = payer_phone
        self.recipients = {}

    def add_recipient(self, recipient_name, recipient_phone, address, id_number):
        self.recipients[recipient_name] = {
            'phone': recipient_phone,
            'address': address,
            'id_number': id_number
        }

# Product and Category classes
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
        "text": {
            "body": answer
        }
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
        else:
            return "Failed", 403
    elif request.method == "POST":
        data = request.get_json()["entry"][0]["changes"][0]["value"]["messages"][0]
        phone_id = request.get_json()["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"]
        message_handler(data, phone_id)
        return jsonify({"status": "ok"}), 200

def message_handler(data, phone_id):
    sender = data["from"]  # This is the phone number of the sender
    if data["type"] == "text":
        prompt = data["text"]["body"].lower()  # Convert to lowercase for easier matching
        
        # Initialize user state if not present
        if sender not in user_states:
            user_states[sender] = {"order_system": OrderSystem(), "user": None}

        order_system = user_states[sender]["order_system"]
        user = user_states[sender]["user"]

        if prompt in ["hi", "hie", "hello", "hey"]:
            response_message = "Hello! Welcome to our service. Would you like to place an order? (yes/no)"
            send(response_message, sender, phone_id)
        elif prompt == "yes":
            response_message = "Great! What's your name?"
            send(response_message, sender, phone_id)
        elif prompt in ["no", "not now"]:
            response_message = "Alright! Let me know if you change your mind."
            send(response_message, sender, phone_id)
        elif user is None:
            # Assume the prompt is the user's name
            payer_name = prompt.title()  # Format name correctly
            payer_phone = sender  # Use the sender's phone number
            user = User(payer_name, payer_phone)
            user_states[sender]["user"] = user

            categories = order_system.list_categories()
            # Number the categories for user display
            category_list = "\n".join([f"{idx + 1}. {category}" for idx, category in enumerate(categories)])
            response_message = f"Thank you, {payer_name}! Available categories:\n{category_list}"
            send(response_message, sender, phone_id)
        elif user is not None and prompt.isdigit():
            category_index = int(prompt) - 1
            categories = order_system.list_categories()
            if 0 <= category_index < len(categories):
                selected_category = categories[category_index]
                products = order_system.list_products(selected_category)
                # List products with numbers
                product_list = "\n".join([f"{idx + 1}. {product.name} - ${product.price}: {product.description}" for idx, product in enumerate(products)])
                response_message = f"Products in {selected_category}:\n{product_list}\nPlease select a product by number."
                user_states[sender]["selected_category"] = selected_category  # Store selected category
            else:
                response_message = "Invalid category selection. Please choose a number from the list."
            send(response_message, sender, phone_id)
        elif user is not None and prompt.isdigit() and "selected_category" in user_states[sender]:
            product_index = int(prompt) - 1
            selected_category = user_states[sender]["selected_category"]
            products = order_system.list_products(selected_category)
            if 0 <= product_index < len(products):
                selected_product = products[product_index]
                user_states[sender]["selected_product"] = selected_product  # Store selected product
                response_message = f"You selected: {selected_product.name} - ${selected_product.price}. Would you like to add it to your cart? (yes/no)"
            else:
                response_message = "Invalid product selection. Please choose a number from the list."
            send(response_message, sender, phone_id)
        elif prompt in ["yes", "no"] and "selected_product" in user_states[sender]:
            if prompt == "yes":
                response_message = f"{user_states[sender]['selected_product'].name} has been added to your cart!"
            else:
                response_message = "No problem! Let me know if you need anything else."
            send(response_message, sender, phone_id)
    else:
        send("This format is not supported by the bot ☹", sender, phone_id)

if __name__ == "__main__":
    app.run(debug=True, port=8000)
