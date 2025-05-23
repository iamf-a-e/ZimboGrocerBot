import os
import logging
import requests
import random
import string
import json
from flask import Flask, request, jsonify, render_template
from redis import StrictRedis

# Setup logging
logging.basicConfig(level=logging.INFO)

# Environment Variables
wa_token = os.environ.get("WA_TOKEN")
gen_api = os.environ.get("GEN_API")
owner_phone = os.environ.get("OWNER_PHONE")
owner_phone_1 = os.environ.get("OWNER_PHONE_1")
owner_phone_2 = os.environ.get("OWNER_PHONE_2")
owner_phone_3 = os.environ.get("OWNER_PHONE_3")
owner_phone_4 = os.environ.get("OWNER_PHONE_4")

# Redis Connection
redis_client = StrictRedis(
    host=os.environ.get("UPSTASH_REDIS_HOST"),
    port=6379,
    password=os.environ.get("UPSTASH_REDIS_PASSWORD"),
    ssl=True,
    decode_responses=True
)

# Flask App
app = Flask(__name__)

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

class OrderSystem:
    def __init__(self):
        self.categories = {
    "Household": [
        Product("Sta Soft Lavender 2L", 59.99, "Fabric softener"),
        Product("Sunlight Dishwashing Liquid 750ml", 35.99, "Dishwashing liquid"),
        Product("Nova 2-Ply Toilet Paper 9s", 49.90, "Toilet paper"),
        Product("Domestos Thick Bleach Assorted 750ml", 39.99, "Bleach cleaner"),
        Product("Doom Odourless Multi-Insect Killer 300ml", 32.90, "Insect killer"),
        Product("Handy Andy Assorted 500ml", 32.99, "Multi-surface cleaner"),
        Product("Jik Assorted 750ml", 29.99, "Disinfectant"),
        Product("Maq Dishwashing Liquid 750ml", 35.99, "Dishwashing liquid"),
        Product("Maq 3kg Washing Powder", 72.90, "Washing powder"),
        Product("Maq Handwashing Powder 2kg", 78.99, "Handwashing powder"),
        Product("Elangeni Washing Bar 1kg", 24.59, "Washing bar"),
        Product("Vim Scourer 500g", 21.99, "Scouring pad"),
        Product("Matches Carton (10s)", 8.99, "Matches"),
        Product("Surf 5kg", 159.99, "Washing powder"),
        Product("Britelite Candles 6s", 32.99, "Candles"),
        Product("Sta-Soft Assorted Refill Sachet 2L", 39.99, "Fabric softener refill"),
        Product("Poppin Fresh Dishwashing Liquid 750ml", 22.99, "Dishwashing liquid"),
        Product("Poppin Fresh Toilet Cleaner 500ml", 34.99, "Toilet cleaner"),
        Product("Poppin Fresh Multi-Purpose Cleaner", 25.99, "Multi-purpose cleaner")
    ],
    "Personal Care": [
        Product("Softex Toilet Tissue 1-Ply 4s", 39.99, "Toilet tissue"),
        Product("Protex Bath Soap Assorted 150g", 21.99, "Bath soap"),
        Product("Sona Bath Soap 300g", 13.99, "Bath soap"),
        Product("Kiwi Black Shoe Polish 50ml", 18.99, "Shoe polish"),
        Product("Nivea Women's Roll On Assorted 50ml", 33.99, "Deodorant"),
        Product("Clere Lanolin Lotion 400ml", 35.99, "Body lotion"),
        Product("Vaseline Men Petroleum Jelly 250ml", 9.99, "Petroleum jelly"),
        Product("Vaseline Petroleum Jelly Original 250ml", 39.99, "Petroleum jelly"),
        Product("Sunlight Bath Soap Lively Lemon 175g", 10.90, "Bath soap"),
        Product("Shield Fresh Shower Deo", 24.99, "Deodorant"),
        Product("Hoity Toity Ladies Spray", 22.90, "Ladies spray"),
        Product("Brut Total Attraction Roll On", 17.90, "Deodorant"),
        Product("Vaseline Men Lotion 400ml", 64.99, "Body lotion"),
        Product("Shield Dry Musk Roll On 50ml", 24.99, "Deodorant"),
        Product("Sunlight Bath Soap Juicy Orange 150g", 10.99, "Bath soap"),
        Product("Axe Men Roll On Wild Spice", 32.99, "Deodorant"),
        Product("Nivea Rich Nourishing Cream 400ml", 79.99, "Body cream"),
        Product("Dawn Rich Lanolin Lotion 400ml", 24.90, "Body lotion"),
        Product("Twinsaver 2-Ply Toilet Paper", 32.90, "Toilet paper"),
        Product("Hoity Toity Body Lotion 400ml", 44.90, "Body lotion"),
        Product("Axe Deo Assorted Men", 36.99, "Deodorant"),
        Product("Stayfree Pads Scented Wings 10s", 15.99, "Sanitary pads"),
        Product("Geisha Bath Soap", 9.90, "Bath soap"),
        Product("Clere Berries and Cream 500ml", 39.99, "Body lotion"),
        Product("Clere Body Cream Cocoa Butter 500ml", 39.99, "Body cream"),
        Product("Ingram's Camphor Cream Herbal 500ml", 57.99, "Herbal cream"),
        Product("Lifebuoy Lemon Fresh 175g", 16.99, "Bath soap"),
        Product("Aquafresh Fresh and Minty Toothpaste 100ml", 22.99, "Toothpaste"),
        Product("Lil Lets Pads Super Maxi Thick 8s", 13.99, "Sanitary pads"),
        Product("Nivea Men Lotion (Assorted) 400ml", 79.99, "Body lotion"),
        Product("Nivea Men Cream (Assorted) 400ml", 79.99, "Body cream"),
        Product("Nivea Body Creme Deep Impact 400ml", 79.99, "Body cream"),
        Product("Clere Berries and Creme Lotion 400ml", 35.99, "Body lotion"),
        Product("Clere Men 400ml Lotion Assorted", 35.99, "Men's lotion"),
        Product("Pearl/Sona Bath Soap Assorted 200g", 13.99, "Bath soap"),
        Product("Nivea Intensive Moisturizing Creme 500ml", 79.99, "Moisturizing cream"),
        Product("Protex for Men Assorted Bath Soap 150g", 21.99, "Bath soap"),
        Product("Axe Roll On Assorted", 36.99, "Deodorant"),
        Product("Satiskin Floral Bouquet 2L", 99.99, "Body wash"),
        Product("Nivea Deep Impact Lotion 400ml", 79.99, "Body lotion"),
        Product("Nivea Ladies Deo Pearl Beauty", 32.90, "Deodorant"),
        Product("Nivea Rich Nourishing Lotion 400ml", 79.99, "Body lotion"),
        Product("Nivea Deo Dry Confidence Women 150ml", 32.99, "Deodorant"),
        Product("Dove Roll On Assorted", 26.99, "Deodorant"),
        Product("Satiskin Foam Bath Berry Fantasy 2L", 99.99, "Foam bath"),
        Product("Clere Glycerin 100ml", 21.99, "Glycerin"),
        Product("Nivea Body Creme Max Hydration 400ml", 79.99, "Body cream"),
        Product("Clere Men Body Cream Assorted 400ml", 39.99, "Men's body cream"),
        Product("Nivea Intensive Moisturizing Lotion 400g", 79.99, "Moisturizing lotion"),
        Product("Lux Soft Touch 175g", 21.99, "Bath soap"),
        Product("Lifebuoy Total 10 175g", 16.99, "Bath soap"),
        Product("Jade Bath Soap Assorted", 12.60, "Bath soap"),
        Product("Stayfree Pads Unscented Wings 10s", 19.90, "Sanitary pads"),
        Product("Colgate 100ml", 18.99, "Toothpaste"),
        Product("Clere Men Fire 450ml", 39.99, "Men's lotion"),
        Product("Shield Men's Roll On Assorted", 24.99, "Deodorant"),
        Product("Shower to Shower Ladies Deodorant", 27.99, "Deodorant"),
        Product("Lux Soft Caress 175g", 21.99, "Bath soap"),
        Product("Nivea Men Revitalizing Body Cream 400g", 79.99, "Body cream"),
        Product("Clere Cocoa Butter Lotion 400ml", 32.99, "Body lotion"),
        Product("Shield Women's Roll On Assorted", 24.99, "Deodorant"),
        Product("Nivea All Season Body Lotion 400ml", 79.99, "Body lotion"),
        Product("Nivea Men Roll On Assorted 50ml", 33.99, "Deodorant"),
        Product("Protex Deep Clean Bath Soap 150g", 21.99, "Bath soap"),
        Product("Sunlight Cooling Mint Bathing Soap 150g", 10.99, "Bath soap"),
        Product("Dettol 250ml", 25.99, "Antiseptic liquid"),
        Product("Woods Peppermint 100ml", 46.90, "Body spray"),
        Product("Med Lemon Sachet 6.1g", 7.90, "Lemon sachet"),
        Product("Predo Adult Diapers 30s (M/L/XL)", 317.99, "Adult diapers"),
        Product("Ingram's Camphor Moisture Plus 500ml", 59.99, "Moisturizing cream"),
        Product("Disposable Face Mask 50s", 39.99, "Face masks")
    ],
    "Baby Section": [
        Product("Huggies Dry Comfort Jumbo Size 5 (44s)", 299.99, "Diapers"),
        Product("Pampers Fresh Clean Wipes 64 Pack", 31.90, "Baby wipes"),
        Product("Johnson and Johnson Scented Baby Jelly 325ml", 52.99, "Baby jelly"),
        Product("Vaseline Baby Jelly 250g", 31.90, "Baby jelly"),
        Product("Predo Baby Wipes Assorted 120s", 52.90, "Baby wipes"),
        Product("Huggies Dry Comfort Size 3 Jumbo (76)", 299.99, "Diapers"),
        Product("Huggies Dry Comfort Size 2 Jumbo (94)", 299.99, "Diapers"),
        Product("Huggies Dry Comfort Size 4 Jumbo", 299.99, "Diapers"),
        Product("Bennetts Aqueous Cream 500ml", 39.30, "Aqueous cream"),
        Product("Predo Baby Wipes Assorted 80s", 38.99, "Baby wipes"),
        Product("Crez Babyline Petroleum Jelly 500g", 42.99, "Petroleum jelly"),
        Product("Johnson and Johnson Lightly Fragranced Aqueous Cream 350ml", 39.90, "Aqueous cream"),
        Product("Nestle Baby Cereal with Milk Regular Wheat 250g", 34.99, "Baby cereal"),
        Product("Nan 2: Infant Formula Optipro 400g", 79.99, "Infant formula"),
        Product("Nan 1: Infant Formula Optipro 400g", 79.99, "Infant formula")
    ],
    "Snacks and Sweets": [
        Product("Jena Maputi 15pack", 23.99, "Popcorn"),
        Product("Tiggies Assorted 50s", 74.99, "Snacks"),
        Product("L Choice Assorted Biscuits", 12.90, "Biscuits"),
        Product("Sneaker Nax Bale Pack 2kg", 39.90, "Snacks"),
        Product("Yogueta Lollipop Split Pack 48 Pack", 59.99, "Lollipops"),
        Product("Arenel Choice Assorted Biscuits 150g", 19.90, "Biscuits"),
        Product("Willards Things 150g", 14.99, "Cheese snacks"),
        Product("Stumbo Assorted Lollipops 48s", 59.99, "Lollipops"),
        Product("Pringles Original 110g", 22.90, "Potato chips"),
        Product("Nibble Naks 20pack", 29.99, "Snacks"),
        Product("King Kurls Chicken Flavour 100g", 12.90, "Snacks"),
        Product("Nik Naks 50s Pack Assorted", 54.90, "Snacks"),
        Product("Proton Ramba Waraira Cookies 1 kg", 68.99, "Cookies"),
        Product("Lobels Marie Biscuits", 6.90, "Biscuits"),
        Product("Chocolate Coated Biscuits", 35.99, "Chocolate biscuits"),
        Product("Top 10 Assorted Sweets", 9.90, "Assorted sweets"),
        Product("Jelido Magic Rings 102 Pieces", 48.90, "Candy rings"),
        Product("Lays Assorted Flavours 105g", 52.99, "Potato chips"),
        Product("Charhons Biscuits 2kg", 99.99, "Biscuits"),
        Product("Zap Nax Cheese and Onion 100g", 3.99, "Snacks")
    ],
    "Fresh Groceries": [
        Product("Economy Steak on Bone Beef Cuts 1kg", 147.99, "Fresh beef"),
        Product("Parmalat Cheddar Cheese", 89.99, "Cheddar cheese slices"),
        Product("Colcom Beef Polony 3kg", 299.00, "Beef polony"),
        Product("Colcom Tastee French Polony 750g", 116.99, "French polony"),
        Product("Colcom Chicken Polony 3kg", 219.90, "Chicken polony"),
        Product("Bulk Mixed Pork 1kg", 128.99, "Mixed pork"),
        Product("Potatoes 7.5kg (Small Pocket)", 219.99, "Fresh potatoes"),
        Product("Colcom Tastee Chicken Polony 1kg", 34.90, "Chicken polony"),
        Product("Colcom Garlic Polony 3kg", 220.00, "Garlic polony"),
        Product("Colcom Tastee Beef Polony 1kg", 35.00, "Beef polony"),
        Product("Wrapped Mixed Size Fresh Eggs 30", 149.99, "Fresh eggs"),
        Product("Texas Meats Juicy Boerewors", 159.99, "Boerewors"),
        Product("Unwrapped Small Size Fresh Eggs 30s", 99.99, "Fresh eggs"),
        Product("Irvines Mixed Chicken Cuts 2kg", 179.99, "Mixed chicken cuts"),
        Product("Dairibord Yoghurt 150ml", 15.99, "Yoghurt")
    ],
    "Stationery": [
        Product("Plastic Cover 3 Meter Roll", 7.99, "Plastic cover"),
        Product("Ruler 30cm", 6.99, "Ruler"),
        Product("A4 Bond Paper White", 126.99, "Bond paper"),
        Product("Kakhi Cover 3 Meter Roll", 8.99, "Kakhi cover"),
        Product("School Trunk", 750.00, "School trunk"),
        Product("Oxford Maths Set", 34.99, "Maths set"),
        Product("Grade 1-3 Exercise Book A4 32 Page (10 Pack)", 36.99, "Exercise books"),
        Product("72 Page Newsprint Maths Book (10 Pack)", 69.99, "Maths books"),
        Product("Cellotape Large 40yard", 5.99, "Cellotape"),
        Product("Newsprint 2 Quire Counter Books (192 Page)", 28.99, "Counter books"),
        Product("72 Page Newsprint Writing Exercise Book (10 Pack)", 69.99, "Writing exercise books"),
        Product("Cellotape Small 20yard", 3.99, "Cellotape"),
        Product("Eversharp Pens Set x 4", 14.99, "Pens set"),
        Product("Newsprint 1 Quire (96 Page) Counter Book", 17.99, "Counter book"),
        Product("HB Pencils x 12 Set", 24.99, "Pencils set"),
        Product("Sharp Scientific Calculator", 319.99, "Scientific calculator"),
        Product("32 Page Newsprint Plain Exercise Book (10 Pack)", 36.99, "Plain exercise books")
    ],
    "Pantry": [
        Product("Ace Instant Porridge 1kg Assorted", 27.99, "Instant porridge mix"),
        Product("All Gold Tomato Sauce 700g", 44.99, "Tomato sauce"),
        Product("Aromat Original 50g", 24.99, "Seasoning"),
        Product("Bakers Inn Bread", 23.99, "Brown loaf bread"),
        Product("Bakers Inn White Loaf", 23.99, "White loaf bread"),
        Product("Bella Macaroni 3kg", 82.99, "Macaroni pasta"),
        Product("Bisto Gravy 125g", 19.99, "Gravy mix"),
        Product("Blue Band Margarine 500g", 44.99, "Margarine"),
        Product("Blue Ribbon Self Raising 2kg", 37.99, "Self-raising flour"),
        Product("Bokomo Cornflakes 1kg", 54.90, "Cornflakes"),
        Product("Bullbrand Corned Beef 300g", 39.99, "Corned beef"),
        Product("Buttercup Margarine 500g", 44.99, "Margarine"),
        Product("Cashel Valley Baked Beans 400g", 18.99, "Baked beans"),
        Product("Cerevita 500g", 69.99, "Cereal"),
        Product("Cookmore Cooking Oil 2L", 67.99, "Cooking oil"),
        Product("Cross and Blackwell Mayonnaise 700g", 49.99, "Mayonnaise"),
        Product("Dried Kapenta 1kg", 134.99, "Dried fish"),
        Product("Ekonol Rice 5kg", 119.29, "Rice"),
        Product("Fattis Macaroni 500g", 22.99, "Macaroni"),
        Product("Gloria Self Raising Flour 5kg", 79.90, "Self-raising flour"),
        Product("Jungle Oats 1kg", 44.99, "Oats"),
        Product("Knorr Brown Onion Soup 50g", 7.99, "Onion soup mix"),
        Product("Lucky Star Pilchards in Tomato Sauce 155g", 17.99, "Pilchards"),
        Product("Mahatma Rice 2kg", 52.99, "Rice"),
        Product("Peanut Butter 350ml", 19.99, "Peanut butter"),
        Product("Roller Meal 10kg- Zim Meal", 136.99, "Maize meal")
    ],
    "Beverages": [
        Product("Stella Teabags 100 Pack", 42.99, "Tea bags"),
        Product("Mazoe Raspberry 2 Litres", 67.99, "Fruit drink"),
        Product("Cremora Creamer 750g", 72.99, "Coffee creamer"),
        Product("Everyday Milk Powder 400g", 67.99, "Milk powder"),
        Product("Freshpack Rooibos 80s", 84.99, "Rooibos tea"),
        Product("Nestle Gold Cross Condensed Milk 385g", 29.99, "Condensed milk"),
        Product("Pine Nut Soft Drink 2L", 37.99, "Soft drink"),
        Product("Mazoe Blackberry 2L", 68.99, "Fruit drink"),
        Product("Quench Mango 2L", 32.99, "Fruit drink"),
        Product("Coca Cola 2L", 39.99, "Soft drink"),
        Product("Pfuko Dairibord Maheu 500ml", 14.99, "Maheu drink"),
        Product("Sprite 2 Litres", 37.99, "Soft drink"),
        Product("Pepsi (500ml x 24)", 178.99, "Soft drink pack"),
        Product("Probands Milk 500ml", 20.99, "Steri milk"),
        Product("Lyons Hot Chocolate 125g", 42.99, "Hot chocolate"),
        Product("Dendairy Long Life Full Cream Milk 1 Litre", 28.99, "Long life milk"),
        Product("Joko Tea Bags 100", 55.99, "Tea bags"),
        Product("Cool Splash 5 Litre Orange Juice", 99.99, "Orange juice"),
        Product("Cremora Coffee Creamer 750g", 72.99, "Coffee creamer"),
        Product("Fanta Orange 2 Litres", 37.99, "Soft drink"),
        Product("Quench Mango 5L", 92.25, "Fruit drink"),
        Product("Ricoffy Coffee 250g", 52.99, "Coffee"),
        Product("Dendairy Low Fat Long Life Milk", 28.99, "Low fat milk"),
        Product("Quickbrew Teabags 50", 25.99, "Teabags"),
        Product("Fruitrade 2L Orange Juice", 32.90, "Orange juice"),
        Product("Mazoe Orange Crush 2L", 69.99, "Fruit drink"),
        Product("Joko Rooibos Tea Bags 80s", 84.99, "Rooibos tea")
    ]
}

