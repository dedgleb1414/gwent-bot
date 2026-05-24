content = open('index.py', encoding='utf-8').read()
old = '    leader = data["factions"][faction_key]["leaders"][leader_idx]\n    await bot.send_message(\n        chat_id,\n        f"{leader[\'icon\']} *{leader[\'name\']}*\\n_{leader[\'power\']}_\\n\\n"\n        f"⏳ Ожидаем выбор противника...",\n        parse_mode="Markdown"\n    )'
new = '    leader = data["factions"][faction_key]["leaders"][leader_idx]\n    if not setup.get("ai_difficulty"):\n        await bot.send_message(\n            chat_id,\n            f"{leader[\'icon\']} *{leader[\'name\']}*\\n_{leader[\'power\']}_\\n\\n"\n            f"⏳ Ожидаем выбор противника...",\n            parse_mode="Markdown"\n        )'
if old in content:
    open('index.py', 'w', encoding='utf-8').write(content.replace(old, new))
    print('Fixed')
else:
    print('NOT FOUND')