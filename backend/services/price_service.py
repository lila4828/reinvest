def calculate_price_targets(acc_data):
    current_price = acc_data.get("current_price")
    ma_30_candidates = [
        acc_data.get("ma_30"),
        acc_data.get("ma30"),
        acc_data.get("moving_average_30"),
        acc_data.get("moving_average_30d"),
    ]
    ma_30 = next(
        (
            value
            for value in ma_30_candidates
            if isinstance(value, (int, float)) and value > 0
        ),
        None,
    )

    if isinstance(current_price, (int, float)) and current_price > 0:
        if ma_30 is not None:
            target_buy_price = ma_30
        else:
            # Temporary fallback until accounting data supplies a real 30-day MA.
            target_buy_price = current_price * 0.96

        defense_price = current_price * 0.7
    else:
        target_buy_price = None
        defense_price = None

    return current_price, target_buy_price, defense_price
