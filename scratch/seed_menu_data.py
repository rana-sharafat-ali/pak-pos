import os
import sys
from pathlib import Path
from decimal import Decimal

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pakpos_project.settings')
import django
django.setup()

from pakpos_project.apps.products.models import Category, Product, ProductVariant

# Clear existing if any
ProductVariant.objects.all().delete()
Product.objects.all().delete()
Category.objects.all().delete()

categories_data = [
    {
        "name": "Pizza & Crusts",
        "icon": "🍕",
        "description": "Stone-baked Italian crusts, stuffed crusts, and traditional Pakistani spicy pizzas.",
    },
    {
        "name": "Burgers & Sandwiches",
        "icon": "🍔",
        "description": "Juicy smashed beef patties, crispy zinger chicken, and gourmet club sandwiches.",
    },
    {
        "name": "BBQ & Grills",
        "icon": "🍢",
        "description": "Charcoal grilled tikka, seekh kababs, malai boti, and sizzling platters.",
    },
    {
        "name": "Fried Chicken & Wings",
        "icon": "🍗",
        "description": "Crispy golden fried broast, hot wings, and tenders.",
    },
    {
        "name": "Karahi & Handi",
        "icon": "🥘",
        "description": "Authentic desi chicken and mutton karahi, boneless handi, and rich gravies.",
    },
    {
        "name": "Pasta & Lasagna",
        "icon": "🍝",
        "description": "Creamy fettuccine alfredo, baked penne arrabbiata, and layered beef lasagna.",
    },
    {
        "name": "Wraps & Shawarma",
        "icon": "🌯",
        "description": "Authentic Arabian garlic mayo shawarmas and loaded tortilla wraps.",
    },
    {
        "name": "Appetizers & Fries",
        "icon": "🍟",
        "description": "Loaded cheese fries, mozzarella sticks, garlic bread, and onion rings.",
    },
    {
        "name": "Beverages & Shakes",
        "icon": "🥤",
        "description": "Chilled soft drinks, fresh lime, mint margaritas, and thick ice cream shakes.",
    },
    {
        "name": "Desserts & Ice Cream",
        "icon": "🍰",
        "description": "Warm molten lava cake, New York cheesecake, and artisan ice cream scoops.",
    },
]

cats = {}
for c_data in categories_data:
    cat = Category.objects.create(**c_data)
    cats[cat.name] = cat

