content = open('index.py', encoding='utf-8').read()

old = '        await bot.send_message(chat_id, "✋ Вы спасовали. AI ходит...")\n        await do_ai_turn(bot, gs, game_id, data)'
new = '        await do_ai_turn(bot, gs, game_id, data)'

if old in content:
    open('index.py', 'w', encoding='utf-8').write(content.replace(old, new))
    print('Fixed')
else:
    print('NOT FOUND')