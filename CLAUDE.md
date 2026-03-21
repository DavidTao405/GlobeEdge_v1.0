# WorldEdge — Claude Code 指引

## 專案說明
社會信念動態世界模型，詳見 WORLDEDGE_PLAN.md

## 開發原則
- 數學核心 (core/) 零外部依賴，可獨立測試
- BeliefState 必須 frozen=True
- 每個 Phase 完成前先跑對應測試
- 介面設計請參考: https://www.ibm.com/design/language/

## 目前進度
- [ ] Phase 1：數學核心
- [ ] Phase 2：資料模型 + API
- [ ] Phase 3：爬蟲層
- [ ] Phase 4：GPU 加速
- [ ] Phase 5：前端
- [ ] Phase 6：校準

## 環境
- Python 3.11, venv 在 .venv\
- Windows, PowerShell
- GPU: RTX 4070 SUPER
