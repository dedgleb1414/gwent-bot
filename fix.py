content = open('index.py', encoding='utf-8').read()

old = '    if check_round_end(gs):\n        await end_round(bot, gs, game_id, load_data())\n        return\n\n    await start_turn(bot, gs, game_id, gs["turn"])\n\n\nasync def do_ai_tu'

new = '    if check_round_end(gs):\n        await end_round(bot, gs, game_id, load_data())\n        return\n\n    next_side = gs["turn"]\n    if gs.get("is_ai_game") and next_side == "p2":\n        await do_ai_turn(bot, gs, game_id, load_data())\n    else:\n        await start_turn(bot, gs, game_id, next_side)\n\n\nasync def do_ai_tu'

if old in content:
    open('index.py', 'w', encoding='utf-8').write(content.replace(old, new))
    print('Fixed')
else:
    print('NOT FOUND')