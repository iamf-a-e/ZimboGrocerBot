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

wa_token = os.environ.get("WA_TOKEN") # WhatsApp API Key
gen_api = os.environ.get("GEN_API")  # Gemini API Key
owner_phone = os.environ.get("OWNER_PHONE") # Owner's phone number with country code
owner_phone_1 = os.environ.get("OWNER_PHONE_1")
owner_phone_1 = os.environ.get("OWNER_PHONE_2")
owner_phone_1 = os.environ.get("OWNER_PHONE_3")
owner_phone_1 = os.environ.get("OWNER_PHONE_4")

app = Flask(__name__)
user_states = {}

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
        # Pantry
        pantry = Category("Pantry")
        pantry.add_product(Product("Ace Instant Porridge 1kg Assorted", 27.99, "Instant porridge mix"))
        pantry.add_product(Product("All Gold Tomato Sauce 700g", 44.99, "Tomato sauce"))
        pantry.add_product(Product("Aromat Original 50g", 24.99, "Seasoning"))
        pantry.add_product(Product("Bakers Inn/Proton Brown Bread", 23.99, "Brown loaf bread"))
        pantry.add_product(Product("Bakers Inn/Proton White Loaf", 23.99, "White loaf bread"))
        pantry.add_product(Product("Bella Macaroni 3kg", 82.99, "Macaroni pasta"))
        pantry.add_product(Product("Bisto Gravy 125g", 19.99, "Gravy mix"))
        pantry.add_product(Product("Blue Band Margarine 500g", 44.99, "Margarine"))
        pantry.add_product(Product("Blue Ribbon Self Raising 2kg", 37.99, "Self-raising flour"))
        pantry.add_product(Product("Bokomo Cornflakes 1kg", 54.90, "Cornflakes"))
        pantry.add_product(Product("Bullbrand Corned Beef 300g", 39.99, "Corned beef"))
        pantry.add_product(Product("Buttercup Margarine 500g", 44.99, "Margarine"))
        pantry.add_product(Product("Cashel Valley Baked Beans 400g", 18.99, "Baked beans"))
        pantry.add_product(Product("Cerevita 500g", 69.99, "Cereal"))
        pantry.add_product(Product("Cookmore/Puredrop Cooking Oil 2L", 67.99, "Cooking oil"))
        pantry.add_product(Product("Cross and Blackwell Mayonnaise 700g", 49.99, "Mayonnaise"))
        pantry.add_product(Product("Dried Kapenta 1kg", 134.99, "Dried fish"))
        pantry.add_product(Product("Ekono/Ideal Rice 5kg", 119.29, "Rice"))
        pantry.add_product(Product("Fattis Macaroni 500g", 22.99, "Macaroni"))
        pantry.add_product(Product("Gloria Self Raising Flour 5kg", 79.90, "Self-raising flour"))
        pantry.add_product(Product("Jungle Oats 1kg", 44.99, "Oats"))
        pantry.add_product(Product("Knorr Brown Onion Soup 50g", 7.99, "Onion soup mix"))
        pantry.add_product(Product("Lucky Star Pilchards in Tomato Sauce 155g", 17.99, "Pilchards"))
        pantry.add_product(Product("Mahatma Rice 2kg", 52.99, "Rice"))
        pantry.add_product(Product("Peanut Butter 350ml", 19.99, "Peanut butter"))
        pantry.add_product(Product("Roller Meal 10kg- Zim Meal", 136.99, "Maize meal"))
        self.add_category(pantry)
        
        # Beverages
        beverages = Category("Beverages")
        beverages.add_product(Product("Coca Cola 2L", 39.99, "Soft drink"))
        beverages.add_product(Product("Mazoe Raspberry 2 Litres", 67.99, "Fruit drink"))
        beverages.add_product(Product("Sprite 2 Litres", 37.99, "Soft drink"))
        beverages.add_product(Product("Nestle Gold Cross Condensed Milk 385g", 29.99, "Condensed milk"))
        beverages.add_product(Product("Dendairy Long Life Full Cream Milk 1 Litre", 28.99, "Long life milk"))
        self.add_category(beverages)
        
        # Household
        household = Category("Household")
        household.add_product(Product("Sunlight Dishwashing Liquid 750ml", 35.99, "Dishwashing liquid"))
        household.add_product(Product("Domestos Thick Bleach 750ml", 39.99, "Bleach cleaner"))
        household.add_product(Product("Handy Andy Assorted 500ml", 32.99, "Multi-surface cleaner"))
        household.add_product(Product("Maq Dishwashing Liquid 750ml", 35.99, "Dishwashing liquid"))
        self.add_category(household)
        
        # Personal Care
        personal_care = Category("Personal Care")
        personal_care.add_product(Product("Protex Bath Soap Assorted 150g", 21.99, "Bath soap"))
        personal_care.add_product(Product("Nivea Men's Roll On Assorted 50ml", 33.99, "Deodorant"))
        personal_care.add_product(Product("Clere Lanolin Lotion 400ml", 35.99, "Body lotion"))
        personal_care.add_product(Product("Vaseline Petroleum Jelly Original 250ml", 39.99, "Petroleum jelly"))
        self.add_category(personal_care)
        
        # Snacks and Sweets
        snacks = Category("Snacks and Sweets")
        snacks.add_product(Product("Jena Maputi 15pack", 23.99, "Popcorn"))
        snacks.add_product(Product("Tiggies/Zim Naks Assorted 50s", 74.99, "Snacks"))
        snacks.add_product(Product("Pringles Original 110g", 22.90, "Potato chips"))
        snacks.add_product(Product("Willards Cheezies 150g", 14.99, "Cheese snacks"))
        self.add_category(snacks)
        
        # Fresh Groceries
        fresh = Category("Fresh Groceries")
        fresh.add_product(Product("Economy Steak on Bone Beef Cuts 1kg", 147.99, "Fresh beef"))
        fresh.add_product(Product("Irvine's Mixed Chicken Cuts 2kg", 179.99, "Mixed chicken cuts"))
        fresh.add_product(Product("Potatoes 7.5kg", 219.99, "Fresh potatoes"))
        fresh.add_product(Product("Dairibord/Kefalos Yoghurt 150ml", 15.99, "Yoghurt"))
        self.add_category(fresh)
        
        # Stationery
        stationery = Category("Stationery")
        stationery.add_product(Product("Plastic Cover 3 Meter Roll", 7.99, "Plastic cover"))
        stationery.add_product(Product("A4 Bond Paper White", 126.99, "Bond paper"))
        stationery.add_product(Product("Cellotape Large 40yard", 5.99, "Cellotape"))
        stationery.add_product(Product("Sharp Scientific Calculator", 319.99, "Calculator"))
        self.add_category(stationery)
        
        # Baby Section
        baby_section = Category("Baby Section")
        baby_section.add_product(Product("Huggies Dry Comfort Jumbo Size 5 (44s)", 299.99, "Diapers"))
        baby_section.add_product(Product("Predo Baby Wipes Assorted 120s", 52.90, "Baby wipes"))
        baby_section.add_product(Product("Johnson and Johnson Scented Baby Jelly 325ml", 52.99, "Baby jelly"))
        self.add_category(baby_section)
        
        # Snacks and Sweets
        snacks = Category("Snacks and Sweets")
        snacks.add_product(Product("Jena Maputi 15pack", 23.99, "Popcorn"))
        snacks.add_product(Product("Tiggies/Zim Naks Assorted 50s", 74.99, "Snacks"))
        snacks.add_product(Product("Pringles Original 110g", 22.90, "Potato chips"))
        snacks.add_product(Product("Willards Cheezies 150g", 14.99, "Cheese snacks"))
        self.add_category(snacks)

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
        details = user.checkout_data
        confirm_message = f"Please confirm the details below:\n\nName: {details['receiver_name']}\nAddress: {details['address']}\nID: {details['id_number']}\nPhone: {details['phone']}\n\nAre these details correct? (yes/no)"
        send(confirm_message, sender, phone_id)
        user_data["step"] = "confirm_details"

    elif step == "confirm_details":
        if prompt.lower() in ["yes", "y"]:
            order_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            payment_info = f"Please make payment using one of the following options:\n\n1. Bank Transfer\nBank: ZimBank\nAccount: 123456789\nReference: {order_id}\n\n2. Pay at supermarkets: Shoprite, Checkers, Usave, Game, Spar, or Pick n Pay\n\n3. Pay via Mukuru\n\n4. Send via WorldRemit or Western Union\n\nInclude your Order ID as reference: {order_id}"
            send(f"Order placed! 🛒\nOrder ID: {order_id}\n\n{show_cart(user)}\n\nReceiver: {user.checkout_data['receiver_name']}\nAddress: {user.checkout_data['address']}\nPhone: {user.checkout_data['phone']}\n\n{payment_info}", sender, phone_id)
            user.clear_cart()
            user_data["step"] = "choose_category"
            send("Would you like to place another order? Select a category:\n" + list_categories(), sender, phone_id)
        else:
            send("Okay, let's correct the details. What's the receiver’s full name?", sender, phone_id)
            user_data["step"] = "get_receiver_name"

    elif step == "post_order_option":
        if prompt.lower() in ["yes", "y"]:
            send("Great! Please select a category:\n" + list_categories(), sender, phone_id)
            user_data["step"] = "choose_category"
        else:
            send("Have a good day!", sender, phone_id)
            user_data["step"] = "ask_name"

    else:
        send("Sorry, I didn't understand that. Please start again with 'Hi'", sender, phone_id)

if __name__ == "__main__":
    app.run(debug=True, port=8000)
