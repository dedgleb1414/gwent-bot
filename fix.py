lines = open('index.py', encoding='utf-8').read().split('\n')
lines[1521] = '            f"{p_name} сдался! Вы победили! /start - новая игра",'
lines[1522] = ''
lines[1523] = ''
open('index.py', 'w', encoding='utf-8').write('\n'.join(lines))
print('Fixed')