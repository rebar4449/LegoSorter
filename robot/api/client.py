import time
from robot.our_types import SystemLifecycleStage
from robot.our_types.irl_runtime_params import IRLSystemRuntimeParams
from robot.our_types.bin_state import BinState


class API:
    def __init__(self, controller):
        self.controller = controller

    def get_lifecycle_stage(self) -> SystemLifecycleStage:
        return self.controller.lifecycle_stage

    def pause(self):
        self.controller.pause()

    def resume(self):
        self.controller.resume()

    def run(self):
        self.controller.run()

    def getIRLRuntimeParams(self) -> IRLSystemRuntimeParams:
        return self.controller.irl_interface["runtime_params"]

    def updateIRLRuntimeParams(self, params: IRLSystemRuntimeParams):
        self.controller.irl_interface["runtime_params"] = params

    def getBinState(self) -> BinState:
        return {
            "bin_contents": self.controller.bin_state_tracker.current_state,
            "timestamp": int(time.time() * 1000),
        }

    def updateBinCategory(self, coordinates: dict, category_id: str | None) -> None:
        from robot.our_types.bin import BinCoordinates

        bin_coords: BinCoordinates = {
            "distribution_module_idx": coordinates["distribution_module_idx"],
            "bin_idx": coordinates["bin_idx"],
        }
        self.controller.bin_state_tracker.updateBinCategory(bin_coords, category_id)

    def setMiscBin(self, coordinates: dict) -> None:
        from robot.our_types.bin import BinCoordinates

        bin_coords: BinCoordinates = {
            "distribution_module_idx": coordinates["distribution_module_idx"],
            "bin_idx": coordinates["bin_idx"],
        }
        self.controller.bin_state_tracker.setMiscBin(bin_coords)

    def setFallbackBin(self, coordinates: dict) -> None:
        from robot.our_types.bin import BinCoordinates

        bin_coords: BinCoordinates = {
            "distribution_module_idx": coordinates["distribution_module_idx"],
            "bin_idx": coordinates["bin_idx"],
        }
        self.controller.bin_state_tracker.setFallbackBin(bin_coords)

    # Set management methods

    def addSet(self, set_num: str) -> str | None:
        """Add a set and sync its inventory"""
        from robot.set_manager import SetManager

        set_manager = SetManager(self.controller.global_config)
        return set_manager.add_set(set_num)

    def activateSet(self, set_num: str, priority: int = 0) -> bool:
        """Activate a set for sorting"""
        from robot.set_manager import SetManager

        set_manager = SetManager(self.controller.global_config)

        # First, check if set exists in database, if not add it
        set_id = set_num if "-" in set_num else f"{set_num}-1"

        # Try to activate the set
        success = set_manager.activate_set(set_id, priority)

        if success:
            # Reserve bins for this set
            self.controller.bin_state_tracker.reserve_bins_for_set(set_id, num_bins=2)

        return success

    def deactivateSet(self, set_id: str) -> bool:
        """Deactivate a set"""
        from robot.set_manager import SetManager

        set_manager = SetManager(self.controller.global_config)
        success = set_manager.deactivate_set(set_id)

        if success:
            # Release the bins reserved for this set
            self.controller.bin_state_tracker.release_set_bins(set_id)

        return success

    def getActiveSets(self):
        """Get all active sets"""
        from robot.set_manager import SetManager

        set_manager = SetManager(self.controller.global_config)
        return set_manager.get_active_sets()

    def getSetProgress(self, set_id: str):
        """Get progress for a specific set"""
        from robot.set_manager import SetManager

        set_manager = SetManager(self.controller.global_config)
        return set_manager.get_set_progress(set_id)

    def getSetInventory(self, set_id: str):
        """Get inventory for a set"""
        import sqlite3
        from robot.storage.sqlite3.migrations import getDatabaseConnection

        conn = getDatabaseConnection(self.controller.global_config)
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT item_id, color_id, quantity_needed, quantity_found, is_spare
                FROM set_inventories
                WHERE set_id = ?
                ORDER BY quantity_needed DESC
                """,
                (set_id,),
            )

            inventory = []
            for row in cursor.fetchall():
                inventory.append(
                    {
                        "item_id": row[0],
                        "color_id": row[1],
                        "quantity_needed": row[2],
                        "quantity_found": row[3],
                        "is_spare": bool(row[4]),
                    }
                )

            return inventory
        finally:
            conn.close()
