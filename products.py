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
