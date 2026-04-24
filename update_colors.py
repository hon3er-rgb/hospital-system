import re

with open('lab.py', 'r', encoding='utf-8') as f:
    text = f.read()

replacements = {
    '#8b5cf6': '#0d6efd',
    '#6d28d9': '#0a58ca',
    '#a78bfa': '#6ea8fe',
    '#7c3aed': '#0b5ed7',
    '139, 92, 246': '13, 110, 253',
    '#1e293b': '#000000',
    '#94a3b8': '#495057', 
    '#64748b': '#212529',
}

for old, new in replacements.items():
    text = text.replace(old, new)

# Fix dark mode colors that got too dark
text = text.replace('color: #495057;', 'color: #adb5bd;')
text = text.replace('color: #212529;', 'color: #ced4da;')
text = text.replace('color: #000000;', 'color: #ffffff;')

# Fix background colors in dark mode that may have been affected
text = re.sub(r'\[data-theme="dark"\] \.p-name \{ color: #\w+; \}', '', text)
text = re.sub(r'\[data-theme="dark"\] \.p-meta \{ color: #\w+; \}', '', text)

with open('lab.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Done!")
