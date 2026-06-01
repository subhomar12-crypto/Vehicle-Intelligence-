"""
PREDICT Desktop GUI Tabs.

This package contains the 6 main tabs of the PREDICT Desktop interface:
- profile_tab: User profile management
- server_ops_tab: Server operations and monitoring
- ai_llm_tab: AI chat and training control
- pdf_tab: PDF report generation
- dtc_tab: DTC management
- analytics_tab: System analytics and charts
"""

from predict.desktop.tabs.profile_tab import ProfileTab
from predict.desktop.tabs.server_ops_tab import ServerOpsTab
from predict.desktop.tabs.ai_llm_tab import AILLMTab
from predict.desktop.tabs.pdf_tab import PDFTab
from predict.desktop.tabs.dtc_tab import DTCTab
from predict.desktop.tabs.analytics_tab import AnalyticsTab
from predict.desktop.tabs.user_detail_dialog import UserDetailDialog

__all__ = [
    "ProfileTab",
    "ServerOpsTab",
    "AILLMTab",
    "PDFTab",
    "DTCTab",
    "AnalyticsTab",
    "UserDetailDialog",
]
