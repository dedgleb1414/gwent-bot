content = open('index.py', encoding='utf-8').read()
old = '            await handle_leader_pick(bot, chat_id, user_id,\n                                     faction_key, leader_idx, data)'
new = '            await handle_leader_pick(bot, chat_id, user_id, user_name,\n                                     faction_key, leader_idx, data)'
if old in content:
    open('index.py', 'w', encoding='utf-8').write(content.replace(old, new))
    print('Fixed')
else:
    print('NOT FOUND')