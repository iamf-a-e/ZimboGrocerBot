import os
import logging
import requests
import random
import string
import pickle

from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template
from sqlalchemy import create_engine, Column, Integer, String, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import google.generativeai as genai
import fitz
import sched
import time
from mimetypes import guess_type
from urlextract import URLExtract

logging.basicConfig(level=logging.INFO)

db = False
wa_token = os.environ.get("WA_TOKEN") # WhatsApp API Key
gen_api = os.environ.get("GEN_API")  # Gemini API Key
owner_phone = os.environ.get("OWNER_PHONE") # Owner's phone number with country code
owner_phone_1 = os.environ.get("OWNER_PHONE_1")
owner_phone_2 = os.environ.get("OWNER_PHONE_2")
owner_phone_3 = os.environ.get("OWNER_PHONE_3")
owner_phone_4 = os.environ.get("OWNER_PHONE_4")
model_name = "gemini-2.0-flash"

app = Flask(__name__)

USER_STATE_FILE = "user_states.pkl"

def load_user_states():
    if os.path.exists(USER_STATE_FILE):
        with open(USER_STATE_FILE, "rb") as f:
            return pickle.load(f)
    return {}

def save_user_states(states):
    with open(USER_STATE_FILE, "wb") as f:
        pickle.dump(states, f)

user_states = load_user_states()

class CustomURLExtract(URLExtract):
    def _get_cache_file_path(self):
        cache_dir = "/tmp"
        return os.path.join(cache_dir, "tlds-alpha-by-domain.txt")

extractor = CustomURLExtract(limit=1)

generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 0,
    "max_output_tokens": 8192,
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},  
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

model = genai.GenerativeModel(model_name=model_name,
                              generation_config=generation_config,
                              safety_settings=safety_settings)

