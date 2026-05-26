lines = open('index.py', encoding='utf-8').read().split('\n')
lines[1401] = '        await bot.send_message(opp_id,'
lines[1402] = '                               f"✋ {p_name} спасовал(а). Ваш ход — можете продолжить или тоже спасовать.")'
lines[1403] = '        add_log(gs, f"✋ {p_name} спасовал(а)")'
lines[1404] = '        save_game(game_id, gs)'
lines[1405] = '        await start_turn(bot, gs, game_id, opp)'
lines[1406] = ''
open('index.py', 'w', encoding='utf-8').write('\n'.join(lines))
print('Fixed')