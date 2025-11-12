from typing import List, Optional, Dict
import time
from robot.global_config import GlobalConfig

ENABLE_MISC_BIN = False
from robot.sorting.sorting_profile import SortingProfile
from robot.irl.distribution import DistributionModule
from robot.storage.sqlite3.operations import saveBinStateToDatabase
from robot.our_types.bin import BinCoordinates
from robot.our_types.bin_state import BinContentsMap, BinState, PersistedBinState
from robot.websocket_manager import WebSocketManager


class BinStateTracker:
    def __init__(
        self,
        global_config: GlobalConfig,
        distribution_modules: List[DistributionModule],
        sorting_profile: SortingProfile,
        websocket_manager: WebSocketManager,
        bin_state_id: Optional[str] = None,
    ):
        self.global_config = global_config
        self.distribution_modules = distribution_modules
        self.available_bin_coordinates = self._buildAvailableBinCoordinates()
        self.sorting_profile = sorting_profile
        self.websocket_manager = websocket_manager
        self.misc_category_id = "misc"
        self.fallback_category_id = "fallback"
        self.current_bin_state_id: Optional[str] = None
        self.misc_bin_coordinates: Optional[BinCoordinates] = None
        self.fallback_bin_coordinates: Optional[BinCoordinates] = None

        # Set-specific bin tracking
        self.set_bins: Dict[str, List[BinCoordinates]] = {}  # Maps set_id -> list of bin coordinates
        self.set_bin_prefix = "set:"  # Prefix for set categories in bin state

        self.current_state: BinContentsMap = {}
        for coordinates in self.available_bin_coordinates:
            key = binCoordinatesToKey(coordinates)
            self.current_state[key] = None

        previous_state = None
        if bin_state_id:
            from robot.storage.sqlite3.operations import (
                getBinStateFromDatabase,
                getMostRecentBinState,
            )

            if bin_state_id == "latest":
                previous_state = getMostRecentBinState(global_config)
                if previous_state:
                    global_config["logger"].info(
                        f"Using most recent bin state: {previous_state['id']}"
                    )
            else:
                previous_state = getBinStateFromDatabase(global_config, bin_state_id)
                if previous_state:
                    global_config["logger"].info(f"Using bin state: {bin_state_id}")

            if not previous_state:
                global_config["logger"].info(
                    "No previous bin state found, starting fresh"
                )

        if previous_state:
            self.current_state.update(previous_state["bin_contents"])
            self.current_bin_state_id = previous_state["id"]
            self.global_config["logger"].info(
                f"Loaded previous bin state: {self.current_bin_state_id}"
            )

        # Reserve bins based on ENABLE_MISC_BIN setting
        if ENABLE_MISC_BIN and len(self.available_bin_coordinates) >= 2:
            # Reserve second to last bin as misc and last bin as fallback
            second_to_last_bin = self.available_bin_coordinates[-2]
            last_bin = self.available_bin_coordinates[-1]
            self._reserveBinInternal(second_to_last_bin, self.misc_category_id)
            self._reserveBinInternal(last_bin, self.fallback_category_id)
            self.misc_bin_coordinates = second_to_last_bin
            self.fallback_bin_coordinates = last_bin
        elif len(self.available_bin_coordinates) >= 1:
            # Reserve only last bin as fallback
            last_bin = self.available_bin_coordinates[-1]
            self._reserveBinInternal(last_bin, self.fallback_category_id)
            self.fallback_bin_coordinates = last_bin

        # Save initial state if this is a new bin state
        if not previous_state:
            self.current_bin_state_id = self.saveBinState()
            self.global_config["logger"].info(
                f"Created new bin state: {self.current_bin_state_id}"
            )

    def _buildAvailableBinCoordinates(self) -> List[BinCoordinates]:
        available_bins = []
        sorted_modules = sorted(
            enumerate(self.distribution_modules),
            key=lambda x: x[1].distance_from_camera_center_to_door_begin_cm,
        )

        for dm_idx, module in sorted_modules:
            for bin_idx in range(len(module.bins)):
                available_bins.append(
                    {"distribution_module_idx": dm_idx, "bin_idx": bin_idx}
                )

        return available_bins

    def findAvailableBin(self, category_id: str) -> Optional[BinCoordinates]:
        # Sort coordinates to ensure consistent "first bin" selection
        sorted_coordinates = sorted(
            self.available_bin_coordinates,
            key=lambda c: (c["distribution_module_idx"], c["bin_idx"]),
        )

        # First, try to find the first bin that already has this category
        for coordinates in sorted_coordinates:
            key = binCoordinatesToKey(coordinates)
            current_category = self.current_state.get(key)
            if current_category == category_id:
                return coordinates

        # If no existing bin found, look for an empty bin
        for coordinates in sorted_coordinates:
            key = binCoordinatesToKey(coordinates)
            current_category = self.current_state.get(key)
            if current_category is None:
                return coordinates

        # If no empty bin available, handle overflow
        if (
            category_id != self.misc_category_id
            and category_id != self.fallback_category_id
        ):
            # For successfully classified items, prefer misc bin if enabled
            if ENABLE_MISC_BIN and self.misc_bin_coordinates:
                self.global_config["logger"].info(
                    f"No available bins for category '{category_id}', sending to misc bin"
                )
                return self.misc_bin_coordinates
            elif self.fallback_bin_coordinates:
                self.global_config["logger"].info(
                    f"No available bins for category '{category_id}', sending to fallback bin"
                )
                return self.fallback_bin_coordinates

        return None

    # Internal method to reserve bin without saving to database (used during initialization)
    def _reserveBinInternal(
        self, coordinates: BinCoordinates, category_id: str
    ) -> None:
        key = binCoordinatesToKey(coordinates)
        self.current_state[key] = category_id

    def reserveBin(self, coordinates: BinCoordinates, category_id: str) -> None:
        # Prevent overwriting fallback bin category unless it's explicitly for fallback
        key = binCoordinatesToKey(coordinates)
        current_category = self.current_state.get(key)

        if (
            current_category == self.fallback_category_id
            and category_id != self.fallback_category_id
        ):
            # Don't overwrite fallback bin with other categories
            self.global_config["logger"].warning(
                f"Attempted to overwrite fallback bin with category '{category_id}', ignoring"
            )
            return

        self._reserveBinInternal(coordinates, category_id)
        self.current_bin_state_id = self.saveBinState()

        bin_state: BinState = {
            "bin_contents": self.current_state,
            "timestamp": int(time.time() * 1000),
        }

        self.websocket_manager.broadcast_bin_state(bin_state)

    def saveBinState(self) -> str:
        bin_state_id = saveBinStateToDatabase(self.global_config, self.current_state)
        return bin_state_id

    def updateBinCategory(
        self, coordinates: BinCoordinates, category_id: Optional[str]
    ) -> None:
        key = binCoordinatesToKey(coordinates)
        self.current_state[key] = category_id
        self.current_bin_state_id = self.saveBinState()

        # Broadcast the updated bin state
        from robot.our_types.bin_state import BinState
        import time

        bin_state: BinState = {
            "bin_contents": self.current_state,
            "timestamp": int(time.time() * 1000),
        }

        # Get websocket manager from global context if available
        self.websocket_manager.broadcast_bin_state(bin_state)

    def setMiscBin(self, coordinates: BinCoordinates) -> None:
        self.misc_bin_coordinates = coordinates
        self.updateBinCategory(coordinates, self.misc_category_id)

    def setFallbackBin(self, coordinates: BinCoordinates) -> None:
        self.fallback_bin_coordinates = coordinates
        self.updateBinCategory(coordinates, self.fallback_category_id)

    # Set-aware bin management methods

    def reserve_bins_for_set(self, set_id: str, num_bins: int = 2) -> List[BinCoordinates]:
        """
        Reserve bins for a specific set

        Args:
            set_id: The set ID to reserve bins for
            num_bins: Number of bins to reserve (default 2)

        Returns:
            List of bin coordinates that were reserved
        """
        reserved_bins = []

        # Find available empty bins (excluding fallback and misc bins)
        sorted_coordinates = sorted(
            self.available_bin_coordinates,
            key=lambda c: (c["distribution_module_idx"], c["bin_idx"]),
        )

        for coordinates in sorted_coordinates:
            if len(reserved_bins) >= num_bins:
                break

            key = binCoordinatesToKey(coordinates)
            current_category = self.current_state.get(key)

            # Skip if bin is already used (fallback, misc, or has content)
            if current_category is not None:
                continue

            # Reserve this bin for the set
            set_category = f"{self.set_bin_prefix}{set_id}"
            self._reserveBinInternal(coordinates, set_category)
            reserved_bins.append(coordinates)

        if reserved_bins:
            self.set_bins[set_id] = reserved_bins
            self.current_bin_state_id = self.saveBinState()
            self.global_config["logger"].info(
                f"Reserved {len(reserved_bins)} bins for set {set_id}: {reserved_bins}"
            )

            # Broadcast updated bin state
            bin_state: BinState = {
                "bin_contents": self.current_state,
                "timestamp": int(time.time() * 1000),
            }
            self.websocket_manager.broadcast_bin_state(bin_state)

        return reserved_bins

    def release_set_bins(self, set_id: str) -> None:
        """
        Release bins that were reserved for a set

        Args:
            set_id: The set ID to release bins for
        """
        if set_id not in self.set_bins:
            return

        for coordinates in self.set_bins[set_id]:
            key = binCoordinatesToKey(coordinates)
            self.current_state[key] = None

        del self.set_bins[set_id]
        self.current_bin_state_id = self.saveBinState()

        self.global_config["logger"].info(f"Released bins for set {set_id}")

        # Broadcast updated bin state
        bin_state: BinState = {
            "bin_contents": self.current_state,
            "timestamp": int(time.time() * 1000),
        }
        self.websocket_manager.broadcast_bin_state(bin_state)

    def find_bin_for_set_piece(self, set_id: str) -> Optional[BinCoordinates]:
        """
        Find a bin for a piece that belongs to a set

        Args:
            set_id: The set ID

        Returns:
            BinCoordinates if available, None otherwise
        """
        # First, try to use a reserved bin for this set
        if set_id in self.set_bins and self.set_bins[set_id]:
            # Return the first reserved bin for this set
            return self.set_bins[set_id][0]

        # If no reserved bins, try to dynamically allocate one
        set_category = f"{self.set_bin_prefix}{set_id}"

        # Look for existing bin with this set's pieces
        sorted_coordinates = sorted(
            self.available_bin_coordinates,
            key=lambda c: (c["distribution_module_idx"], c["bin_idx"]),
        )

        for coordinates in sorted_coordinates:
            key = binCoordinatesToKey(coordinates)
            current_category = self.current_state.get(key)
            if current_category == set_category:
                return coordinates

        # If no existing bin, try to find an empty one
        for coordinates in sorted_coordinates:
            key = binCoordinatesToKey(coordinates)
            current_category = self.current_state.get(key)
            if current_category is None:
                # Reserve this bin for the set
                self._reserveBinInternal(coordinates, set_category)
                if set_id not in self.set_bins:
                    self.set_bins[set_id] = []
                self.set_bins[set_id].append(coordinates)
                self.current_bin_state_id = self.saveBinState()
                self.global_config["logger"].info(
                    f"Dynamically allocated bin for set {set_id}: {coordinates}"
                )
                return coordinates

        # No available bins, use fallback
        self.global_config["logger"].warning(
            f"No available bins for set {set_id}, using fallback"
        )
        return self.fallback_bin_coordinates


def binCoordinatesToKey(coordinates: BinCoordinates) -> str:
    return f"{coordinates['distribution_module_idx']}_{coordinates['bin_idx']}"