def deserialize_user(data, phone):
    user = User(data['payer_name'], phone)
    user.cart = [(Product(p['name'], p['price'], p['description']), p['quantity']) for p in data.get('cart', [])]
    user.checkout_data = data.get('checkout_data', {})
    return user

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()["entry"][0]["changes"][0]["value"]["messages"][0]
    phone_id = request.get_json()["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"]
    message_handler(data, phone_id)
    return jsonify({"status": "ok"}), 200

def get_action(current_state, prompt, user_data):
    action_mapping = {
        "ask_name": handle_ask_name,
        "save_name": handle_save_name,
        "choose_category": handle_choose_category,
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
        "ask_place_another_order": handle_ask_place_another_order,
    }
    handler = action_mapping.get(current_state, handle_default)
    return handler(prompt, user_data)

def message_handler(data, phone_id):
    sender = data["from"]
    prompt = data["text"]["body"].strip()

    # Retrieve from Redis
    raw_data = redis_client.get(sender)
    if raw_data:
        user_data = json.loads(raw_data)
        user_data['order_system'] = OrderSystem()
        if 'user' in user_data:
            user_data['user'] = deserialize_user(user_data['user'], sender)
    else:
        user_data = {
            "step": "ask_name",
            "order_system": OrderSystem()
        }

    user_data['sender'] = sender
    user_data['phone_id'] = phone_id
    user_data['delivery_areas'] = {
        "Harare": 240, "Chitungwiza": 300, "Mabvuku": 300, "Ruwa": 300,
        "Domboshava": 250, "Southlea": 300, "Southview": 300, "Epworth": 300,
        "Mazoe": 300, "Chinhoyi": 350, "Banket": 350, "Rusape": 400, "Dema": 300
    }

    step = user_data["step"]
    get_action(step, prompt, user_data)

    # Save to Redis
    to_store = user_data.copy()
    to_store.pop("order_system", None)
    if 'user' in to_store:
        to_store['user'] = serialize_user(to_store['user'])
    redis_client.set(sender, json.dumps(to_store))

