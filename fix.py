content = open('index.py', encoding='utf-8').read()
old = '    gs["is_ai_game"] = True\n    gs["ai_difficulty"] = difficulty\n    gs["phase"] = "play"\n    gs["turn"] = "p1"'
new = '    gs["is_ai_game"] = True\n    gs["ai_difficulty"] = difficulty\n    gs["phase"] = "mulligan_p1"\n    gs["turn"] = "p1"'
if old in content:
    open('index.py', 'w', encoding='utf-8').write(content.replace(old, new))
    print('Fixed')
else:
    print('NOT FOUND')