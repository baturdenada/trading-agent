"""
CONSENSUS ENGINE - Multi-agent agreement mechanism
Prevents trades unless multiple independent systems agree
Implements intelligent disagreement detection
"""

import logging
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class VoteResult(Enum):
    """Consensus voting results"""
    STRONG_BUY = "STRONG_BUY"       # 3/3 agree on BUY
    WEAK_BUY = "WEAK_BUY"           # 2/3 agree on BUY
    NEUTRAL = "NEUTRAL"             # No agreement or mixed signals
    WEAK_SELL = "WEAK_SELL"         # 2/3 agree on SELL
    STRONG_SELL = "STRONG_SELL"     # 3/3 agree on SELL
    DISAGREEMENT = "DISAGREEMENT"   # Conflicting signals


@dataclass
class AgentOpinion:
    """An agent's opinion on a trade"""
    agent_name: str
    action: str  # BUY, SELL, NEUTRAL, or SKIP
    confidence: float  # 0-100
    reasoning: str
    signal_strength: str  # STRONG, WEAK, NEUTRAL
    regime: Optional[str] = None


@dataclass
class ConsensusDecision:
    """Final consensus decision"""
    symbol: str
    verdict: VoteResult
    action: str  # BUY, SELL, SKIP
    consensus_confidence: float  # 0-100
    agreement_level: float  # % of agents that agreed
    opinions: List[AgentOpinion]
    reasoning: str
    should_execute: bool