convo = model.start_chat(history=[])

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
        pantry.add_product(Product("Bakers Inn Bread", 23.99, "Brown loaf bread"))
        pantry.add_product(Product("Bakers Inn White Loaf", 23.99, "White loaf bread"))
        pantry.add_product(Product("Bella Macaroni 3kg", 82.99, "Macaroni pasta"))
        pantry.add_product(Product("Bisto Gravy 125g", 19.99, "Gravy mix"))
        pantry.add_product(Product("Blue Band Margarine 500g", 44.99, "Margarine"))
        pantry.add_product(Product("Blue Ribbon Self Raising 2kg", 37.99, "Self-raising flour"))
        pantry.add_product(Product("Bokomo Cornflakes 1kg", 54.90, "Cornflakes"))
        pantry.add_product(Product("Bullbrand Corned Beef 300g", 39.99, "Corned beef"))
        pantry.add_product(Product("Buttercup Margarine 500g", 44.99, "Margarine"))
        pantry.add_product(Product("Cashel Valley Baked Beans 400g", 18.99, "Baked beans"))
        pantry.add_product(Product("Cerevita 500g", 69.99, "Cereal"))
        pantry.add_product(Product("Cookmore Cooking Oil 2L", 67.99, "Cooking oil"))
        pantry.add_product(Product("Cross and Blackwell Mayonnaise 700g", 49.99, "Mayonnaise"))
        pantry.add_product(Product("Dried Kapenta 1kg", 134.99, "Dried fish"))
        pantry.add_product(Product("Ekonol Rice 5kg", 119.29, "Rice"))
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
        beverages.add_product(Product("Stella Teabags 100 Pack", 42.99, "Tea bags"))
        beverages.add_product(Product("Mazoe Raspberry 2 Litres", 67.99, "Fruit drink"))
        beverages.add_product(Product("Cremora Creamer 750g", 72.99, "Coffee creamer"))
        beverages.add_product(Product("Everyday Milk Powder 400g", 67.99, "Milk powder"))
        beverages.add_product(Product("Freshpack Rooibos 80s", 84.99, "Rooibos tea"))
        beverages.add_product(Product("Nestle Gold Cross Condensed Milk 385g", 29.99, "Condensed milk"))
        beverages.add_product(Product("Pine Nut Soft Drink 2L", 37.99, "Soft drink"))
        beverages.add_product(Product("Mazoe Blackberry 2L", 68.99, "Fruit drink"))
        beverages.add_product(Product("Quench Mango 2L", 32.99, "Fruit drink"))
        beverages.add_product(Product("Coca Cola 2L", 39.99, "Soft drink"))
        beverages.add_product(Product("Pfuko Dairibord Maheu 500ml", 14.99, "Maheu drink"))
        beverages.add_product(Product("Sprite 2 Litres", 37.99, "Soft drink"))
        beverages.add_product(Product("Pepsi (500ml x 24)", 178.99, "Soft drink pack"))
        beverages.add_product(Product("Probands Milk 500ml", 20.99, "Steri milk"))
        beverages.add_product(Product("Lyons Hot Chocolate 125g", 42.99, "Hot chocolate"))
        beverages.add_product(Product("Dendairy Long Life Full Cream Milk 1 Litre", 28.99, "Long life milk"))
        beverages.add_product(Product("Joko Tea Bags 100", 55.99, "Tea bags"))
        beverages.add_product(Product("Cool Splash 5 Litre Orange Juice", 99.99, "Orange juice"))
        beverages.add_product(Product("Cremora Coffee Creamer 750g", 72.99, "Coffee creamer"))
        beverages.add_product(Product("Fanta Orange 2 Litres", 37.99, "Soft drink"))
        beverages.add_product(Product("Quench Mango 5L", 92.25, "Fruit drink"))
        beverages.add_product(Product("Ricoffy Coffee 250g", 52.99, "Coffee"))
        beverages.add_product(Product("Dendairy Low Fat Long Life Milk", 28.99, "Low fat milk"))
        beverages.add_product(Product("Quickbrew Teabags 50", 25.99, "Teabags"))
        beverages.add_product(Product("Fruitrade 2L Orange Juice", 32.90, "Orange juice"))
        beverages.add_product(Product("Mazoe Orange Crush 2L", 69.99, "Fruit drink"))
        beverages.add_product(Product("Joko Rooibos Tea Bags 80s", 84.99, "Rooibos tea"))
        self.add_category(beverages)
                
        # Household
        household = Category("Household")
        household.add_product(Product("Sta Soft Lavender 2L", 59.99, "Fabric softener"))
        household.add_product(Product("Sunlight Dishwashing Liquid 750ml", 35.99, "Dishwashing liquid"))
        household.add_product(Product("Nova 2-Ply Toilet Paper 9s", 49.90, "Toilet paper"))
        household.add_product(Product("Domestos Thick Bleach Assorted 750ml", 39.99, "Bleach cleaner"))
        household.add_product(Product("Doom Odourless Multi-Insect Killer 300ml", 32.90, "Insect killer"))
        household.add_product(Product("Handy Andy Assorted 500ml", 32.99, "Multi-surface cleaner"))
        household.add_product(Product("Jik Assorted 750ml", 29.99, "Disinfectant"))
        household.add_product(Product("Maq Dishwashing Liquid 750ml", 35.99, "Dishwashing liquid"))
        household.add_product(Product("Maq 3kg Washing Powder", 72.90, "Washing powder"))
        household.add_product(Product("Maq Handwashing Powder 2kg", 78.99, "Handwashing powder"))
        household.add_product(Product("Elangeni Washing Bar 1kg", 24.59, "Washing bar"))
        household.add_product(Product("Vim Scourer 500g", 21.99, "Scouring pad"))
        household.add_product(Product("Matches Carton (10s)", 8.99, "Matches"))
        household.add_product(Product("Surf 5kg", 159.99, "Washing powder"))
        household.add_product(Product("Britelite Candles 6s", 32.99, "Candles"))
        household.add_product(Product("Sta-Soft Assorted Refill Sachet 2L", 39.99, "Fabric softener refill"))
        household.add_product(Product("Poppin Fresh Dishwashing Liquid 750ml", 22.99, "Dishwashing liquid"))
        household.add_product(Product("Poppin Fresh Toilet Cleaner 500ml", 34.99, "Toilet cleaner"))
        household.add_product(Product("Poppin Fresh Multi-Purpose Cleaner", 25.99, "Multi-purpose cleaner"))
        self.add_category(household)
        
        # Personal Care
        personal_care = Category("Personal Care")
        personal_care.add_product(Product("Softex Toilet Tissue 1-Ply 4s", 39.99, "Toilet tissue"))
        personal_care.add_product(Product("Protex Bath Soap Assorted 150g", 21.99, "Bath soap"))
        personal_care.add_product(Product("Sona Bath Soap 300g", 13.99, "Bath soap"))
        personal_care.add_product(Product("Kiwi Black Shoe Polish 50ml", 18.99, "Shoe polish"))
        personal_care.add_product(Product("Nivea Women's Roll On Assorted 50ml", 33.99, "Deodorant"))
        personal_care.add_product(Product("Clere Lanolin Lotion 400ml", 35.99, "Body lotion"))
        personal_care.add_product(Product("Vaseline Men Petroleum Jelly 250ml", 9.99, "Petroleum jelly"))
        personal_care.add_product(Product("Vaseline Petroleum Jelly Original 250ml", 39.99, "Petroleum jelly"))
        personal_care.add_product(Product("Sunlight Bath Soap Lively Lemon 175g", 10.90, "Bath soap"))
        personal_care.add_product(Product("Shield Fresh Shower Deo", 24.99, "Deodorant"))
        personal_care.add_product(Product("Hoity Toity Ladies Spray", 22.90, "Ladies spray"))
        personal_care.add_product(Product("Brut Total Attraction Roll On", 17.90, "Deodorant"))
        personal_care.add_product(Product("Vaseline Men Lotion 400ml", 64.99, "Body lotion"))
        personal_care.add_product(Product("Shield Dry Musk Roll On 50ml", 24.99, "Deodorant"))
        personal_care.add_product(Product("Sunlight Bath Soap Juicy Orange 150g", 10.99, "Bath soap"))
        personal_care.add_product(Product("Axe Men Roll On Wild Spice", 32.99, "Deodorant"))
        personal_care.add_product(Product("Nivea Rich Nourishing Cream 400ml", 79.99, "Body cream"))
        personal_care.add_product(Product("Dawn Rich Lanolin Lotion 400ml", 24.90, "Body lotion"))
        personal_care.add_product(Product("Twinsaver 2-Ply Toilet Paper", 32.90, "Toilet paper"))
        personal_care.add_product(Product("Hoity Toity Body Lotion 400ml", 44.90, "Body lotion"))
        personal_care.add_product(Product("Axe Deo Assorted Men", 36.99, "Deodorant"))
        personal_care.add_product(Product("Stayfree Pads Scented Wings 10s", 15.99, "Sanitary pads"))
        personal_care.add_product(Product("Geisha Bath Soap", 9.90, "Bath soap"))
        personal_care.add_product(Product("Clere Berries and Cream 500ml", 39.99, "Body lotion"))
        personal_care.add_product(Product("Clere Body Cream Cocoa Butter 500ml", 39.99, "Body cream"))
        personal_care.add_product(Product("Ingram's Camphor Cream Herbal 500ml", 57.99, "Herbal cream"))
        personal_care.add_product(Product("Lifebuoy Lemon Fresh 175g", 16.99, "Bath soap"))
        personal_care.add_product(Product("Aquafresh Fresh and Minty Toothpaste 100ml", 22.99, "Toothpaste"))
        personal_care.add_product(Product("Lil Lets Pads Super Maxi Thick 8s", 13.99, "Sanitary pads"))
        personal_care.add_product(Product("Nivea Men Lotion (Assorted) 400ml", 79.99, "Body lotion"))
        personal_care.add_product(Product("Nivea Men Cream (Assorted) 400ml", 79.99, "Body cream"))
        personal_care.add_product(Product("Nivea Body Creme Deep Impact 400ml", 79.99, "Body cream"))
        personal_care.add_product(Product("Clere Berries and Creme Lotion 400ml", 35.99, "Body lotion"))
        personal_care.add_product(Product("Clere Men 400ml Lotion Assorted", 35.99, "Men's lotion"))
        personal_care.add_product(Product("Pearl/Sona Bath Soap Assorted 200g", 13.99, "Bath soap"))
        personal_care.add_product(Product("Nivea Intensive Moisturizing Creme 500ml", 79.99, "Moisturizing cream"))
        personal_care.add_product(Product("Protex for Men Assorted Bath Soap 150g", 21.99, "Bath soap"))
        personal_care.add_product(Product("Axe Roll On Assorted", 36.99, "Deodorant"))
        personal_care.add_product(Product("Satiskin Floral Bouquet 2L", 99.99, "Body wash"))
        personal_care.add_product(Product("Nivea Deep Impact Lotion 400ml", 79.99, "Body lotion"))
        personal_care.add_product(Product("Nivea Ladies Deo Pearl Beauty", 32.90, "Deodorant"))
        personal_care.add_product(Product("Nivea Rich Nourishing Lotion 400ml", 79.99, "Body lotion"))
        personal_care.add_product(Product("Nivea Deo Dry Confidence Women 150ml", 32.99, "Deodorant"))
        personal_care.add_product(Product("Dove Roll On Assorted", 26.99, "Deodorant"))
        personal_care.add_product(Product("Satiskin Foam Bath Berry Fantasy 2L", 99.99, "Foam bath"))
        personal_care.add_product(Product("Clere Glycerin 100ml", 21.99, "Glycerin"))
        personal_care.add_product(Product("Nivea Body Creme Max Hydration 400ml", 79.99, "Body cream"))
        personal_care.add_product(Product("Clere Men Body Cream Assorted 400ml", 39.99, "Men's body cream"))
        personal_care.add_product(Product("Nivea Intensive Moisturizing Lotion 400g", 79.99, "Moisturizing lotion"))
        personal_care.add_product(Product("Lux Soft Touch 175g", 21.99, "Bath soap"))
        personal_care.add_product(Product("Lifebuoy Total 10 175g", 16.99, "Bath soap"))
        personal_care.add_product(Product("Jade Bath Soap Assorted", 12.60, "Bath soap"))
        personal_care.add_product(Product("Stayfree Pads Unscented Wings 10s", 19.90, "Sanitary pads"))
        personal_care.add_product(Product("Colgate 100ml", 18.99, "Toothpaste"))
        personal_care.add_product(Product("Clere Men Fire 450ml", 39.99, "Men's lotion"))
        personal_care.add_product(Product("Shield Men's Roll On Assorted", 24.99, "Deodorant"))
        personal_care.add_product(Product("Shower to Shower Ladies Deodorant", 27.99, "Deodorant"))
        personal_care.add_product(Product("Lux Soft Caress 175g", 21.99, "Bath soap"))
        personal_care.add_product(Product("Nivea Men Revitalizing Body Cream 400g", 79.99, "Body cream"))
        personal_care.add_product(Product("Clere Cocoa Butter Lotion 400ml", 32.99, "Body lotion"))
        personal_care.add_product(Product("Shield Women's Roll On Assorted", 24.99, "Deodorant"))
        personal_care.add_product(Product("Nivea All Season Body Lotion 400ml", 79.99, "Body lotion"))
        personal_care.add_product(Product("Nivea Men Roll On Assorted 50ml", 33.99, "Deodorant"))
        personal_care.add_product(Product("Protex Deep Clean Bath Soap 150g", 21.99, "Bath soap"))
        personal_care.add_product(Product("Sunlight Cooling Mint Bathing Soap 150g", 10.99, "Bath soap"))
        personal_care.add_product(Product("Dettol 250ml", 25.99, "Antiseptic liquid"))
        personal_care.add_product(Product("Woods Peppermint 100ml", 46.90, "Body spray"))
        personal_care.add_product(Product("Med Lemon Sachet 6.1g", 7.90, "Lemon sachet"))
        personal_care.add_product(Product("Predo Adult Diapers 30s (M/L/XL)", 317.99, "Adult diapers"))
        personal_care.add_product(Product("Ingram's Camphor Moisture Plus 500ml", 59.99, "Moisturizing cream"))
        personal_care.add_product(Product("Disposable Face Mask 50s", 39.99, "Face masks"))
        self.add_category(personal_care)
        
        # Snacks and Sweets
        snacks = Category("Snacks and Sweets")
        snacks.add_product(Product("Jena Maputi 15pack", 23.99, "Popcorn"))
        snacks.add_product(Product("Tiggies Assorted 50s", 74.99, "Snacks"))
        snacks.add_product(Product("L Choice Assorted Biscuits", 12.90, "Biscuits"))
        snacks.add_product(Product("Sneaker Nax Bale Pack 2kg", 39.90, "Snacks"))
        snacks.add_product(Product("Yogueta Lollipop Split Pack 48 Pack", 59.99, "Lollipops"))
        snacks.add_product(Product("Arenel Choice Assorted Biscuits 150g", 19.90, "Biscuits"))
        snacks.add_product(Product("Willards Things 150g", 14.99, "Cheese snacks"))
        snacks.add_product(Product("Stumbo Assorted Lollipops 48s", 59.99, "Lollipops"))
        snacks.add_product(Product("Pringles Original 110g", 22.90, "Potato chips"))
        snacks.add_product(Product("Nibble Naks 20pack", 29.99, "Snacks"))
        snacks.add_product(Product("King Kurls Chicken Flavour 100g", 12.90, "Snacks"))
        snacks.add_product(Product("Nik Naks 50s Pack Assorted", 54.90, "Snacks"))
        snacks.add_product(Product("Proton Ramba Waraira Cookies 1 kg", 68.99, "Cookies"))
        snacks.add_product(Product("Lobels Marie Biscuits", 6.90, "Biscuits"))
        snacks.add_product(Product("Chocolate Coated Biscuits", 35.99, "Chocolate biscuits"))
        snacks.add_product(Product("Top 10 Assorted Sweets", 9.90, "Assorted sweets"))
        snacks.add_product(Product("Jelido Magic Rings 102 Pieces", 48.90, "Candy rings"))
        snacks.add_product(Product("Lays Assorted Flavours 105g", 52.99, "Potato chips"))
        snacks.add_product(Product("Charhons Biscuits 2kg", 99.99, "Biscuits"))
        snacks.add_product(Product("Zap Nax Cheese and Onion 100g", 3.99, "Snacks"))
        self.add_category(snacks)
        
        # Fresh Groceries
        fresh = Category("Fresh Groceries")
        fresh.add_product(Product("Economy Steak on Bone Beef Cuts 1kg", 147.99, "Fresh beef"))
        fresh.add_product(Product("Parmalat Cheddar Cheese", 89.99, "Cheddar cheese slices"))
        fresh.add_product(Product("Colcom Beef Polony 3kg", 299.00, "Beef polony"))
        fresh.add_product(Product("Colcom Tastee French Polony 750g", 116.99, "French polony"))
        fresh.add_product(Product("Colcom Chicken Polony 3kg", 219.90, "Chicken polony"))
        fresh.add_product(Product("Bulk Mixed Pork 1kg", 128.99, "Mixed pork"))
        fresh.add_product(Product("Potatoes 7.5kg (Small Pocket)", 219.99, "Fresh potatoes"))
        fresh.add_product(Product("Colcom Tastee Chicken Polony 1kg", 34.90, "Chicken polony"))
        fresh.add_product(Product("Colcom Garlic Polony 3kg", 220.00, "Garlic polony"))
        fresh.add_product(Product("Colcom Tastee Beef Polony 1kg", 35.00, "Beef polony"))
        fresh.add_product(Product("Wrapped Mixed Size Fresh Eggs 30", 149.99, "Fresh eggs"))
        fresh.add_product(Product("Texas Meats Juicy Boerewors", 159.99, "Boerewors"))
        fresh.add_product(Product("Unwrapped Small Size Fresh Eggs 30s", 99.99, "Fresh eggs"))
        fresh.add_product(Product("Irvines Mixed Chicken Cuts 2kg", 179.99, "Mixed chicken cuts"))
        fresh.add_product(Product("Dairibord Yoghurt 150ml", 15.99, "Yoghurt"))
        self.add_category(fresh)
        
        # Stationery
        stationery = Category("Stationery")
        stationery.add_product(Product("Plastic Cover 3 Meter Roll", 7.99, "Plastic cover"))
        stationery.add_product(Product("Ruler 30cm", 6.99, "Ruler"))
        stationery.add_product(Product("A4 Bond Paper White", 126.99, "Bond paper"))
        stationery.add_product(Product("Kakhi Cover 3 Meter Roll", 8.99, "Kakhi cover"))
        stationery.add_product(Product("School Trunk", 750.00, "School trunk"))
        stationery.add_product(Product("Oxford Maths Set", 34.99, "Maths set"))
        stationery.add_product(Product("Grade 1-3 Exercise Book A4 32 Page (10 Pack)", 36.99, "Exercise books"))
        stationery.add_product(Product("72 Page Newsprint Maths Book (10 Pack)", 69.99, "Maths books"))
        stationery.add_product(Product("Cellotape Large 40yard", 5.99, "Cellotape"))
        stationery.add_product(Product("Newsprint 2 Quire Counter Books (192 Page)", 28.99, "Counter books"))
        stationery.add_product(Product("72 Page Newsprint Writing Exercise Book (10 Pack)", 69.99, "Writing exercise books"))
        stationery.add_product(Product("Cellotape Small 20yard", 3.99, "Cellotape"))
        stationery.add_product(Product("Eversharp Pens Set x 4", 14.99, "Pens set"))
        stationery.add_product(Product("Newsprint 1 Quire (96 Page) Counter Book", 17.99, "Counter book"))
        stationery.add_product(Product("HB Pencils x 12 Set", 24.99, "Pencils set"))
        stationery.add_product(Product("Sharp Scientific Calculator", 319.99, "Scientific calculator"))
        stationery.add_product(Product("32 Page Newsprint Plain Exercise Book (10 Pack)", 36.99, "Plain exercise books"))
        self.add_category(stationery)
        
        # Baby Section
        baby_section = Category("Baby Section")
        baby_section.add_product(Product("Huggies Dry Comfort Jumbo Size 5 (44s)", 299.99, "Diapers"))
        baby_section.add_product(Product("Pampers Fresh Clean Wipes 64 Pack", 31.90, "Baby wipes"))
        baby_section.add_product(Product("Johnson and Johnson Scented Baby Jelly 325ml", 52.99, "Baby jelly"))
        baby_section.add_product(Product("Vaseline Baby Jelly 250g", 31.90, "Baby jelly"))
        baby_section.add_product(Product("Predo Baby Wipes Assorted 120s", 52.90, "Baby wipes"))
        baby_section.add_product(Product("Huggies Dry Comfort Size 3 Jumbo (76)", 299.99, "Diapers"))
        baby_section.add_product(Product("Huggies Dry Comfort Size 2 Jumbo (94)", 299.99, "Diapers"))
        baby_section.add_product(Product("Huggies Dry Comfort Size 4 Jumbo", 299.99, "Diapers"))
        baby_section.add_product(Product("Bennetts Aqueous Cream 500ml", 39.30, "Aqueous cream"))
        baby_section.add_product(Product("Predo Baby Wipes Assorted 80s", 38.99, "Baby wipes"))
        baby_section.add_product(Product("Crez Babyline Petroleum Jelly 500g", 42.99, "Petroleum jelly"))
        baby_section.add_product(Product("Johnson and Johnson Lightly Fragranced Aqueous Cream 350ml", 39.90, "Aqueous cream"))
        baby_section.add_product(Product("Nestle Baby Cereal with Milk Regular Wheat 250g", 34.99, "Baby cereal"))
        baby_section.add_product(Product("Nan 2: Infant Formula Optipro 400g", 79.99, "Infant formula"))
        baby_section.add_product(Product("Nan 1: Infant Formula Optipro 400g", 79.99, "Infant formula"))
        self.add_category(baby_section)


    def add_category(self, category):
        self.categories[category.name] = category

    def list_categories(self):
        return list(self.categories.keys())

    def list_products(self, category_name):
        return self.categories[category_name].products if category_name in self.categories else []

