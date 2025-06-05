"""Display utilities for Brevo sync operations."""


def display_sync_info(
    acquisition_data,
    activation_data,
    acquisition_pipeline,
    activation_pipeline,
    acquisition_only,
    activation_only,
    dry_run,
):
    if acquisition_only:
        print(f"\n🎯 Acquisition-only sync: {len(acquisition_data)} companies")
        print(f"Pipeline: {acquisition_pipeline}")
    elif activation_only:
        print(f"\n🚀 Activation-only sync: {len(activation_data)} companies")
        print(f"Pipeline: {activation_pipeline}")
    else:
        print(f"\n🔄 Dual pipeline sync:")
        print(
            f"   🎯 Acquisition: {len(acquisition_data)} companies → '{acquisition_pipeline}'"
        )
        print(
            f"   🚀 Activation: {len(activation_data)} companies → '{activation_pipeline}'"
        )

    print("=" * 60)

    if dry_run:
        print("🧪 DRY RUN MODE - No changes will be made")


def display_sync_results(result, dry_run):
    print(f"\n📊 Sync Results:")
    print(f"   Total companies processed: {result.total_companies}")

    if hasattr(result, "acquisition_synced") and hasattr(
        result, "activation_synced"
    ):
        print(f"   Acquisition deals processed: {result.acquisition_synced}")
        print(f"   Activation deals processed: {result.activation_synced}")

    print(f"   Deals created: {result.created_deals}")
    print(f"   Deals updated: {result.updated_deals}")

    if result.errors:
        print(f"\n⚠️  Errors encountered ({len(result.errors)}):")
        for error in result.errors[:5]:
            print(f"   • {error}")
        if len(result.errors) > 5:
            print(f"   ... and {len(result.errors) - 5} more errors")

    if dry_run:
        print("\n✅ Dry run completed - no changes were made")
    else:
        print(f"\n✅ Sync completed successfully")
