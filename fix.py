content = open('index.py', encoding='utf-8').read()

old = '    await asyncio.sleep(1.2)  # пауза для реалистичности'
new = '    # пауза убрана для совместимости с serverless'

if old in content:
    open('index.py', 'w', encoding='utf-8').write(content.replace(old, new))
    print('Fixed')
else:
    print('NOT FOUND')