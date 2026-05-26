content = open('index.py', encoding='utf-8').read()

old = '                await bot.send_message(\n                    chat_id, "↩️ Выбор отменён.",\n                    reply_markup=kb_hand(get_game(game_id) or {}, side or "p1")\n                )'
new = '                gs2 = get_game(game_id)\n                if gs2:\n                    await start_turn(bot, gs2, game_id, side)'

if old in content:
    open('index.py', 'w', encoding='utf-8').write(content.replace(old, new))
    print('Fixed')
else:
    print('NOT FOUND')