products_data = [
    # --- 1. Pizza & Crusts (10 Pizzas with Small, Medium, Large sizes) ---
    {
        "name": "Chicken Tikka Pizza",
        "category": "Pizza & Crusts",
        "has_variants": True,
        "description": "Tender chicken tikka chunks, sweet onions, mozzarella cheese, and signature tomato sauce.",
        "variants": [
            ("Small", Decimal("650.00"), Decimal("380.00")),
            ("Medium", Decimal("1250.00"), Decimal("700.00")),
            ("Large", Decimal("1750.00"), Decimal("950.00")),
        ]
    },
    {
        "name": "Chicken Fajita Pizza",
        "category": "Pizza & Crusts",
        "has_variants": True,
        "description": "Spicy fajita chicken, crunchy bell peppers, onions, black olives, and melted mozzarella.",
        "variants": [
            ("Small", Decimal("690.00"), Decimal("400.00")),
            ("Medium", Decimal("1290.00"), Decimal("720.00")),
            ("Large", Decimal("1850.00"), Decimal("990.00")),
        ]
    },
    {
        "name": "Creamy Malai Boti Pizza",
        "category": "Pizza & Crusts",
        "has_variants": True,
        "description": "Rich creamy white sauce, tender malai boti pieces, mushrooms, and jalapeños.",
        "variants": [
            ("Small", Decimal("750.00"), Decimal("420.00")),
            ("Medium", Decimal("1390.00"), Decimal("780.00")),
            ("Large", Decimal("1950.00"), Decimal("1050.00")),
        ]
    },
    {
        "name": "Crown Crust Supreme Pizza",
        "category": "Pizza & Crusts",
        "has_variants": True,
        "description": "Golden cheese kabab stuffed crown crust, loaded with smoked chicken, beef pepperoni, and olives.",
        "variants": [
            ("Medium", Decimal("1550.00"), Decimal("850.00")),
            ("Large", Decimal("2150.00"), Decimal("1150.00")),
        ]
    },
    {
        "name": "Cheese Lover Margherita",
        "category": "Pizza & Crusts",
        "has_variants": True,
        "description": "Triple layer of pure mozzarella, gouda, fresh basil leaves, and herb tomato sauce.",
        "variants": [
            ("Small", Decimal("590.00"), Decimal("320.00")),
            ("Medium", Decimal("1090.00"), Decimal("580.00")),
            ("Large", Decimal("1590.00"), Decimal("820.00")),
        ]
    },
    {
        "name": "Smoky BBQ Chicken Pizza",
        "category": "Pizza & Crusts",
        "has_variants": True,
        "description": "Mesquite BBQ glazed chicken, red onions, sweet corn, and blend of cheddar and mozzarella.",
        "variants": [
            ("Small", Decimal("720.00"), Decimal("410.00")),
            ("Medium", Decimal("1350.00"), Decimal("740.00")),
            ("Large", Decimal("1890.00"), Decimal("1020.00")),
        ]
    },
    {
        "name": "Spicy Rancher Pizza",
        "category": "Pizza & Crusts",
        "has_variants": True,
        "description": "Crispy chicken bites, jalapeño slices, drizzled with zesty buttermilk ranch sauce.",
        "variants": [
            ("Small", Decimal("750.00"), Decimal("430.00")),
            ("Medium", Decimal("1390.00"), Decimal("760.00")),
            ("Large", Decimal("1950.00"), Decimal("1060.00")),
        ]
    },
    {
        "name": "Beef Pepperoni Passion",
        "category": "Pizza & Crusts",
        "has_variants": True,
        "description": "Generously topped with premium spicy cured beef pepperoni and extra cheese.",
        "variants": [
            ("Small", Decimal("790.00"), Decimal("450.00")),
            ("Medium", Decimal("1450.00"), Decimal("800.00")),
            ("Large", Decimal("2050.00"), Decimal("1100.00")),
        ]
    },
    {
        "name": "Kababish Delight Pizza",
        "category": "Pizza & Crusts",
        "has_variants": True,
        "description": "Mughlai seekh kabab pieces, green chilies, coriander, and desi spiced tomato sauce.",
        "variants": [
            ("Small", Decimal("720.00"), Decimal("400.00")),
            ("Medium", Decimal("1350.00"), Decimal("730.00")),
            ("Large", Decimal("1890.00"), Decimal("1010.00")),
        ]
    },
    {
        "name": "Vegetarian Garden Fresh",
        "category": "Pizza & Crusts",
        "has_variants": True,
        "description": "Fresh mushrooms, green peppers, black olives, onions, sweet corn, and ripe tomatoes.",
        "variants": [
            ("Small", Decimal("550.00"), Decimal("300.00")),
            ("Medium", Decimal("990.00"), Decimal("520.00")),
            ("Large", Decimal("1450.00"), Decimal("750.00")),
        ]
    },

    # --- 2. Burgers & Sandwiches (8 Burgers) ---
    {
        "name": "Classic Crispy Zinger Burger",
        "category": "Burgers & Sandwiches",
        "has_variants": False,
        "base_price": Decimal("520.00"),
        "cost_price": Decimal("290.00"),
        "stock_quantity": 80,
        "description": "Golden battered crispy chicken breast fillet with spicy secret mayo and fresh lettuce."
    },
    {
        "name": "Double Smash Beef Burger",
        "category": "Burgers & Sandwiches",
        "has_variants": False,
        "base_price": Decimal("850.00"),
        "cost_price": Decimal("480.00"),
        "stock_quantity": 50,
        "description": "Two seared Australian beef patties, double American cheddar cheese, caramelized onions, and house sauce."
    },
    {
        "name": "Mushroom Swiss Beef Burger",
        "category": "Burgers & Sandwiches",
        "has_variants": False,
        "base_price": Decimal("790.00"),
        "cost_price": Decimal("440.00"),
        "stock_quantity": 40,
        "description": "Flame grilled beef patty, sautéed button mushrooms, melted Swiss cheese, and garlic mayo."
    },
    {
        "name": "Spicy Jalapeño Crunch Burger",
        "category": "Burgers & Sandwiches",
        "has_variants": False,
        "base_price": Decimal("580.00"),
        "cost_price": Decimal("320.00"),
        "stock_quantity": 60,
        "description": "Crispy fried chicken fillet, spicy cheese sauce, sliced pickled jalapeños, and chipotle dip."
    },
    {
        "name": "Grilled Chicken Fillet Burger",
        "category": "Burgers & Sandwiches",
        "has_variants": False,
        "base_price": Decimal("550.00"),
        "cost_price": Decimal("300.00"),
        "stock_quantity": 50,
        "description": "Herb marinated charcoal grilled chicken breast with iceberg lettuce and light honey mustard."
    },
    {
        "name": "BBQ Smoky Bacon Beef Burger",
        "category": "Burgers & Sandwiches",
        "has_variants": False,
        "base_price": Decimal("890.00"),
        "cost_price": Decimal("510.00"),
        "stock_quantity": 35,
        "description": "Juicy beef patty, crispy beef bacon strips, smoky BBQ glaze, and cheddar cheese slice."
    },
    {
        "name": "Classic Club Sandwich",
        "category": "Burgers & Sandwiches",
        "has_variants": False,
        "base_price": Decimal("650.00"),
        "cost_price": Decimal("350.00"),
        "stock_quantity": 45,
        "description": "Triple decker toasted sandwich with pulled chicken, fried egg, cheese slice, lettuce, and cucumber."
    },
    {
        "name": "Grilled Panini Sandwich",
        "category": "Burgers & Sandwiches",
        "has_variants": False,
        "base_price": Decimal("590.00"),
        "cost_price": Decimal("310.00"),
        "stock_quantity": 40,
        "description": "Italian focaccia bread pressed with smoked chicken, mozzarella, sundried tomatoes, and pesto mayo."
    },

    # --- 3. BBQ & Grills (7 Items) ---
    {
        "name": "Chicken Tikka Boti",
        "category": "BBQ & Grills",
        "has_variants": True,
        "description": "Boneless chicken cubes marinated in red tikka spices and skewered over live charcoal.",
        "variants": [
            ("Half Plate (6 pcs)", Decimal("550.00"), Decimal("300.00")),
            ("Full Plate (12 pcs)", Decimal("990.00"), Decimal("540.00")),
        ]
    },
    {
        "name": "Chicken Malai Boti",
        "category": "BBQ & Grills",
        "has_variants": True,
        "description": "Melt-in-mouth chicken cubes marinated in rich fresh cream, cheese, cardamom, and mild spices.",
        "variants": [
            ("Half Plate (6 pcs)", Decimal("620.00"), Decimal("340.00")),
            ("Full Plate (12 pcs)", Decimal("1150.00"), Decimal("620.00")),
        ]
    },
    {
        "name": "Beef Seekh Kabab",
        "category": "BBQ & Grills",
        "has_variants": True,
        "description": "Minced beef blended with ginger, garlic, onions, green chili, and roasted cumin grilled on skewers.",
        "variants": [
            ("Half (2 Kababs)", Decimal("450.00"), Decimal("240.00")),
            ("Full (4 Kababs)", Decimal("850.00"), Decimal("450.00")),
        ]
    },
    {
        "name": "Chicken Reshmi Kabab",
        "category": "BBQ & Grills",
        "has_variants": True,
        "description": "Fine minced chicken infused with cream, saffron, and aromatic herbs.",
        "variants": [
            ("Half (2 Kababs)", Decimal("490.00"), Decimal("260.00")),
            ("Full (4 Kababs)", Decimal("920.00"), Decimal("490.00")),
        ]
    },
    {
        "name": "Mutton Chops BBQ (Sizzling)",
        "category": "BBQ & Grills",
        "has_variants": False,
        "base_price": Decimal("1650.00"),
        "cost_price": Decimal("1050.00"),
        "stock_quantity": 25,
        "description": "Prime mutton ribs marinated in raw papaya, mustard oil, and spices, served on sizzling onions."
    },
    {
        "name": "Chicken Tikka (Leg Piece)",
        "category": "BBQ & Grills",
        "has_variants": False,
        "base_price": Decimal("420.00"),
        "cost_price": Decimal("230.00"),
        "stock_quantity": 60,
        "description": "Full chicken leg piece seasoned in spicy Lahori masala and roasted over open fire."
    },
    {
        "name": "Chicken Tikka (Breast Piece)",
        "category": "BBQ & Grills",
        "has_variants": False,
        "base_price": Decimal("450.00"),
        "cost_price": Decimal("250.00"),
        "stock_quantity": 60,
        "description": "Full chicken breast piece cut with deep incisions and coated with red spice rub."
    },

    # --- 4. Fried Chicken & Wings (6 Items) ---
    {
        "name": "Crispy Broast Chicken",
        "category": "Fried Chicken & Wings",
        "has_variants": True,
        "description": "Deep-fried pressure cooked crispy chicken served with garlic mayo dip and golden fries.",
        "variants": [
            ("Quarter (2 pcs)", Decimal("480.00"), Decimal("270.00")),
            ("Half (4 pcs)", Decimal("920.00"), Decimal("510.00")),
            ("Full (8 pcs)", Decimal("1750.00"), Decimal("950.00")),
        ]
    },
    {
        "name": "Buffalo Hot Wings",
        "category": "Fried Chicken & Wings",
        "has_variants": True,
        "description": "Crispy fried wings tossed in authentic fiery cayenne pepper buffalo sauce.",
        "variants": [
            ("6 Pieces", Decimal("490.00"), Decimal("260.00")),
            ("12 Pieces", Decimal("890.00"), Decimal("480.00")),
        ]
    },
    {
        "name": "Honey Mustard Glazed Wings",
        "category": "Fried Chicken & Wings",
        "has_variants": True,
        "description": "Crispy chicken wings smothered in sweet honey, dijon mustard, and toasted sesame seeds.",
        "variants": [
            ("6 Pieces", Decimal("520.00"), Decimal("280.00")),
            ("12 Pieces", Decimal("950.00"), Decimal("510.00")),
        ]
    },
    {
        "name": "Crispy Chicken Tenders (5 pcs)",
        "category": "Fried Chicken & Wings",
        "has_variants": False,
        "base_price": Decimal("480.00"),
        "cost_price": Decimal("250.00"),
        "stock_quantity": 70,
        "description": "100% chicken breast strips seasoned, battered, and fried with honey mustard dip."
    },
    {
        "name": "Popcorn Chicken Bucket",
        "category": "Fried Chicken & Wings",
        "has_variants": False,
        "base_price": Decimal("450.00"),
        "cost_price": Decimal("220.00"),
        "stock_quantity": 80,
        "description": "Bite-sized seasoned chicken nuggets served piping hot with ketchup."
    },
    {
        "name": "Spicy Peri Peri Drumsticks (4 pcs)",
        "category": "Fried Chicken & Wings",
        "has_variants": False,
        "base_price": Decimal("590.00"),
        "cost_price": Decimal("320.00"),
        "stock_quantity": 40,
        "description": "Juicy chicken drumsticks fried and basted in hot African bird's eye peri peri sauce."
    },

    # --- 5. Karahi & Handi (6 Items) ---
    {
        "name": "Chicken Shinwari Karahi",
        "category": "Karahi & Handi",
        "has_variants": True,
        "description": "Authentic Peshawari style karahi prepared with tomatoes, green chilies, animal fat, and black pepper.",
        "variants": [
            ("Half KG", Decimal("950.00"), Decimal("550.00")),
            ("Full KG", Decimal("1790.00"), Decimal("990.00")),
        ]
    },
    {
        "name": "Chicken Makhni Handi (Boneless)",
        "category": "Karahi & Handi",
        "has_variants": True,
        "description": "Velvety smooth butter and cream gravy with tender boneless chicken cubes.",
        "variants": [
            ("Half Handi", Decimal("1100.00"), Decimal("620.00")),
            ("Full Handi", Decimal("2050.00"), Decimal("1150.00")),
        ]
    },
    {
        "name": "Chicken White Karahi",
        "category": "Karahi & Handi",
        "has_variants": True,
        "description": "Creamy white yogurt and cashew paste gravy seasoned with cumin and white pepper.",
        "variants": [
            ("Half KG", Decimal("1050.00"), Decimal("600.00")),
            ("Full KG", Decimal("1950.00"), Decimal("1080.00")),
        ]
    },
    {
        "name": "Mutton Desi Ghee Karahi",
        "category": "Karahi & Handi",
        "has_variants": True,
        "description": "Tender young goat meat cooked in pure desi ghee, fresh tomatoes, and ginger juliennes.",
        "variants": [
            ("Half KG", Decimal("1850.00"), Decimal("1150.00")),
            ("Full KG", Decimal("3500.00"), Decimal("2150.00")),
        ]
    },
    {
        "name": "Paneer Reshmi Handi",
        "category": "Karahi & Handi",
        "has_variants": True,
        "description": "Fresh cottage cheese cubes simmered in spiced tomato cashew cream gravy.",
        "variants": [
            ("Half Handi", Decimal("790.00"), Decimal("420.00")),
            ("Full Handi", Decimal("1450.00"), Decimal("780.00")),
        ]
    },
    {
        "name": "Chicken Achari Karahi",
        "category": "Karahi & Handi",
        "has_variants": True,
        "description": "Tangy pickled spices, mustard seeds, and whole red chilies cooked with chicken in a wok.",
        "variants": [
            ("Half KG", Decimal("980.00"), Decimal("560.00")),
            ("Full KG", Decimal("1850.00"), Decimal("1020.00")),
        ]
    },

    # --- 6. Pasta & Lasagna (5 Items) ---
    {
        "name": "Fettuccine Chicken Alfredo",
        "category": "Pasta & Lasagna",
        "has_variants": False,
        "base_price": Decimal("890.00"),
        "cost_price": Decimal("480.00"),
        "stock_quantity": 40,
        "description": "Egg fettuccine pasta in rich heavy parmesan cream sauce, topped with grilled chicken breast and parsley."
    },
    {
        "name": "Baked Beef Lasagna",
        "category": "Pasta & Lasagna",
        "has_variants": False,
        "base_price": Decimal("990.00"),
        "cost_price": Decimal("540.00"),
        "stock_quantity": 30,
        "description": "Layers of pasta sheets, minced beef ragù, creamy bechamel, and golden gratinated mozzarella cheese."
    },
    {
        "name": "Penne Arrabbiata (Spicy)",
        "category": "Pasta & Lasagna",
        "has_variants": False,
        "base_price": Decimal("750.00"),
        "cost_price": Decimal("380.00"),
        "stock_quantity": 40,
        "description": "Al dente penne pasta in fiery garlic, tomato, chili flakes sauce, finished with parmesan."
    },
    {
        "name": "Creamy Cajun Chicken Pasta",
        "category": "Pasta & Lasagna",
        "has_variants": False,
        "base_price": Decimal("920.00"),
        "cost_price": Decimal("510.00"),
        "stock_quantity": 35,
        "description": "Spicy cajun seasoned chicken, sautéed bell peppers, and penne tossed in spiced cream sauce."
    },
    {
        "name": "Mac & 4-Cheese Gratin",
        "category": "Pasta & Lasagna",
        "has_variants": False,
        "base_price": Decimal("690.00"),
        "cost_price": Decimal("360.00"),
        "stock_quantity": 45,
        "description": "Elbow macaroni enveloped in cheddar, mozzarella, gouda, and parmesan cheese sauce with herb breadcrumb crust."
    },

    # --- 7. Wraps & Shawarma (5 Items) ---
    {
        "name": "Arabian Chicken Shawarma",
        "category": "Wraps & Shawarma",
        "has_variants": False,
        "base_price": Decimal("320.00"),
        "cost_price": Decimal("160.00"),
        "stock_quantity": 90,
        "description": "Slow roasted vertical rotisserie chicken, garlic toum sauce, and pickled cucumbers wrapped in pita."
    },
    {
        "name": "Cheesy Mexican Burrito Wrap",
        "category": "Wraps & Shawarma",
        "has_variants": False,
        "base_price": Decimal("490.00"),
        "cost_price": Decimal("260.00"),
        "stock_quantity": 50,
        "description": "Grilled chicken, spicy salsa, melted cheddar, jalapeños, and rice wrapped in a soft flour tortilla."
    },
    {
        "name": "Zinger Paratha Roll",
        "category": "Wraps & Shawarma",
        "has_variants": False,
        "base_price": Decimal("380.00"),
        "cost_price": Decimal("190.00"),
        "stock_quantity": 80,
        "description": "Crispy fried chicken strips, spicy mayo, onions, and chat masala in a flaky crispy paratha."
    },
    {
        "name": "Beef Seekh Kabab Roll",
        "category": "Wraps & Shawarma",
        "has_variants": False,
        "base_price": Decimal("390.00"),
        "cost_price": Decimal("200.00"),
        "stock_quantity": 60,
        "description": "Grilled beef seekh kabab with green mint chutney and sliced onions rolled in puri paratha."
    },
    {
        "name": "BBQ Malai Boti Paratha Roll",
        "category": "Wraps & Shawarma",
        "has_variants": False,
        "base_price": Decimal("420.00"),
        "cost_price": Decimal("220.00"),
        "stock_quantity": 70,
        "description": "Creamy malai boti pieces rolled with garlic sauce and onions in a golden fried paratha."
    },

    # --- 8. Appetizers & Fries (5 Items) ---
    {
        "name": "Loaded Cheese & Chicken Fries",
        "category": "Appetizers & Fries",
        "has_variants": False,
        "base_price": Decimal("650.00"),
        "cost_price": Decimal("330.00"),
        "stock_quantity": 60,
        "description": "Crispy skin-on fries topped with grilled chicken chunks, liquid cheddar cheese, jalapeños, and ranch."
    },
    {
        "name": "Golden French Fries",
        "category": "Appetizers & Fries",
        "has_variants": True,
        "description": "Classic salted crispy potato fries.",
        "variants": [
            ("Regular", Decimal("220.00"), Decimal("90.00")),
            ("Large", Decimal("350.00"), Decimal("140.00")),
        ]
    },
    {
        "name": "Cheesy Mozzarella Sticks (6 pcs)",
        "category": "Appetizers & Fries",
        "has_variants": False,
        "base_price": Decimal("550.00"),
        "cost_price": Decimal("280.00"),
        "stock_quantity": 40,
        "description": "Breaded string mozzarella sticks fried golden brown with marinara dipping sauce."
    },
    {
        "name": "Garlic Herb Cheese Bread (4 pcs)",
        "category": "Appetizers & Fries",
        "has_variants": False,
        "base_price": Decimal("390.00"),
        "cost_price": Decimal("180.00"),
        "stock_quantity": 50,
        "description": "French baguette slices toasted with herb garlic butter and bubbling mozzarella cheese."
    },
    {
        "name": "Crispy Onion Rings Basket",
        "category": "Appetizers & Fries",
        "has_variants": False,
        "base_price": Decimal("320.00"),
        "cost_price": Decimal("140.00"),
        "stock_quantity": 45,
        "description": "Beer battered whole white onion rings fried crunchy with honey BBQ dip."
    },

    # --- 9. Beverages & Shakes (6 Items) ---
    {
        "name": "Soft Drinks",
        "category": "Beverages & Shakes",
        "has_variants": True,
        "description": "Chilled refreshing soft drinks (Coke, Sprite, Fanta, Dew).",
        "variants": [
            ("Can 250ml", Decimal("120.00"), Decimal("75.00")),
            ("Bottle 500ml", Decimal("160.00"), Decimal("95.00")),
            ("Bottle 1.5L", Decimal("260.00"), Decimal("160.00")),
        ]
    },
    {
        "name": "Fresh Mint Margarita",
        "category": "Beverages & Shakes",
        "has_variants": False,
        "base_price": Decimal("280.00"),
        "cost_price": Decimal("110.00"),
        "stock_quantity": 100,
        "description": "Crushed ice, fresh mint leaves, lemon juice, black salt, and sparkling soda."
    },
    {
        "name": "Belgium Chocolate Thickshake",
        "category": "Beverages & Shakes",
        "has_variants": False,
        "base_price": Decimal("520.00"),
        "cost_price": Decimal("260.00"),
        "stock_quantity": 60,
        "description": "Dark Belgian chocolate ice cream blended with full cream milk, topped with chocolate fudge and whipped cream."
    },
    {
        "name": "Strawberry Cheesecake Shake",
        "category": "Beverages & Shakes",
        "has_variants": False,
        "base_price": Decimal("550.00"),
        "cost_price": Decimal("280.00"),
        "stock_quantity": 50,
        "description": "Fresh strawberries blended with cream cheese, vanilla ice cream, and graham cracker crumbs."
    },
    {
        "name": "Nutella Brownie Shake",
        "category": "Beverages & Shakes",
        "has_variants": False,
        "base_price": Decimal("590.00"),
        "cost_price": Decimal("310.00"),
        "stock_quantity": 40,
        "description": "Rich Nutella spread and fudge brownie blended with ice cream and cocoa drizzle."
    },
    {
        "name": "Mineral Water",
        "category": "Beverages & Shakes",
        "has_variants": True,
        "description": "Pure premium filtered drinking water.",
        "variants": [
            ("Small (500ml)", Decimal("70.00"), Decimal("35.00")),
            ("Large (1.5L)", Decimal("120.00"), Decimal("60.00")),
        ]
    },

    # --- 10. Desserts & Ice Cream (6 Items) ---
    {
        "name": "Molten Lava Cake",
        "category": "Desserts & Ice Cream",
        "has_variants": False,
        "base_price": Decimal("590.00"),
        "cost_price": Decimal("280.00"),
        "stock_quantity": 35,
        "description": "Warm chocolate sponge cake with a flowing molten center, served with a scoop of vanilla ice cream."
    },
    {
        "name": "New York Classic Cheesecake",
        "category": "Desserts & Ice Cream",
        "has_variants": False,
        "base_price": Decimal("620.00"),
        "cost_price": Decimal("310.00"),
        "stock_quantity": 25,
        "description": "Dense and creamy baked cheesecake on a buttery biscuit crust with blueberry compote."
    },
    {
        "name": "Sizzling Brownie with Ice Cream",
        "category": "Desserts & Ice Cream",
        "has_variants": False,
        "base_price": Decimal("550.00"),
        "cost_price": Decimal("260.00"),
        "stock_quantity": 30,
        "description": "Fudge walnut brownie served on a hot sizzler plate with vanilla gelato and sizzling chocolate sauce."
    },
    {
        "name": "Lotus Biscoff Waffle",
        "category": "Desserts & Ice Cream",
        "has_variants": False,
        "base_price": Decimal("650.00"),
        "cost_price": Decimal("320.00"),
        "stock_quantity": 30,
        "description": "Belgian waffle smothered in warm Biscoff spread, crushed lotus crumbs, and vanilla ice cream."
    },
    {
        "name": "Nutella Crepe",
        "category": "Desserts & Ice Cream",
        "has_variants": False,
        "base_price": Decimal("580.00"),
        "cost_price": Decimal("270.00"),
        "stock_quantity": 35,
        "description": "Thin French crepe stuffed with Nutella and fresh banana slices, dusted with powdered sugar."
    },
    {
        "name": "Artisan Ice Cream Scoop",
        "category": "Desserts & Ice Cream",
        "has_variants": True,
        "description": "Fresh premium ice cream (Vanilla, Belgian Chocolate, Mango, Pistachio).",
        "variants": [
            ("Single Scoop", Decimal("180.00"), Decimal("80.00")),
            ("Double Scoop", Decimal("320.00"), Decimal("140.00")),
            ("Triple Scoop", Decimal("450.00"), Decimal("200.00")),
        ]
    },
]

created_prods = 0
created_variants = 0

for p_data in products_data:
    cat = cats[p_data["category"]]
    has_variants = p_data.get("has_variants", False)
    
    prod = Product.objects.create(
        name=p_data["name"],
        category=cat,
        has_variants=has_variants,
        base_price=p_data.get("base_price", Decimal("0.00")),
        cost_price=p_data.get("cost_price", Decimal("0.00")),
        stock_quantity=p_data.get("stock_quantity", 0),
        description=p_data.get("description", ""),
        is_active=True,
    )
    created_prods += 1
    
    if has_variants and "variants" in p_data:
        for v_name, v_sell, v_cost in p_data["variants"]:
            ProductVariant.objects.create(
                product=prod,
                name=v_name,
                selling_price=v_sell,
                cost_price=v_cost,
                stock_quantity=50,
                is_active=True,
            )
            created_variants += 1

print(f"DONE! Successfully created {len(cats)} Categories, {created_prods} Products, and {created_variants} Size Variants!")
