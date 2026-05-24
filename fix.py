content = open('index.py', encoding='utf-8').read()
old = '    await start_turn(bot, gs, game_id, opp)\n\n\nasync de'
new = '    if gs.get("is_ai_game") and opp == "p2":\n        await do_ai_turn(bot, gs, game_id, data)\n    else:\n        await start_turn(bot, gs, game_id, opp)\n\n\nasync de'
if old in content:
    open('index.py', 'w', encoding='utf-8').write(content.replace(old, new))
    print('Fixed')
else:
    print('NOT FOUND')