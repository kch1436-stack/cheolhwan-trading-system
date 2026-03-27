import math
from datetime import date
import pandas as pd
import streamlit as st

st.set_page_config(page_title="철환 트레이딩 시스템 PRO", page_icon="🔥", layout="wide")

# -------------------- 초기 상태 --------------------
if "journal" not in st.session_state:
    st.session_state.journal = pd.DataFrame(columns=[
        "날짜", "종목", "시간봉", "방향", "자리등급", "체크점수", "진입가", "손절가", "TP1", "TP2",
        "리스크%", "권장레버리지", "손익비TP1", "결과(%)", "실수유형", "원칙준수", "메모"
    ])

if "daily_loss_limit_pct" not in st.session_state:
    st.session_state.daily_loss_limit_pct = 6.0

if "daily_loss_used_pct" not in st.session_state:
    st.session_state.daily_loss_used_pct = 0.0

if "daily_trade_limit" not in st.session_state:
    st.session_state.daily_trade_limit = 2

if "daily_trades_used" not in st.session_state:
    st.session_state.daily_trades_used = 0

if "day_mode" not in st.session_state:
    st.session_state.day_mode = True

if "last_grade" not in st.session_state:
    st.session_state.last_grade = "미판정"

if "last_action" not in st.session_state:
    st.session_state.last_action = "-"

# -------------------- 함수 --------------------
def calc_trade(balance, risk_pct, direction, entry, stop, tp1, tp2, max_lev, fee_pct):
    if min(balance, risk_pct, entry, stop, tp1) <= 0:
        return {"status": "입력값 오류"}
    if entry == stop:
        return {"status": "진입가와 손절가 동일"}

    risk_amount = balance * (risk_pct / 100.0)
    stop_distance = abs(entry - stop)
    stop_pct = (stop_distance / entry) * 100.0
    position_notional = risk_amount / (stop_distance / entry)
    qty = position_notional / entry
    required_lev = position_notional / balance
    fee_amount = position_notional * (fee_pct / 100.0)

    if direction == "Long":
        stop_valid = stop < entry
        tp1_valid = tp1 > entry
        tp2_valid = tp2 > entry
        rr1 = (tp1 - entry) / (entry - stop) if (entry - stop) != 0 else 0.0
        rr2 = (tp2 - entry) / (entry - stop) if (entry - stop) != 0 else 0.0
        expected_tp1 = (tp1 - entry) * qty - fee_amount
        expected_tp2 = (tp2 - entry) * qty - fee_amount
    else:
        stop_valid = stop > entry
        tp1_valid = tp1 < entry
        tp2_valid = tp2 < entry
        rr1 = (entry - tp1) / (stop - entry) if (stop - entry) != 0 else 0.0
        rr2 = (entry - tp2) / (stop - entry) if (stop - entry) != 0 else 0.0
        expected_tp1 = (entry - tp1) * qty - fee_amount
        expected_tp2 = (entry - tp2) * qty - fee_amount

    issues = []
    if not stop_valid:
        issues.append("손절 방향 오류")
    if not tp1_valid:
        issues.append("TP1 방향 오류")
    if not tp2_valid:
        issues.append("TP2 방향 오류")
    if required_lev > max_lev:
        issues.append("최대 레버리지 초과")
    if rr1 < 1.5:
        issues.append("손익비 낮음")
    if stop_pct < 0.15:
        issues.append("손절폭 너무 짧음")

    status = "OK" if not issues else " / ".join(issues)

    return {
        "risk_amount": risk_amount,
        "stop_pct": stop_pct,
        "position_notional": position_notional,
        "qty": qty,
        "required_lev": required_lev,
        "recommended_lev": max(1, math.ceil(required_lev)),
        "rr1": rr1,
        "rr2": rr2,
        "expected_tp1": expected_tp1,
        "expected_tp2": expected_tp2,
        "fee_amount": fee_amount,
        "status": status,
    }

def grade_logic(score):
    if score >= 7:
        return "A급", "진입 검토 가능", "좋다. 네 기준에서 A급에 가깝다."
    elif score >= 5:
        return "B급", "소액 또는 대기", "패턴은 있으나 확정이 부족하다."
    else:
        return "쓰레기", "진입 금지", "조건 부족. 관찰이 맞다."

