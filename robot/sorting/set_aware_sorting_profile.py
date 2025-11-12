from typing import Optional, Dict, List, Tuple
from robot.sorting.piece_sorting_profile import PieceSortingProfile
from robot.global_config import GlobalConfig
from robot.set_manager import SetManager


class SetDestination:
    """Represents a destination for a set-specific piece"""

    def __init__(self, set_id: str, set_name: str, is_set_piece: bool):
        self.set_id = set_id
        self.set_name = set_name
        self.is_set_piece = is_set_piece


class SetAwareSortingProfile(PieceSortingProfile):
    """
    Sorting profile that prioritizes set-specific sorting over category-based sorting

    When a piece is classified:
    1. Check if it belongs to any active set
    2. If yes, mark it for set-specific bin
    3. If no, fall back to category-based sorting
    """

    def __init__(
        self,
        global_config: GlobalConfig,
        profile_name: str,
        item_id_to_category_id_mapping: Dict[str, str],
        set_manager: SetManager,
        description: Optional[str] = None,
        kinds: Optional[Dict] = None,
        colors: Optional[Dict] = None,
        pieces: Optional[Dict] = None,
    ):
        super().__init__(
            global_config,
            profile_name,
            item_id_to_category_id_mapping,
            description,
            kinds,
            colors,
            pieces,
        )
        self.set_manager = set_manager
        self.logger = global_config["logger"].ctx(system="set_aware_sorting_profile")

    def get_destination(
        self, item_id: str, color_id: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[SetDestination]]:
        """
        Determine the sorting destination for a piece

        Args:
            item_id: The BrickLink part ID
            color_id: Optional color ID

        Returns:
            Tuple of (category_id, set_destination)
            - If piece belongs to active set: (None, SetDestination)
            - If piece doesn't belong to set: (category_id, None)
        """
        # First, check if piece belongs to any active sets
        matching_sets = self.set_manager.check_piece_in_sets(item_id, color_id)

        if matching_sets:
            # Piece belongs to at least one active set
            # Use the highest priority set (first in list)
            primary_set_id = matching_sets[0]

            # Get set info for logging
            active_sets = self.set_manager.get_active_sets()
            set_info = next((s for s in active_sets if s["set_id"] == primary_set_id), None)
            set_name = set_info["name"] if set_info else primary_set_id

            self.logger.info(
                f"Piece {item_id} (color: {color_id}) belongs to set: {set_name}"
            )

            return (None, SetDestination(primary_set_id, set_name, True))

        # Not a set piece, use category-based sorting
        category_id = self.getCategoryId(item_id)

        if category_id:
            self.logger.info(
                f"Piece {item_id} not in active sets, routing to category: {category_id}"
            )
        else:
            self.logger.warning(
                f"Piece {item_id} not found in sets or categories, will use fallback"
            )

        return (category_id, None)

    def record_set_piece_found(
        self, item_id: str, set_id: str, color_id: Optional[str] = None, observation_id: Optional[int] = None
    ) -> bool:
        """
        Record that a piece for a set has been found

        Args:
            item_id: The BrickLink part ID
            set_id: The set ID
            color_id: Optional color ID
            observation_id: Optional observation ID to link

        Returns:
            True if successful, False otherwise
        """
        success = self.set_manager.increment_piece_found(set_id, item_id, color_id)

        if success:
            self.logger.info(
                f"Recorded piece {item_id} (color: {color_id}) found for set {set_id}"
            )

            # TODO: Link observation to set in set_piece_observations table
            # if observation_id:
            #     self.set_manager.link_observation_to_set(observation_id, set_id)

        return success

    def get_all_active_sets(self) -> List[Dict]:
        """Get all currently active sets"""
        return self.set_manager.get_active_sets()

    def get_set_progress(self, set_id: str) -> Optional[Dict]:
        """Get progress information for a specific set"""
        return self.set_manager.get_set_progress(set_id)
