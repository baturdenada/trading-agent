"""
Position Optimizer - Intelligently swap weak trades for better setups
Scores positions by profitability, setup quality, and win probability
Closes weak positions to make room for excellent opportunities
"""

import logging
import MetaTrader5 as mt5

logger = logging.getLogger(__name__)

class PositionOptimizer:
    def __init__(self, historian=None, regime_detector=None):
        self.historian = historian
        self.regime_detector = regime_detector

    def score_position(self, position, symbol_info, indicators, account):
        """
        Score an open position on multiple factors (0-100):
        - Profitability: Is it winning?
        - Setup Quality: How good was the original entry signal?
        - Win Probability: Based on historical win rate
        - Risk/Reward: How much profit potential vs risk?
        """
        tick = mt5.symbol_info_tick(symbol_info['name'])
        if not tick:
            return 0

        current_price = tick.ask if position.type == 0 else tick.bid
        entry = position.price_open
        pnl = position.profit
        pnl_pct = (pnl / (position.volume * entry * 100)) * 100 if entry > 0 else 0

        # 1. Profitability score (0-30 points)
        if pnl > 0:
            profit_score = min(30, 10 + (pnl_pct / 0.1))  # 30 points for profitable
        else:
            profit_score = max(0, 10 + pnl_pct)  # Negative for losses

        # 2. Setup quality score (0-30 points)
        # Based on RSI at entry and trend alignment
        rsi_score = 0
        if indicators['rsi'] < 15 or indicators['rsi'] > 85:
            rsi_score = 25  # Entered at extreme (good edge)
        elif indicators['rsi'] < 30 or indicators['rsi'] > 70:
            rsi_score = 20  # Entered at overbought/oversold
        elif 40 < indicators['rsi'] < 60:
            rsi_score = 10  # Neutral entry
        else:
            rsi_score = 15  # Moderate entry

        # Trend alignment bonus
        if indicators['trend'] in ["STRONG_UP", "STRONG_DOWN"]:
            rsi_score += 5

        setup_quality_score = min(30, rsi_score)

        # 3. Win probability score (0-25 points)
        # Based on historical performance of similar setups
        if self.historian:
            symbol_priority = self.historian.get_symbol_priority(position.symbol)
            setup_probability = 0.5  # Default
            win_prob_score = symbol_priority * 25
        else:
            win_prob_score = 12.5  # Neutral

        # 4. Risk/Reward score (0-15 points)
        # How much room to profit vs risk
        if position.tp:
            profit_room = abs(position.tp - current_price)
            risk_room = abs(current_price - position.sl) if position.sl else 0.01
            rr_ratio = profit_room / risk_room if risk_room > 0 else 0
            rr_score = min(15, rr_ratio * 5)  # 15 points for 3:1 RR
        else:
            rr_score = 10  # Average

        # Total score
        total_score = profit_score + setup_quality_score + win_prob_score + rr_score

        score_breakdown = {
            "total": round(total_score, 1),
            "profitability": round(profit_score, 1),
            "setup_quality": round(setup_quality_score, 1),
            "win_probability": round(win_prob_score, 1),
            "risk_reward": round(rr_score, 1),
            "pnl": pnl,
            "pnl_pct": pnl_pct
        }

        return score_breakdown

    def should_swap_for_new_trade(self, open_positions, new_signal_confidence, account, max_positions=5):
        """
        Decide if we should close a weak position to open a better one
        Returns: (should_swap: bool, position_to_close: position_ticket or None)
        """
        # Only swap if new signal is very high confidence
        if new_signal_confidence < 75:
            return False, None

        # Only swap if we're at max positions
        if len(open_positions) < max_positions:
            return False, None

        # If we have room, don't swap
        if len(open_positions) <= max_positions - 1:
            return False, None

        # Find the weakest position
        if not open_positions:
            return False, None

        weakest = min(open_positions, key=lambda p: p['score']['total'])

        # Only swap if weakest position is below threshold
        if weakest['score']['total'] < 40:  # Below 40/100 is weak
            logger.warning(f"SWAPPING: Closing {weakest['symbol']} (score: {weakest['score']['total']}) "
                          f"for new signal (confidence: {new_signal_confidence}%)")
            return True, weakest['ticket']

        return False, None

    def evaluate_all_positions(self, symbols, account):
        """
        Evaluate all open positions and return scored list
        """
        import MetaTrader5 as mt5
        from ultimate_trader import UltimateTrader

        trader = UltimateTrader()
        all_positions = []

        for symbol_info in symbols:
            positions = mt5.positions_get(symbol=symbol_info['name'])
            if positions:
                for pos in positions:
                    indicators = trader.calculate_indicators(symbol_info['name'])
                    if indicators:
                        score = self.score_position(pos, symbol_info, indicators, account)
                        all_positions.append({
                            "ticket": pos.ticket,
                            "symbol": pos.symbol,
                            "type": "BUY" if pos.type == 0 else "SELL",
                            "volume": pos.volume,
                            "entry": pos.price_open,
                            "current": indicators['price'],
                            "sl": pos.sl,
                            "tp": pos.tp,
                            "score": score
                        })

        # Sort by score (weakest first)
        all_positions.sort(key=lambda p: p['score']['total'])

        return all_positions

    def print_position_scores(self, positions):
        """Print ranked positions by quality"""
        if not positions:
            logger.info("No open positions to score")
            return

        logger.info("=" * 100)
        logger.info("POSITION QUALITY RANKING (1 = Best, Last = Weakest)")
        logger.info("=" * 100)

        for i, pos in enumerate(sorted(positions, key=lambda p: p['score']['total'], reverse=True), 1):
            score = pos['score']
            logger.info(f"{i}. {pos['symbol']} - Score: {score['total']:.1f}/100")
            logger.info(f"   Type: {pos['type']} | Volume: {pos['volume']} | Entry: ${pos['entry']:.4f}")
            logger.info(f"   P&L: ${score['pnl']:+.2f} ({score['pnl_pct']:+.1f}%)")
            logger.info(f"   Breakdown: Setup={score['setup_quality']:.0f} | "
                       f"Profit={score['profitability']:.0f} | "
                       f"WinProb={score['win_probability']:.0f} | "
                       f"RR={score['risk_reward']:.0f}")

        logger.info("=" * 100)

    def get_position_quality_recommendation(self, positions):
        """Get trading recommendations based on position quality"""
        recommendations = []

        if len(positions) < 3:
            recommendations.append("OPPORTUNITY: Few positions open, excellent setups can be taken")
        elif len(positions) >= 5:
            recommendations.append("WARNING: Maximum positions reached. Consider closing weak setups for better ones")

        # Find weak positions
        weak_positions = [p for p in positions if p['score']['total'] < 35]
        if weak_positions:
            for pos in weak_positions:
                recommendations.append(
                    f"CONSIDER CLOSING: {pos['symbol']} (score: {pos['score']['total']:.0f}/100, "
                    f"P&L: {pos['score']['pnl']:+.2f})"
                )

        # Find strong positions
        strong_positions = [p for p in positions if p['score']['total'] > 70]
        if strong_positions:
            for pos in strong_positions:
                recommendations.append(
                    f"KEEP: {pos['symbol']} is a strong position (score: {pos['score']['total']:.0f}/100)"
                )

        return recommendations

    def calculate_portfolio_correlation_impact(self, positions):
        """
        Check if adding a new symbol would over-correlate portfolio
        """
        if len(positions) < 2:
            return 0  # No correlation risk with < 2 positions

        # Simple correlation check based on asset class
        forex_pairs = ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "USDCHF"]
        metals = ["XAUUSD", "XAGUSD"]
        indices = ["SP500", "NAS100"]

        position_categories = []
        for pos in positions:
            if any(pair in pos['symbol'] for pair in forex_pairs):
                position_categories.append("forex")
            elif any(metal in pos['symbol'] for metal in metals):
                position_categories.append("metals")
            elif any(idx in pos['symbol'] for idx in indices):
                position_categories.append("indices")

        # Count duplicates
        correlation_risk = max([position_categories.count(cat) for cat in position_categories]) if position_categories else 0

        return correlation_risk

    def should_allow_new_position(self, positions, new_symbol, max_positions=5, max_correlated=2):
        """
        Decide if a new position should be opened based on:
        - Position count
        - Correlation with existing positions
        - Average position quality
        """
        if len(positions) >= max_positions:
            return False, f"Max positions ({max_positions}) reached"

        corr_risk = self.calculate_portfolio_correlation_impact(positions)
        if corr_risk >= max_correlated:
            return False, f"Adding {new_symbol} would create {corr_risk + 1} correlated positions (max: {max_correlated})"

        return True, "Position allowed"
