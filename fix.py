content = open('index.py', encoding='utf-8').read()

old = '    else:\n        # New round: send mulligan\n        for pid in (p1_id, p2_id):\n            await bot.send_message(\n                pid,\n                f"{result_msg}\\n\\n⚔️ *Раунд {gs[\'round\']} начинается!*\\nМуллиган: замените до 2 карт.",\n                parse_mode="Markdown"\n            )\n\n        side_now = "p1" if gs["phase"] == "mulligan_p1" else "p2"\n        opp_side = get_opponent(side_now)\n        pid_now = gs["players"][side_now]["id"]\n        pid_opp = gs["players"][opp_side]["id"]\n\n        await bot.send_message(\n            pid_now,\n            "Замените карты:",\n            reply_markup=kb_mulligan(gs["hand"][side_now])\n        )\n        await bot.send_message(pid_opp, "⏳ Ждём противника (муллиган)...")\n\n'

new = '    else:\n        # New round: start directly\n        gs["phase"] = "play"\n        gs["turn"] = "p1"\n        save_game(game_id, gs)\n        await bot.send_message(\n            p1_id,\n            f"{result_msg}\\n\\n⚔️ *Раунд {gs[\'round\']} начинается!*",\n            parse_mode="Markdown"\n        )\n        if p2_id != AI_USER_ID:\n            await bot.send_message(\n                p2_id,\n                f"{result_msg}\\n\\n⚔️ *Раунд {gs[\'round\']} начинается!*",\n                parse_mode="Markdown"\n            )\n        if gs.get("is_ai_game"):\n            await start_turn(bot, gs, game_id, "p1")\n        else:\n            await start_turn(bot, gs, game_id, "p1")\n\n'

if old in content:
    open('index.py', 'w', encoding='utf-8').write(content.replace(old, new))
    print('Fixed')
else:
    print('NOT FOUND')