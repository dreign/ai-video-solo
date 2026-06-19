import json

with open('d:\\AAA\\video-tools\\ai-video-solo\\doc\\poems.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

fields = ['author_intro', 'writing_background', 'translation', 'theme', 'appreciation']

for poem in data:
    for field in fields:
        if field in poem and isinstance(poem[field], str) and '---' in poem[field]:
            print(f'Found --- in index {poem["index"]} - {poem["title"]} - field: {field}')
            print(repr(poem[field][-50:]))
            print()
