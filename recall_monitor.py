"""
PREDICT - Vehicle Intelligence Platform
Copyright 2026 PREDICT
All rights reserved.

Recall Monitor - Automatic NHTSA recall checking and notifications.

Monitors for new recalls and Technical Service Bulletins (TSBs) and
notifies affected vehicle owners.
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
import logging
import json
import os
import hashlib
import asyncio
import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class RecallInfo:
    """Information about a vehicle recall."""

    recall_id: str
    campaign_number: str
    make: str
    model: str
    year: int

    # Recall details
    component: str
    summary: str
    consequence: str
    remedy: str
    notes: str = ""

    # Severity
    severity: str = "medium"  # low, medium, high, critical

    # Dates
    recall_date: str = ""
    report_received_date: str = ""

    # Counts
    potentially_affected: int = 0

    # Status
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_nhtsa_data(cls, data: Dict[str, Any]) -> 'RecallInfo':
        """Create RecallInfo from NHTSA API response."""
        campaign = data.get('NHTSACampaignNumber', '')

        # Generate unique ID
        recall_id = hashlib.md5(
            f"{campaign}_{data.get('Make', '')}_{data.get('Model', '')}_{data.get('ModelYear', '')}".encode()
        ).hexdigest()[:16]

        # Determine severity based on consequence
        consequence = data.get('Consequence', '').lower()
        if 'crash' in consequence or 'fire' in consequence or 'injury' in consequence:
            severity = 'critical'
        elif 'accident' in consequence or 'loss of' in consequence:
            severity = 'high'
        elif 'warning' in consequence or 'malfunction' in consequence:
            severity = 'medium'
        else:
            severity = 'low'

        return cls(
            recall_id=recall_id,
            campaign_number=campaign,
            make=data.get('Make', ''),
            model=data.get('Model', ''),
            year=int(data.get('ModelYear', 0)),
            component=data.get('Component', ''),
            summary=data.get('Summary', ''),
            consequence=data.get('Consequence', ''),
            remedy=data.get('Remedy', ''),
            notes=data.get('Notes', ''),
            severity=severity,
            recall_date=data.get('ReportReceivedDate', ''),
            report_received_date=data.get('ReportReceivedDate', ''),
            potentially_affected=int(data.get('PotentialNumberofUnitsAffected', 0) or 0),
            is_active=True
        )


@dataclass
class TSBInfo:
    """Technical Service Bulletin information."""

    tsb_id: str
    bulletin_number: str
    make: str
    model: str
    year: int

    # TSB details
    component: str
    summary: str

    # Date
    bulletin_date: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RecallCheckResult:
    """Result of a recall check for a vehicle."""

    make: str
    model: str
    year: int
    check_timestamp: str

    # Recalls found
    recalls: List[RecallInfo] = field(default_factory=list)
    new_recalls: List[RecallInfo] = field(default_factory=list)  # Not seen before

    # TSBs found
    tsbs: List[TSBInfo] = field(default_factory=list)

    # Summary
    total_recalls: int = 0
    critical_recalls: int = 0
    has_new_recalls: bool = False

    # Status
    success: bool = True
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        result = {
            'make': self.make,
            'model': self.model,
            'year': self.year,
            'check_timestamp': self.check_timestamp,
            'recalls': [r.to_dict() for r in self.recalls],
            'new_recalls': [r.to_dict() for r in self.new_recalls],
            'tsbs': [t.to_dict() for t in self.tsbs],
            'total_recalls': self.total_recalls,
            'critical_recalls': self.critical_recalls,
            'has_new_recalls': self.has_new_recalls,
            'success': self.success,
            'error_message': self.error_message
        }
        return result


class RecallMonitor:
    """
    Monitors NHTSA recalls and TSBs for registered vehicles.

    Can run as a background job to check for new recalls periodically.
    """

    NHTSA_BASE_URL = "https://api.nhtsa.gov"
    RECALLS_ENDPOINT = "/recalls/recallsByVehicle"
    COMPLAINTS_ENDPOINT = "/complaints/complaintsByVehicle"

    def __init__(self, base_path: str = "./PredictData"):
        self.base_path = base_path
        self.vehicles_path = os.path.join(base_path, "vehicles")
        self._known_recalls: Dict[str, set] = {}  # make_model_year -> set of recall_ids
        self._last_check: Dict[str, datetime] = {}
        self._check_interval = timedelta(days=7)  # Check weekly

    def get_year_research_path(self, make: str, model: str, year: int) -> str:
        """Get path to year-level research file."""
        return os.path.join(
            self.vehicles_path,
            make,
            model,
            str(year),
            "_year_research.json"
        )

    def load_known_recalls(self, make: str, model: str, year: int) -> set:
        """Load previously known recall IDs for a make/model/year."""
        key = f"{make}_{model}_{year}"

        if key in self._known_recalls:
            return self._known_recalls[key]

        known = set()
        research_path = self.get_year_research_path(make, model, year)

        if os.path.exists(research_path):
            try:
                with open(research_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                recalls = data.get('recalls', [])
                for recall in recalls:
                    recall_id = recall.get('recall_id', '')
                    if recall_id:
                        known.add(recall_id)

            except Exception as e:
                logger.error(f"Error loading known recalls: {e}")

        self._known_recalls[key] = known
        return known

    def save_recalls_to_research(
        self,
        make: str,
        model: str,
        year: int,
        recalls: List[RecallInfo]
    ):
        """Save recall data to year research file."""
        research_path = self.get_year_research_path(make, model, year)

        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(research_path), exist_ok=True)

            # Load existing data
            data = {}
            if os.path.exists(research_path):
                with open(research_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

            # Update recalls
            data['recalls'] = [r.to_dict() for r in recalls]
            data['recall_check_date'] = datetime.now().isoformat()
            data['total_recalls'] = len(recalls)
            data['critical_recalls'] = sum(1 for r in recalls if r.severity == 'critical')

            # Save
            with open(research_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)

            logger.info(f"Saved {len(recalls)} recalls for {make} {model} {year}")

        except Exception as e:
            logger.error(f"Error saving recalls: {e}")

    async def fetch_recalls_async(
        self,
        make: str,
        model: str,
        year: int
    ) -> List[RecallInfo]:
        """Fetch recalls from NHTSA API asynchronously."""
        url = f"{self.NHTSA_BASE_URL}{self.RECALLS_ENDPOINT}"
        params = {
            "make": make.upper(),
            "model": model.upper(),
            "modelYear": str(year)
        }

        recalls = []

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        results = data.get('results', [])

                        for result in results:
                            try:
                                recall = RecallInfo.from_nhtsa_data(result)
                                recalls.append(recall)
                            except Exception as e:
                                logger.error(f"Error parsing recall: {e}")

                        logger.info(f"Found {len(recalls)} recalls for {make} {model} {year}")
                    else:
                        logger.warning(f"NHTSA API returned status {response.status}")

        except asyncio.TimeoutError:
            logger.error("NHTSA API request timed out")
        except Exception as e:
            logger.error(f"Error fetching recalls: {e}")

        return recalls

    def fetch_recalls_sync(
        self,
        make: str,
        model: str,
        year: int
    ) -> List[RecallInfo]:
        """Fetch recalls from NHTSA API synchronously."""
        import requests

        url = f"{self.NHTSA_BASE_URL}{self.RECALLS_ENDPOINT}"
        params = {
            "make": make.upper(),
            "model": model.upper(),
            "modelYear": str(year)
        }

        recalls = []

        try:
            response = requests.get(url, params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])

                for result in results:
                    try:
                        recall = RecallInfo.from_nhtsa_data(result)
                        recalls.append(recall)
                    except Exception as e:
                        logger.error(f"Error parsing recall: {e}")

                logger.info(f"Found {len(recalls)} recalls for {make} {model} {year}")
            else:
                logger.warning(f"NHTSA API returned status {response.status_code}")

        except Exception as e:
            logger.error(f"Error fetching recalls: {e}")

        return recalls

    def check_vehicle_recalls(
        self,
        make: str,
        model: str,
        year: int,
        force: bool = False
    ) -> RecallCheckResult:
        """
        Check for recalls for a specific vehicle.

        Args:
            make: Vehicle make
            model: Vehicle model
            year: Vehicle year
            force: Force check even if recently checked

        Returns:
            RecallCheckResult with recall information
        """
        result = RecallCheckResult(
            make=make,
            model=model,
            year=year,
            check_timestamp=datetime.now().isoformat()
        )

        # Check if recently checked
        key = f"{make}_{model}_{year}"
        if not force and key in self._last_check:
            if datetime.now() - self._last_check[key] < self._check_interval:
                logger.info(f"Skipping recall check for {make} {model} {year} - checked recently")
                # Load cached results
                research_path = self.get_year_research_path(make, model, year)
                if os.path.exists(research_path):
                    try:
                        with open(research_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        recalls_data = data.get('recalls', [])
                        result.recalls = [
                            RecallInfo(**r) for r in recalls_data
                            if isinstance(r, dict) and 'recall_id' in r
                        ]
                        result.total_recalls = len(result.recalls)
                        result.critical_recalls = sum(
                            1 for r in result.recalls if r.severity == 'critical'
                        )
                        return result
                    except Exception:
                        pass

        try:
            # Load known recalls for comparison
            known_ids = self.load_known_recalls(make, model, year)

            # Fetch current recalls from NHTSA
            recalls = self.fetch_recalls_sync(make, model, year)

            # Identify new recalls
            new_recalls = []
            for recall in recalls:
                if recall.recall_id not in known_ids:
                    new_recalls.append(recall)

            result.recalls = recalls
            result.new_recalls = new_recalls
            result.total_recalls = len(recalls)
            result.critical_recalls = sum(1 for r in recalls if r.severity == 'critical')
            result.has_new_recalls = len(new_recalls) > 0
            result.success = True

            # Save to research file
            self.save_recalls_to_research(make, model, year, recalls)

            # Update tracking
            self._known_recalls[key] = {r.recall_id for r in recalls}
            self._last_check[key] = datetime.now()

            if new_recalls:
                logger.warning(
                    f"Found {len(new_recalls)} NEW recalls for {make} {model} {year}!"
                )

        except Exception as e:
            result.success = False
            result.error_message = str(e)
            logger.error(f"Error checking recalls: {e}")

        return result

    def check_all_registered_vehicles(
        self,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, RecallCheckResult]:
        """
        Check recalls for all registered vehicles.

        This is intended to run as a background/scheduled job.

        Args:
            progress_callback: Optional callback(current, total, message)

        Returns:
            Dict mapping vehicle key to RecallCheckResult
        """
        results = {}

        # Get all unique make/model/year combinations
        combinations = self._get_all_vehicle_combinations()

        total = len(combinations)
        logger.info(f"Checking recalls for {total} vehicle types")

        for i, (make, model, year) in enumerate(combinations):
            key = f"{make}_{model}_{year}"

            if progress_callback:
                progress_callback(i + 1, total, f"Checking {make} {model} {year}...")

            try:
                result = self.check_vehicle_recalls(make, model, year)
                results[key] = result

            except Exception as e:
                logger.error(f"Error checking recalls for {key}: {e}")
                results[key] = RecallCheckResult(
                    make=make,
                    model=model,
                    year=year,
                    check_timestamp=datetime.now().isoformat(),
                    success=False,
                    error_message=str(e)
                )

        return results

    def _get_all_vehicle_combinations(self) -> List[tuple]:
        """Get all unique make/model/year combinations from registered vehicles."""
        combinations = set()

        if not os.path.exists(self.vehicles_path):
            return []

        try:
            # Iterate through make folders
            for make in os.listdir(self.vehicles_path):
                make_path = os.path.join(self.vehicles_path, make)
                if not os.path.isdir(make_path) or make.startswith('_'):
                    continue

                # Iterate through model folders
                for model in os.listdir(make_path):
                    model_path = os.path.join(make_path, model)
                    if not os.path.isdir(model_path) or model.startswith('_'):
                        continue

                    # Iterate through year folders
                    for year_str in os.listdir(model_path):
                        year_path = os.path.join(model_path, year_str)
                        if not os.path.isdir(year_path) or year_str.startswith('_'):
                            continue

                        try:
                            year = int(year_str)
                            combinations.add((make, model, year))
                        except ValueError:
                            continue

        except Exception as e:
            logger.error(f"Error scanning vehicle combinations: {e}")

        return list(combinations)

    def get_affected_owners(
        self,
        make: str,
        model: str,
        year: int
    ) -> List[Dict[str, Any]]:
        """
        Get list of owners affected by recalls for a make/model/year.

        Returns owner information for notification purposes.
        """
        affected = []
        year_path = os.path.join(self.vehicles_path, make, model, str(year))

        if not os.path.exists(year_path):
            return affected

        try:
            for item in os.listdir(year_path):
                if item.startswith('_') or item.startswith('.'):
                    continue

                vehicle_path = os.path.join(year_path, item)
                if not os.path.isdir(vehicle_path):
                    continue

                profile_path = os.path.join(vehicle_path, "profile.json")
                if os.path.exists(profile_path):
                    with open(profile_path, 'r', encoding='utf-8') as f:
                        profile = json.load(f)

                    affected.append({
                        'vehicle_id': item,
                        'owner_id': profile.get('owner_id'),
                        'owner_name': profile.get('owner_name'),
                        'owner_email': profile.get('owner_email'),
                        'license_plate': profile.get('license_plate'),
                        'make': make,
                        'model': model,
                        'year': year
                    })

        except Exception as e:
            logger.error(f"Error getting affected owners: {e}")

        return affected

    def get_recall_summary_for_vehicle(
        self,
        make: str,
        model: str,
        year: int
    ) -> Dict[str, Any]:
        """
        Get recall summary formatted for UI display.
        """
        research_path = self.get_year_research_path(make, model, year)

        summary = {
            'has_recalls': False,
            'total_recalls': 0,
            'critical_recalls': 0,
            'recalls': [],
            'last_checked': None
        }

        if os.path.exists(research_path):
            try:
                with open(research_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                recalls = data.get('recalls', [])
                summary['has_recalls'] = len(recalls) > 0
                summary['total_recalls'] = len(recalls)
                summary['critical_recalls'] = sum(
                    1 for r in recalls
                    if isinstance(r, dict) and r.get('severity') == 'critical'
                )
                summary['last_checked'] = data.get('recall_check_date')

                # Include recall details (limited for display)
                summary['recalls'] = [
                    {
                        'campaign_number': r.get('campaign_number', ''),
                        'component': r.get('component', ''),
                        'summary': r.get('summary', '')[:200] + '...' if len(r.get('summary', '')) > 200 else r.get('summary', ''),
                        'severity': r.get('severity', 'unknown'),
                        'remedy': r.get('remedy', '')[:150] + '...' if len(r.get('remedy', '')) > 150 else r.get('remedy', '')
                    }
                    for r in recalls[:10]  # Limit to 10 for display
                    if isinstance(r, dict)
                ]

            except Exception as e:
                logger.error(f"Error loading recall summary: {e}")

        return summary


# Singleton instance
_monitor: Optional[RecallMonitor] = None


def get_recall_monitor(base_path: str = "./PredictData") -> RecallMonitor:
    """Get global recall monitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = RecallMonitor(base_path)
    return _monitor


