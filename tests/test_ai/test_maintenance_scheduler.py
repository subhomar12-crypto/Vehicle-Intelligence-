"""Tests for maintenance scheduler."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from predict.core.ai.maintenance_scheduler import (
    MaintenanceScheduler,
    generate_maintenance_schedule,
    get_vehicle_maintenance_summary,
    COMPONENT_IDS,
)


class TestMaintenanceScheduler:
    """Test MaintenanceScheduler."""

    def setup_method(self):
        """Set up test fixtures."""
        self.scheduler = MaintenanceScheduler()

    def test_component_ids_available(self):
        """COMPONENT_IDS imported from survival_engine."""
        assert len(COMPONENT_IDS) == 10
        assert "engine_oil" in COMPONENT_IDS
        assert "battery" in COMPONENT_IDS

    @pytest.mark.asyncio
    async def test_schedule_for_vehicle(self):
        """Generate schedule for vehicle."""
        mock_session = AsyncMock()
        
        # Train survival engine with synthetic data
        self.scheduler.survival_engine.train_from_synthetic(n_samples=100)
        
        current_ages = {"engine_oil": 100, "battery": 500}
        
        schedule = await self.scheduler.schedule_for_vehicle(
            mock_session, profile_id=1, current_ages=current_ages
        )
        
        assert schedule["profile_id"] == 1
        assert "generated_at" in schedule
        assert len(schedule["maintenance_items"]) == 10
        
        # Check item format
        item = schedule["maintenance_items"][0]
        assert "component" in item
        assert "due_date" in item
        assert "due_in_days" in item
        assert "priority" in item
        assert item["priority"] in ["critical", "high", "medium", "low"]
        assert "estimated_cost" in item
        assert "parts" in item["estimated_cost"]
        assert "labor" in item["estimated_cost"]
        assert "total" in item["estimated_cost"]

    @pytest.mark.asyncio
    async def test_schedule_sorted_by_due_date(self):
        """Schedule items sorted by due date."""
        mock_session = AsyncMock()
        
        self.scheduler.survival_engine.train_from_synthetic(n_samples=100)
        
        schedule = await self.scheduler.schedule_for_vehicle(
            mock_session, profile_id=1
        )
        
        # Check sorting
        due_days = [item["due_in_days"] for item in schedule["maintenance_items"]]
        assert due_days == sorted(due_days)

    @pytest.mark.asyncio
    async def test_schedule_priority_levels(self):
        """Priority levels assigned correctly."""
        mock_session = AsyncMock()
        
        self.scheduler.survival_engine.train_from_synthetic(n_samples=100)
        
        schedule = await self.scheduler.schedule_for_vehicle(
            mock_session, profile_id=1
        )
        
        for item in schedule["maintenance_items"]:
            if item["due_in_days"] <= 30:
                assert item["priority"] == "critical"
            elif item["due_in_days"] <= 90:
                assert item["priority"] == "high"
            elif item["due_in_days"] <= 180:
                assert item["priority"] == "medium"
            else:
                assert item["priority"] == "low"

    def test_estimate_cost(self):
        """Cost estimation returns expected structure."""
        costs = self.scheduler._estimate_cost("engine_oil")
        
        assert "parts" in costs
        assert "labor" in costs
        assert "total" in costs
        assert costs["total"] == costs["parts"] + costs["labor"]
        assert costs["total"] > 0

    def test_estimate_cost_unknown_component(self):
        """Cost estimation handles unknown components."""
        costs = self.scheduler._estimate_cost("unknown_component")
        
        assert costs["parts"] == 300  # Default
        assert costs["labor"] == 100  # Default
        assert costs["total"] == 400

    @pytest.mark.asyncio
    async def test_get_upcoming_maintenance(self):
        """Get upcoming maintenance within days."""
        mock_session = AsyncMock()
        
        self.scheduler.survival_engine.train_from_synthetic(n_samples=100)
        
        upcoming = await self.scheduler.get_upcoming_maintenance(
            mock_session, profile_id=1, days_ahead=90
        )
        
        # All items should be due within 90 days
        for item in upcoming:
            assert item["due_in_days"] <= 90

    @pytest.mark.asyncio
    async def test_get_maintenance_summary(self):
        """Get maintenance summary for dashboard."""
        mock_session = AsyncMock()
        
        self.scheduler.survival_engine.train_from_synthetic(n_samples=100)
        
        summary = await self.scheduler.get_maintenance_summary(
            mock_session, profile_id=1
        )
        
        assert summary["profile_id"] == 1
        assert summary["total_items"] == 10
        assert "by_priority" in summary
        assert "critical" in summary["by_priority"]
        assert "high" in summary["by_priority"]
        assert "medium" in summary["by_priority"]
        assert "low" in summary["by_priority"]
        assert "estimated_total_cost" in summary
        assert summary["estimated_total_cost"] > 0
        assert "next_maintenance" in summary
        assert "generated_at" in summary


class TestARQJobs:
    """Test ARQ job functions."""

    @pytest.mark.asyncio
    async def test_generate_maintenance_schedule_job(self):
        """Generate schedule ARQ job runs."""
        with patch('predict.core.db.session.get_session_maker') as mock_session_maker:
            mock_session = AsyncMock()
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=False)
            mock_session_maker.return_value = MagicMock(return_value=mock_context)
            
            result = await generate_maintenance_schedule(profile_id=1)
            
            assert result["profile_id"] == 1
            assert "generated_at" in result
            assert "maintenance_items" in result

    @pytest.mark.asyncio
    async def test_get_vehicle_maintenance_summary_job(self):
        """Get summary ARQ job runs."""
        with patch('predict.core.db.session.get_session_maker') as mock_session_maker:
            mock_session = AsyncMock()
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=False)
            mock_session_maker.return_value = MagicMock(return_value=mock_context)
            
            result = await get_vehicle_maintenance_summary(profile_id=1)
            
            assert result["profile_id"] == 1
            assert "by_priority" in result
