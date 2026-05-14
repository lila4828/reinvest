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
