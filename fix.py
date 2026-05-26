content = open('index.py', encoding='utf-8').read()

old = '        elif text == "/help" or text == "/rules":\n            await handle_rules(bot, chat_id)'
new = '        elif text == "/help":\n            await handle_help(bot, chat_id)\n\n        elif text == "/rules":\n            await handle_rules(bot, chat_id)'

if old in content:
    open('index.py', 'w', encoding='utf-8').write(content.replace(old, new))
    print('Fixed')
else:
    print('NOT FOUND')