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
    current = get_user_state(phone_number)  # Load existing state
    current.update(updates)                 # Merge changes
    current['phone_number'] = phone_number
    if 'sender' not in current:
        current['sender'] = phone_number
    redis_client.setex(f"user_state:{phone_number}", 86400, json.dumps(current))


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
    send("Hello! Welcome to Zimbogrocer. What's your full name? e.g Mildred Moyo", user_data['sender'], phone_id)
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
        f"Hie {user.payer_name}! Here are products from *{first_category}*:\n"
        f"{first_products}\n\n"
        f"If you're done shopping in the *{first_category}* category.\n"
        "Type 'more' to see the next category.",
        user_data['sender'], phone_id
    )


    return {'step': 'choose_product', 'user': user.to_dict()}



def handle_next_category(user_data, phone_id):
    if 'category_names' not in user_data or 'current_category_index' not in user_data:
        send("Something went wrong. Please start again or type 'menu'.", user_data['sender'], phone_id)
        return {'step': 'choose_product'}

    user = User.from_dict(user_data['user'])

    category_names = user_data['category_names']
    current_index = user_data['current_category_index']
    next_index = current_index + 1

    if next_index >= len(category_names):
        send("No more categories. You can now select a product or type 'menu' to go back.",
             user_data['sender'], phone_id)
        return {
            'step': 'choose_product',
            'user': user.to_dict(),
            'category_names': category_names,
            'current_category_index': current_index
        }

    order_system = OrderSystem()
    categories_products = order_system.get_products_by_category()
    next_category = category_names[next_index]
    next_products = categories_products.get(next_category, "No products found.")

    # Update user state in Redis
    update_user_state(user_data['sender'], {
        'step': 'choose_product',
        'user': user.to_dict(),
        'category_names': category_names,
        'current_category_index': next_index
    })

    send(
        f"Here are products from *{next_category}*:\n"
        f"{next_products}\n\n"
        f"If you're done shopping in the *{next_category}* category.\n"
        "Type 'more' to see the next category.",
        user_data['sender'], phone_id
    )


    return {
        'step': 'choose_product',
        'user': user.to_dict(),
        'category_names': category_names,
        'current_category_index': next_index
    }


def handle_choose_product(prompt, user_data, phone_id):
    try:
        index = int(prompt) - 1
        if index < 0:
            raise ValueError

        # ✅ Get current category from state
        category_names = user_data.get("category_names", [])
        current_index = user_data.get("current_category_index", 0)

        if not category_names or current_index >= len(category_names):
            send("Your session expired. Please type '4' to add an item again.", user_data['sender'], phone_id)
            return {'step': 'choose_product'}

        current_category = category_names[current_index]
        order_system = OrderSystem()
        products = order_system.list_products(current_category)

        if index < len(products):
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
    send('''Item added to your cart.
What would you like to do next?
1. View cart
2. Clear cart
3. Remove <item>
4. Add Item''', user_data['sender'], phone_id)
    return {'step': 'post_add_menu', 'user': user.to_dict()}
    
    
def handle_post_add_menu(prompt, user_data, phone_id):
    user = User.from_dict(user_data['user'])
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
    
   
    if prompt.lower() in ["view", "view cart", "1"]:   
        cart_message = show_cart(user)
        update_user_state(user_data['sender'], {
            'step': 'get_area',
            'delivery_areas': delivery_areas
        })
        send(cart_message + "\n\nPlease select your delivery area:\n" + list_delivery_areas(delivery_areas), user_data['sender'], phone_id)
        return {
            'step': 'get_area',
            'delivery_areas': delivery_areas,
            'user': user.to_dict()
        }

    elif prompt.lower() in ["clear", "clear cart", "2"]:    
        user.clear_cart()
        update_user_state(user_data['sender'], {
            'user': user.to_dict(),
            'step': 'post_add_menu'
        })
        send("Cart cleared.\nWhat would you like to do next?\n1 View cart\n4 Add Item", user_data['sender'], phone_id)
        return {
            'step': 'post_add_menu',
            'user': user.to_dict()
        }
    elif prompt.lower() in ["remove", "3"]:     
        item = prompt[7:].strip()
        user.remove_from_cart(item)
        update_user_state(user_data['sender'], {
            'user': user.to_dict(),
            'step': 'post_add_menu'
        })
        send(f"{item} removed from cart.\n{show_cart(user)}\nWhat would you like to do next?\n1 View cart\n4 Add Item", user_data['sender'], phone_id)
        return {
            'step': 'post_add_menu',
            'user': user.to_dict()
        }
    elif prompt.lower() in ["add", "add item", "add another", "add more", "4"]:
        order_system = OrderSystem()
        categories_products = order_system.get_products_by_category()
        
        # 🧠 Try to continue from previous state
        category_names = user_data.get("category_names") or list(categories_products.keys())
        current_index = user_data.get("current_category_index", 0)
        
        # Prevent out-of-range errors
        if current_index >= len(category_names):
            current_index = 0
        
        current_category = category_names[current_index]
        first_products = categories_products.get(current_category, "No products found.")

        update_user_state(user_data['sender'], {
            'step': 'choose_product',
            'user': user.to_dict(),
            'category_names': category_names,
            'current_category_index': current_index
        })
    
        send(
            f"Sure! Here are products from *{current_category}*:\n"
            f"{first_products}\n\n"
            f"If you're done shopping in the *{current_category}* category.\n"
            "Type 'more' to see the next category.",
            user_data['sender'],
            phone_id
        )

    
        return {
            'step': 'choose_product',
            'user': user.to_dict()
        }

