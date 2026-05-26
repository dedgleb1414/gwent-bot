content = open('index.py', encoding='utf-8').read()

old = '        elif text == "/game" or text == "/board":\n            await handle_game_view(bot, chat_id, user_id)'
new = '        elif text == "/game" or text == "/board":\n            await handle_game_view(bot, chat_id, user_id)\n\n        elif text == "/hand":\n            await handle_hand(bot, chat_id, user_id)'

if old in content:
    open('index.py', 'w', encoding='utf-8').write(content.replace(old, new))
    print('Fixed')
else:
    print('NOT FOUND')