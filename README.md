# reactive-resume · 中文求职套件 Skill

一个**隐私优先、数据存本地**的中文求职技能，灵感来自开源项目 [reactive-resume](https://github.com/reactive-resume/reactive-resume)。它陪你走完从「投简历」到「拿 offer」的全流程，所有简历与求职数据只存在本地 JSON 文件里，随时可带走、可迁移。

## 功能

| 工作流 | 做什么 |
|---|---|
| 从零建简历 | 访谈式采集 → 写入 `resume.json` → schema 校验 → 渲染 Markdown/HTML |
| 针对 JD 优化 | JD 逐条匹配分析（具备/部分/缺失 + 证据）→ 改写前后对照 → ATS 体检 |
| 求职信 | 三段式结构，与简历互为印证，绝不引入简历里没有的经历 |
| 投递跟踪 | `career.json` 记录每次投递，按阶段生成看板，自动提醒超期 |
| 面试准备 | 高频问题清单 + STAR 故事挂接 + 3 分钟开场白 + 反问 + 时间盒 |
| 面试复盘 | 自评 → 补事实库/故事库 → 下周改进计划 |
| Offer 比较 | 统一维度换算年总包与有效时薪，辅助但不替你决策 |

设计上继承原项目的三件事：**数据主权、单一数据源、求职是一个系统不是一张纸**。

## 安装

### 方式一：复制源码（推荐，可改可调试）

```bash
# 把 reactive-resume/ 整个目录复制到 WorkBuddy 技能目录
cp -R reactive-resume ~/.workbuddy/skills/reactive-resume
```

重启/刷新 WorkBuddy 后，对话里提到「简历 / 求职 / 面试 / 投递 / Offer」等意图即会自动触发。

### 方式二：安装打包文件

`reactive-resume.skill` 是分发用的打包文件，可通过 WorkBuddy 的技能安装入口导入。

## 目录结构

```
reactive-resume/
├── SKILL.md                  # 技能主文件（7 条工作流 + 检查清单）
├── references/               # 数据结构与写作/ATS 指南
│   ├── resume-schema.md      # 简历数据结构（resume.json）
│   ├── career-schema.md      # 求职管理结构（career.json）
│   ├── writing-playbook.md   # 简历与求职信写作手册
│   ├── ats-guide.md          # ATS 优化指南
│   └── templates.md          # 模板与排版
├── scripts/
│   └── validate_resume.py    # 纯标准库：schema 校验 / ATS 扫描 / Markdown+HTML 渲染
└── evals/                    # 触发评测与回归用例
```

## 示例角色说明

参考文件里的完整示例统一用「用户增长运营」角色演示；**任意行业（研发 / 销售 / 职能 / 设计）字段完全一致，只换文字内容**。

## 诚信红线

本技能刻意把「不编造」写进工作流与校验器：标注了「具备」却拿不出证据会被校验器报错，缺失的经历诚实告知而非硬凑。