def hard_block_reasons(grade, confirm_score, calc_status, daily_locked, stop_clear, structure_clear, hl_lh_clear, rr_clear):
    reasons = []
    if daily_locked:
        reasons.append("오늘 손실 한도 초과 또는 트레이드 한도 초과")
    if grade != "A급":
        reasons.append("A급 자리가 아님")
    if not structure_clear:
        reasons.append("구조 깨짐 불충분")
    if not hl_lh_clear:
        reasons.append("HL/LH 확인 부족")
    if not stop_clear:
        reasons.append("손절 기준 불명확")
    if not rr_clear:
        reasons.append("손익비 1:2 미만")
    if confirm_score < 5:
        reasons.append("BTC/ETH 동시 확인 약함")
    if calc_status != "OK":
        reasons.append("포지션 계산 경고 존재")
    return reasons

def make_x_post(symbol, timeframe, direction, grade, entry, stop, tp1, tp2, notes):
    arrow = "📉➡️📈" if direction == "Long" else "📈➡️📉"
    side = "롱" if direction == "Long" else "숏"
    return f"""{symbol} {timeframe} 📊

{side} 시나리오 {arrow}
자리 등급: {grade}

📍진입: {entry:,.2f}
🛑손절: {stop:,.2f}
🎯TP1: {tp1:,.2f}
🎯TP2: {tp2:,.2f}

메모:
{notes}

추격 금지 ❌
자리만 간다 🎯

#{symbol.replace('/','').replace('-','')} #트레이딩"""

# -------------------- 헤더 --------------------
st.title("🔥 철환 트레이딩 시스템 PRO")
st.caption("충동 방지 · 진입 금지 필터 · 하루 손실 제한 잠금 · 실수 패턴 통계 · 4월 1일 실전 모드")

tabs = st.tabs([
    "실전 대시보드", "진입 판정기", "포지션 계산기", "BTC/ETH 확인",
    "복리 추적기", "매매일지", "통계", "X 게시물"
])

# -------------------- 1. 실전 대시보드 --------------------
with tabs[0]:
    st.subheader("실전 대시보드")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("오늘 손실 한도", f"{st.session_state.daily_loss_limit_pct:.1f}%")
    c2.metric("오늘 사용 손실", f"{st.session_state.daily_loss_used_pct:.1f}%")
    c3.metric("남은 트레이드 수", f"{max(0, st.session_state.daily_trade_limit - st.session_state.daily_trades_used)}")
    c4.metric("최근 판정", st.session_state.last_grade)

    d1, d2 = st.columns(2)
    with d1:
        st.session_state.day_mode = st.checkbox("4월 1일 실전 모드 사용", value=st.session_state.day_mode)
        st.session_state.daily_loss_limit_pct = st.number_input("하루 손실 제한 (%)", min_value=1.0, max_value=20.0, value=float(st.session_state.daily_loss_limit_pct), step=0.5)
        st.session_state.daily_trade_limit = st.number_input("하루 최대 트레이드 수", min_value=1, max_value=20, value=int(st.session_state.daily_trade_limit), step=1)
    with d2:
        if st.button("오늘 기록 초기화"):
            st.session_state.daily_loss_used_pct = 0.0
            st.session_state.daily_trades_used = 0
            st.success("오늘 기록이 초기화됐다.")

        manual_loss = st.number_input("오늘 추가 손실 입력 (%)", min_value=0.0, max_value=100.0, value=0.0, step=0.1)
        if st.button("손실 누적 반영"):
            st.session_state.daily_loss_used_pct += manual_loss
            st.success("오늘 손실 누적 반영 완료")

        if st.button("트레이드 1회 사용 처리"):
            st.session_state.daily_trades_used += 1
            st.success("오늘 트레이드 수 반영 완료")

    locked = (
        st.session_state.daily_loss_used_pct >= st.session_state.daily_loss_limit_pct or
        st.session_state.daily_trades_used >= st.session_state.daily_trade_limit
    )

    if locked:
        st.error("오늘은 종료다. 손실 한도 또는 트레이드 한도를 넘었다.")
    else:
        st.success("오늘 아직 거래 가능. 그래도 A급 외 진입 금지.")

    st.markdown("""
### 오늘의 핵심 규칙
- 목표는 수익보다 **원칙 준수**
- **A급만 진입**
- 하루 2트레이드 기본
- 손절 애매하면 진입 금지
- BTC로 방향, ETH로 힘 확인
""")

