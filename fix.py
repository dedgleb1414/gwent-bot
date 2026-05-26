content = open('index.py', encoding='utf-8').read()

old = '            else:\n                row = card.get("row", "melee")\n                if row not in ROWS:\n                    row = "melee"\n                gs["rows"][side][row].append(card)\n            gs["awaiting_medic"][side] = False'

new = '            elif "kazn" in card.get("abilities", []):\n                # Дракон воскрешается и сразу убивает сильнейшую карту melee врага\n                row = card.get("row", "melee")\n                if row not in ROWS:\n                    row = "melee"\n                gs["rows"][side][row].append(card)\n                best_val = 0\n                best_card = None\n                for c in gs["rows"][opp]["melee"]:\n                    if c["type"] != "hero" and c["val"] > best_val:\n                        best_val = c["val"]\n                        best_card = c\n                if best_card:\n                    gs["rows"][opp]["melee"] = [\n                        c for c in gs["rows"][opp]["melee"]\n                        if c["uid"] != best_card["uid"]\n                    ]\n                    gs["graveyard"][opp].append(best_card)\n                    await bot.send_message(\n                        chat_id,\n                        f"🐲 {card[\'name\']} воскрешён! Казнь: {best_card[\'name\']} ({best_val}) уничтожен"\n                    )\n            else:\n                row = card.get("row", "melee")\n                if row not in ROWS:\n                    row = "melee"\n                gs["rows"][side][row].append(card)\n            gs["awaiting_medic"][side] = False'

if old in content:
    open('index.py', 'w', encoding='utf-8').write(content.replace(old, new))
    print('Fixed')
else:
    print('NOT FOUND')