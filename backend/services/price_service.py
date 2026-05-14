def calculate_price_targets(acc_data):
    current_price = acc_data.get("current_price")
    ma_60 = acc_data.get("ma_60")
    ma_200 = acc_data.get("ma_200")
    ma_350 = acc_data.get("ma_350")

    if isinstance(current_price, (int, float)) and current_price > 0:
        if (
            isinstance(ma_60, (int, float))
            and isinstance(ma_200, (int, float))
            and ma_60 > ma_200
            and ma_200 > 0
        ):
            target_buy_price = ma_60
            defense_price = ma_200
        else:
            target_buy_price = current_price * 0.96

            candidates = [
                x for x in [ma_60, ma_200, ma_350]
                if isinstance(x, (int, float)) and 0 < x < target_buy_price
            ]

            defense_price = max(candidates) if candidates else target_buy_price * 0.92
    else:
        target_buy_price = None
        defense_price = None

    return current_price, target_buy_price, defense_price