@app.route("/", methods=["GET"])
def index():
    return render_template("connected.html")

# Existing handler functions here: handle_ask_name, handle_save_name, etc.

def handle_ask_name(prompt, user_data):
    send("Hello! Welcome to Zimbogrocer. What's your name?", user_data['sender'], user_data['phone_id'])
    user_data['step'] = 'save_name'

def handle_save_name(prompt, user_data):
    user = User(prompt.title(), user_data['sender'])
    user_data['user'] = user
    send(f"Thanks {user.payer_name}! Please select a category:
{list_categories(user_data['order_system'])}", user_data['sender'], user_data['phone_id'])
    user_data['step'] = 'choose_category'

def handle_choose_category(prompt, user_data):
    if prompt.isalpha() and len(prompt) == 1:
        idx = ord(prompt.upper()) - 65
        categories = user_data['order_system'].list_categories()
        if 0 <= idx < len(categories):
            cat = categories[idx]
            user_data["selected_category"] = cat
            send(f"Products in {cat}:
{list_products(user_data['order_system'], cat)}
Select a product by number.", user_data['sender'], user_data['phone_id'])
            user_data["step"] = "choose_product"
        else:
            send("Invalid category. Try again:
" + list_categories(user_data['order_system']), user_data['sender'], user_data['phone_id'])
    else:
        send("Please enter a valid category letter (e.g., A, B, C).", user_data['sender'], user_data['phone_id'])

def handle_choose_product(prompt, user_data):
    try:
        index = int(prompt) - 1
        cat = user_data["selected_category"]
        products = user_data['order_system'].list_products(cat)
        if 0 <= index < len(products):
            user_data["selected_product"] = products[index]
            send(f"You selected {products[index].name}. How many would you like to add?", user_data['sender'], user_data['phone_id'])
            user_data["step"] = "ask_quantity"
        else:
            send("Invalid product number. Try again.", user_data['sender'], user_data['phone_id'])
    except Exception:
        send("Please enter a valid product number.", user_data['sender'], user_data['phone_id'])

def handle_ask_quantity(prompt, user_data):
    user = user_data['user']
    try:
        qty = int(prompt)
        prod = user_data["selected_product"]
        if qty < 1:
            raise ValueError
        user.add_to_cart(prod, qty)
        send("Item added to your cart.
What would you like to do next?
- View cart
- Clear cart
- Remove <item>
- Add Item", user_data['sender'], user_data['phone_id'])
        user_data["step"] = "post_add_menu"
    except Exception:
        send("Please enter a valid number for quantity (e.g., 1, 2, 3).", user_data['sender'], user_data['phone_id'])

def handle_post_add_menu(prompt, user_data):
    user = user_data['user']
    delivery_areas = user_data['delivery_areas']
    if prompt.lower() == "view cart":
        cart_message = show_cart(user)
        send(cart_message + "

Please select your delivery area:
" + list_delivery_areas(delivery_areas), user_data['sender'], user_data['phone_id'])
        user_data["step"] = "get_area"
    elif prompt.lower() == "clear cart":
        user.clear_cart()
        send("Cart cleared.
What would you like to do next?
- View cart
- Add Item", user_data['sender'], user_data['phone_id'])
        user_data["step"] = "post_add_menu"
    elif prompt.lower().startswith("remove "):
        item = prompt[7:].strip()
        user.remove_from_cart(item)
        send(f"{item} removed from cart.
{show_cart(user)}
What would you like to do next?
- View cart
- Add Item", user_data['sender'], user_data['phone_id'])
        user_data["step"] = "post_add_menu"
    elif prompt.lower() in ["add", "add item", "add another", "add more"]:
        send("Sure! Here are the available categories:
" + list_categories(user_data['order_system']), user_data['sender'], user_data['phone_id'])
        user_data["step"] = "choose_category"
    else:
        send("Sorry, I didn't understand. You can:
- View Cart
- Clear Cart
- Remove <item>
- Add Item", user_data['sender'], user_data['phone_id'])

def handle_get_area(prompt, user_data):
    user = user_data['user']
    delivery_areas = user_data['delivery_areas']
    area = prompt.strip().title()
    if area in delivery_areas:
        user.checkout_data["delivery_area"] = area
        fee = delivery_areas[area]
        user.checkout_data["delivery_fee"] = fee
        delivery_product = Product("__Delivery__", fee, f"Delivery to {area}")
        user.add_to_cart(delivery_product, 1)
        send(show_cart(user) + "
Would you like to checkout? (yes/no)", user_data['sender'], user_data['phone_id'])
        user_data["step"] = "ask_checkout"
    else:
        send(f"Invalid area. Please choose from:
{list_delivery_areas(delivery_areas)}", user_data['sender'], user_data['phone_id'])

def handle_ask_checkout(prompt, user_data):
    if prompt.lower() in ["yes", "y"]:
        send("Please enter the receiver’s full name.", user_data['sender'], user_data['phone_id'])
        user_data["step"] = "get_receiver_name"
    elif prompt.lower() in ["no", "n"]:
        send("What would you like to do next?
- View cart
- Clear cart
- Remove <item>
- Add Item", user_data['sender'], user_data['phone_id'])
        user_data["step"] = "post_add_menu"
    else:
        send("Please respond with 'yes' or 'no'.", user_data['sender'], user_data['phone_id'])

def handle_get_receiver_name(prompt, user_data):
    user = user_data['user']
    user.checkout_data["receiver_name"] = prompt
    send("Enter the delivery address.", user_data['sender'], user_data['phone_id'])
    user_data["step"] = "get_address"

def handle_get_address(prompt, user_data):
    user = user_data['user']
    user.checkout_data["address"] = prompt
    send("Enter receiver’s ID number.", user_data['sender'], user_data['phone_id'])
    user_data["step"] = "get_id"

def handle_get_id(prompt, user_data):
    user = user_data['user']
    user.checkout_data["id_number"] = prompt
    send("Enter receiver’s phone number.", user_data['sender'], user_data['phone_id'])
    user_data["step"] = "get_phone"

def handle_get_phone(prompt, user_data):
    user = user_data['user']
    user.checkout_data["phone"] = prompt
    details = user.checkout_data
    confirm_message = (
        f"Please confirm the details below:

"
        f"Name: {details['receiver_name']}
"
        f"Address: {details['address']}
"
        f"ID: {details['id_number']}
"
        f"Phone: {details['phone']}

"
        "Are these correct? (yes/no)"
    )
    send(confirm_message, user_data['sender'], user_data['phone_id'])
    user_data["step"] = "confirm_details"

def handle_confirm_details(prompt, user_data):
    user = user_data['user']
    if prompt.lower() in ["yes", "y"]:
        order_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        payment_info = (
            f"Please make payment using one of the following options:

"
            f"1. EFT
Bank: FNB
Name: Zimbogrocer (Pty) Ltd
Account: 62847698167
Branch Code: 250655
Swift Code: FIRNZAJJ
Reference: {order_id}
"
            f"Please remember to send the Proof of Payment as soon as you make payment.
Have a nice day.

"
            f"2. Pay at supermarkets using Mukuru wicode
"
            f"3. World Remit Transfer (on request)
"
            f"4. Western Union (on request)

"
            f"Order ID: {order_id}"
        )
        send(
            f"Order placed! 🛒
Order ID: {order_id}

"
            f"{show_cart(user)}

"
            f"Receiver: {user.checkout_data['receiver_name']}
"
            f"Address: {user.checkout_data['address']}
"
            f"Phone: {user.checkout_data['phone']}

"
            f"{payment_info}

Would you like to place another order? (yes/no)",
            user_data['sender'], user_data['phone_id']
        )
        user.clear_cart()
        user_data["step"] = "ask_place_another_order"
    else:
        send("Okay, let's correct the details. What's the receiver’s full name?", user_data['sender'], user_data['phone_id'])
        user_data["step"] = "get_receiver_name"

def handle_ask_place_another_order(prompt, user_data):
    if prompt.lower() in ["yes", "y"]:
        send("Great! Please select a category:
" + list_categories(user_data['order_system']), user_data['sender'], user_data['phone_id'])
        user_data["step"] = "choose_category"
    else:
        send("Okay. Have a good day! 😊", user_data['sender'], user_data['phone_id'])
        user_data["step"] = "ask_name"

def handle_default(prompt, user_data):
    send("Sorry, something went wrong. Please try again.", user_data['sender'], user_data['phone_id'])

def list_categories(order_system):
    return "
".join([f"{chr(65+i)}. {cat}" for i, cat in enumerate(order_system.list_categories())])

def list_products(order_system, category_name):
    products = order_system.list_products(category_name)
    return "
".join([f"{i+1}. {p.name} - R{p.price:.2f}: {p.description}" for i, p in enumerate(products)])

def show_cart(user):
    cart = user.get_cart_contents()
    if not cart:
        return "Your cart is empty."
    lines = [f"{p.name} x{q} = R{p.price*q:.2f}" for p, q in cart]
    total = sum(p.price*q for p, q in cart)
    return "
".join(lines) + f"

Total: R{total:.2f}"

def list_delivery_areas(delivery_areas):
    return "
".join([f"{k} - R{v:.2f}" for k, v in delivery_areas.items()])
# Paste your full handler implementations below this line

if __name__ == "__main__":
    app.run(debug=True, port=8000)
