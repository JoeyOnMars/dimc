# dimc down 完整流程图

## 整体架构

```mermaid
flowchart TB
    subgraph CLI["dimc CLI"]
        CMD["dimc down"]
    end

    subgraph L0["Layer 0: SessionEndService"]
        SES[SessionEndService.execute]
        SMART[run_smart_scan]
        FINALIZE[finalize]
    end

    subgraph L1["Layer 1: DataCollector"]
        DC[DataCollector.collect_all]
    end

    subgraph L2["Layer 2: Context & Extraction"]
        CI[ContextInjector.inject]
        EE[EventExtractor]
        EI[EventIndex.add]
    end

    subgraph L3["Layer 3: Storage & Index"]
        EVENTS[~/.dimcause/events/extracted/]
        DOCS[docs/logs/]
    end

    CMD --> SES
    SES --> DC
    SES --> SMART
    SES --> FINALIZE
    DC --> CI
    CI --> DOCS
    SMART --> EE
    EE --> EI
    EI --> EVENTS
```

## 详细流程：dimc down

```mermaid
flowchart TB
    START(["dimc down"]) --> GET_TS["获取 session 时间窗口<br/>get_session_start_timestamp()"]

    GET_TS --> DC["DataCollector.collect_all()"]

    subgraph L1_DataCollection["L1: 数据采集"]
        direction TB
        DC --> BRAIN["_collect_brain_artifacts()"]
        BRAIN --> CHATS["_collect_raw_chats()"]
        CHATS --> JSONL["_collect_claude_code_sessions()"]
        JSONL --> GIT["_collect_git_context()"]
        GIT --> JOBS["_collect_job_logs()"]
    end

    JSONL --> PARSE["ClaudeCodeLogParser<br/>find_sessions() + parse_to_markdown()"]

    PARSE --> SUMMARY["打印采集统计面板"]

    SUMMARY --> CHECK{"检查数据存在性"}
    CHECK -->|无 logs 无 brain| CONFIRM1["Confirm.ask 确认继续"]
    CHECK -->|无 logs 有 brain| CONFIRM2["Confirm.ask 警告继续"]
    CHECK -->|有数据| CREATE_LOG["create_daily_log('end')"]

    CONFIRM1 -->|No| ABORT["return False"]
    CONFIRM1 -->|Yes| CREATE_LOG
    CONFIRM2 -->|No| ABORT
    CONFIRM2 -->|Yes| CREATE_LOG

    CREATE_LOG -->|新建| WRITE["写入 end.md 模板"]
    CREATE_LOG -->|复用| READ["读取已有 end.md"]

    WRITE --> INJECT["ContextInjector.inject()"]

    subgraph L2_ContextInjection["L2: 上下文注入"]
        direction TB
        INJECT --> OBJ["提取 session objective"]
        OBJ --> TEMPLATE["填充 end.md 模板"]
        TEMPLATE --> SECTION["添加各区块内容"]
    end

    SECTION --> JOBS_GEN["_generate_claude_code_jobs()"]

    subgraph JobGen["Job 文件生成 (Phase 2)"]
        JOBS_GEN --> SCAN["扫描 claude_code_sessions"]
        SCAN --> AGENT["parser.extract_agent_jobs(session)"]
        AGENT --> SUBAGENTS["遍历 subagents/agent-*.jsonl"]
        SUBAGENTS --> EXTRACT_JOB["提取 goal / result_summary"]
        EXTRACT_JOB --> WRITE_JOB["写入 job-start.md / job-end.md"]
    end

    WRITE_JOB --> SMART_SCAN["run_smart_scan()"]

    subgraph L2_5_SmartScan["L2.5: Smart Scan (LLM Event Extraction)"]
        SMART_SCAN --> SETUP["初始化 LLM Client + EventExtractor"]
        SETUP --> PROCESS_JSONL["处理 Claude Code JSONL markdown"]

        subgraph JSONL_Extraction["JSONL 处理 (Phase 1)"]
            PROCESS_JSONL --> EXTRACT_CC["extractor.extract_from_text()"]
            EXTRACT_CC --> SAVE_CC["保存到 ~/.dimcause/events/extracted/"]
            SAVE_CC --> INDEX_CC["EventIndex.add()"]
        end

        PROCESS_JSONL --> PROCESS_AG["遍历 AG_Exports raw_chat_files"]

        subgraph AG_Extraction["AG_Exports 处理"]
            PROCESS_AG --> READ_LOG["读取 log.md 文件"]
            READ_LOG --> EXTRACT_AG["extractor.extract_from_text()"]
            EXTRACT_AG --> SAVE_AG["保存事件到 storage"]
            SAVE_AG --> INDEX_AG["EventIndex.add()"]
        end
    end

    SMART_SCAN --> FINALIZE["finalize()"]

    subgraph L3_Finalize["L3: 完成"]
        FINALIZE --> UPDATE["update_index()"]
        UPDATE --> GIT_COMMIT["git add + commit"]
        GIT_COMMIT --> DONE(["return True"])
    end

    style L1_DataCollection fill:#e1f5fe
    style L2_ContextInjection fill:#e8f5e8
    style L2_5_SmartScan fill:#fff3e0
    style L3_Finalize fill:#f3e5f5
    style JobGen fill:#ffebee
    style JSONL_Extraction fill:#ffebee
```

