"""Testing utilities for funnel classification logic."""

from typing import List, Dict, Any


class FunnelTester:
    """Utility class for testing and analyzing funnel classification."""

    @staticmethod
    def run_classification_test(
        acquisition_only: bool = False, activation_only: bool = False
    ) -> None:
        """Run classification test mode with coordinated logic.

        Args:
            acquisition_only: Test only acquisition funnel
            activation_only: Test only activation funnel
        """
        from .acquisition_data_finder import get_companies_acquisition_data
        from .activation_data_finder import get_companies_activation_data

        print("🧪 Testing Funnel Classification (Coordinated Logic)")
        print("=" * 55)
        print("📋 Logic: Activation first (strict), then Acquisition (rest)")

        if activation_only:
            activation_data = get_companies_activation_data()
            acquisition_data = []
            print(f"📊 Activation data: {len(activation_data)} companies")
        elif acquisition_only:
            activation_data = get_companies_activation_data()
            activation_company_ids = [c["company_id"] for c in activation_data]

            from .acquisition_data_finder import AcquisitionDataFinder

            finder = AcquisitionDataFinder()
            acquisition_data = finder.find_companies(
                exclude_company_ids=activation_company_ids
            )
            activation_data = []
            print(f"📊 Acquisition data: {len(acquisition_data)} companies")
            print(
                f"📊 (Excluded {len(activation_company_ids)} activation companies)"
            )
        else:
            activation_data = get_companies_activation_data()
            activation_company_ids = [c["company_id"] for c in activation_data]

            from .acquisition_data_finder import AcquisitionDataFinder

            finder = AcquisitionDataFinder()
            acquisition_data = finder.find_companies(
                exclude_company_ids=activation_company_ids
            )

            print(
                f"📊 Activation data: {len(activation_data)} companies (strict criteria)"
            )
            print(
                f"📊 Acquisition data: {len(acquisition_data)} companies (all others)"
            )
            print(
                f"📊 Total: {len(activation_data) + len(acquisition_data)} companies"
            )

        if not activation_only:
            FunnelTester._display_acquisition_analysis(acquisition_data)

        if not acquisition_only:
            FunnelTester._display_activation_analysis(activation_data)

        print("\n✅ Test classification completed")

    @staticmethod
    def _display_acquisition_analysis(
        acquisition_data: List[Dict[str, Any]]
    ) -> None:
        print("🎯 Acquisition Funnel Analysis:")
        print("=" * 40)

        status_counts = {}
        for company in acquisition_data:
            status = company["acquisition_status"]
            status_counts[status] = status_counts.get(status, 0) + 1

        for status, count in sorted(
            status_counts.items(), key=lambda x: x[1], reverse=True
        ):
            percentage = count / len(acquisition_data) * 100
            print(f"   {count:3d} companies ({percentage:5.1f}%): {status}")

    @staticmethod
    def _display_activation_analysis(
        activation_data: List[Dict[str, Any]]
    ) -> None:
        print("\n🚀 Activation Funnel Analysis:")
        print("=" * 40)

        status_counts = {}
        total_invitation_rate = 0
        companies_with_employees = 0

        for company in activation_data:
            status = company["activation_status"]
            status_counts[status] = status_counts.get(status, 0) + 1

            total_employees = company.get("total_employees_count", 0)
            if total_employees > 0:
                companies_with_employees += 1
                invitation_percentage = company.get("invitation_percentage", 0)
                total_invitation_rate += invitation_percentage

        for status, count in sorted(
            status_counts.items(), key=lambda x: x[1], reverse=True
        ):
            percentage = count / len(activation_data) * 100
            print(f"   {count:3d} companies ({percentage:5.1f}%): {status}")

        if companies_with_employees > 0:
            avg_invitation_rate = (
                total_invitation_rate / companies_with_employees
            )
            print(f"\n📈 Average invitation rate: {avg_invitation_rate:.1f}%")
            print(
                "👥 Companies with employees: Analysis completed successfully."
            )
