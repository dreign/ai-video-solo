import json

# 读取 parsed_讲解.json
with open('d:\\AAA\\video-tools\\ai-video-solo\\doc\\parsed_讲解.json', 'r', encoding='utf-8') as f:
    parsed = json.load(f)

# 建立 title -> 解析数据的映射（讲解文档中的标题不含书名号）
parse_map = {}
for p in parsed['poems']:
    parse_map[p['title']] = p

# 读取 poems.json
with open('d:\\AAA\\video-tools\\ai-video-solo\\doc\\poems.json', 'r', encoding='utf-8') as f:
    poems = json.load(f)

print(f'poems.json 原有诗词数量: {len(poems)}')
print(f'parsed_讲解.json 诗词数量: {len(parsed["poems"])}')

# 建立模糊匹配映射：去掉括号及其中内容后的标题
def normalize_title(t):
    import re
    return re.sub(r'[（(].*?[）)]', '', t).strip()

parse_map_normalized = {}
for title, data in parse_map.items():
    parse_map_normalized[normalize_title(title)] = data

# Task 3: 为 poems.json 中已有诗词补充讲解字段
matched = 0
not_matched = []
for poem in poems:
    title = poem['title']
    p = parse_map.get(title)
    if not p:
        p = parse_map_normalized.get(normalize_title(title))
    if p:
        poem['author_intro'] = p['author_intro']
        poem['writing_background'] = p['writing_background']
        poem['translation'] = p['translation']
        poem['theme'] = p['theme']
        poem['appreciation'] = p['appreciation']
        matched += 1
    else:
        not_matched.append(title)

print(f'匹配到的诗词: {matched}/{len(poems)}')
print(f'未匹配到的诗词: {len(not_matched)}')
if not_matched:
    print('未匹配列表:', not_matched[:20])

# Task 4: 将讲解文档中有但 poems.json 中没有的诗词补充进去
existing_titles = set(p['title'] for p in poems)
existing_titles_normalized = set(normalize_title(t) for t in existing_titles)
new_poems = []
for p in parsed['poems']:
    if p['title'] not in existing_titles and normalize_title(p['title']) not in existing_titles_normalized:
        new_poems.append(p)

print(f'讲解文档中有但 poems.json 中没有的诗词: {len(new_poems)}')
if new_poems:
    print('新增诗词标题:', [p['title'] for p in new_poems[:20]])

# 找到当前最大 index
max_index = max(p['index'] for p in poems)
for idx, p in enumerate(new_poems, start=max_index + 1):
    poems.append({
        'index': idx,
        'title': p['title'],
        'author': '',
        'dynasty': '',
        'content': '',
        'fame_score': 0,
        'author_intro': p['author_intro'],
        'writing_background': p['writing_background'],
        'translation': p['translation'],
        'theme': p['theme'],
        'appreciation': p['appreciation']
    })

# 按 index 排序
poems.sort(key=lambda x: x['index'])

print(f'合并后诗词总数: {len(poems)}')

# Task 5: 二次校验
# 5.1 校验所有诗词都有完整的6个新字段
missing_fields = []
for p in poems:
    for field in ['author_intro', 'writing_background', 'translation', 'theme', 'appreciation']:
        if not p.get(field):
            missing_fields.append((p['title'], field))

print(f'缺失字段的诗词数量: {len(missing_fields)}')
if missing_fields:
    print('部分缺失示例:', missing_fields[:10])

# 5.2 校验 index 连续无重复
indices = [p['index'] for p in poems]
duplicates = [i for i in set(indices) if indices.count(i) > 1]
print(f'重复 index: {duplicates}')

expected_indices = list(range(1, len(poems) + 1))
missing_indices = [i for i in expected_indices if i not in indices]
print(f'缺失 index: {missing_indices}')

# 5.3 校验诗词总数
print(f'最终诗词总数: {len(poems)}')

# 清理 appreciation 字段末尾的文档注释
for p in poems:
    app = p.get('appreciation', '')
    if '您可将全部内容合并为一个' in app or '至此，第1-300首已全部完成' in app:
        # 找到最后一个艺术赏析点，去掉后面的注释
        lines = app.split('\n')
        clean_lines = []
        for line in lines:
            if line.startswith('**注**：') or '您可将全部内容合并为一个' in line or '至此，第1-300首已全部完成' in line:
                break
            clean_lines.append(line)
        p['appreciation'] = '\n'.join(clean_lines).strip()

# 保存最终文件
with open('d:\\AAA\\video-tools\\ai-video-solo\\doc\\poems.json', 'w', encoding='utf-8') as f:
    json.dump(poems, f, ensure_ascii=False, indent=2)

print('已保存到 poems.json')