class ConsensusEngine:
    """Multi-agent consensus decision making"""

    def __init__(self, required_agreement: float = 0.66):
        """
        Args:
            required_agreement: Minimum agreement % required (0.66 = 2/3 agree)
        """
        self.required_agreement = required_agreement
        self.agent_weights = {
            'nlp_engine': 1.0,  # Natural language analysis
            'regime_detector': 1.2,  # Market regime has more weight
            'position_optimizer': 0.8,  # Position scoring
            'historian': 0.9,  # Historical pattern matching
            'technical_analysis': 1.1  # Technical signals have high weight
        }
        logger.info(f"Consensus Engine initialized (required agreement: {required_agreement*100:.0f}%)")

    def collect_opinions(self, symbol: str, opinions: List[AgentOpinion]) -> ConsensusDecision:
        """
        Collect opinions from multiple agents and reach consensus

        Args:
            symbol: Trading symbol
            opinions: List of AgentOpinion from different agents

        Returns:
            ConsensusDecision with final verdict
        """
        if not opinions:
            return ConsensusDecision(
                symbol=symbol,
                verdict=VoteResult.NEUTRAL,
                action='SKIP',
                consensus_confidence=0,
                agreement_level=0,
                opinions=[],
                reasoning='No agent opinions provided',
                should_execute=False
            )

        # Count votes
        buy_votes = sum(1 for o in opinions if o.action.upper() == 'BUY')
        sell_votes = sum(1 for o in opinions if o.action.upper() == 'SELL')
        neutral_votes = sum(1 for o in opinions if o.action.upper() in ['NEUTRAL', 'SKIP'])

        total_agents = len(opinions)
        buy_pct = buy_votes / total_agents
        sell_pct = sell_votes / total_agents

        # Determine verdict
        if buy_pct >= self.required_agreement and buy_votes >= 2:
            if buy_votes == total_agents:
                verdict = VoteResult.STRONG_BUY
                action = 'BUY'
                agreement = buy_pct
            else:
                verdict = VoteResult.WEAK_BUY
                action = 'BUY'
                agreement = buy_pct
        elif sell_pct >= self.required_agreement and sell_votes >= 2:
            if sell_votes == total_agents:
                verdict = VoteResult.STRONG_SELL
                action = 'SELL'
                agreement = sell_pct
            else:
                verdict = VoteResult.WEAK_SELL
                action = 'SELL'
                agreement = sell_pct
        elif abs(buy_pct - sell_pct) > 0.3:  # Strong disagreement
            verdict = VoteResult.DISAGREEMENT
            action = 'SKIP'
            agreement = max(buy_pct, sell_pct)
        else:
            verdict = VoteResult.NEUTRAL
            action = 'SKIP'
            agreement = 0

        # Calculate consensus confidence (weighted by agent confidence)
        consensus_confidence = self._calculate_weighted_confidence(opinions, action)

        # Build reasoning
        reasoning = self._build_consensus_reasoning(opinions, verdict, buy_votes, sell_votes)

        # Determine if should execute
        should_execute = verdict in [VoteResult.STRONG_BUY, VoteResult.STRONG_SELL]
        if verdict == VoteResult.WEAK_BUY and consensus_confidence >= 70:
            should_execute = True
        if verdict == VoteResult.WEAK_SELL and consensus_confidence >= 70:
            should_execute = True

        return ConsensusDecision(
            symbol=symbol,
            verdict=verdict,
            action=action,
            consensus_confidence=consensus_confidence,
            agreement_level=agreement * 100,
            opinions=opinions,
            reasoning=reasoning,
            should_execute=should_execute
        )

    def _calculate_weighted_confidence(self, opinions: List[AgentOpinion], action: str) -> float:
        """Calculate confidence based on weighted agent opinions"""
        if not opinions:
            return 0

        # Filter opinions that agree with consensus action
        agreeing_opinions = [o for o in opinions if o.action.upper() == action.upper()]

        if not agreeing_opinions:
            return 0

        # Weight by confidence and agent weight
        total_weight = 0
        weighted_confidence = 0

        for opinion in agreeing_opinions:
            agent_weight = self.agent_weights.get(opinion.agent_name.lower(), 1.0)
            weight = opinion.confidence * agent_weight / 100
            total_weight += weight
            weighted_confidence += opinion.confidence * weight

        if total_weight == 0:
            return 0

        return weighted_confidence / total_weight

    def _build_consensus_reasoning(self, opinions: List[AgentOpinion], verdict: VoteResult,
                                   buy_votes: int, sell_votes: int) -> str:
        """Build explanation for consensus decision"""
        reasoning = f"Consensus {verdict.value}: "

        if verdict == VoteResult.STRONG_BUY:
            reasoning += f"All {len(opinions)} agents recommend BUY"
        elif verdict == VoteResult.WEAK_BUY:
            reasoning += f"{buy_votes}/{len(opinions)} agents recommend BUY"
        elif verdict == VoteResult.STRONG_SELL:
            reasoning += f"All {len(opinions)} agents recommend SELL"
        elif verdict == VoteResult.WEAK_SELL:
            reasoning += f"{sell_votes}/{len(opinions)} agents recommend SELL"
        elif verdict == VoteResult.DISAGREEMENT:
            reasoning += f"Agents disagree: {buy_votes} BUY vs {sell_votes} SELL"
        else:
            reasoning += "No clear consensus reached"

        # Add top agents' reasoning
        top_agents = sorted(opinions, key=lambda o: o.confidence, reverse=True)[:2]
        if top_agents:
            reasoning += "\n\nTop opinions:"
            for opinion in top_agents:
                reasoning += f"\n• {opinion.agent_name} ({opinion.confidence}%): {opinion.reasoning[:60]}"

        return reasoning

    def detect_disagreement(self, opinions: List[AgentOpinion]) -> Dict:
        """
        Detect and analyze disagreement between agents

        Returns:
            {
                'has_disagreement': bool,
                'conflicting_agents': [agent1, agent2],
                'conflict_severity': 'LOW' | 'MEDIUM' | 'HIGH',
                'analysis': str
            }
        """
        if len(opinions) < 2:
            return {
                'has_disagreement': False,
                'conflicting_agents': [],
                'conflict_severity': 'NONE',
                'analysis': 'Insufficient agents for disagreement detection'
            }

        buy_agents = [o.agent_name for o in opinions if o.action.upper() == 'BUY']
        sell_agents = [o.agent_name for o in opinions if o.action.upper() == 'SELL']

        if not buy_agents or not sell_agents:
            return {
                'has_disagreement': False,
                'conflicting_agents': [],
                'conflict_severity': 'NONE',
                'analysis': 'All agents agree'
            }

        conflict_severity = 'MEDIUM' if len(buy_agents) == 1 or len(sell_agents) == 1 else 'HIGH'

        return {
            'has_disagreement': True,
            'conflicting_agents': buy_agents + sell_agents,
            'conflict_severity': conflict_severity,
            'analysis': f"Disagreement: {', '.join(buy_agents)} say BUY vs {', '.join(sell_agents)} say SELL"
        }

    def log_consensus(self, decision: ConsensusDecision):
        """Log consensus decision for analysis"""
        emoji = "✅" if decision.should_execute else "⏭️"
        logger.info(
            f"{emoji} {decision.symbol} {decision.verdict.value} | "
            f"Agreement: {decision.agreement_level:.0f}% | "
            f"Confidence: {decision.consensus_confidence:.0f}% | "
            f"Execute: {decision.should_execute}"
        )

        if decision.verdict == VoteResult.DISAGREEMENT:
            logger.warning(f"⚠️ AGENT DISAGREEMENT on {decision.symbol}: {decision.reasoning}")