# -------------------- 2. 진입 판정기 --------------------
with tabs[1]:
    st.subheader("진입 판정기")

    balance = st.number_input("계좌 잔고 (USDT)", min_value=0.0, value=1000.0, step=100.0, key="judge_balance")
    risk_pct = st.number_input("리스크 (%)", min_value=0.1, max_value=100.0, value=3.0, step=0.5, key="judge_risk")
    direction = st.selectbox("방향", ["Long", "Short"], key="judge_dir")
    symbol = st.text_input("종목", value="BTCUSDT", key="judge_symbol")
    timeframe = st.selectbox("기준 시간봉", ["15M", "1H", "4H", "1D"], index=1, key="judge_tf")

    j1, j2, j3 = st.columns(3)
    with j1:
        tf_high = st.selectbox("상위 시간봉", ["1H", "4H", "1D"], index=0, key="judge_high")
        structure_clear = st.checkbox(f"{tf_high} 구조 깨짐 확인")
        pullback_clear = st.checkbox(f"{tf_high} 눌림/반등 확인")
        d_prz = st.checkbox("D점/PRZ 반응")
    with j2:
        tf_low = st.selectbox("하위 시간봉", ["15M", "30M", "1H"], index=0, key="judge_low")
        hl_lh_clear = st.checkbox(f"{tf_low} HL/LH 형성")
        retrigger = st.checkbox(f"{tf_low} 재돌파/재이탈")
        trigger_candle = st.checkbox("트리거 캔들 존재")
    with j3:
        rsi_check = st.checkbox("RSI 보조 확인")
        stop_clear = st.checkbox("손절 기준 명확")
        rr_clear = st.checkbox("손익비 1:2 이상")

    # BTC/ETH confirm
    st.markdown("#### BTC/ETH 동시 확인")
    e1, e2 = st.columns(2)
    with e1:
        btc_structure = st.checkbox("BTC 구조 조건 충족", key="btc1")
        btc_trigger = st.checkbox("BTC 트리거 조건 충족", key="btc2")
        btc_flow = st.checkbox("BTC 흐름 동일", key="btc3")
    with e2:
        eth_structure = st.checkbox("ETH도 같은 방향 구조 확인", key="eth1")
        eth_strength = st.checkbox("ETH도 힘이 실림", key="eth2")
        eth_ok = st.checkbox("ETH가 반대 신호가 약함", key="eth3")

    confirm_score = sum([btc_structure, btc_trigger, btc_flow, eth_structure, eth_strength, eth_ok])

    # calculator part
    st.markdown("#### 계산 입력")
    p1, p2 = st.columns(2)
    with p1:
        entry = st.number_input("진입가", min_value=0.0, value=70000.0, step=10.0, key="judge_entry")
        stop = st.number_input("손절가", min_value=0.0, value=69300.0, step=10.0, key="judge_stop")
        max_lev = st.number_input("최대 허용 레버리지", min_value=1, max_value=200, value=20, step=1, key="judge_maxlev")
    with p2:
        tp1 = st.number_input("TP1", min_value=0.0, value=71200.0, step=10.0, key="judge_tp1")
        tp2 = st.number_input("TP2", min_value=0.0, value=71800.0, step=10.0, key="judge_tp2")
        fee_pct = st.number_input("수수료 추정 (%)", min_value=0.0, value=0.10, step=0.01, key="judge_fee")

    calc = calc_trade(balance, risk_pct, direction, entry, stop, tp1, tp2, max_lev, fee_pct)

    check_score = sum([
        structure_clear, pullback_clear, d_prz, hl_lh_clear, retrigger,
        trigger_candle, rsi_check, stop_clear, rr_clear
    ])
    grade, action, msg = grade_logic(check_score)

    daily_locked = (
        st.session_state.daily_loss_used_pct >= st.session_state.daily_loss_limit_pct or
        st.session_state.daily_trades_used >= st.session_state.daily_trade_limit
    ) if st.session_state.day_mode else False

    block_reasons = hard_block_reasons(
        grade, confirm_score, calc["status"] if "status" in calc else "입력값 오류",
        daily_locked, stop_clear, structure_clear, hl_lh_clear, rr_clear
    )

    st.session_state.last_grade = grade
    st.session_state.last_action = action

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("체크 점수", f"{check_score}/9")
    r2.metric("자리 등급", grade)
    r3.metric("BTC/ETH 확인", f"{confirm_score}/6")
    r4.metric("행동", action)

    if not block_reasons:
        st.success("✅ 진입 금지 필터 통과. 그래도 추격은 금지.")
    else:
        st.error("⛔ 진입 금지")
        for reason in block_reasons:
            st.write(f"- {reason}")

    if "status" in calc and calc["status"] not in {"입력값 오류", "진입가와 손절가 동일"}:
        c1, c2, c3 = st.columns(3)
        c1.metric("권장 포지션 규모", f"${calc['position_notional']:,.2f}")
        c2.metric("필요 레버리지", f"{calc['required_lev']:.2f}x")
        c3.metric("TP1 손익비", f"{calc['rr1']:.2f}")