def handle_get_area(prompt, user_data, phone_id):
    user = User.from_dict(user_data['user'])
    delivery_areas = user_data['delivery_areas']
    area = prompt.strip().title()

    if area.lower() == "harare":
        send("Would you like to *pick up* or *have it delivered*?", user_data['sender'], phone_id)
        update_user_state(user_data['sender'], {
            'user': user.to_dict(),
            'step': 'choose_delivery_or_pickup',
            'area': area
        })
        return {
            'step': 'choose_delivery_or_pickup',
            'user': user.to_dict()
        }

    elif area in delivery_areas:
        user.checkout_data["delivery_area"] = area
        fee = delivery_areas[area]
        user.checkout_data["delivery_fee"] = fee
        delivery_product = Product(f"Delivery to {area}", fee, "Delivery fee")
        user.add_to_cart(delivery_product, 1)

        update_user_state(user_data['sender'], {
            'user': user.to_dict(),
            'step': 'ask_checkout'
        })

        send(f"{show_cart(user)}\nWould you like to checkout? (yes/no)", user_data['sender'], phone_id)
        return {
            'step': 'ask_checkout',
            'user': user.to_dict()
        }

    else:
        send(f"Invalid area. Please choose from:\n{list_delivery_areas(delivery_areas)}", user_data['sender'], phone_id)
        return {
            'step': 'get_area',
            'delivery_areas': delivery_areas,
            'user': user.to_dict()
        }

def handle_choose_delivery_or_pickup(prompt, user_data, phone_id):
    user = User.from_dict(user_data['user'])
    choice = prompt.strip().lower()

    if choice in ['pickup', 'pick up']:
        update_user_state(user_data['sender'], {
            'user': user.to_dict(),
            'step': 'get_receiver_name_pickup',
            'delivery_type': 'pickup',
            'area': 'Harare'
        })
        send("What's the full name of the receiver?", user_data['sender'], phone_id)
        return {
            'step': 'get_receiver_name_pickup',
            'user': user.to_dict()
        }

    elif choice in ['delivery', 'deliver']:
        user.checkout_data['area'] = 'Harare'
        update_user_state(user_data['sender'], {
            'user': user.to_dict(),
            'step': 'get_receiver_name',
            'delivery_type': 'delivery',
            'area': 'Harare'
        })
        send("What's the full name of the receiver?", user_data['sender'], phone_id)
        return {
            'step': 'get_receiver_name',
            'user': user.to_dict()
        }

    send("Please reply with *pickup* or *delivery*.", user_data['sender'], phone_id)
    return {
        'step': 'choose_delivery_or_pickup',
        'user': user.to_dict()
    }

def handle_get_receiver_name_pickup(prompt, user_data, phone_id):
    user = User.from_dict(user_data['user'])
    user.checkout_data['receiver_name'] = prompt.strip()

    update_user_state(user_data['sender'], {
        'user': user.to_dict(),
        'step': 'get_id_pickup'
    })
    send("Please provide the receiver's ID number.", user_data['sender'], phone_id)
    return {
        'step': 'get_id_pickup',
        'user': user.to_dict()
    }


