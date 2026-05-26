content = open('index.py', encoding='utf-8').read()

old = '            elif cbd == "cancel_select":\n                gs = get_game(game_id)\n                if gs:\n                    side = get_side_for_user(gs, user_id)\n                    if side:\n                        gs["selected_card_uid"][side] = None\n                        save_game(game_id, gs)'

new = '            elif cbd == "cancel_select":\n                gs = get_game(game_id)\n                if gs:\n                    side = get_side_for_user(gs, user_id)\n                    if side:\n                        gs["selected_card_uid"][side] = None\n                        tmp_id = gs.get("tmp_msg_id", {}).get(side)\n                        await delete_msg(bot, chat_id, tmp_id)\n                        gs.setdefault("tmp_msg_id", {})[side] = None\n                        save_game(game_id, gs)'

if old in content:
    open('index.py', 'w', encoding='utf-8').write(content.replace(old, new))
    print('Fixed')
else:
    print('NOT FOUND')