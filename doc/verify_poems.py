import json

with open('d:\\AAA\\video-tools\\ai-video-solo\\doc\\poems.json', 'r', encoding='utf-8') as f:
    poems = json.load(f)

print(f'诗词总数: {len(poems)}')

# 检查原有字段是否保留
required_old_fields = ['index', 'title', 'author', 'dynasty', 'content', 'fame_score']
missing_old = []
for p in poems:
    for field in required_old_fields:
        if field not in p:
            missing_old.append((p.get('title', 'UNKNOWN'), field))
print(f'缺失原有字段: {len(missing_old)}')
if missing_old:
    print(missing_old[:10])

# 检查新字段
required_new_fields = ['author_intro', 'writing_background', 'translation', 'theme', 'appreciation']
missing_new = []
for p in poems:
    for field in required_new_fields:
        if not p.get(field):
            missing_new.append((p['title'], field))
print(f'缺失新字段: {len(missing_new)}')
if missing_new:
    print(missing_new[:20])

# 检查 index
indices = [p['index'] for p in poems]
duplicates = [i for i in set(indices) if indices.count(i) > 1]
print(f'重复 index: {duplicates}')

expected = list(range(1, len(poems) + 1))
missing_indices = [i for i in expected if i not in indices]
print(f'缺失 index: {missing_indices}')

# 检查新增诗词（index > 300）
new_poems = [p for p in poems if p['index'] > 300]
print(f'新增诗词数量 (index > 300): {len(new_poems)}')
for p in new_poems:
    print(f"  index={p['index']}, title={p['title']}, author={p.get('author','')}, dynasty={p.get('dynasty','')}")

# 抽样检查
print('\n抽样检查（前3首）：')
for p in poems[:3]:
    print(f"[{p['index']}] {p['title']}")
    for field in required_new_fields:
        content = p.get(field, '')
        print(f'  {field}: {content[:50]}...' if len(content) > 50 else f'  {field}: {content}')

print('\n校验完成！')