# -------------------- 3. 포지션 계산기 --------------------
with tabs[2]:
    st.subheader("포지션 계산기")

    c1, c2 = st.columns(2)
    with c1:
        bal2 = st.number_input("계좌 잔고 (USDT)", min_value=0.0, value=1000.0, step=100.0, key="calc_bal")
        risk2 = st.number_input("리스크 (%)", min_value=0.1, max_value=100.0, value=3.0, step=0.5, key="calc_risk")
        dir2 = st.selectbox("방향", ["Long", "Short"], key="calc_dir")
        maxlev2 = st.number_input("최대 허용 레버리지", min_value=1, max_value=200, value=20, step=1, key="calc_max")
    with c2:
        entry2 = st.number_input("진입가", min_value=0.0, value=70000.0, step=10.0, key="calc_entry")
        stop2 = st.number_input("손절가", min_value=0.0, value=69300.0, step=10.0, key="calc_stop")
        tp12 = st.number_input("TP1", min_value=0.0, value=71200.0, step=10.0, key="calc_tp1")
        tp22 = st.number_input("TP2", min_value=0.0, value=71800.0, step=10.0, key="calc_tp2")
        fee2 = st.number_input("수수료 추정 (%)", min_value=0.0, value=0.10, step=0.01, key="calc_fee")

    res = calc_trade(bal2, risk2, dir2, entry2, stop2, tp12, tp22, maxlev2, fee2)
    if res["status"] in {"입력값 오류", "진입가와 손절가 동일"}:
        st.error(res["status"])
    else:
        a, b, c = st.columns(3)
        a.metric("허용 손실금액", f"${res['risk_amount']:,.2f}")
        b.metric("손절폭", f"{res['stop_pct']:.3f}%")
        c.metric("상태", res["status"])

        d, e, f = st.columns(3)
        d.metric("권장 포지션 규모", f"${res['position_notional']:,.2f}")
        e.metric("권장 수량", f"{res['qty']:.6f}")
        f.metric("필요 레버리지", f"{res['required_lev']:.2f}x")

        g, h, i = st.columns(3)
        g.metric("자동 설정 레버리지", f"{res['recommended_lev']}x")
        h.metric("TP1 손익비", f"{res['rr1']:.2f}")
        i.metric("TP2 손익비", f"{res['rr2']:.2f}")

# -------------------- 4. BTC/ETH 확인 --------------------
with tabs[3]:
    st.subheader("BTC/ETH 확인")

    b1, b2 = st.columns(2)
    with b1:
        st.markdown("#### BTC")
        btc1 = st.checkbox("BTC 구조 깨짐/재이탈 확인", key="tab4_btc1")
        btc2 = st.checkbox("BTC 눌림/반등 확인", key="tab4_btc2")
        btc3 = st.checkbox("BTC 트리거 캔들 확인", key="tab4_btc3")
    with b2:
        st.markdown("#### ETH")
        eth1 = st.checkbox("ETH도 같은 방향 구조", key="tab4_eth1")
        eth2 = st.checkbox("ETH도 같이 힘이 실림", key="tab4_eth2")
        eth3 = st.checkbox("ETH가 반대로 약하지 않음", key="tab4_eth3")

    score4 = sum([btc1, btc2, btc3, eth1, eth2, eth3])
    if score4 >= 5:
        st.success("강한 공진. BTC와 ETH가 같이 맞아떨어진다.")
    elif score4 >= 3:
        st.warning("보통. BTC는 괜찮지만 ETH 힘이 약할 수 있다.")
    else:
        st.error("약함. BTC 단독 해석에 너무 기대지 마라.")

