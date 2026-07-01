# 启元智能 · 大脑一键恢复指南

> 傻瓜式恢复文档。不用懂Python，跟着做就行。
> 最后更新：2026-06-20

---

## 什么时候用

| 场景 | 操作 |
|:--|:--|
| brain/ 目录被误删或损坏 | 从备份恢复 |
| 规则文件被改坏了 | 从备份恢复brain/rules/ |
| 升级brain后出问题 | 回滚到备份版本 |
| 换电脑/重装系统 | 从备份重建整个brain |

---

## 前提条件

1. 有Python 3.10+（装过就行）
2. 有备份目录（如 `_backup/brain_full_20260620_035352/`）
3. 在启元智能根目录下执行（能看到 `brain/` 文件夹的地方）

---

## 三步恢复

### 第一步：验证备份（可选，耗时1秒）

```bash
python brain/restore.py _backup/brain_full_20260620_035352 --dry-run
```

看到 `[OK]` = 备份完整，可以恢复。
看到 `[!!]` = 备份有问题，换个备份或找原因。

### 第二步：隔离测试恢复（推荐，耗时10秒）

```bash
python brain/restore.py _backup/brain_full_20260620_035352
```

这一步会把备份复制到临时文件夹，然后自动运行5项验证：
- brain status（大脑是否在线）
- rule validate（规则是否合法）
- count_rules（规则数量是否对得上）
- kb search（知识库是否可查询）
- health check（健康检查是否通过）

看到 `结果: PASS` = 备份完好，可以放心执行第三步。
看到 `结果: FAIL` = 备份本身有问题，换备份。

### 第三步：正式恢复到工作区（P0级，需谨慎）

```bash
python brain/restore.py _backup/brain_full_20260620_035352 --live
```

> ⚠️ 这会覆盖当前 `brain/` 目录！脚本会要求你输入 `YES` 确认。

---

## 报告解读

恢复报告会显示每步结果：

```
[OK] validate_backup: 备份中找到了X个规则文件
[OK] copy_brain: 复制成功
[OK] brain_status: brain在线，5个组件全OK
[OK] rule_validate: 全部规则通过校验
[OK] count_rules: backup=21 restored=21（数量一致）
[OK] kb_search: 知识库查询正常
[OK] health_check: 健康检查通过
```

- `[OK]` = 通过
- `[!!]` = 失败，看后面的错误信息
- `PASS` = 全部通过，可以放心用
- `FAIL` = 有问题，不要用

---

## JSON输出（供脚本调用）

```bash
python brain/restore.py _backup/brain_full_20260620_035352 --json
```

输出标准JSON，方便其他脚本解析。

---

## 常见问题

**Q: 没有备份怎么办？**
找最近的 `_backup/brain_full_*` 目录。或运行 `_scripts/backup-critical.ps1` 生成新备份。

**Q: 只恢复规则文件可以吗？**
目前restore.py恢复整个brain/。只恢复部分文件的话，手动从备份复制单个文件即可。

**Q: 恢复后brain不工作？**
说明备份本身就有问题。用 `--dry-run` 先验证，或者换更早的备份。

**Q: 怎么创建备份？**
参考 `SOP-012_灾难恢复标准`。Python版备份脚本正在开发中（P0-2）。

---

> *"恢复不是给灾难准备的——是给你自己准备的。"*
> *启元智能 · 2026-06-20*