def send(content, sender, phone_id, type="text"):
    url = f"https://graph.facebook.com/v19.0/{phone_id}/messages"
    headers = {
        'Authorization': f'Bearer {wa_token}',
        'Content-Type': 'application/json'
    }
    data = {
        "messaging_product": "whatsapp",
        "to": sender,
        "type": type,
        type: {
            "body": content,
            **({"caption": content} if type != "text" else {})
        }
    }
    try:
        requests.post(url, headers=headers, json=data, timeout=10)
    except Exception:
        pass

def remove(*file_paths):
    for file in file_paths:
        if os.path.exists(file):
            os.remove(file)

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

    delivery_areas = {
        "Harare": 240,
        "Chitungwiza": 300,
        "Mabvuku": 300,
        "Ruwa": 300,
        "Domboshava": 250,
        "Southlea": 300,
        "Southview": 300,
        "Epworth": 300,
        "Mazoe": 300,
        "Chinhoyi": 350,
        "Banket": 350,
        "Rusape": 400,
        "Dema": 300
    }

    # ---- FIX: Only ONE send per prompt, combine messages where needed ----

    if step == "ask_name":
        send("Hello! Welcome to Zimbogrocer. What's your name?", sender, phone_id)
        user_data["step"] = "save_name"

    elif step == "save_name":
        user = User(prompt.title(), sender)
        user_data["user"] = user
        send(f"Thanks {user.payer_name}! Please select a category:\n{list_categories()}", sender, phone_id)
        user_data["step"] = "choose_category"

    elif step == "choose_category":
        if prompt.isalpha() and len(prompt) == 1:
            idx = ord(prompt.upper()) - 65
            categories = order_system.list_categories()
            if 0 <= idx < len(categories):
                cat = categories[idx]
                user_data["selected_category"] = cat
                send(f"Products in {cat}:\n{list_products(cat)}\nSelect a product by number.", sender, phone_id)
                user_data["step"] = "choose_product"
            else:
                send("Invalid category. Try again:\n" + list_categories(), sender, phone_id)
        else:
            send("Please enter a valid category letter (e.g., A, B, C).", sender, phone_id)

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
            send("Please enter a valid product number.", sender, phone_id)

    elif step == "ask_quantity":
        try:
            qty = int(prompt)
            prod = user_data["selected_product"]
            if qty < 1:
                raise ValueError
            user.add_to_cart(prod, qty)
            send("Item added to your cart.\nWhat would you like to do next?\n- View cart\n- Clear cart\n- Remove <item>\n- Add Item", sender, phone_id)
            user_data["step"] = "post_add_menu"
        except:
            send("Please enter a valid number for quantity (e.g., 1, 2, 3).", sender, phone_id)

    elif step == "post_add_menu":
        if prompt.lower() == "view cart":
            cart_message = show_cart(user)
            # FIX: Combine cart and next prompt into one message
            send(cart_message + "\n\nPlease select your delivery area:\n" + "\n".join([f"{k} - R{v:.2f}" for k, v in delivery_areas.items()]), sender, phone_id)
            user_data["step"] = "get_area"
        elif prompt.lower() == "clear cart":
            user.clear_cart()
            send("Cart cleared.\nWhat would you like to do next?\n- View cart\n- Add Item", sender, phone_id)
            user_data["step"] = "post_add_menu"
        elif prompt.lower().startswith("remove "):
            item = prompt[7:].strip()
            user.remove_from_cart(item)
            send(f"{item} removed from cart.\n{show_cart(user)}\nWhat would you like to do next?\n- View cart\n- Add Item", sender, phone_id)
            user_data["step"] = "post_add_menu"
        elif prompt.lower() in ["add", "add item", "add another", "add more"]:
            send("Sure! Here are the available categories:\n" + list_categories(), sender, phone_id)
            user_data["step"] = "choose_category"
        else:
            send("Sorry, I didn't understand. You can:\n- View Cart\n- Clear Cart\n- Remove <item>\n- Add Item", sender, phone_id)

    elif step == "get_area":
        area = prompt.strip().title()
        if area in delivery_areas:
            user.checkout_data["delivery_area"] = area
            fee = delivery_areas[area]
            user.checkout_data["delivery_fee"] = fee
            delivery_product = Product("__Delivery__", fee, f"Delivery to {area}")
            user.add_to_cart(delivery_product, 1)
            send(show_cart(user) + "\nWould you like to checkout? (yes/no)", sender, phone_id)
            user_data["step"] = "ask_checkout"
        else:
            area_list = "\n".join([f"{k} - R{v:.2f}" for k, v in delivery_areas.items()])
            send(f"Invalid area. Please choose from:\n{area_list}", sender, phone_id)

    elif step == "ask_checkout":
        if prompt.lower() in ["yes", "y"]:
            send("Please enter the receiver’s full name.", sender, phone_id)
            user_data["step"] = "get_receiver_name"
        elif prompt.lower() in ["no", "n"]:
            send("What would you like to do next?\n- View cart\n- Clear cart\n- Remove <item>\n- Add Item", sender, phone_id)
            user_data["step"] = "post_add_menu"
        else:
            send("Please respond with 'yes' or 'no'.", sender, phone_id)

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
        confirm_message = (f"Please confirm the details below:\n\n"
            f"Name: {details['receiver_name']}\n"
            f"Address: {details['address']}\n"
            f"ID: {details['id_number']}\n"
            f"Phone: {details['phone']}\n\n"
            "Are these correct? (yes/no)")
        send(confirm_message, sender, phone_id)
        user_data["step"] = "confirm_details"

    elif step == "confirm_details":
        if prompt.lower() in ["yes", "y"]:
            order_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            payment_info = (
                f"Please make payment using one of the following options:\n\n"
                f"1. EFT\nBank: FNB\nName: Zimbogrocer (Pty) Ltd\nAccount: 62847698167\nBranch Code: 250655\nSwift Code: FIRNZAJJ\nReference: {order_id}\nPlease remember to send the Proof of Payment as soon as you make payment. Have a nice day.\n\n"
                f"2. Pay at supermarkets: SHOPRITE/CHECKERS/USAVE/PICK N PAY/ GAME/ MAKRO/ SPAR using Mukuru wicode\n"
                f"3. World Remit Transfer (payment details provided upon request)\n"
                f"4. Western Union ( payment details provided upon request)\n"
                f"Order ID: {order_id}"
            )
            send(
                f"Order placed! 🛒\nOrder ID: {order_id}\n\n{show_cart(user)}\n\n"
                f"Receiver: {user.checkout_data['receiver_name']}\n"
                f"Address: {user.checkout_data['address']}\n"
                f"Phone: {user.checkout_data['phone']}\n\n"
                f"{payment_info}\nWould you like to place another order? (yes/no)", sender, phone_id
            )
            user.clear_cart()
            user_data["step"] = "ask_place_another_order"
        else:
            send("Okay, let's correct the details. What's the receiver’s full name?", sender, phone_id)
            user_data["step"] = "get_receiver_name"

    elif step == "ask_place_another_order":
        if prompt.lower() in ["yes", "y"]:
            send("Great! Please select a category:\n" + list_categories(), sender, phone_id)
            user_data["step"] = "choose_category"
        else:
            send("Okay. Have a good day! 😊", sender, phone_id)
            user_data["step"] = "ask_name"

    # Persist user states after each message
    user_states[sender] = user_data
    save_user_states(user_states)

if __name__ == "__main__":
    app.run(debug=True, port=8000)