# -------------------- 5. 복리 추적기 --------------------
with tabs[4]:
    st.subheader("복리 추적기")

    start_balance = st.number_input("시작 금액", min_value=1.0, value=1000.0, step=100.0, key="comp_start")
    target_balance = st.number_input("목표 금액", min_value=1.0, value=100000.0, step=1000.0, key="comp_target")
    avg_return = st.number_input("평균 수익률 (% / 회차)", min_value=-100.0, value=2.0, step=0.1, key="comp_return")
    periods = st.slider("시뮬레이션 횟수", min_value=1, max_value=300, value=100, key="comp_periods")

    balances = [start_balance]
    for _ in range(periods):
        balances.append(balances[-1] * (1 + avg_return / 100.0))

    comp_df = pd.DataFrame({"회차": list(range(len(balances))), "잔고": balances})
    st.line_chart(comp_df.set_index("회차"))

    target_n = None
    if avg_return > 0:
        bal = start_balance
        n = 0
        while bal < target_balance and n < 5000:
            bal *= (1 + avg_return / 100.0)
            n += 1
        if bal >= target_balance:
            target_n = n

    s1, s2, s3 = st.columns(3)
    s1.metric("예상 최종 잔고", f"${balances[-1]:,.2f}")
    s2.metric("총 성장률", f"{((balances[-1] / start_balance) - 1) * 100:,.2f}%")
    s3.metric("목표 도달 회차", "-" if target_n is None else f"{target_n}회")

    # milestone tracker
    st.markdown("#### 구간 목표")
    milestones = [1200, 1500, 2000, 5000, 10000, 100000]
    reached = [m for m in milestones if balances[-1] >= m]
    st.write("달성한 목표:", ", ".join([f"${m:,.0f}" for m in reached]) if reached else "아직 없음")

# -------------------- 6. 매매일지 --------------------
with tabs[5]:
    st.subheader("매매일지")
    st.caption("한 번의 매매보다 반복 기록이 계좌를 키운다")

    j1, j2, j3 = st.columns(3)
    with j1:
        j_date = st.date_input("날짜", value=date.today())
        j_symbol = st.text_input("종목명", value="BTCUSDT", key="j_symbol")
        j_tf = st.selectbox("시간봉", ["15M", "1H", "4H", "1D"], index=1, key="j_tf")
    with j2:
        j_dir = st.selectbox("방향", ["Long", "Short"], key="j_dir")
        j_grade = st.selectbox("자리 등급", ["A급", "B급", "쓰레기"], key="j_grade")
        j_score = st.number_input("체크 점수", min_value=0, max_value=9, value=7, step=1, key="j_score")
    with j3:
        j_result = st.number_input("결과(%)", value=0.0, step=0.1, key="j_result")
        j_mistake = st.selectbox("실수 유형", ["없음", "손절 늦음", "HL 전 선진입", "추격 진입", "RSI만 보고 진입", "손절 기준 불명확", "기타"], key="j_mistake")
        j_rule = st.selectbox("원칙 준수", ["예", "아니오"], key="j_rule")

    k1, k2, k3 = st.columns(3)
    with k1:
        j_entry = st.number_input("진입가", min_value=0.0, value=0.0, step=10.0, key="j_entry")
        j_stop = st.number_input("손절가", min_value=0.0, value=0.0, step=10.0, key="j_stop")
    with k2:
        j_tp1 = st.number_input("TP1", min_value=0.0, value=0.0, step=10.0, key="j_tp1")
        j_tp2 = st.number_input("TP2", min_value=0.0, value=0.0, step=10.0, key="j_tp2")
    with k3:
        j_risk = st.number_input("리스크 %", min_value=0.0, value=3.0, step=0.5, key="j_risk")
        j_lev = st.number_input("권장 레버리지", min_value=0.0, value=0.0, step=0.5, key="j_lev")
        j_rr = st.number_input("손익비 TP1", min_value=0.0, value=0.0, step=0.1, key="j_rr")

    j_notes = st.text_area("메모", value="", key="j_notes")

    if st.button("매매일지 추가"):
        new_row = pd.DataFrame([{
            "날짜": str(j_date),
            "종목": j_symbol,
            "시간봉": j_tf,
            "방향": j_dir,
            "자리등급": j_grade,
            "체크점수": j_score,
            "진입가": j_entry,
            "손절가": j_stop,
            "TP1": j_tp1,
            "TP2": j_tp2,
            "리스크%": j_risk,
            "권장레버리지": j_lev,
            "손익비TP1": j_rr,
            "결과(%)": j_result,
            "실수유형": j_mistake,
            "원칙준수": j_rule,
            "메모": j_notes
        }])
        st.session_state.journal = pd.concat([st.session_state.journal, new_row], ignore_index=True)
        st.success("매매일지가 추가됐다.")

    st.dataframe(st.session_state.journal, use_container_width=True, height=300)

    if not st.session_state.journal.empty:
        csv = st.session_state.journal.to_csv(index=False).encode("utf-8-sig")
        st.download_button("매매일지 CSV 다운로드", data=csv, file_name="trading_journal.csv", mime="text/csv")