def handle_get_id_pickup(prompt, user_data, phone_id):
    user = User.from_dict(user_data['user'])
    user.checkout_data['receiver_id'] = prompt.strip()

    # Send pickup address and proceed to payment
    send(
        "Thanks! Please collect your order at:\n"
        "*123 Main Street, Harare CBD*\n"
        "Hours: 8am - 5pm, Mon-Sat.\n\n"
        "Now let's choose a payment method.",
        user_data['sender'], phone_id
    )

    payment_prompt = (
        "Please select a payment method:\n"
        "1. EFT\n"
        "2. Pay at SHOPRITE/CHECKERS/USAVE/PICK N PAY/ GAME/ MAKRO/ SPAR using Mukuru wicode\n"
        "3. World Remit\n"
        "4. Western Union\n"
        "5. Mukuru Direct Transfer (DETAILS PROVIDED UPON REQUEST)"
    )
    send(payment_prompt, user_data['sender'], phone_id)

    update_user_state(user_data['sender'], {
        'user': user.to_dict(),
        'step': 'await_payment_selection'
    })

    return {
        'step': 'await_payment_selection',
        'user': user.to_dict()
    }

    
    if user.checkout_data.get("delivery_method") == "pickup":
        send("Pickup Address:\n42A Mbuya Nehanda St, Harare\nMon–Fri, 9am–5pm", user_data['sender'], phone_id)

        # Proceed to payment options
        payment_prompt = (
            "Please select a payment method:\n"
            "1. EFT\n"
            "2. Pay at SHOPRITE/CHECKERS/USAVE/PICK N PAY/ GAME/ MAKRO/ SPAR using Mukuru wicode\n"
            "3. World Remit\n"
            "4. Western Union\n"
            "5. Mukuru Direct Transfer (DETAILS PROVIDED UPON REQUEST)"
        )
        send(payment_prompt, user_data['sender'], phone_id)

        update_user_state(user_data['sender'], {
            'user': user.to_dict(),
            'step': 'await_payment_selection'
        })
        return {
            'step': 'await_payment_selection',
            'user': user.to_dict()
        }

    else:
        # Proceed to get phone for delivery flow
        update_user_state(user_data['sender'], {
            'user': user.to_dict(),
            'step': 'get_phone'
        })
        send("Please provide the receiver's phone number.", user_data['sender'], phone_id)
        return {
            'step': 'get_phone',
            'user': user.to_dict()
        }


def handle_ask_checkout(prompt, user_data, phone_id):
    user = User.from_dict(user_data['user'])
    
    if prompt.lower() in ["yes", "y"]:
        update_user_state(user_data['sender'], {'step': 'get_receiver_name'})
        send("Please enter the receiver's full name as on national ID.", user_data['sender'], phone_id)
        return {'step': 'get_receiver_name', 'user': user.to_dict()}
    elif prompt.lower() in ["no", "n"]:
        # Remove delivery fee if added
        user.remove_from_cart("Delivery to")
        update_user_state(user_data['sender'], {
            'user': user.to_dict(),
            'step': 'post_add_menu'
        })
        send("What would you like to do next?\n1 View cart\n2 Clear cart\n3 Remove <item>\n4 Add Item", user_data['sender'], phone_id)
        return {'step': 'post_add_menu', 'user': user.to_dict()}
    else:
        send("Please respond with 'yes' or 'no'.", user_data['sender'], phone_id)
        return {'step': 'ask_checkout', 'user': user.to_dict()}

def handle_get_receiver_name(prompt, user_data, phone_id):
    user = User.from_dict(user_data['user'])
    user.checkout_data["receiver_name"] = prompt
    update_user_state(user_data['sender'], {
        'user': user.to_dict(),
        'step': 'get_address'
    })
    send("Enter the delivery address.", user_data['sender'], phone_id)
    return {
        'step': 'get_address',
        'user': user.to_dict()
    }

def handle_get_address(prompt, user_data, phone_id):
    user = User.from_dict(user_data['user'])
    user.checkout_data["address"] = prompt
    update_user_state(user_data['sender'], {
        'user': user.to_dict(),
        'step': 'get_id'
    })
    send("Enter receiver's ID number.", user_data['sender'], phone_id)
    return {
        'step': 'get_id',
        'user': user.to_dict()
    }

def handle_get_id(prompt, user_data, phone_id):
    user = User.from_dict(user_data['user'])
    user.checkout_data["receiver_id"] = prompt
    update_user_state(user_data['sender'], {
        'user': user.to_dict(),
        'step': 'get_phone'
    })
    send("Enter receiver's phone number.", user_data['sender'], phone_id)
    return {
        'step': 'get_phone',
        'user': user.to_dict()
    }

def handle_get_phone(prompt, user_data, phone_id):
    user = User.from_dict(user_data['user'])
    user.checkout_data["phone"] = prompt
    details = user.checkout_data
    confirm_message = (
        f"Please confirm the details below:\n\n"
        f"Name: {details['receiver_name']}\n"
        f"Address: {user.checkout_data.get('address', 'N/A')}\n"
        f"ID: {details['receiver_id']}\n"
        f"Phone: {details['phone']}\n\n"
        "Are these correct? (yes/no)"
    )
    update_user_state(user_data['sender'], {
        'user': user.to_dict(),
        'step': 'confirm_details'
    })
    send(confirm_message, user_data['sender'], phone_id)
    return {
        'step': 'confirm_details',
        'user': user.to_dict()
    }

