content = open('index.py', encoding='utf-8').read()

old = '        elif text == "/cancel":\n            redis_del(queue_key())\n            await bot.send_message(chat_id, "❌ Поиск отменён.")'

new = '        elif text == "/cancel":\n            redis_del(queue_key())\n            await bot.send_message(chat_id, "❌ Поиск отменён.")\n\n        elif text == "/stats":\n            await handle_stats(bot, chat_id, user_id, user_name)'

if old in content:
    open('index.py', 'w', encoding='utf-8').write(content.replace(old, new))
    print('Fixed')
else:
    print('NOT FOUND')