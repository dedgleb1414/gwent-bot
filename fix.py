content = open('index.py', encoding='utf-8').read()

old = '    await bot.send_message(chat_id, "✋ Вы спасовали. Ждём противника...")\n    await bot.send_message(opp_id,\n                           f"✋ {p_name} спасовал(а). Ваш ход — можете продолжить или тоже спасовать.")\n    print(f"DEBUG pass: is_ai_game={gs.get(\'is_ai_game\')}, opp={opp}")\n    if gs.get("is_ai_game") and opp == "p2":\n        await do_ai_turn(bot, gs, game_id, data)\n    else:\n        await start_turn(bot, gs, game_id, opp)'

new = '    if gs.get("is_ai_game") and opp == "p2":\n        await bot.send_message(chat_id, "✋ Вы спасовали. AI ходит...")\n        await do_ai_turn(bot, gs, game_id, data)\n    else:\n        await bot.send_message(chat_id, "✋ Вы спасовали. Ждём противника...")\n        await bot.send_message(opp_id,\n                               f"✋ {p_name} спасовал(а). Ваш ход — можете продолжить или тоже спасовать.")\n        await start_turn(bot, gs, game_id, opp)'

if old in content:
    open('index.py', 'w', encoding='utf-8').write(content.replace(old, new))
    print('Fixed')
else:
    print('NOT FOUND')