def handle_confirm_details(prompt, user_data, phone_id):
    user = User.from_dict(user_data['user'])

    if prompt.lower() in ["yes", "y"]:
        # Ask the user to select a payment method
        payment_prompt = (
            "Please select a payment method:\n"
            "1. EFT\n"
            "2. Pay at SHOPRITE/CHECKERS/USAVE/PICK N PAY/ GAME/ MAKRO/ SPAR using Mukuru wicode\n"
            "3. World Remit\n"
            "4. Western Union\n"
            "5. Mukuru Direct Transfer (DETAILS PROVIDED UPON REQUEST)"
        )
        send(payment_prompt, user_data['sender'], phone_id)

        # Update state to wait for payment method selection
        update_user_state(user_data['sender'], {
            'user': user.to_dict(),
            'step': 'await_payment_selection'
        })

        return {
            'step': 'await_payment_selection',
            'user': user.to_dict()
        }


def handle_payment_selection(selection, user_data, phone_id):
    user = User.from_dict(user_data['user'])
    order_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

    # Map selection to payment method
    payment_methods = {
        "1": (
            "EFT\nBank: FNB\nName: Zimbogrocer (Pty) Ltd\n"
            "Account: 62847698167\nBranch Code: 250655\n"
            "Swift Code: FIRNZAJJ\nReference: " + order_id
        ),
        "2": "Pay at SHOPRITE/CHECKERS/USAVE/PICK N PAY/ GAME/ MAKRO/ SPAR using Mukuru wicode",
        "3": "World Remit Transfer (details provided upon request)",
        "4": "Western Union (details provided upon request)",
        "5": "Mukuru Direct Transfer (DETAILS PROVIDED UPON REQUEST)"
    }

    payment_text = payment_methods.get(selection)
    if payment_text:
        # Save order to DB
        order_data = {
            'order_id': order_id,
            'user_data': user.to_dict(),
            'timestamp': datetime.now(),
            'status': 'pending',
            'total_amount': user.get_cart_total()
        }
        orders_collection.insert_one(order_data)
    
        # Notify owner
        owner_message = (
            f"New Order #{order_id}\n"
            f"From: {user.payer_name} ({user.payer_phone})\n"
            f"Receiver: {user.checkout_data['receiver_name']}\n"
            f"ID: {user.checkout_data['receiver_id']}\n"
            f"Address: {user.checkout_data.get('address', 'N/A')}\n"
            f"Phone: {user.checkout_data.get('phone', 'N/A')}\n"
            f"Payment Method: {payment_text}\n\n"
            f"Items:\n{show_cart(user)}"
        )
        send(owner_message, owner_phone, phone_id)
    
        # Send confirmation to user
        send(
            f"Order placed! 🛒\nOrder ID: {order_id}\n\n"
            f"{show_cart(user)}\n\n"
            f"Receiver: {user.checkout_data['receiver_name']}\n"
            f"ID: {user.checkout_data['receiver_id']}\n"
            f"Address: {user.checkout_data.get('address', 'N/A')}\n"
            f"Phone: {user.checkout_data.get('phone', 'N/A')}\n\n"
            f"Payment Method: {payment_text}\n\n"
            f"Would you like to place another order? (yes/no)",
            user_data['sender'], phone_id
        )

        # Save the message to Redis
        message_key = f"user_message:{order_id}"
        redis_client.setex(message_key, user_message)  
    
        # Clear cart and update state
        user.clear_cart()
        update_user_state(user_data['sender'], {
            'user': user.to_dict(),
            'step': 'ask_place_another_order'
        })
    
        return {
            'step': 'ask_place_another_order',
            'user': user.to_dict()
        }
    
    else:
        send("Invalid selection. Please enter a number between 1 and 5.", user_data['sender'], phone_id)
        update_user_state(user_data['sender'], {
            'user': user.to_dict(),
            'step': 'await_payment_selection'
        })
        return {
            'step': 'await_payment_selection',
            'user': user.to_dict()
        }


def handle_ask_place_another_order(prompt, user_data, phone_id):
    if prompt.lower() in ["yes", "y"]:
        update_user_state(user_data['sender'], {'step': 'choose_category'})
        send("Great! Please select a category:\n" + list_categories(), user_data['sender'], phone_id)
        return {'step': 'choose_category'}
    else:
        update_user_state(user_data['sender'], {'step': 'ask_name'})
        send("Thank you for shopping with us! Have a good day! 😊", user_data['sender'], phone_id)
        return {'step': 'ask_name'}

def handle_default(prompt, user_data, phone_id):
    send("Sorry, I didn't understand that. Please try again.", user_data['sender'], phone_id)
    return {'step': user_data.get('step', 'ask_name')}


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

    # ✅ Safe fallback
    step = user_state.get('step') or 'ask_name'
    updated_state = get_action(step, prompt, user_state, phone_id)
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
