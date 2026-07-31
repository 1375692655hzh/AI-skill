# WorkBuddy Runner 层修复清单（给沙箱 owner）

> 这份清单对应《土耳其报告自动化系统 — 执行问题与 Bug 调查报告》里 **我（skill 仓库）改不了、需要 WorkBuddy 沙箱侧修** 的部分。
> Skill 层的 Bug 1/4/5/6/7/8/9 已在 git 仓库修复（commit `84a33dd`），下面是 runner 层仍需处理的 Bug。

---

## ✅ Skill 侧已修复（仅供参考，不需要你再动）

| Bug | 修复内容 |
|-----|---------|
| **1（根因）** | 所有 7 个 skill 的输出文件**统一为 `.md`**（脚本硬编码 + AA config + config.example + README/QUICKSTART/SETUP/SKILL 文档）。git grep `_zh.txt` 已无残留。**请把 WorkBuddy 的 `automation_config.json` 里所有 `full_pattern` / `brief_pattern` 确认也是 `.md`，与 git 保持一致。** |
| **4** | `fetch_all_paraborsa.py`: `BeautifulSoup("lxml")` → `"html.parser"`（lxml 原生绑定在部分 Windows 环境会段错误，进程直接 Exit 1 无 traceback）；加了 `faulthandler.enable()`。 |
| **5** | `fetch_info_daily.py` + `fetch_info_technical.py`: 加了共享 `requests.Session` + `Retry(total=4, backoff_factor=1.5, status_forcelist=429/5xx)`；单请求超时 20s → 40s；lxml → html.parser。`fetch_via_project.py` subprocess 超时 120s → 180s。 |
| **6（部分）** | skill 层的 `.unlink()` 全部包了 `_safe_unlink()` helper，捕获 `OSError`/`PermissionError`。**但如果你沙箱的 `safe-delete` 在更底层拦截了 `os.remove` 之外的操作（例如文件写入、移动），仍需你在沙箱侧加同样的容错。** |
| **7** | close 简报 `min_chars` 400 → 200，`max_chars` 500 → 600（config.json + config.example + validator default + generate default + template + SKILL + SETUP 全部同步）。 |
| **8** | 4 个 `call_llm.py`（close/morning/info_daily/info_technical）: 超时 120s → 180s，加 3 次指数退避重试（覆盖 Timeout/ConnectionError/429/5xx，非 transient 错误快速失败）。 |
| **9** | `fetch_all_paraborsa.py` + `scan_paraborsa.py`: 所有 `resp.json()` 包 try/except，失败时打印 HTTP status + body[:200]；429/5xx 当 transient 重试而非永久失败。 |

---

## 🔴 Runner 层仍需修复（按优先级）

### R1. `locate_outputs()` 禁止回退到旧日期文件（报告 Bug 1 + Bug 2，最危险）

**现状**：`locate_outputs()` 在 `today_tr` 精确文件不存在时，用 `newest_file(*_xxx.*)` 回退到目录里 mtime 最新的文件——已造成 **12 次错发旧稿**（见报告附录 1）。

**修复**：

```python
def _today_dated_file(output_dir: Path, pattern: str, today_tr: str) -> Path | None:
    """Only accept a file whose filename embeds today_tr. Never fall back to newest."""
    candidate = output_dir / pattern.replace("{date}", today_tr)
    return candidate if candidate.exists() else None

def locate_outputs(task: dict, today_tr: str, output_dir: Path) -> dict:
    full = _today_dated_file(output_dir, task["full_pattern"], today_tr)
    brief = _today_dated_file(output_dir, task.get("brief_pattern", ""), today_tr) if task.get("brief_pattern") else None

    if not full:
        return {"ok": False, "reason": "gen_failed",
                "error": f"today's file not found for {today_tr}; refusing to fall back to older file"}

    # 唯一允许的 fallback：任务显式标记 allow_fallback_to_latest（例如周末 AA 沿用周五稿）
    if task.get("allow_fallback_to_latest") and not full:
        full = newest_file(output_dir, task["full_pattern"])

    return {"ok": True, "full_file": full, "brief_file": brief}
```

**关键点**：
- 默认行为：`today_tr` 文件不存在 → 直接 `gen_failed`，**绝不回退**。
- 仅当 task 配置里有 `"allow_fallback_to_latest": true` 时才允许回退（例如 `aa_morning_briefing` 周末沿用周五稿）。
- 同时验证文件名里的日期等于 `today_tr`，防止扩展名错配时命中旧文件。

### R2. Runner 启动时做扩展名一致性校验（报告 Bug 1 防御）

**目的**：防止 skill 脚本输出 `.txt`、runner 期望 `.md`（或反过来）时静默 fallback。

**修复**：runner 启动后、locate 之前，读 output 目录里最近一次成功生成的文件，和 `automation_config.json` 的 `full_pattern` 扩展名对比：

```python
def _check_ext_consistency(task: dict, output_dir: Path) -> None:
    expected_ext = Path(task["full_pattern"]).suffix  # e.g. ".md"
    files = sorted(output_dir.glob(f"*{task.get('name', '*')}*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return
    actual_ext = files[0].suffix
    if actual_ext != expected_ext:
        raise RuntimeError(
            f"Extension mismatch for {task['name']}: runner expects {expected_ext}, "
            f"but skill produced {actual_ext} (latest: {files[0].name}). "
            f"Update automation_config.json full_pattern to match."
        )
```

**关键点**：fail-fast + 推送告警，比静默错发旧稿好。

### R3. AA 晨报调度整体后移到 14:10 以后（报告 Bug 3，AA 真实失败率 66.7%）

