content = open('index.py', encoding='utf-8').read()

old = '    ctype = card["type"]\n    if ctype in ("normal", "hero", "spy", "horn", "weather", "decoy"):\n        msg = await bot.send_message(\n            chat_id,\n            f"Выбрана: {card[\'emoji\']} *{card[\'name\']}*\\n_{card.get(\'tip\',\'\')}_\\n\\nКуда поставить?",\n            reply_markup=kb_row_select(card_uid, card),\n            parse_mode="Markdown"\n        )\n        gs.setdefault("tmp_msg_id", {})[side] = msg.message_id\n        save_game(game_id, gs)\n    else:\n        msg = await bot.send_message(chat_id, f"Выбрана карта: {card[\'name\']}")\n        gs.setdefault("tmp_msg_id", {})[side] = msg.message_id\n        save_game(game_id, gs)'

new = '    ctype = card["type"]\n    # Определяем доступные ряды\n    card_row = card.get("row", "melee")\n    if card_row == "any" or ctype in ("horn", "weather", "decoy"):\n        rows_available = ROWS\n    elif card_row in ROWS:\n        rows_available = [card_row]\n    else:\n        rows_available = ROWS\n\n    # Если ряд один — сразу размещаем без вопроса\n    if len(rows_available) == 1:\n        gs["selected_card_uid"][side] = card_uid\n        save_game(game_id, gs)\n        await handle_place_card(bot, chat_id, user_id,\n                                card_uid, rows_available[0], game_id, data)\n        return\n\n    # Иначе спрашиваем\n    msg = await bot.send_message(\n        chat_id,\n        f"Выбрана: {card[\'emoji\']} *{card[\'name\']}*\\n_{card.get(\'tip\',\'\')}_\\n\\nКуда поставить?",\n        reply_markup=kb_row_select(card_uid, card),\n        parse_mode="Markdown"\n    )\n    gs.setdefault("tmp_msg_id", {})[side] = msg.message_id\n    save_game(game_id, gs)'

if old in content:
    open('index.py', 'w', encoding='utf-8').write(content.replace(old, new))
    print('Fixed')
else:
    print('NOT FOUND')