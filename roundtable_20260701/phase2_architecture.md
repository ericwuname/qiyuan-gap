# Phase 2 | Architecture & Design | 30 Rounds

| # | Speaker | Topic |
|:--|:--|:--|
| 1 | Software Architect | 17-dim scan: all organs present, no nervous system |
| 2 | Execution Director | Confirmed: body_daemon hardcoded calls, model_router standalone, no unified trigger |
| 3 | Software Architect | Three candidates: A.Orchestrator B.EventBus C.Blackboard+Heartbeat |
| 4 | Security Auditor | Hard constraints: write isolation, read audit, permission tiering |
| 5 | Software Architect | Recommend C: upgrade body_daemon, blackboard enables audit natively |
| 6 | Execution Director | Work packages: WP1.blackboard core, WP2.body_daemon upgrade, WP3.module adapters |
| 7 | Scrum Master | Sprints: S1-blackboard+daemon, S2-probe+evolve, S3-router+CEO report |
| 8 | Security Auditor | Sprint security gates: permission matrix, suggested isolation, source traceability |
| 9 | Software Architect | Event format: JSON with event_id/source/type/severity/timestamp/payload/permissions |
| 10 | Execution Director | Storage: JSON+mtime polling, 10min latency acceptable for Phase 1 |
| 11 | Scrum Master | Risk: 10min delay, Phase 2 optimize to real-time |
| 12 | Security Auditor | Blackboard self-defense: SHA256 checksum, tamper detection |
| 13 | Software Architect | Architecture diagram: CEO-router-blackboard-probes-memory-body_daemon |
| 14 | Execution Director | Phase 1 scope: probe+evolve+router+memory(readonly). NOT: curiosity/world_model/social |
| 15 | Scrum Master | Sprint 1 tasks: 6 cards, bus dir/blackboard.py/permissions.py/audit.py/daemon upgrade/test |
| 16 | Security Auditor | Test cases: permission denial, checksum failure, audit log integrity |
| 17 | Software Architect | 5 critical dimensions: layout OK, modules OK, protocol OK, security OK, observability WARN |
| 18 | Execution Director | Observability: blackboard exposes health.json |
| 19 | Scrum Master | Effort: 4-6 hours, no external dependencies |
| 20 | Security Auditor | bus/ in .gitignore whitelist |
| 21 | Execution Director | Capacity: 72KB/day, 26MB/year, acceptable |
| 22 | Software Architect | Rotate: daily files, 30-day retention, archive via coral protocol |
| 23 | Security Auditor | Archive: old blackboard to _archive/, never delete |
| 24 | Scrum Master | Phase 2 deliverables: bus/ + upgraded daemon + test_bus.py |
| 25 | Execution Director | Handoff to Phase 3 |
| 26 | Software Architect | Architecture decision: Central Blackboard, 3 sprints, no open issues |
| 27 | Execution Director | Next: Phase 3 stress-test by CVO + Proactive Defender |
| 28 | Scrum Master | Cross-phase: Phase 3 can parallel-discuss at architecture level |
| 29 | Security Auditor | Final: architecture doc itself is sensitive, limit external sharing |
| 30 | Software Architect | Phase 2 closed. Handing off to Phase 3 |

> Phase 2 complete | 30 rounds | Handoff to Phase 3 (Risk & Prevention)