with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "query = response.text.strip().replace('\"', '').replace('" in line:
        lines[i] = "            query = response.text.strip().replace('\"', '').replace('\\n', '')\n"
        # also delete the next line if it's just the end of the string
        if i + 1 < len(lines) and "', '')" in lines[i+1]:
            lines[i+1] = ""

with open('main.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
