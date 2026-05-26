content = open('index.py', encoding='utf-8').read()

old = '    if gs["phase"] == "mulligan_p1" and side == "p1":\n        if gs.get("is_ai_game"):\n            gs["phase"] = "play"\n            gs["turn"] = "p1"\n            save_game(game_id, gs)\n            await bot.send_message(chat_id, "✅ Готов! Игра начинается!")\n            await start_turn(bot, gs, game_id, "p1")\n            return'

new = '    if gs["phase"] == "mulligan_p1" and side == "p1":\n        prev_mid = gs.get("mulligan_msg_id", {}).get(side)\n        await delete_msg(bot, chat_id, prev_mid)\n        if gs.get("is_ai_game"):\n            gs["phase"] = "play"\n            gs["turn"] = "p1"\n            save_game(game_id, gs)\n            await start_turn(bot, gs, game_id, "p1")\n            return'

if old in content:
    open('index.py', 'w', encoding='utf-8').write(content.replace(old, new))
    print('Fixed')
else:
    print('NOT FOUND')