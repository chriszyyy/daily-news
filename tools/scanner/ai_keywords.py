"""
AI 4 链关键词词典。

匹配方式:
  - 公司名 contains keyword → 强匹配 (20 分)
  - 行业名 contains keyword → 弱匹配 (10 分)
  - 都不命中 → 0 分

可后续 override:加新关键词到对应链 list 即可。
"""

AI_CHAIN_KEYWORDS = {
    "pcb_hbm": [
        # PCB / 覆铜板 / 封装基板
        "PCB", "印制电路", "电路板", "覆铜板", "覆铜", "层压",
        # 先进封装 / HBM
        "封装", "测试", "靶材", "载板", "晶圆", "芯片", "半导体",
        "存储", "存储器", "HBM",
    ],
    "cooling": [
        # 液冷 / 散热
        "液冷", "散热", "冷却", "热管理", "温控",
        "精密空调", "空调", "压缩机", "氟化液", "制冷剂", "制冷",
        "冷板", "导热",
    ],
    "power": [
        # 变压器 / 电源 / 配电
        "变压器", "互感器", "开关", "GIS", "电源", "UPS", "HVDC",
        "智能电网", "配电", "电网", "电气", "高压", "中压",
        "电力设备", "输变电",
    ],
    "optical": [
        # 光通信 / 光模块
        "光模块", "光器件", "光纤", "光通信", "光电",
        "连接器", "电感", "镀银", "高速铜缆", "铜缆", "电缆",
        "光芯片", "DSP",
    ],
}

# 行业关键词(industry 字段命中):弱匹配阈值
INDUSTRY_HINTS = {
    "pcb_hbm": ["半导体", "电子", "印制电路", "PCB", "光伏设备"],
    "cooling": ["家电零部件", "通用设备", "专用设备", "制冷"],
    "power": ["电网设备", "电力", "电气", "输变电", "电源设备"],
    "optical": ["通信设备", "光学", "电子元件"],
}


def match_chain(name: str, industry: str) -> tuple[str | None, str, int]:
    """
    返回 (chain_id, match_strength, score)
      chain_id: pcb_hbm / cooling / power / optical / None
      match_strength: 'strong' (公司名命中) / 'weak' (行业命中) / 'none'
      score: 20 / 10 / 0
    多链命中取第一个强匹配,否则取第一个弱匹配。
    """
    name = name or ""
    industry = industry or ""

    # 优先公司名强匹配
    for chain, kws in AI_CHAIN_KEYWORDS.items():
        for kw in kws:
            if kw in name:
                return chain, "strong", 20

    # 行业弱匹配
    for chain, kws in INDUSTRY_HINTS.items():
        for kw in kws:
            if kw in industry:
                return chain, "weak", 10

    return None, "none", 0


if __name__ == "__main__":
    import sys
    import io
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    # 自测
    cases = [
        ("崇达技术", "印制电路板"),  # 强匹配 pcb_hbm
        ("佳力图", "通用设备"),       # 强匹配 cooling(空调/冷板等不在名字里,但"佳力图"不命中 → 应行业 weak)
        ("白云电器", "电网设备"),     # 强匹配 power
        ("中际旭创", "通信设备"),     # 弱匹配 optical(industry)
        ("贵州茅台", "白酒"),         # none
    ]
    for n, i in cases:
        c, s, sc = match_chain(n, i)
        print(f"{n} / {i} → {c} {s} {sc}")
