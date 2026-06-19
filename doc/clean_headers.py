import json
import re

with open('d:\\AAA\\video-tools\\ai-video-solo\\doc\\poems.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

fields = ['author_intro', 'writing_background', 'translation', 'theme', 'appreciation']
pattern = re.compile(r'\n*#+\s*中华经典诗词三百首教学解析.*$', re.MULTILINE)

count = 0
for poem in data:
    for field in fields:
        if field in poem and isinstance(poem[field], str):
            cleaned = pattern.sub('', poem[field])
            # Also clean trailing newlines
            cleaned = cleaned.rstrip('\n')
            if cleaned != poem[field]:
                poem[field] = cleaned
                count += 1

with open('d:\\AAA\\video-tools\\ai-video-solo\\doc\\poems.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f'Cleaned {count} fields')