def check_recalls(
    make: str,
    model: str,
    year: int,
    force: bool = False
) -> RecallCheckResult:
    """
    Convenience function to check recalls for a vehicle.

    Args:
        make: Vehicle make
        model: Vehicle model
        year: Vehicle year
        force: Force check even if recently checked

    Returns:
        RecallCheckResult with recall information
    """
    monitor = get_recall_monitor()
    return monitor.check_vehicle_recalls(make, model, year, force)


def get_recall_summary(make: str, model: str, year: int) -> Dict[str, Any]:
    """
    Convenience function to get recall summary for display.

    Args:
        make: Vehicle make
        model: Vehicle model
        year: Vehicle year

    Returns:
        Summary dict for UI display
    """
    monitor = get_recall_monitor()
    return monitor.get_recall_summary_for_vehicle(make, model, year)


# Background job support
class RecallCheckJob:
    """
    Background job for periodic recall checking.

    Can be integrated with task schedulers or run as standalone.
    """

    def __init__(self, base_path: str = "./PredictData"):
        self.monitor = RecallMonitor(base_path)
        self._running = False

    def run_check(
        self,
        on_new_recall: Optional[Callable[[RecallInfo, List[Dict]], None]] = None
    ) -> Dict[str, RecallCheckResult]:
        """
        Run recall check for all vehicles.

        Args:
            on_new_recall: Callback when new recall found (recall, affected_owners)

        Returns:
            Results for all vehicle types
        """
        self._running = True
        results = {}

        try:
            combinations = self.monitor._get_all_vehicle_combinations()

            for make, model, year in combinations:
                if not self._running:
                    break

                result = self.monitor.check_vehicle_recalls(make, model, year)
                key = f"{make}_{model}_{year}"
                results[key] = result

                # Notify about new recalls
                if result.has_new_recalls and on_new_recall:
                    affected = self.monitor.get_affected_owners(make, model, year)
                    for recall in result.new_recalls:
                        on_new_recall(recall, affected)

        finally:
            self._running = False

        return results

    def stop(self):
        """Stop the running check."""
        self._running = False
