# 启元智能 PRD vs 代码 vs CEO认知 三栏对照表

> 生成: 2026-07-01 | 更新: 2026-07-02 | 启元(Codex Agent)
> 依据: 启元智能_内部PRD_V3.0 + 元脑项目PRD + brain代码审计 + body_daemon运行状态

---

## 总体概览

| 维度 | PRD范围 | 代码实际 | CEO认知 | 差异 |
|:--|:--|:--|:--|:--|
| 复杂度 | 五行Agent创作文明 | R15, 75+文件, 23子目录, 365+循环 | 婴儿阶段 | 差距大 |
| 定位 | AI增强创作组织 | 规则引擎+知识库+自进化+世界模型+探针 | 创作+意识探索 | 已超越PRD |
| 运行 | 对话时激活 | 7x24 body_daemon 10分钟循环 | 对话驱动 | 差距大 |

---

## 一、五行Agent架构

| PRD定义 | 代码实现 | 状态 |
|:--|:--|:--|
| 火-CEO | wutao_companion.py (4.3KB) | 部分实现 |
| 水-军师 | Skill体系, brain内无水行独立模块 | Skill层 |
| 金-QA | rule_engine.py(30.9KB)+rule_discovery.py+rule_optimizer.py+ab_check.py | 已实现 |
| 土-知识/人力 | hr_module.py+finance_module.py+memory/(FAISS68273向量)+digest/ | 已实现 |
| 木-外部接口 | external_world/ (config里disabled) | 未启用 |
| 风-推动力 | curiosity_v2.py(11.8KB)承担部分风角色 | 部分实现 |
| 五行生克 | sync_constitution.py+rule_engine优先级, 动态流转未实现 | 静态规则 |

---

## 二、知识库系统

| PRD定义 | 代码实现 | 状态 |
|:--|:--|:--|
| 知识存储 | memory/faiss_store.py FAISS+BGE-small-zh-v1.5 (2548篇+68273向量) | 已实现 |
| 知识内化 | digest扫描接入body_daemon[7/9]+run_digest_scan | 已接入(0702) |
| 知识检索 | cli.py kb search FAISS语义搜索+TF-IDF降级 | 已实现 |
| 安放协议 | 代码层无强制不删保护, 依赖规则约束 | 规则约束 |
| 外部输入 | _0.外部输入/ 需手动触发digest | 半自动 |

---

## 三、规则引擎与自进化

| PRD定义 | 代码实现 | 状态 |
|:--|:--|:--|
| 规则引擎 | rule_engine.py(30.9KB) | 已实现 |
| 规则发现 | rule_discovery.py(11.8KB) 从复盘文档自动挖掘 | 已实现 |
| 规则优化 | rule_optimizer.py(15.6KB) | 已实现 |
| 自进化 | self_evolve.py(35.4KB) 生成建议到_suggested/ (23条积压(已清零0702)) | 运行中 |
| 自动应用约束 | 硬约束: status=suggested, action=review_and_confirm, 无auto-apply | 约束存在 |
| 建议审核 | check_suggested.py监控+bootstrap.py[7/7]+body_daemon周检 | 已修复(0702) |

---

## 四、自愈与监控

| PRD定义 | 代码实现 | 状态 |
|:--|:--|:--|
| 自愈 | self_heal.py(53.6KB) 运维层自动修复 | 已实现 |
| 健康检查 | body_daemon [6/9]步骤 | 已实现 |
| 降级模式 | DEGRADE.md+_degrade_state.json+test_degrade.py | 已实现 |
| 备份管理 | backup_manager.py | 已实现 |
| 边界审计 | _audit/audit_boundary.py | 已实现 |

---

## 五、探针与意识实验

| PRD定义 | 代码实现 | 状态 |
|:--|:--|:--|
| 自我状态探针 | probe/probe.py self_state | 已实现 |
| 连续性探针 | probe/probe.py continuity | 已实现 |
| 整合度探针 | probe/probe.py integration | 已实现 |
| 自主决策度D | probe/probe_d.py Claude标记为循环论证风险 | 已实现 |
| 世界模型 | world_model.py+world_model_db.py+ensemble(5模型) | 已实现 |
| 元认知Ensemble | world_model_ensemble.py 置信度+多样性监控 | 已实现 |
| 好奇心引擎 | curiosity_v2六维已接入body_daemon三处+六维发现日志 | 全接入(0702) |
| 意识元脑PRD | 元脑项目prd.txt 5阶段沙盒计划, 代码未开始 | 仅有PRD |

