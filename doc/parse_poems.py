import re
import json
from collections import Counter

with open('d:\\AAA\\video-tools\\ai-video-solo\\doc\\诗词三百首讲解.md', 'r', encoding='utf-8') as f:
    content = f.read()

# 用正则表达式按标题分割，然后逐个解析
# 匹配模式: ## 【数字】《标题》
pattern = r'##\s*【(\d+)】《([^》]+)》'
matches = list(re.finditer(pattern, content))

poems = []
for idx, m in enumerate(matches):
    num = int(m.group(1))
    title = m.group(2)
    start = m.end()
    if idx + 1 < len(matches):
        end = matches[idx + 1].start()
    else:
        end = len(content)
    block = content[start:end]

    # 在各个section中提取内容
    def extract_section(text, section_name):
        # 匹配 **【section_name】** 或 **【section_name】】 直到下一个 **【xxx】 或文档结束
        sec_pattern = r'\*\*【' + re.escape(section_name) + r'】[^\n]*\n'
        sec_match = re.search(sec_pattern, text)
        if not sec_match:
            return ''
        sec_start = sec_match.end()
        # 找下一个section
        next_match = re.search(r'\*\*【(原文|作者简介|写作背景|白话译文|主旨情感|艺术赏析)】', text[sec_start:])
        if next_match:
            sec_end = sec_start + next_match.start()
        else:
            sec_end = len(text)
        return text[sec_start:sec_end].strip()

    poem = {
        'num': num,
        'title': title,
        'author_intro': extract_section(block, '作者简介'),
        'writing_background': extract_section(block, '写作背景'),
        'translation': extract_section(block, '白话译文'),
        'theme': extract_section(block, '主旨情感'),
        'appreciation': extract_section(block, '艺术赏析')
    }
    poems.append(poem)

print(f'Total poems extracted: {len(poems)}')
print(f'First poem: {poems[0]["title"]}')
print(f'Last poem: {poems[-1]["title"]}')

# 检查缺失字段
missing_counts = {'author_intro': 0, 'writing_background': 0, 'translation': 0, 'theme': 0, 'appreciation': 0}
for p in poems:
    for k in missing_counts:
        if not p.get(k):
            missing_counts[k] += 1
print(f'Missing fields: {missing_counts}')

# 检查重复序号
nums = [p['num'] for p in poems]
dups = {k: v for k, v in Counter(nums).items() if v > 1}
print(f'Duplicate nums: {len(dups)}')
for k, v in sorted(dups.items()):
    print(f'  {k}: {v} times')

# 去重：保留每个序号最后一次出现的（因为文档后面的是完整版）
seen = set()
unique_poems = []
for p in reversed(poems):
    if p['num'] not in seen:
        seen.add(p['num'])
        unique_poems.append(p)
unique_poems = list(reversed(unique_poems))

print(f'Unique poems: {len(unique_poems)}')
print(f'Num range: {unique_poems[0]["num"]} - {unique_poems[-1]["num"]}')

# 检查是否有缺失的序号
all_nums = set(p['num'] for p in unique_poems)
missing_nums = [n for n in range(1, 301) if n not in all_nums]
print(f'Missing nums (1-300): {missing_nums}')

# 构建输出JSON
output = {'poems': []}
for p in unique_poems:
    output['poems'].append({
        'title': p['title'],
        'author_intro': p['author_intro'],
        'writing_background': p['writing_background'],
        'translation': p['translation'],
        'theme': p['theme'],
        'appreciation': p['appreciation']
    })

with open('d:\\AAA\\video-tools\\ai-video-solo\\doc\\parsed_讲解.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print('Saved to parsed_讲解.json')
