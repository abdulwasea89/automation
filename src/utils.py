import re

def extract_keywords(user_message: str) -> str:
    """Extracts main product keyword(s) from user message."""
    match = re.search(r"(?:i want|show me|need|find|get|looking for|search for|buy)\s+(?:a|an|the|some)?\s*([\w\s]+)", user_message, re.I)
    if match:
        return match.group(1).strip()
    return user_message.strip()

def generate_forms(keyword: str) -> list:
    """Generate plural, singular, and verb forms of the keyword."""
    forms = set()
    forms.add(keyword)
    if keyword.endswith('s'):
        forms.add(keyword[:-1])
    else:
        forms.add(keyword + 's')
    if keyword.endswith('ing'):
        forms.add(keyword[:-3])
    else:
        forms.add(keyword + 'ing')
    if keyword.endswith('ed'):
        forms.add(keyword[:-2])
    else:
        forms.add(keyword + 'ed')
    return list(forms)

def is_all_request(user_message: str) -> bool:
    """Detects if the user is requesting all products."""
    return any(word in user_message.lower() for word in ["all", "everything", "show all", "list all", "every product"]) 