## 双轨并行：AG_Exports vs Claude Code JSONL

```mermaid
flowchart LR
    subgraph Input["数据源"]
        AG["AG_Exports/*.md"]:::ag
        JSONL["Claude Code JSONL"]:::jsonl
    end

    subgraph Process["处理流水线"]
        direction TB
        AG --> DC1["DataCollector<br/>_collect_raw_chats()"]
        JSONL --> DC2["DataCollector<br/>_collect_claude_code_sessions()"]

        DC1 --> PARSE1["EventExtractor<br/>AG_Exports"]
        DC2 --> PARSE2["EventExtractor<br/>Claude Code"]

        PARSE1 --> MERGE["end.md 合并"]
        PARSE2 --> MERGE
    end

    subgraph Output["输出"]
        MERGE --> END_MD["docs/logs/YYYY/MM-DD/XX-end.md"]
        MERGE --> EVENTS["~/.dimcause/events/extracted/"]
    end

    style AG fill:#bbdefb
    style JSONL fill:#ffcc80
    style Process fill:#f5f5f5
    style Output fill:#c8e6c9
```

## 数据流：SessionData

```mermaid
classDiagram
    class SessionData {
        +session_id: str
        +date_str: str
        +brain_artifacts: List[Path]
        +raw_chat_files: List[Path]
        +external_source_files: List[Path]
        +claude_code_sessions: List[ClaudeSession]  // Phase 1
        +claude_code_markdown: str                   // Phase 1
        +git_diff: str
        +git_log: str
        +job_logs: List[JobLog]
    }

    class ClaudeSession {
        +jsonl_path: Path
        +session_id: str
        +slug: Optional[str]
        +first_ts: datetime
        +last_ts: datetime
        +git_branch: Optional[str]
    }

    class AgentJob {
        +agent_id: str
        +jsonl_path: Path
        +start_ts: datetime
        +end_ts: datetime
        +goal: str
        +result_summary: str
        +full_markdown: str
    }

    SessionData --> ClaudeSession : contains
    SessionData --> AgentJob : generated from
```

## 关键文件位置

```mermaid
flowchart TB
    subgraph Config["配置检测"]
        CONFIG[config.py<br/>claude_code_sessions_dir]
    end

    subgraph Sessions["Claude Code Sessions"]
        HOME["~/.claude/projects/<br/>-Users-mini-projects-GithubRepos-dimc/"]
        SESSION["{sessionId}.jsonl"]
        SUBAGENTS["{sessionId}/subagents/<br/>agent-{id}.jsonl"]
    end

    subgraph Output["dimc 输出"]
        DOCS["docs/logs/{date}/<br/>XX-end.md"]
        JOBS["docs/logs/{date}/jobs/<br/>cc-{agentId}/"]
        EVENTS["~/.dimcause/events/<br/>extracted/{date}/"]
    end

    CONFIG --> HOME
    HOME --> SESSION
    SESSION --> SUBAGENTS

    SUBAGENTS --> JOBS

    HOME --> DOCS
    HOME --> EVENTS
```

## Phase 1 vs Phase 2 功能对比

| 功能 | Phase 1 | Phase 2 |
|------|---------|---------|
| JSONL → markdown | ✅ | ✅ |
| EventExtractor 集成 | ✅ | ✅ |
| 提取 session objective | ✅ | ✅ |
| Subagent job 检测 | - | ✅ |
| 生成 job-start.md | - | ✅ |
| 生成 job-end.md | - | ✅ |

## 时间窗口过滤

```mermaid
sequenceDiagram
    participant User as 用户
    participant DC as DataCollector
    participant Parser as ClaudeCodeLogParser
    participant File as Claude Code JSONL

    User->>DC: dimc down
    DC->>DC: 获取 session_start, session_end

    Note over DC: 窗口: [start-1h, end+5min]

    DC->>Parser: find_sessions(start, end, sessions_dir)
    Parser->>File: 扫描 *.jsonl
    File->>Parser: 返回匹配的时间范围

    Parser->>Parser: 过滤 timestamp ∉ 窗口的会话

    Parser-->>DC: List[ClaudeSession]

    DC->>Parser: parse_to_markdown(session)
    Parser->>File: 读取主文件 + sidechain
    File->>Parser: 按 timestamp 排序

    Parser-->>DC: markdown 字符串
```

## 错误处理原则

```mermaid
flowchart TB
    subgraph ErrorHandling["非致命原则"]
        E1["JSONL 扫描异常"]
        E2["EventExtractor 失败"]
        E3["Job 文件已存在"]
    end

    E1 --> LOG["logger.warning + return"]
    E2 --> LOG2["self.console.print 红色错误<br/>继续处理其他文件"]
    E3 --> SKIP["跳过，不覆盖用户编辑"]

    style ErrorHandling fill:#ffebee
```

## 依赖检查顺序

```mermaid
flowchart LR
    subgraph Check["启动检查"]
        C1["1. 检查 brain_dir 存在"]
        C2["2. 检查 export_dir 存在"]
        C3["3. 检测 Claude Code sessions_dir"]
    end

    C1 --> C2
    C2 --> C3

    C1 -->|不存在| WARN["warning + 允许继续"]
    C2 -->|不存在| WARN
    C3 -->|不存在| SKIP["跳过 JSONL 处理<br/>不影响 AG_Exports"]

    style Check fill:#fff8e1
```
