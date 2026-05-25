content = open('index.py', encoding='utf-8').read()

old = '''    save_game(game_id, gs)

    swaps = gs["mulligan_swaps"][side]
    await bot.send_message(
        chat_id,
        f"🔄 Замена {swaps}/2: {card['name']} → {new_card['emoji']}{new_card['name']}\\n\\n"
        f"{'Ещё можно заменить 1 карту.' if swaps < 2 else 'Лимит замен исчерпан.'}",
        reply_markup=kb_mulligan(gs["hand"][side]),
    )'''

new = '''    save_game(game_id, gs)

    swaps = gs["mulligan_swaps"][side]
    prev_mid = gs.get("mulligan_msg_id", {}).get(side)
    await delete_msg(bot, chat_id, prev_mid)
    msg = await bot.send_message(
        chat_id,
        f"🔄 Замена {swaps}/2: {card['name']} → {new_card['emoji']}{new_card['name']}\\n\\n"
        f"{'Ещё можно заменить 1 карту.' if swaps < 2 else 'Лимит замен исчерпан.'}",
        reply_markup=kb_mulligan(gs["hand"][side]),
    )
    gs.setdefault("mulligan_msg_id", {})[side] = msg.message_id
    save_game(game_id, gs)'''

if old in content:
    open('index.py', 'w', encoding='utf-8').write(content.replace(old, new))
    print('mulligan: Fixed')
else:
    print('mulligan: NOT FOUND')