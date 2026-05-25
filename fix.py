content = open('index.py', encoding='utf-8').read()

old = '    # Continue game\n    next_side = gs["turn"]\n    if gs.get("is_ai_game") and next_side == "p2":\n        await do_ai_turn(bot, gs, game_id, load_data())\n    else:\n        await start_turn(bot, gs, game_id, next_side)'

new = '    # Continue game\n    gs = get_game(game_id)  # перечитываем свежий gs из Redis\n    next_side = gs["turn"]\n    if gs.get("is_ai_game") and next_side == "p2":\n        await do_ai_turn(bot, gs, game_id, load_data())\n    else:\n        await start_turn(bot, gs, game_id, next_side)'

if old in content:
    open('index.py', 'w', encoding='utf-8').write(content.replace(old, new))
    print('Fixed')
else:
    print('NOT FOUND')