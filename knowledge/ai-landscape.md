# AI Industry Landscape — Living Document

*Last updated: 2026-04-30*

---

## US AI Leaders

### Chip / Infrastructure (Picks & Shovels)

| Company | Ticker | Price | Market Cap | P/E | Rev Growth | AI Role | Rating |
|---------|--------|-------|------------|-----|------------|---------|--------|
| NVIDIA | NVDA | $209.25 | $5.09T | 42.7 | +73.2% | GPU monopoly — training + inference | Strong Buy |
| AMD | AMD | $337.11 | $550B | 129.7 | +34.1% | Instinct MI-series, EPYC CPUs | Buy |
| TSMC | TSM | $393.83 | $2.04T | 33.7 | +35.1% | Fab for all leading AI chips | Strong Buy |
| Broadcom | AVGO | — | — | — | — | AI networking (custom ASICs, NICs) | — |
| Super Micro | SMCI | $26.32 | $15.8B | 19.2 | +123.4% | AI server assembly, liquid cooling | Hold |

### Cloud / Platform (Hyperscalers)

| Company | Ticker | AI Product | Status |
|---------|--------|------------|--------|
| Microsoft | MSFT | Azure AI, OpenAI partnership, Copilot | Azure +40% growth. Largest AI capex spender |
| Alphabet | GOOGL | Gemini models, Google Cloud AI, DeepMind | Q1 beat. Cloud AI growing fast |
| Amazon | AMZN | AWS Bedrock, custom Trainium/Inferentia chips | Q1 beat. Building custom AI silicon |
| Meta | META | Llama open-source models, AI infra | Beat but stock dropped — raised capex guidance, market questioning ROI |

### AI Software / Applications
- OpenAI (private) — GPT series, ChatGPT, enterprise APIs
- Anthropic (private) — Claude models, enterprise safety focus
- Palantir (PLTR) — AI for government/enterprise
- CrowdStrike, Palo Alto — AI-powered cybersecurity
- ServiceNow, Salesforce — AI enterprise agents

---

## China AI Leaders

### Models & Platforms

| Company | Ticker(s) | AI Product | Notes |
|---------|-----------|------------|-------|
| Baidu | BIDU / 9888.HK | ERNIE Bot, ERNIE 4.0, Apollo Go (autonomous driving) | Revenue declining (-4.1%). Strong Buy rating. AI cloud + autonomous driving play |
| Alibaba | BABA / 9988.HK | Qwen models (open-source), Alibaba Cloud AI | Cloud AI growing. Open-sourcing aggressively |
| Tencent | 0700.HK | Hunyuan model, AI integration across WeChat/gaming | Less AI-pure but massive distribution |
| ByteDance | Private | Doubao model, AI in TikTok/Douyin | Major AI investor but not publicly traded |
| DeepSeek | Private | DeepSeek-V2/V3, open-source frontier models | Narrowing gap with GPT-4 class. Backed by quant fund High-Flyer |
| Zhipu AI | Private | GLM-4 series | One of China's leading model startups |
| Moonshot AI (Kimi) | Private | Kimi chat assistant | Popular consumer AI product in China |
| iFlytek | 002230.SZ | Speech AI, education AI | Leading Chinese speech recognition |
| SenseTime | 0020.HK | SenseNova models, computer vision, AI chips | Government-linked, surveillance + enterprise AI |

### China AI Chips & Hardware

| Company | Ticker | Role | Notes |
|---------|--------|------|-------|
| Cambricon | 688256.SS | AI training/inference chips | A-share only. China's leading AI chip designer |
| SMIC | 0981.HK / 688981.SS | Chip fabrication | Largest Chinese foundry. Under US sanctions |
| Hua Hong | 1347.HK | Chip fabrication | Second-largest Chinese foundry |
| Zhongji Innolight | 300308.SZ | AI optical modules (800G/1.6T) | Hit record highs on AI data center demand |
| NAURA Technology | 002371.SZ | Semiconductor equipment | China's leading chip equipment maker |
| Hygon (Haiguang) | 688041.SS | x86-compatible server CPUs | AMD-derived architecture, used in Chinese data centers |

---

## AI Supply Chain Map

```
[AI Models] ← Training on → [GPU Chips] ← Fabricated by → [Foundries]
     |                            |                              |
  OpenAI, Anthropic,        NVIDIA (NVDA)                  TSMC (TSM)
  Google, Meta, Baidu,      AMD (AMD)                      SMIC (sanctioned)
  DeepSeek, Alibaba         Broadcom (AVGO)                Hua Hong
                            Cambricon (China)
                                 |
                        [Server Assembly]
                         SMCI, Dell, Lenovo
                                 |
                        [Networking/Optical]
                         Zhongji Innolight (300308.SZ)
                         Broadcom, Arista
                                 |
                        [Data Centers / Cloud]
                         MSFT Azure, GOOG, AMZN, 
                         Alibaba Cloud, Baidu Cloud
```

---

## US-China AI Rivalry — Current State

### US Restrictions on China
- **Chip export controls**: Advanced NVIDIA GPUs (H100, A100, H800) banned for export to China since Oct 2022, tightened in Oct 2023
- **Entity list**: SMIC, Huawei, and dozens of Chinese AI/chip companies restricted
- **AI chip ban from state data centers**: China retaliated by banning foreign AI chips from government-funded data centers (Apr 2026)
- **Additional controls under consideration**: US weighing further restrictions on AI chip exports

### China's Response
- Accelerating domestic chip development (Cambricon, Hygon, Huawei Ascend)
- Open-sourcing AI models (DeepSeek, Qwen, GLM) to build ecosystem without US dependency
- Stockpiling chips before new restrictions take effect
- PBOC/government directing investment into semiconductor self-sufficiency

### Key Tension Points
- TSMC (Taiwan) — fabricates chips for both US and China; Taiwan's geopolitical status adds risk
- Rare earth controls — China controls ~60% of global rare earth mining, ~90% of processing
- AI talent flow — restrictions on Chinese nationals at US AI labs being discussed

---

## AI Investment Themes for China Stocks

### 1. Domestic Chip Substitution (Bullish China)
If US tightens export controls → more demand for Cambricon, SMIC, Hygon, NAURA
- **Watch**: any new entity list additions or chip ban announcements

### 2. AI Infrastructure Build-out (Bullish)
China building "智算中心" (AI compute centers) nationwide
- **Beneficiaries**: Zhongji Innolight (optical), Cambricon (chips), server makers
- **Watch**: government procurement announcements, data center capex data

### 3. AI Application Monetization (Medium-term)
Baidu (ERNIE), Alibaba (Qwen), Tencent (Hunyuan) — can they monetize AI?
- Baidu revenue declining — needs AI cloud to reverse trend
- **Watch**: quarterly cloud revenue growth, enterprise AI adoption metrics

### 4. Autonomous Driving (Long-term)
Baidu Apollo Go, Huawei (through partners), Pony.ai, WeRide
- **Watch**: regulatory approvals for robotaxi expansion, ride volumes

### 5. Open-Source AI (China advantage?)
DeepSeek, Qwen, GLM models competitive with Western closed models at lower cost
- If open-source wins → China AI companies benefit from lower barrier to entry
- **Watch**: benchmark results, enterprise adoption of Chinese models
