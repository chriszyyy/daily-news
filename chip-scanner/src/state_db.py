"""SQLite 状态机 — 三级漏斗持久化, 从根本绕开全市场筹码限流。

核心设计 (解决限流):
  - Low  池: 全 universe (~1897 只), 仅用全市场快照字段流转, **不逐只算筹码**。
  - Mid  池: 由 Low 用"廉价信号"(低位+流动性健康, 均来自一次批量快照) 晋升而来。
             **只对 Mid+High 池逐只算筹码 SCR** → 每日筹码请求量降至几十, 不触发封禁。
  - High 池: 由 Mid 用筹码指标 (低 SCR + 低获利 + 价≤成本) 晋升, 送视觉终审。

防抖 (anti-flapping):
  - level_since: 进入当前级别日期; min_stay_days 内不降级。
  - cooldown_until: 降级后冷却, 期间不可再晋升。

表:
  stocks      — 主状态表 (每只一行)
  transitions — 状态流转审计日志
  scan_runs   — 每日扫描运行日志
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                       "data", "state.db")

LEVELS = ("Low", "Mid", "High")


def connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS stocks (
            code            TEXT PRIMARY KEY,
            name            TEXT,
            level           TEXT NOT NULL DEFAULT 'Low',
            level_since     TEXT NOT NULL,
            -- 快照字段 (每日批量刷新)
            price           REAL,
            change_60d_pct  REAL,
            turnover_yuan   REAL,
            float_mktcap    REAL,
            turnover_ratio  REAL,    -- 成交额占流通市值 %
            health          TEXT,
            industry        TEXT,
            pe_ttm          REAL,    -- PE-TTM (剔除亏损用, <=0 为亏损)
            -- 筹码字段 (仅 Mid/High 刷新)
            scr             REAL,
            scr70           REAL,
            band70          REAL,
            dominance       REAL,
            sharpness       REAL,
            near_peak       REAL,
            second_ratio    REAL,
            profit_ratio    REAL,
            avg_cost        REAL,
            cost_low90      REAL,
            cost_high90     REAL,
            chip_date       TEXT,
            -- 防抖
            cooldown_until  TEXT,
            updated_at      TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS transitions (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            code      TEXT NOT NULL,
            from_lvl  TEXT,
            to_lvl    TEXT,
            reason    TEXT,
            ts        TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS scan_runs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date    TEXT NOT NULL,
            phase       TEXT NOT NULL,
            scanned     INTEGER DEFAULT 0,
            success     INTEGER DEFAULT 0,
            failed      INTEGER DEFAULT 0,
            promoted    INTEGER DEFAULT 0,
            demoted     INTEGER DEFAULT 0,
            note        TEXT,
            ts          TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_stocks_level ON stocks(level);
        """
    )
    conn.commit()


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today() -> str:
    return date.today().isoformat()


def upsert_snapshot(conn: sqlite3.Connection, rows: list[dict]) -> int:
    """灌入/刷新全市场快照字段。新代码默认 Low; 已存在仅更新快照列。"""
    n = 0
    for r in rows:
        code = r["code"]
        exists = conn.execute(
            "SELECT 1 FROM stocks WHERE code=?", (code,)).fetchone()
        if exists:
            conn.execute(
                """UPDATE stocks SET name=?, price=?, change_60d_pct=?,
                   turnover_yuan=?, float_mktcap=?, turnover_ratio=?,
                   health=?, industry=?, pe_ttm=?, updated_at=? WHERE code=?""",
                (r.get("name"), r.get("price"), r.get("change_60d_pct"),
                 r.get("turnover_yuan"), r.get("float_mktcap"),
                 r.get("turnover_ratio"), r.get("health"), r.get("industry"),
                 r.get("pe_ttm"), _now(), code))
        else:
            conn.execute(
                """INSERT INTO stocks (code, name, level, level_since, price,
                   change_60d_pct, turnover_yuan, float_mktcap, turnover_ratio,
                   health, industry, pe_ttm, updated_at)
                   VALUES (?,?,'Low',?,?,?,?,?,?,?,?,?,?)""",
                (code, r.get("name"), _today(), r.get("price"),
                 r.get("change_60d_pct"), r.get("turnover_yuan"),
                 r.get("float_mktcap"), r.get("turnover_ratio"),
                 r.get("health"), r.get("industry"), r.get("pe_ttm"),
                 _now()))
        n += 1
    conn.commit()
    return n


