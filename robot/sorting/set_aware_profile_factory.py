from robot.global_config import GlobalConfig
from robot.sorting.sorting_profile import SortingProfile
from robot.sorting.piece_sorting_profile import PieceSortingProfile
from robot.sorting.set_aware_sorting_profile import SetAwareSortingProfile
from robot.sorting.bricklink_categories_sorting_profile import (
    mkBricklinkCategoriesSortingProfile,
)
from robot.set_manager import SetManager


def mkSetAwareSortingProfile(
    global_config: GlobalConfig,
) -> SetAwareSortingProfile:
    """
    Create a set-aware sorting profile that wraps the BrickLink categories profile

    This profile will:
    1. Check if a piece belongs to an active set
    2. If yes, route to set-specific bin
    3. If no, fall back to BrickLink category sorting
    """
    # Get the base category mapping from BrickLink
    base_profile = mkBricklinkCategoriesSortingProfile(global_config)

    # Create set manager
    set_manager = SetManager(global_config)

    # Wrap in set-aware profile
    return SetAwareSortingProfile(
        global_config,
        "Set-Aware BrickLink Categories",
        base_profile.item_id_to_category_id_mapping,
        set_manager,
        "Set-aware sorting profile with BrickLink category fallback",
        base_profile.kinds,
        base_profile.colors,
        base_profile.pieces,
    )
