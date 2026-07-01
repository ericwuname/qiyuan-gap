import os

report_dir = r"D:\0.个人文档\个人文档\启元智能\02_基础信息\复盘报告\$调用技能发现故障_2026-07-02"
if not os.path.exists(report_dir):
    os.makedirs(report_dir)

content = r"""# 军师复盘报告：$调用技能发现故障

> 日期：2026-07-02 | 复盘人：军师（CVO）

---

## 一、事件概述

CEO报告`$chatgpt-advisor`、`$yuanbao-advisor`、`$claude-advisor`三个技能在Codex前端`$`下拉列表中搜索不到。排查过程中，`$军师`（decision-auditor）也从列表中消失。

---

## 二、军师独立调查：根因分析

### 直接原因：SKILL.md文件格式损坏

| 技能 | 文件总字节 | 实际换行符(LF) | 字面量\n字符串 | 问题 |
|:--|--:|--:|--:|:--|
| yuanbao-advisor | 2066 | **0** | **30** | 全文件一行，\n是字面量文本 |
| claude-advisor | 1670 | **0** | **30** | 同上 |
| chatgpt-advisor | 3506 | 57 | 0 | 换行正确，缺根目录链接 |
| decision-auditor | 18578 | 455 | 0 | 文件正常，索引缓存被挤 |

**根本问题**：`yuanbao-advisor`和`claude-advisor`的SKILL.md使用字面量字符串`\\n`代替实际换行符。YAML front matter解析器无法识别`name:`、`description:`等字段，导致技能在`$`下拉列表中永久不可见。

### 排查走弯路的原因：沟通偏差

> CEO自述："以前是我没有描述清楚导致了理解偏差"

| 轮次 | CEO说的 | 被理解的 | 偏差 |
|:--|:--|:--|:--|
| 1 | "搜不到" | 理解为技能发现深度问题 | 不是深度，是文件格式损坏 |
| 2 | "创建了但$调用没有序列" | 理解为需要Junction链接 | 只解决了路径问题，没解决格式问题 |
| 3 | "军师也不能调用了" | 理解为Junction导致索引被覆盖 | Junction无害，是Codex索引缓存有上限 |

**教训**：当用户说"搜不到"时，第一步应该是验证技能文件本身的格式完整性（validate_skill.ps1），而非跳转到路径/缓存等外部原因。

---

## 三、已执行的修复

### 修复1：SKILL.md换行符修复
- yuanbao-advisor/SKILL.md：字面量\n → CRLF实际换行符 ✅
- claude-advisor/SKILL.md：字面量\n → CRLF实际换行符 ✅
- 修复后均通过 validate_skill.ps1 验证

### 修复2：创建根目录Junction链接
- chatgpt-advisor → 公司核心\Tier2_中层\chatgpt-advisor ✅
- yuanbao-advisor → 公司核心\Tier2_中层\yuanbao-advisor ✅
- claude-advisor → 公司核心\Tier2_中层\claude-advisor ✅

### 待完成
- 重启Codex桌面端（刷新$下拉缓存）

---

## 四、经验沉淀（组织知识库入库）

### 规则1：新技能创建后自动验证

新建技能 → 自动运行 validate_skill.ps1 → 若FAIL则禁止发布

### 规则2：\$调用不可见排查流程

用户反馈\$搜不到技能:
  ① 确认技能目录存在
  ② 验证SKILL.md格式: validate_skill.ps1
  ③ 检查换行符: LF>0 且 CRLF格式
  ④ 检查name/description字段在front matter中可解析
  ⑤ 检查技能在根目录或通过Junction可见
  ⑥ 重启Codex桌面端刷新缓存

### 规则3：SKILL.md创建规范
- 必须使用实际换行符（CRLF），禁止字面量\n
---

## 五、军师评估

**问题严重性**: P2（日常操作故障）
**修复完整性**: 🟢 已完成
**是否需第二次审计**: 否
**CEO需关注**: 重启Codex桌面端后，确认$下拉列表恢复正常

---

> *"真正的根因往往不是表象。但真正的救赎是，下一次能更快找到根因。"*
> 军师 · 2026-07-02
"""

report_path = os.path.join(report_dir, "01_军师_CVO.md")
with open(report_path, "w", encoding="utf-8") as f:
    f.write(content)
print(f"Written: {report_path}")
