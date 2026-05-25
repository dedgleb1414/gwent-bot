content = open('index.py', encoding='utf-8').read()
idx = content.find('is_ai_game')
print(f"Index: {idx}")
if idx > 0:
    print(repr(content[idx-5:idx+150]))