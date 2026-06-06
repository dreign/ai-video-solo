# Tasks

- [x] Task 1: 解析讲解文档并提取所有诗词解析数据
  - [x] SubTask 1.1: 读取 `诗词三百首讲解.md`，按诗词分割提取每首的 title, author_intro, writing_background, translation, theme, appreciation
  - [x] SubTask 1.2: 建立 title -> 解析数据的映射表

- [x] Task 2: 解析 poems.json 并建立映射
  - [x] SubTask 2.1: 读取 `poems.json`，建立 title -> 基础数据的映射表
  - [x] SubTask 2.2: 统计 poems.json 中的诗词总数

- [x] Task 3: 匹配并补充 poems.json 中已有诗词的讲解字段
  - [x] SubTask 3.1: 对 poems.json 中每条诗词，在讲解文档映射表中查找匹配
  - [x] SubTask 3.2: 匹配到的，将解析字段补充到 poems.json 数据中
  - [x] SubTask 3.3: 未匹配到的，通过大模型/搜索补全讲解内容

- [x] Task 4: 将讲解文档中有但 poems.json 中没有的诗词补充进去
  - [x] SubTask 4.1: 找出讲解文档中有但 poems.json 中没有的诗词列表
  - [x] SubTask 4.2: 搜索补全这些诗词的基础信息（title, author, dynasty, content, fame_score）
  - [x] SubTask 4.3: 将新诗词添加到 poems.json，index 自增

- [x] Task 5: 二次校验并输出最终文件
  - [x] SubTask 5.1: 校验所有诗词都有完整的 author_intro, writing_background, translation, theme, appreciation
  - [x] SubTask 5.2: 校验 index 连续无重复
  - [x] SubTask 5.3: 校验诗词总数
  - [x] SubTask 5.4: 输出最终的 poems.json
