# Translation keys for all user/system messages in product search, handoff, and general flows
TRANSLATIONS = {
    # When products are found for a query
    "found_products": {
        "en": "Found {count} products matching your query.",
        "cs": "Nalezeno {count} produktů odpovídajících vašemu dotazu.",
    },
    # Prompt to select from options (e.g., interactive list)
    "choose_option": {
        "en": "Choose an option:",
        "cs": "Vyberte možnost:",
    },
    # When no products are found for a query
    "no_products": {
        "en": "Sorry, could not find any products.",
        "cs": "Omlouváme se, nenašli jsme žádné produkty.",
    },
    # Title for product lists (e.g., WhatsApp list header)
    "product_list_title": {
        "en": "LEVA Houses",
        "cs": "LEVA Domy",
    },
    # Button/action to order a product
    "order_product": {
        "en": "Order {product}",
        "cs": "Objednat {product}",
    },
    # No product found for a given ID
    "no_product_with_id": {
        "en": "Sorry, no product found with ID {id}.",
        "cs": "Omlouváme se, žádný produkt s ID {id} nebyl nalezen.",
    },
    # Error when fetching product details
    "error_fetching_product_details": {
        "en": "Sorry, there was an error fetching the product details.",
        "cs": "Omlouváme se, došlo k chybě při načítání detailů produktu.",
    },
    # Error when browsing all products
    "error_browsing_products": {
        "en": "Sorry, there was an error browsing products.",
        "cs": "Omlouváme se, došlo k chybě při procházení produktů.",
    },
    # User input is not understood
    "invalid_input": {
        "en": "Sorry, I didn't understand that. Please try again.",
        "cs": "Omlouváme se, nerozuměli jsme. Zkuste to prosím znovu.",
    },
    # Generic fallback for errors
    "try_again": {
        "en": "Something went wrong. Please try again later.",
        "cs": "Něco se pokazilo. Zkuste to prosím později.",
    },
    # Confirmation after ordering
    "confirm_order": {
        "en": "Your order for {product} has been placed!",
        "cs": "Vaše objednávka na {product} byla přijata!",
    },
    # Label for product details section
    "product_details": {
        "en": "Product Details",
        "cs": "Detaily produktu",
    },
    # Initial greeting
    "welcome_message": {
        "en": "Welcome to LEVA! How can I assist you today?",
        "cs": "Vítejte v LEVA! Jak vám mohu dnes pomoci?",
    },
    # End of conversation
    "goodbye_message": {
        "en": "Thank you for visiting LEVA. Have a great day!",
        "cs": "Děkujeme za návštěvu LEVA. Přejeme hezký den!",
    },
    # Help or instructions
    "help_message": {
        "en": "You can search for houses, browse all products, or ask for details about a specific product.",
        "cs": "Můžete hledat domy, procházet všechny produkty nebo požádat o detaily konkrétního produktu.",
    },
    # While searching/loading
    "loading_message": {
        "en": "Searching, please wait...",
        "cs": "Hledám, prosím čekejte...",
    },
    # Catch-all error
    "unexpected_error": {
        "en": "An unexpected error occurred. Please try again later.",
        "cs": "Došlo k neočekávané chybě. Zkuste to prosím později.",
    },
}

from langdetect import detect, LangDetectException

def detect_language(text):
    """Detects the language of the input text. Returns 'cs' for Czech, 'en' for English, defaults to 'en'."""
    try:
        lang = detect(text)
        if lang.startswith("cs"):
            return "cs"
        return "en"
    except LangDetectException:
        return "en"

def get_translation(key, lang, **kwargs):
    if lang not in TRANSLATIONS.get(key, {}):
        lang = "en"
    return TRANSLATIONS.get(key, {}).get(lang, TRANSLATIONS[key]["en"]).format(**kwargs) 