# -------------------- 7. 통계 --------------------
with tabs[6]:
    st.subheader("통계")

    if st.session_state.journal.empty:
        st.info("아직 매매일지가 없다.")
    else:
        stats_df = st.session_state.journal.copy()
        stats_df["결과(%)"] = pd.to_numeric(stats_df["결과(%)"], errors="coerce").fillna(0)

        total = len(stats_df)
        wins = (stats_df["결과(%)"] > 0).sum()
        win_rate = wins / total * 100 if total else 0
        avg_result = stats_df["결과(%)"].mean()

        a1, a2, a3 = st.columns(3)
        a1.metric("총 트레이드", f"{total}")
        a2.metric("승률", f"{win_rate:.1f}%")
        a3.metric("평균 결과", f"{avg_result:.2f}%")

        st.markdown("#### A/B/쓰레기 성과")
        grade_stats = stats_df.groupby("자리등급")["결과(%)"].agg(["count", "mean"])
        st.dataframe(grade_stats, use_container_width=True)

        st.markdown("#### 실수 패턴 집계")
        mistake_counts = stats_df["실수유형"].value_counts()
        st.bar_chart(mistake_counts)

        st.markdown("#### A급만 분석")
        a_df = stats_df[stats_df["자리등급"] == "A급"]
        if not a_df.empty:
            a_win = (a_df["결과(%)"] > 0).sum()
            a_total = len(a_df)
            a_wr = a_win / a_total * 100 if a_total else 0
            b1, b2 = st.columns(2)
            b1.metric("A급 트레이드 수", f"{a_total}")
            b2.metric("A급 승률", f"{a_wr:.1f}%")
        else:
            st.write("A급 기록이 아직 없다.")

        st.markdown("#### 원칙 준수율")
        rule_yes = (stats_df["원칙준수"] == "예").sum()
        rule_rate = rule_yes / total * 100 if total else 0
        st.metric("원칙 준수율", f"{rule_rate:.1f}%")

# -------------------- 8. X 게시물 --------------------
with tabs[7]:
    st.subheader("X 게시물 생성기")

    p1, p2 = st.columns(2)
    with p1:
        p_symbol = st.text_input("종목", value="BTC", key="p_symbol")
        p_tf = st.selectbox("시간봉", ["15M", "1H", "4H", "1D"], index=1, key="p_tf")
        p_dir = st.selectbox("방향", ["Long", "Short"], key="p_dir")
        p_grade = st.selectbox("자리 등급", ["A급", "B급", "쓰레기"], index=0, key="p_grade")
    with p2:
        p_entry = st.number_input("진입가", min_value=0.0, value=70000.0, step=10.0, key="p_entry")
        p_stop = st.number_input("손절가", min_value=0.0, value=69300.0, step=10.0, key="p_stop")
        p_tp1 = st.number_input("TP1", min_value=0.0, value=71200.0, step=10.0, key="p_tp1")
        p_tp2 = st.number_input("TP2", min_value=0.0, value=71800.0, step=10.0, key="p_tp2")

    p_notes = st.text_area("게시물 메모", value="구조 깨짐 후 눌림 확인, 추격은 금지.", key="p_notes")
    post_text = make_x_post(p_symbol, p_tf, p_dir, p_grade, p_entry, p_stop, p_tp1, p_tp2, p_notes)
    st.text_area("생성된 게시물", value=post_text, height=220)

st.divider()
st.caption("면책: 이 앱은 투자 자문이 아니라 리스크 관리, 계획 수립, 복기, 규율 유지 보조 도구입니다.")
