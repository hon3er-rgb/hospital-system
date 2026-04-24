with open('lab.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if 'data-theme=\"dark\"' not in line:
        line = line.replace('color: #ffffff;', 'color: #000000;')
        line = line.replace('color: #ced4da;', 'color: #1a1e21;')
    new_lines.append(line)

with open('lab.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print('Done fixing colors!')
