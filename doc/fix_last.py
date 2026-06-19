import json

with open('d:\\AAA\\video-tools\\ai-video-solo\\doc\\poems.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for poem in data:
    if poem.get('index') == 40:
        orig = poem['appreciation']
        cleaned = orig.rstrip('\n').rstrip('-').rstrip('\n').rstrip('-').rstrip('\n').rstrip('-').rstrip('\n')
        if cleaned != orig:
            poem['appreciation'] = cleaned
            print('Fixed index 40 appreciation')
            print(repr(cleaned[-30:]))

with open('d:\\AAA\\video-tools\\ai-video-solo\\doc\\poems.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
