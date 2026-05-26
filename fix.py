content = open('index.py', encoding='utf-8').read()

old = '    if not gs["passed"]["p1"]:\n        gs["turn"] = "p1"\n    save_game(game_id, gs)\n\n    if check_round_end(gs):\n        await end_round(bot, gs, game_id, data)\n        return\n\n    await start_turn(bot, gs, game_id, "p1")\n    \nasync def end_round'

new = '    save_game(game_id, gs)\n\n    if check_round_end(gs):\n        await end_round(bot, gs, game_id, data)\n        return\n\n    # Если игрок спасовал — AI продолжает ходить\n    if gs["passed"]["p1"]:\n        await do_ai_turn(bot, gs, game_id, data)\n    else:\n        gs["turn"] = "p1"\n        save_game(game_id, gs)\n        await start_turn(bot, gs, game_id, "p1")\n\nasync def end_round'

if old in content:
    open('index.py', 'w', encoding='utf-8').write(content.replace(old, new))
    print('Fixed')
else:
    print('NOT FOUND')