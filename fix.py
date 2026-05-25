content = open('index.py', encoding='utf-8').read()
old = '        if cbd.startswith("mulligan:"):\n                card_uid = cbd.split(":", 1)[1]\n                await handle_mulligan(bot, chat_id, user_id, card_uid, game_id, data)'
new = '        if cbd.startswith("mulligan:"):\n                card_uid = cbd.split(":", 1)[1]\n                gs_debug = get_game(game_id)\n                print(f"DEBUG mulligan: phase={gs_debug and gs_debug.get(\'phase\')}, side={get_side_for_user(gs_debug, user_id) if gs_debug else None}")\n                await handle_mulligan(bot, chat_id, user_id, card_uid, game_id, data)'
if old in content:
    open('index.py', 'w', encoding='utf-8').write(content.replace(old, new))
    print('Fixed')
else:
    print('NOT FOUND')