def prune_absent(conn: sqlite3.Connection, present_codes: set[str]) -> int:
    """从 stocks 删除已不在最新 universe 的代码 (退市/被过滤)。"""
    all_codes = [row["code"] for row in
                 conn.execute("SELECT code FROM stocks").fetchall()]
    gone = [c for c in all_codes if c not in present_codes]
    for c in gone:
        conn.execute("DELETE FROM stocks WHERE code=?", (c,))
    conn.commit()
    return len(gone)


def get_by_level(conn: sqlite3.Connection, level: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM stocks WHERE level=?", (level,)).fetchall()


def update_chips(conn: sqlite3.Connection, code: str, chip: dict) -> None:
    conn.execute(
        """UPDATE stocks SET scr=?, scr70=?, band70=?, dominance=?,
           sharpness=?, near_peak=?, second_ratio=?, profit_ratio=?, avg_cost=?,
           cost_low90=?, cost_high90=?, chip_date=?, price=?, updated_at=?
           WHERE code=?""",
        (chip.get("SCR"), chip.get("SCR70"), chip.get("带宽70"),
         chip.get("主峰占比"), chip.get("尖锐度"), chip.get("距主峰"),
         chip.get("次峰比"), chip.get("获利比例"), chip.get("平均成本"),
         chip.get("90成本低"), chip.get("90成本高"), chip.get("chip_date"),
         chip.get("现价"), _now(), code))
    conn.commit()


def transition(conn: sqlite3.Connection, code: str, to_lvl: str,
               reason: str, cooldown_days: int = 0) -> None:
    """执行状态流转 + 写审计 + (降级时)设冷却。"""
    cur = conn.execute("SELECT level FROM stocks WHERE code=?",
                       (code,)).fetchone()
    if cur is None:
        return
    from_lvl = cur["level"]
    if from_lvl == to_lvl:
        return
    cooldown = None
    if cooldown_days > 0:
        cooldown = (date.today() + timedelta(days=cooldown_days)).isoformat()
    conn.execute(
        """UPDATE stocks SET level=?, level_since=?, cooldown_until=?,
           updated_at=? WHERE code=?""",
        (to_lvl, _today(), cooldown, _now(), code))
    conn.execute(
        "INSERT INTO transitions (code, from_lvl, to_lvl, reason, ts) "
        "VALUES (?,?,?,?,?)",
        (code, from_lvl, to_lvl, reason, _now()))
    conn.commit()


def in_cooldown(row: sqlite3.Row) -> bool:
    cd = row["cooldown_until"]
    return cd is not None and cd > _today()


def days_in_level(row: sqlite3.Row) -> int:
    try:
        since = date.fromisoformat(row["level_since"])
        return (date.today() - since).days
    except (TypeError, ValueError):
        return 0


def log_run(conn: sqlite3.Connection, phase: str, **kw) -> None:
    conn.execute(
        """INSERT INTO scan_runs (run_date, phase, scanned, success, failed,
           promoted, demoted, note, ts) VALUES (?,?,?,?,?,?,?,?,?)""",
        (_today(), phase, kw.get("scanned", 0), kw.get("success", 0),
         kw.get("failed", 0), kw.get("promoted", 0), kw.get("demoted", 0),
         kw.get("note", ""), _now()))
    conn.commit()


def level_counts(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        "SELECT level, COUNT(*) c FROM stocks GROUP BY level").fetchall()
    return {r["level"]: r["c"] for r in rows}
