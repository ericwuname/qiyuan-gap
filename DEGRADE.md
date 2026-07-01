# 启元智脑 · 降级路径文档 (DEGRADE.md)

> **P1-4**: 明确定义三层降级的触发条件、行为、恢复方式
> **版本**: V1.0 · 2026-06-20
> **依赖**: self_heal.py (degrade_level L0-L3)

---

## 降级总览

| 级别 | 名称 | 触发条件 | 行为 | 恢复方式 | 影响 |
|:--|:--|:--|:--|:--|:--|
| **L0** | 全功能 | 所有组件正常 | 完整规则匹配+ChromaDB检索 | — | 无 |
| **L1** | 记忆降级 | ChromaDB不可用 | TF-IDF fallback检索 | pip重装ChromaDB/重启服务 | 检索精度下降但不中断 |
| **L2** | 规则降级 | 规则引擎崩溃 | 读取fallback.md固定规则 | 修复规则文件+`brain rule validate` | 规则匹配使用静态规则 |
| **L3** | 大脑不可用 | 核心组件全崩溃 | 直接读取AGENTS.md | `python restore.py <备份路径> --live` | 退回手动模式 |

---

## L1 · 记忆引擎降级

### 触发条件
- ChromaDB/BGE模型加载失败
- 向量数据库连接超时（>5秒）
- 知识库索引损坏

### 行为
1. `self_heal.py` 检测到memory_engine异常
2. 自动切换到TF-IDF fallback模式（memory_engine.py内置）
3. `brain status` 显示: `memory_engine.status=warning`
4. degrade_level设为1，degrade_name="L1-记忆降级"

### 恢复方式
```bash
# 方案1: 重新安装ChromaDB
pip install chromadb

# 方案2: 重建索引
brain kb rebuild

# 方案3: 手动健康检查+修复
brain health repair memory_engine
```

### 验证
```bash
brain health check
brain status
# 确认: degrade_level=0, memory_engine.ok=true
```

---

## L2 · 规则引擎降级

### 触发条件
- 规则YAML文件全部损坏
- 规则引擎import失败
- 规则引擎check()抛出不可恢复异常

### 行为
1. `self_heal.py` 检测到rule_engine异常
2. 自动触发 `brain rule validate` 尝试修复
3. 如果validate失败，切换到fallback.md
4. fallback.md包含核心P0规则的硬编码版本
5. `brain status` 显示: `rule_engine.status=error`
6. degrade_level设为2，degrade_name="L2-规则降级"

### 恢复方式
```bash
# 方案1: 校验并修复规则文件
brain rule validate

# 方案2: 从备份恢复规则
python restore.py _backup/brain_full_YYYYMMDD_HHMMSS/ --target brain/rules

# 方案3: 从09_AIskill备份恢复constitution/gene_protocols/immune_system
```

### 验证
```bash
brain rule validate
brain health check
# 确认: 0 issues, all rules valid
```

---

## L3 · 大脑完全不可用

### 触发条件
- 无法导入rule_engine和memory_engine
- brain CLI本身崩溃
- config.yaml损坏

### 行为
1. Codex Agent检测到brain_ok=false
2. 自动回退到AGENTS.md入口守卫规则
3. AGENTS.md包含核心P0扫描路径和三条死规则
4. 所有操作回退到手动确认模式

### 恢复方式（唯一途径：一键恢复）
```bash
# Step 1: 找到最近的完整备份
dir _backup\ /od

# Step 2: 先干运行验证备份完整性
python brain/restore.py _backup/brain_full_YYYYMMDD_HHMMSS/ --dry-run

# Step 3: 一键恢复
python brain/restore.py _backup/brain_full_YYYYMMDD_HHMMSS/ --live

# Step 4: 验证恢复结果
brain status
brain health check
```

### 验证
```bash
brain status
# 必须输出: brain_ok=true, 5/5 components ok
brain rule validate
# 必须: 0 issues
```

---

## 降级状态文件

降级状态持久化在: `brain/_degrade_state.json`

```json
{
  "level": 0,
  "name": "L0-全功能",
  "triggered_at": null,
  "reason": null,
  "auto_recovered": false
}
```

---

> *启元智能 · 军师 · P1-4降级路径文档 · 2026-06-20*