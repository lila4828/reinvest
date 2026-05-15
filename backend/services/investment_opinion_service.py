def calculate_investment_opinion(
    fundamental_score,
    macro_score,
    sentiment,
    guru_score,
    guru_weight,
    final_config,
):
    total_score = fundamental_score + macro_score + sentiment

    # total_score 범위
    # fundamental_score: -3 ~ +3
    # macro_score: -3 ~ +3
    # sentiment: -1 ~ +1
    # 총합: -7 ~ +7
    # 50점을 중립으로 잡고, 1점당 약 7점씩 이동
    system_score = max(0, min(100, 50 + (total_score * 7)))

    if guru_weight > 0:
        system_weight = final_config["system_weight"]
    else:
        system_weight = 1.0

    final_weighted_score = (system_score * system_weight) + (guru_score * guru_weight)

    if final_weighted_score >= final_config["strong_buy_cutoff"]:
        final_opinion = "Strong Buy"
    elif final_weighted_score >= final_config["buy_cutoff"]:
        final_opinion = "Buy"
    elif final_weighted_score >= final_config["hold_cutoff"]:
        final_opinion = "Hold"
    else:
        final_opinion = "Sell"

    if guru_score >= 65:
        guru_sentiment_label = "Bullish"
    elif guru_score <= 35:
        guru_sentiment_label = "Bearish"
    else:
        guru_sentiment_label = "Neutral"

    return {
        "final_opinion": final_opinion,
        "system_score": system_score,
        "system_weight": system_weight,
        "final_weighted_score": final_weighted_score,
        "guru_sentiment_label": guru_sentiment_label,
    }


def _all_recent_negative(values):
    if not isinstance(values, list) or not values:
        return False

    recent_values = [
        value for value in values[-3:]
        if isinstance(value, (int, float))
    ]
    return bool(recent_values) and all(value < 0 for value in recent_values)


def has_hard_risk(accounting_data: dict | None = None) -> bool:
    """Conservative hard-risk gate for guru-positive Hold-to-Buy upgrades."""
    data = accounting_data if isinstance(accounting_data, dict) else {}

    if data.get("is_data_valid") is False:
        return True

    fundamental_score = data.get("fundamental_score")
    if isinstance(fundamental_score, (int, float)) and fundamental_score <= -2:
        return True

    if _all_recent_negative(data.get("net_income")):
        return True

    if _all_recent_negative(data.get("fcf")):
        return True

    debt_to_equity = data.get("debt_to_equity")
    # Use the existing project convention: debt above 200% is a hard failure risk.
    if isinstance(debt_to_equity, (int, float)) and debt_to_equity > 200:
        return True

    severe_markers = [
        "분석 중단",
        "상장폐지",
        "자본잠식",
        "감사의견",
        "default",
        "bankruptcy",
        "insolvency",
        "delisting",
    ]
    reasons = data.get("fundamental_score_reasons")
    if isinstance(reasons, list):
        joined_reasons = " ".join(str(reason).lower() for reason in reasons)
        if any(marker.lower() in joined_reasons for marker in severe_markers):
            return True

    return False


def _is_guru_positive_upgrade_eligible(guru_opinion: dict | None = None) -> bool:
    opinion = guru_opinion if isinstance(guru_opinion, dict) else {}
    return (
        opinion.get("buy_upgrade_signal") is True
        and opinion.get("sentiment") == "BULLISH"
        and opinion.get("mention_type") in ["DIRECT", "SECTOR", "MARKET"]
        and opinion.get("confidence") in ["HIGH", "MEDIUM"]
    )


def apply_guru_positive_policy(
    base_result: dict,
    guru_opinion: dict | None = None,
    accounting_data: dict | None = None,
) -> dict:
    """Apply a narrow guru-positive policy after baseline scoring.

    Only baseline Hold can be upgraded to Buy, and only when the guru opinion is
    bullish, relevant, confident, and no deterministic hard risk is present.
    """
    result = dict(base_result or {})
    result["guru_positive_upgrade_applied"] = False

    if result.get("final_opinion") != "Hold":
        return result

    if not _is_guru_positive_upgrade_eligible(guru_opinion):
        return result

    if has_hard_risk(accounting_data):
        result["guru_positive_upgrade_blocked_by_hard_risk"] = True
        return result

    result["final_opinion"] = "Buy"
    result["guru_positive_upgrade_applied"] = True
    result["guru_positive_upgrade_reason"] = (
        "Guru opinion is bullish with direct/sector/market relevance and no hard accounting risk."
    )
    return result
