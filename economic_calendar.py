"""
ECONOMIC CALENDAR - Avoid trading during major economic events
Checks for upcoming high-impact news that could cause volatile gaps
Blocks trades within N minutes of scheduled economic releases
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional
import requests
from functools import lru_cache

logger = logging.getLogger(__name__)


class EventImpact(Enum):
    """Event impact level"""
    HIGH = 3       # Major events (NFP, CPI, Interest rates)
    MEDIUM = 2     # Moderate events
    LOW = 1        # Low-impact events


@dataclass
class EconomicEvent:
    """Represents a scheduled economic event"""
    country: str
    event_name: str
    impact: EventImpact
    scheduled_time: datetime
    forecast: Optional[float] = None
    previous: Optional[float] = None
    actual: Optional[float] = None


class EconomicCalendar:
    """Manages economic calendar data and checks"""

    # High-impact events that affect all pairs
    HIGH_IMPACT_EVENTS = [
        'NFP',  # Non-Farm Payroll (US)
        'Unemployment Rate',
        'Consumer Price Index',
        'Retail Sales',
        'Industrial Production',
        'Federal Funds Rate',
        'ECB Interest Rate Decision',
        'GDP',
        'Core CPI',
        'Core PCE',
        'Initial Jobless Claims',
        'ADP Employment Change',
        'Trade Balance',
        'Housing Starts'
    ]

    # Medium-impact events
    MEDIUM_IMPACT_EVENTS = [
        'Manufacturing PMI',
        'Services PMI',
        'Consumer Sentiment',
        'Existing Home Sales',
        'New Home Sales',
        'Durable Goods Orders',
        'Factory Orders',
        'Building Permits'
    ]

    # Country event mappings
    COUNTRY_EVENTS = {
        'USD': ['NFP', 'Initial Jobless Claims', 'Federal Funds Rate', 'CPI', 'GDP', 'Retail Sales'],
        'EUR': ['ECB Interest Rate Decision', 'CPI', 'GDP', 'Manufacturing PMI', 'Services PMI'],
        'GBP': ['BoE Interest Rate', 'CPI', 'Retail Sales', 'Services PMI'],
        'AUD': ['RBA Interest Rate Decision', 'Employment Change', 'CPI', 'Retail Sales'],
        'CAD': ['BoC Interest Rate', 'GDP', 'Employment', 'CPI'],
        'JPY': ['BoJ Interest Rate', 'CPI', 'Manufacturing PMI'],
        'CHF': ['SNB Interest Rate', 'CPI']
    }

    def __init__(self,
                 lookback_minutes: int = 60,
                 lookahead_minutes: int = 120):
        """
        Args:
            lookback_minutes: Minutes before event start to check (avoid pre-event volatility)
            lookahead_minutes: Minutes after event start to avoid (avoid post-event volatility)
        """
        self.lookback_minutes = lookback_minutes
        self.lookahead_minutes = lookahead_minutes
        self.events: List[EconomicEvent] = []
        self.last_update = None
        self.update_interval = timedelta(hours=1)

        logger.info(f"EconomicCalendar initialized: {lookback_minutes}min lookback, {lookahead_minutes}min lookahead")

    def fetch_events(self, currencies: List[str] = None) -> bool:
        """
        Fetch economic calendar data from API
        Uses free economic calendar API

        Returns:
            True if successful, False otherwise
        """
        try:
            # Using tradingeconomics.com API (no auth required for basic use)
            # For production, consider: https://www.tradingeconomics.com/rss/calendar.xml

            if currencies is None:
                currencies = ['USD', 'EUR', 'GBP', 'AUD', 'CAD', 'JPY', 'CHF']

            logger.info(f"Fetching economic events for: {', '.join(currencies)}")

            # In production, you would fetch from:
            # https://www.tradingeconomics.com/calendar/
            # For now, we'll use a simplified approach with hardcoded high-impact times

            self.events = []  # Reset events
            now = datetime.utcnow()

            # Add some example high-impact events (in real implementation, fetch from API)
            # Mock data for demonstration
            self._add_mock_events(now)

            self.last_update = datetime.utcnow()
            logger.info(f"Fetched {len(self.events)} economic events")
            return True

        except Exception as e:
            logger.error(f"Error fetching economic calendar: {e}")
            return False

    def _add_mock_events(self, base_time: datetime):
        """Add mock economic events for demonstration"""
        # Next week's high-impact events (example)
        event_times = [
            (base_time + timedelta(days=2, hours=8, minutes=30), 'USD', 'Initial Jobless Claims', EventImpact.HIGH),
            (base_time + timedelta(days=3, hours=13), 'EUR', 'Manufacturing PMI', EventImpact.MEDIUM),
            (base_time + timedelta(days=4, hours=12, minutes=30), 'USD', 'CPI', EventImpact.HIGH),
            (base_time + timedelta(days=5, hours=13), 'GBP', 'Retail Sales', EventImpact.MEDIUM),
        ]

        for event_time, country, event_name, impact in event_times:
            self.events.append(EconomicEvent(
                country=country,
                event_name=event_name,
                impact=impact,
                scheduled_time=event_time
            ))

    def should_skip_trade(self, symbol: str, current_time: datetime = None) -> bool:
        """
        Check if trading should be skipped due to upcoming economic events

        Returns:
            True if major event is too close, False if safe to trade
        """
        if current_time is None:
            current_time = datetime.utcnow()

        # Extract currency pair
        currencies = self._get_affected_currencies(symbol)

        # Check for nearby high-impact events
        for event in self.events:
            if event.country not in currencies:
                continue

            if event.impact != EventImpact.HIGH:
                continue

            # Check if event is within blocked window
            time_to_event = (event.scheduled_time - current_time).total_seconds() / 60

            if -self.lookback_minutes <= time_to_event <= self.lookahead_minutes:
                logger.warning(
                    f"🚫 BLOCKING TRADE: {event.country} {event.event_name} "
                    f"in {time_to_event:.0f} minutes"
                )
                return True

        return False

    def get_upcoming_events(self, hours: int = 24, min_impact: EventImpact = EventImpact.MEDIUM) -> List[Dict]:
        """Get upcoming economic events"""
        now = datetime.utcnow()
        cutoff = now + timedelta(hours=hours)

        upcoming = [
            {
                'country': e.country,
                'event': e.event_name,
                'impact': e.impact.name,
                'time': e.scheduled_time.isoformat(),
                'time_until': round((e.scheduled_time - now).total_seconds() / 3600, 1),  # hours
                'forecast': e.forecast,
                'previous': e.previous
            }
            for e in self.events
            if now <= e.scheduled_time <= cutoff and e.impact.value >= min_impact.value
        ]

        return sorted(upcoming, key=lambda x: x['time'])

    def _get_affected_currencies(self, symbol: str) -> List[str]:
        """Extract currency codes from symbol"""
        # Handle common formats: EURUSD, XAUUSD, GBPUSD, etc.
        symbol_upper = symbol.replace('.s', '').replace('.d', '').upper()

        currencies = []

        # Check for major currency pairs
        if 'EUR' in symbol_upper:
            currencies.append('EUR')
        if 'USD' in symbol_upper:
            currencies.append('USD')
        if 'GBP' in symbol_upper:
            currencies.append('GBP')
        if 'JPY' in symbol_upper:
            currencies.append('JPY')
        if 'AUD' in symbol_upper:
            currencies.append('AUD')
        if 'CAD' in symbol_upper:
            currencies.append('CAD')
        if 'CHF' in symbol_upper:
            currencies.append('CHF')

        # For commodities like XAUUSD, also check USD currency
        if 'XAU' in symbol_upper or 'XAG' in symbol_upper:
            if 'USD' not in currencies:
                currencies.append('USD')

        return currencies if currencies else ['USD']  # Default to USD

    def print_calendar(self):
        """Print upcoming economic events"""
        upcoming = self.get_upcoming_events(hours=168, min_impact=EventImpact.MEDIUM)

        if not upcoming:
            logger.info("No upcoming economic events")
            return

        logger.info("\n" + "="*70)
        logger.info("ECONOMIC CALENDAR")
        logger.info("="*70)

        for event in upcoming[:20]:  # Show next 20
            logger.info(
                f"{event['country']:4} | {event['event']:25} | "
                f"{event['impact']:6} | In {event['time_until']:5.1f}h"
            )

        logger.info("="*70 + "\n")

    def is_data_stale(self) -> bool:
        """Check if calendar data needs refresh"""
        if self.last_update is None:
            return True

        elapsed = datetime.utcnow() - self.last_update
        return elapsed > self.update_interval

    def maybe_refresh(self) -> bool:
        """Refresh calendar if stale"""
        if self.is_data_stale():
            logger.info("Refreshing economic calendar...")
            return self.fetch_events()
        return True


# Global calendar instance
_calendar = None


def get_calendar() -> EconomicCalendar:
    """Get or create global calendar instance"""
    global _calendar
    if _calendar is None:
        _calendar = EconomicCalendar(
            lookback_minutes=60,      # Don't trade 1 hour before major event
            lookahead_minutes=120     # Don't trade 2 hours after major event starts
        )
        _calendar.fetch_events()
    return _calendar