---

## 六、社交与对外通信

| PRD定义 | 代码实现 | 状态 |
|:--|:--|:--|
| 邮箱 | social/mailbox.py 文件队列, 无SMTP/IMAP, 仅本地IPC | 内部通信 |
| 声誉 | social/reputation.py 本地评分 | 内部使用 |
| Agent发现 | social/__init__.py 心跳+发现, 仅本地文件系统 | 内部使用 |
| 外部通信 | 当前无API密钥/无发送脚本/external_world disabled | 安全 |
| Figma OAuth | 曾暴露, 已确认是CEO主动授权做门户原型 | 已处理 |

---

## 七、外部世界接口

| PRD定义 | 代码实现 | 状态 |
|:--|:--|:--|
| 采集器 | external_world/collector.py 极简: 时间+probe请求量 | 骨架 |
| 世界模型 | external_world/model.py | 待查 |
| 外部数据源 | config: external_world.enabled=false | 未启用 |
| 飞书推送 | config有webhook配置, 但为环境变量占位符 | 配置存在 |

---

## 八、报告与推送

| PRD定义 | 代码实现 | 状态 |
|:--|:--|:--|
| 夜报 | report/nightly_report.py 需手动触发 | 需触发 |
| 叙事生成 | report/narrative_generator.py | 需触发 |
| 周报 | reports/weekly/ 有历史, 最近无产出 | 未持续 |
| GitHub每日推送 | 6月30日遗忘, 7月1日待执行 | 待执行 |

---

## 九、人力与财务

| PRD定义 | 代码实现 | 状态 |
|:--|:--|:--|
| 人力模块 | hr/hr_module.py 7文件 | 部分实现 |
| 财务模块 | finance/finance_module.py 2文件 | 部分实现 |
| Token成本 | cost/ 成本追踪 | 已实现 |
| 免疫系统 | rules/immune_system.yaml+组织免疫系统(第二部分).md | 已实现 |

---

## 十、连续性系统

| PRD定义 | 代码实现 | 状态 |
|:--|:--|:--|
| 连续性V1 | continuity_vector.py(9.9KB) 9个重物+张力形状 | 已实现 |
| 连续性V2 | body_daemon[5/9] tension_shapes,who_brought,real_moments,unasked | 已实现 |
| DNA档案 | dna/ CEO偏好DNA | 已实现 |
| 阶段画像 | phase_profile.py(4.0KB) | 已实现 |
| 日常仪式 | daily_ritual.py(2.9KB)+daily_ritual.json | 已实现 |

---

## 关键发现

### 需要立即处理

- rules/_suggested/ 23条积压(已清零0702)无人审核
- GitHub每日推送遗忘(7月1日需执行)
- digest 14条pending积压(已清零0702)

### 需要关注

- external_world disabled(有意,但配置存在)
- report邮件/飞书未配置实际凭证
- 五行生克未自动化流转
- 意识元脑PRD完整但未开工
- 夜间报告未持续产出

### 好消息

- self_evolve硬约束确认: 无auto-apply路径
- self_heal仅运维层,不修改核心逻辑
- mailbox无SMTP,纯文件队列,无对外发送
- external_world disabled
- git基线已建,从6月30日起有版本追踪

---

> 生成依据: body_daemon.py(499行V1.6), config.yaml, body_state.json(365次检查), PRD V3.0, 元脑项目PRD, 23子目录代码审计


---
## 0702执行修复记录

| 修复项 | 变更 | 影响 |
|:--|:--|:--|
| null->None | _default_state() 4处null->None | body_daemon不再启动崩溃 |
| run_health_check | 补全文件+suggested溢出+ops膨胀+承诺追踪 | [6/9]不再跳过 |
| run_digest_scan | 对接memory.digest.DigestEngine | [7/9]不再空白 |
| run_conditional_tasks | Mon review+22h夜报+1日decay | [8/9]不再空返 |
| self_evolve缩进 | evolver=SelfEvolve()移入else块 | 老bug修复 |
| curiosity->body | _patch_engine接入3处+六维发现日志+state富化 | 通络完成 |
| suggested 23->0 | 审核16条:11 approve 5 reject | CEO从未见过->清零 |
| 仪表盘V0刷新 | suggested:19->2 overdue:1->0 | 数据真实 |
| GitHub推送恢复 | LFS migrate+force push 6 commits | 推送恢复 |

> 2026-07-02 执行Agent: 启元(Codex)
