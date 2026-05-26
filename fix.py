content = open('index.py', encoding='utf-8').read()

old = '        elif text == "/stats":\n            await handle_stats(bot, chat_id, user_id, user_name)'
new = '        elif text == "/stats":\n            await handle_stats(bot, chat_id, user_id, user_name)\n\n        elif text == "/leaderboard" or text == "/top":\n            await handle_leaderboard(bot, chat_id)'

if old in content:
    open('index.py', 'w', encoding='utf-8').write(content.replace(old, new))
    print('Fixed')
else:
    print('NOT FOUND')