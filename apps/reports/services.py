"""Reports - Service Layer."""
from typing import Any

from .models import Report


class ReportService:
    @staticmethod
    def generate_report(*, data: dict[str, Any]) -> Report:
        """Generate and store a report."""
        report = Report(**data)
        report.full_clean()
        report.save()
        return report
