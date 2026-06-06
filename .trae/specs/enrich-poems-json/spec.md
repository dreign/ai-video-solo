# 诗词数据补充完善 Spec

## Why
现有 `poems.json` 仅有诗词基础信息（index, title, author, dynasty, content, fame_score），而 `诗词三百首讲解.md` 中包含丰富的教学解析内容（作者简介、写作背景、白话译文、主旨情感、艺术赏析）。需要将讲解内容补充到 poems.json 中，使数据更完整。同时处理两边数据不一致的情况。

## What Changes
- 为 `poems.json` 中每条诗词添加以下新字段（不删除原有字段）：
  - `author_intro`: 作者简介
  - `writing_background`: 写作背景
  - `translation`: 白话译文
  - `theme`: 主旨情感
  - `appreciation`: 艺术赏析
- 如果 `诗词三百首讲解.md` 中没有对应的诗词，通过大模型或搜索补全讲解内容
- 如果 `诗词三百首讲解.md` 中有但 `poems.json` 中没有的诗词，搜索补全后添加到 poems.json，序号用 index 自增
- 最后进行二次校验，保证内容正确性

## Impact
- Affected files: `poems.json`
- Source data: `诗词三百首讲解.md`

## ADDED Requirements

### Requirement: 数据字段补充
The system SHALL 为 poems.json 中的每条诗词添加 author_intro, writing_background, translation, theme, appreciation 字段。

#### Scenario: 讲解文档中有对应诗词
- **WHEN** 诗词三百首讲解.md 中有该诗词的完整解析
- **THEN** 将对应字段内容提取并补充到 poems.json 中

#### Scenario: 讲解文档中无对应诗词
- **WHEN** 诗词三百首讲解.md 中没有该诗词的解析
- **THEN** 通过大模型或搜索补全对应的讲解内容

#### Scenario: 讲解文档中有但 poems.json 中无
- **WHEN** 诗词三百首讲解.md 中有解析但 poems.json 中没有该诗词
- **THEN** 搜索补全该诗词的 title, author, dynasty, content 等基础信息，添加到 poems.json，index 自增

### Requirement: 数据一致性校验
The system SHALL 在补充完成后进行二次校验。

#### Scenario: 二次校验
- **WHEN** 所有数据补充完成后
- **THEN** 校验：1) 所有诗词都有完整的6个新字段；2) 字段内容不为空；3) index 连续无重复；4) 诗词总数与讲解文档中的数量一致