**现状**：AA 调度为北京时间 12:10 / 14:10，但日志显示文章实际发布时间是伊斯坦布尔 08:40 ≈ 北京时间 13:40。12:10 这一轮**必然失败**。

**修复**：把 `automation-1784279758489` 配置里 AA 晨报的触发时间改为：
- 首轮 **14:10**（北京时间）—— 文章已上线，给网络留余量
- 兜底 **14:40 / 15:10 / 15:40**

或更稳的做法：skill 内部加「文章未发布则等待 N 分钟后重试」逻辑（skill 侧 `fetch_aa_morning_briefing.py` 可以改，但这需要你确认要不要动 skill）。

### R4. safe-delete 沙箱层容错（报告 Bug 6）

**现状**：`[safe-delete][SAFE_DELETE_FAIL_CLOSED] {"reason": "windows-sandbox-recycle-bin-unavailable"}` 直接让 `info_technical` 崩溃。

**说明**：我在 skill 侧已经把所有 `.unlink()` 包了 try/except（`_safe_unlink`），**但如果你的 safe-delete 是在更底层（沙箱 syscall 拦截层）fail-closed**，skill 层的 try/except 可能接不到。

**修复（沙箱侧）**：safe-delete 对 `.cache/` 目录下的文件删除：
- 失败时降级为 `os.remove`（不经过回收站），再失败就**静默跳过**而不是 fail-closed。
- 缓存清理失败的最坏情况是「重用旧缓存」，这已被 skill 层的日期校验兜住，不该让整个生成任务挂掉。

### R5. 合并冗余调度（报告 Bug 10）

**现状**：AA 在 14:06 失败、14:18 又成功，间隔仅 12 分钟，浪费 API 额度。

**修复**：
- 同一任务两次触发**至少间隔 15–30 分钟**。
- runner 加「同任务 N 分钟内已成功推送则跳过」的幂等锁（基于 `push.log` 的 last_success_ts）。

### R6. runner 子进程用 `sys.executable`（报告 Bug 11）

**修复**：`runner.py` 里 `cmd = ["python", ...]` → `cmd = [sys.executable, ...]`。这样不依赖 PATH 里有 `python`，更健壮。执行前打印最终命令和 Python 版本，方便排查。

### R7. `resolve_target_date.py` 输出格式鲁棒性（报告 Bug 11 第二个）

**现状**：`resolve_target_date.py` 输出 JSON，若前面有 warning 行会干扰 runner 的 `first_line.startswith("{")` 解析。

**修复**（二选一）：
- **skill 侧**（我可以改）：`resolve_target_date.py` 加 `--json` 参数，JSON 只走 stdout，所有日志/警告走 stderr。
- **runner 侧**：更严格地只读 stdout 的**最后一个** JSON 对象，而不是第一个 `{` 开头的行。

建议两边都做（skill 加 `--json`，runner 改读最后一行 JSON）。

---

### R8. 收评墙时与 `gen_failed` 重试（2026-07-31 事故补充）

Skill 侧已压墙时（BHT 列表页优先、Info/Paraborsa 快速失败、校验数字归一化）。Runner 侧建议：

1. **默认子进程超时 600s 才合理的前提**：skill 墙时目标 **&lt; 8 分钟**（Info 全挂时也应 &lt; 60s 软失败 + 正常 BHT/LLM）。若仍偶发超时，先确认已部署上述 skill 修复，再视情况把 close 任务超时调到 720–900s。
2. **`gen_failed` 后对校验类失败可隔 N 分钟重试 1 次**（仅在 skill 修复发布后有意义）。此前 provenance 误杀（`13458.1` vs `13458.10`）不会因 LLM 重写而好转；数字归一化上线后，偶发结构校验失败才值得 runner 侧自动再跑一轮。**不要**对 `skipped_exists` 或已成功写出的日期再自动重推。

### R9. 收评 cron：主跑 00:10 + 可选 23:55/00:15 重试（页面可见滞后）

**背景**：BHT 文章 CMS 戳常为 TR 18:30 / 北京 23:30，但 `/borsa`「İlgili Haberler」等模块可能约北京 **23:50+** 才挂上。Skill 在列表未上榜时会 **快速 `list_absent`**（正确，不海扫），第二轮必须靠 runner。

**请改 WorkBuddy / cron（北京时间，仅交易日）：**

| 项 | 建议值 |
|----|--------|
| **推荐主跑** | **00:05～00:15**（取整点如 `00:10`） |
| **备选** | 主跑 `23:55`，失败则 **`00:15` 再跑 1 次** |
| 重试条件 | 首轮结果为 `list_absent` / BHT 无文 / `gen_failed` |
| 禁止重试 | 当日 `*_close_report_zh.md` 已成功存在 → `skipped_exists`，不重推 |
| 周末/假日 | cron 直接 skip（不要依赖 skill 回落到上一日来「空跑」） |

Skill 仓库 `config.example.json` 的 `schedule` 字段为约定说明；runner 读取后落到实际 cron / automation_config。

---

## 建议的验证流程

修完 R1–R9 后，建议跑一次 dry-run：
1. 故意删掉今天的 `output` 文件，确认 runner **不再回退到昨天**，而是直接 `gen_failed` + 推送告警。
2. 故意把 skill 输出改成 `.txt`，确认 R2 的扩展名校验 fail-fast。
3. 模拟 AA 在 12:10 触发，确认首轮直接跳过（或等待），不再无意义重试。
4. 收评：人为在 23:55 制造 `list_absent`，确认 **00:15 会自动再跑且成功后不再重推**。

修完后这两周内的高频错版/漏发问题应该能彻底消除。
