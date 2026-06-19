import json

with open('d:\\AAA\\video-tools\\ai-video-solo\\doc\\poems.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

fields = ['author_intro', 'writing_background', 'translation', 'theme', 'appreciation']

# Check 1: All poems have all 5 new fields
missing_fields = 0
empty_fields = 0
for poem in data:
    for field in fields:
        if field not in poem:
            missing_fields += 1
            print(f'Missing {field} in index {poem.get("index")} - {poem.get("title")}')
        elif not poem[field] or not str(poem[field]).strip():
            empty_fields += 1
            print(f'Empty {field} in index {poem.get("index")} - {poem.get("title")}')

# Check 2: index continuity
indices = [p['index'] for p in data]
expected = list(range(1, len(data) + 1))
if indices == expected:
    print('Index check: PASSED - indices are continuous from 1 to', len(data))
else:
    print('Index check: FAILED')

# Check 3: No duplicate indices
if len(indices) == len(set(indices)):
    print('Duplicate index check: PASSED')
else:
    print('Duplicate index check: FAILED')

# Check 4: Original fields preserved
original_fields = ['index', 'title', 'author', 'dynasty', 'content', 'fame_score']
missing_original = 0
for poem in data:
    for field in original_fields:
        if field not in poem:
            missing_original += 1

if missing_original == 0:
    print('Original fields check: PASSED')
else:
    print(f'Original fields check: FAILED - {missing_original} missing')

# Check 5: Check for remaining ---
has_separator = 0
for poem in data:
    for field in fields:
        if field in poem and isinstance(poem[field], str) and '---' in poem[field]:
            has_separator += 1

print(f'Fields with remaining ---: {has_separator}')

print(f'\nTotal poems: {len(data)}')
print(f'Missing fields: {missing_fields}')
print(f'Empty fields: {empty_fields}')
