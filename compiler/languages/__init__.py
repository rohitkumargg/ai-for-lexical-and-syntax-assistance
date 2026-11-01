import os

LANGUAGES = [
    {
        "id": "c",
        "label": "C",
        "extensions": [".c"],
        "monaco": "c",
        "new_label": "New C Program",
        "default_name": "main.c",
    },
    {
        "id": "python",
        "label": "Python",
        "extensions": [".py"],
        "monaco": "python",
        "new_label": "New Python Program",
        "default_name": "main.py",
    },
]

STARTER_TEMPLATES = {
    "c": "int main() {\n    return 0;\n}\n",
    "python": "def main():\n    print(\"Hello\")\n\n\nmain()\n",
}

def get_language(lang_id):
    if not lang_id:
        return None
    for lang in LANGUAGES:
        if lang["id"] == lang_id:
            return lang
    return None

def detect_language(filename=None, requested=None):
    if requested:
        req = requested.strip().lower()
        if get_language(req):
            return req
    if filename:
        ext = os.path.splitext(filename)[1].lower()
        for lang in LANGUAGES:
            if ext in lang["extensions"]:
                return lang["id"]
    return "c"

def extension_ok(lang_id, filename):
    lang = get_language(lang_id)
    if not lang:
        return False
    ext = os.path.splitext(filename)[1].lower()
    return ext in lang["extensions"]

def get_starter_template(lang_id):
    return STARTER_TEMPLATES.get(lang_id, "")
