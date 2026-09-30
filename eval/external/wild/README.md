# Tribunal 真实纠纷测试集 wild-v1(64 案)

**来源**:272 条真实网约车投诉帖 → 84 道英文题(`en/cases.jsonl`)→ 按 schema 1.2.0 生成的 64 个案件文件 + 答案键。每案的 `seed_map.json` 能追到出自哪道英文题、哪条原帖。

**和封存集的关系**:封存集(24 案)是冻结后只跑一次的;这一套是**dev/回归用**,可以反复跑、可以看答案、可以按 miss 调 prompt。它的陷阱来自真实投诉,不是我编的。

## 目录

```
data/wild/
  index.json               agent 可读清单(只有身份字段)
  cases/case-005xx.json    ROUTE_DEVIATION x37(501-537,含 14 个计费/ERP/一口价/范围类)
  cases/case-006xx.json    NO_SHOW_CHARGE  x27(601-627)
eval/wild/
  ground_truth.json        完整答案键(ruling / amount / driver_comp / referrals / clauses / difficulty / rationale)
  eval_index.json          评分用精简索引
  summary.csv              一行一案:案号、来源题、裁决、金额、难度、条款
  seed_map.json            案号 → 英文题号
  MANIFEST.json            哈希 + 分布
gen/                       生成器(spec 驱动),改 specs_*.py 重跑 build.py 即可
```

`case_set_sha256`  `77bc2dbb603393a4eea252136a0936623854cc42a05b445ab34466a019188bea`
`answer_key_sha256` `d8037d23e5aab93ba90e8cc28644ec2fb48a6661c1c43979dc12589f86e3ffde`

## 校验状态

- 64/64 通过 `schema.json`(`$defs/case_file`)和 SCHEMA.md §9 全部交叉检查(`gen/validate.py`)
- 案件文件原始字节不含任何答案字段
- `gen/semcheck.py` 只读案件文件、不读生成器,按政策独立重算裁决:61/64 一致;3 个不一致是 RD-06(b) 加重(502、515)和 RD-04 司机补偿(520),检查脚本故意没建模这两条
- 每条 rationale 里的数字(轨迹长度、超出比例、重算车费、退款、驻留秒数、到达时刻距离与速度)都是从生成数据算出来填进去的,不是手写的

## 分布

| | RD | NS | 合计 |
|---|---|---|---|
| FULL_REFUND | 3 | 20 | 23 |
| PARTIAL_REFUND | 20 | 0 | 20 |
| NO_ACTION | 12 | 2 | 14 |
| DRIVER_COMPENSATION | 1 | 2 | 3 |
| ESCALATE | 1 | 3 | 4 |

难度 EASY 11 · HARD 37 · REVERSAL 12 · INDETERMINATE 4。司机申诉 4 案(520、608、618、624 里的 608/618 是司机申诉 NO_ACTION)。

## 这套题考什么(封存集没有的)

| 陷阱 | 案 |
|---|---|
| 一口价被超但 GPS 没偏——按 RD-11 退,不能 NO_ACTION | 506, 510, 517, 524, 525, 533 |
| 一口价 + 幻影 ERP(龙门架不在轨迹 250 m 内) | 516, 521, 532 |
| 一口价 + 司机私自绕路的 ERP:RD-11(b) 退,里程不退 | 501 |
| 计时/预估价/车型错派/拼车按 solo 算——都是 NO_ACTION | 511, 526, 527, 528, 529, 537 |
| 司机私自走高速 ERP 但里程超出 <20%:政策没有退款路径 → NO_ACTION | 523 |
| 现金/线下收费:平台账单正确 → NO_ACTION,现金不在裁决范围 | 522, 531 |
| RD-06 模式 + 重大偏离 → FULL_REFUND 加重,两个数字并列 | 502, 515 |
| ERP 反双计(RD-09(1)) | 515 |
| 司机申诉 RD-04 未计费里程补偿 | 520 |
| 轨迹缺口覆盖争议段 → ESCALATE | 512 |
| 乘客索赔误车/误机损失 → 只退车费差额 | 505, 509, 535 |
| 乘客自己陈述"司机没绕路" | 511 |
| 乘客取消 + 司机从未到达 → NS-02 FULL(NS-01(d) 本来就不满足) | 602, 605, 609, 610, 611, 615, 622* |
| 虚假到达(>300 m 或 ≥15 km/h)+ 全程无合格定位 → NS-05(ii) + 转介 | 606, 612, 614, 616, 625 |
| 错入口(≤400 m)+ 乘客在聊天里说了位置 → 不补偿司机 | 604, 619, 620 |
| 到达后 <300 s 就取消/离开 | 601, 603, 607, 613, 617 |
| **48 m 合格到达 + 等满 + 司机回了消息 + 乘客就在旁边 → 政策判司机赢** | 621 |
| 司机申诉但是乘客取消的/已完成的 → NO_ACTION | 608, 618 |
| 乘客 30 天投诉计数 2(差一个到 3)→ 不升级,司机补偿 | 624 |
| 司机反刷计数触发 NS-09(d) → 明明乘客有理也 ESCALATE | 622 |
| GPS MISSING / 到达记录冲突 → ESCALATE | 626, 627 |

## 政策上的发现(出题时撞到的,建议写进 DECISIONS.md)

1. **乘客取消的费用**:NS-01(d) 要求司机以 no-show 码终止,所以任何"乘客取消被扣费"在现有政策下都退——政策没有"迟取消费"的概念。本集按政策写,但产品上这是个洞。
2. **司机 41 分钟才到、等满 5 分钟、乘客早走了**:NS-01 全满足,政策会补偿司机。本集没出这题(613 改成了等 240 s),要不要补一条"到达时限"你们定。
3. **48 m 边界(621)**:合格到达 + 等满 + 有回复 → 司机赢,哪怕乘客就站在 5 米外。这是政策原意(NS-06 是严格责任,反过来也是),但演示时评委会问。
4. **中途赶客/没上车被扣全程车费**:两类政策都不覆盖,只能靠 RD-10(8)(账单行无对应)升级;本集没出,因为 fare 恒等式会先在校验层报错。
5. **RD-06(c) 转介必须先有 pattern**:没有 pattern 的司机恶劣行为(线下收费、骂人)在现有政策下**无处转介**。本集所有 NO_ACTION 现金案都因此没有 referral。

## 使用建议

- 先跑 8 个校准:506, 521, 523, 602, 606, 621, 622, 511
- 报告按 RD/NS 分开,再按"计费类(521–537)"单列一行——那是封存集没有的题型
- rationale 是答案键的一部分,但评分只比四个字段(ruling / amount / driver_comp / referrals)
- 原帖不进仓库;`en/cases.jsonl` 里的陈述已经改写成新加坡语境,可以进

## 复跑

```
export TRIBUNAL_REPO=/path/to/Tribunal      # 要读 data/schema.json 和 policy/*.json
cd gen && python3 validate.py               # 21 条交叉检查
python3 semcheck.py                         # 独立重算裁决
python3 build.py                            # 改 specs_*.py 后重新生成(会覆盖 data/ eval/)
```
