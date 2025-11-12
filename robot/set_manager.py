import sqlite3
import time
import json
from typing import List, Optional, Dict, Tuple, cast
from robot.global_config import GlobalConfig
from robot.storage.sqlite3.migrations import getDatabaseConnection
from robot.external.rebrickable import RebrickableClient, getSetInfo, getSetInventory
from robot.external.rebrickable.types import RebrickableSetData, RebrickablePartData


class SetManager:
    """Manages LEGO sets for set-specific sorting"""

    def __init__(self, global_config: GlobalConfig):
        self.global_config = global_config
        self.logger = global_config["logger"].ctx(system="set_manager")
        self.db_path = global_config["db_path"]
        self.run_id = global_config["run_id"]
        self.rebrickable_client = RebrickableClient()

    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection"""
        return getDatabaseConnection(self.global_config)

    def search_sets(self, query: str) -> List[RebrickableSetData]:
        """
        Search for sets on Rebrickable

        Args:
            query: Search query (set number or name)

        Returns:
            List of set data from Rebrickable
        """
        self.logger.info(f"Searching for sets: {query}")
        result = self.rebrickable_client.search_sets(query)

        if result and "results" in result:
            return result["results"]

        return []

    def add_set(self, set_num: str) -> Optional[str]:
        """
        Add a set to the database and sync its inventory from Rebrickable

        Args:
            set_num: Set number (e.g., "75192-1")

        Returns:
            The set_id if successful, None otherwise
        """
        self.logger.info(f"Adding set: {set_num}")

        # Get set info from Rebrickable
        set_info = getSetInfo(set_num)
        if not set_info:
            self.logger.error(f"Failed to get set info for {set_num}")
            return None

        # Insert set into database
        conn = self._get_conn()
        cursor = conn.cursor()
        now = int(time.time() * 1000)

        try:
            cursor.execute(
                """
                INSERT OR REPLACE INTO lego_sets
                (set_id, set_num, name, year, theme, num_parts, set_img_url, rebrickable_url, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    set_info["set_num"],
                    set_num.split("-")[0],  # Remove variant suffix
                    set_info["name"],
                    set_info.get("year"),
                    str(set_info.get("theme_id", "")),
                    set_info.get("num_parts"),
                    set_info.get("set_img_url"),
                    set_info.get("set_url"),
                    now,
                    now,
                ),
            )

            set_id = set_info["set_num"]

            # Sync inventory
            self._sync_inventory(set_id, conn)

            conn.commit()
            self.logger.info(f"Successfully added set {set_id}")
            return set_id

        except Exception as e:
            self.logger.error(f"Failed to add set {set_num}: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()

    def _sync_inventory(self, set_id: str, conn: sqlite3.Connection) -> None:
        """
        Sync set inventory from Rebrickable to database

        Args:
            set_id: The set ID
            conn: Database connection
        """
        self.logger.info(f"Syncing inventory for set {set_id}")

        # Get inventory from Rebrickable
        inventory = getSetInventory(set_id, include_spares=False)

        if not inventory:
            self.logger.warning(f"No inventory found for set {set_id}")
            return

        cursor = conn.cursor()
        now = int(time.time() * 1000)

        # Process each part
        for part_data in inventory:
            # Extract part info
            part_info = part_data.get("part", {})
            color_info = part_data.get("color", {})

            part_num = part_info.get("part_num", "")
            color_id = str(color_info.get("id", ""))
            quantity = part_data.get("quantity", 1)
            is_spare = part_data.get("is_spare", False)

            # For now, use Rebrickable part numbers directly
            # TODO: Implement proper mapping to BrickLink IDs
            item_id = part_num

            try:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO set_inventories
                    (set_id, item_id, color_id, quantity_needed, quantity_found, is_spare, created_at, updated_at)
                    VALUES (?, ?, ?, ?, COALESCE((SELECT quantity_found FROM set_inventories WHERE set_id = ? AND item_id = ? AND color_id = ?), 0), ?, ?, ?)
                    """,
                    (
                        set_id,
                        item_id,
                        color_id,
                        quantity,
                        set_id,
                        item_id,
                        color_id,
                        is_spare,
                        now,
                        now,
                    ),
                )
            except Exception as e:
                self.logger.error(f"Failed to insert inventory item: {e}")

        self.logger.info(f"Synced {len(inventory)} parts for set {set_id}")

    def activate_set(
        self, set_id: str, priority: int = 0, reserved_bins: Optional[List[Tuple[int, int]]] = None
    ) -> bool:
        """
        Activate a set for sorting in the current run

        Args:
            set_id: The set ID to activate
            priority: Priority level (higher = preferred when piece matches multiple sets)
            reserved_bins: List of bin coordinates [[dm_idx, bin_idx], ...] to reserve

        Returns:
            True if successful, False otherwise
        """
        self.logger.info(f"Activating set {set_id} with priority {priority}")

        conn = self._get_conn()
        cursor = conn.cursor()
        now = int(time.time() * 1000)

        try:
            # Check if set exists
            cursor.execute("SELECT set_id FROM lego_sets WHERE set_id = ?", (set_id,))
            if not cursor.fetchone():
                self.logger.error(f"Set {set_id} not found in database")
                return False

            # Activate the set
            cursor.execute(
                """
                INSERT INTO active_sorting_sets
                (run_id, set_id, priority, reserved_bins, enabled_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    self.run_id,
                    set_id,
                    priority,
                    json.dumps(reserved_bins or []),
                    now,
                    now,
                ),
            )

            conn.commit()
            self.logger.info(f"Successfully activated set {set_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to activate set {set_id}: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def deactivate_set(self, set_id: str) -> bool:
        """
        Deactivate a set from sorting

        Args:
            set_id: The set ID to deactivate

        Returns:
            True if successful, False otherwise
        """
        self.logger.info(f"Deactivating set {set_id}")

        conn = self._get_conn()
        cursor = conn.cursor()
        now = int(time.time() * 1000)

        try:
            cursor.execute(
                """
                UPDATE active_sorting_sets
                SET disabled_at = ?
                WHERE run_id = ? AND set_id = ? AND disabled_at IS NULL
                """,
                (now, self.run_id, set_id),
            )

            conn.commit()
            self.logger.info(f"Successfully deactivated set {set_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to deactivate set {set_id}: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_active_sets(self) -> List[Dict]:
        """
        Get all currently active sets for this run

        Returns:
            List of active set data with progress information
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT
                    ass.set_id,
                    ass.priority,
                    ass.reserved_bins,
                    ls.name,
                    ls.year,
                    ls.num_parts,
                    ls.set_img_url,
                    COUNT(DISTINCT si.id) as total_unique_parts,
                    SUM(si.quantity_needed) as total_parts_needed,
                    SUM(si.quantity_found) as total_parts_found
                FROM active_sorting_sets ass
                JOIN lego_sets ls ON ass.set_id = ls.set_id
                LEFT JOIN set_inventories si ON ls.set_id = si.set_id
                WHERE ass.run_id = ? AND ass.disabled_at IS NULL
                GROUP BY ass.set_id
                ORDER BY ass.priority DESC
                """,
                (self.run_id,),
            )

            results = []
            for row in cursor.fetchall():
                results.append(
                    {
                        "set_id": row[0],
                        "priority": row[1],
                        "reserved_bins": json.loads(row[2]) if row[2] else [],
                        "name": row[3],
                        "year": row[4],
                        "num_parts": row[5],
                        "set_img_url": row[6],
                        "total_unique_parts": row[7] or 0,
                        "total_parts_needed": row[8] or 0,
                        "total_parts_found": row[9] or 0,
                        "completion_percentage": (
                            (row[9] / row[8] * 100) if row[8] and row[8] > 0 else 0
                        ),
                    }
                )

            return results

        except Exception as e:
            self.logger.error(f"Failed to get active sets: {e}")
            return []
        finally:
            conn.close()

    def check_piece_in_sets(self, item_id: str, color_id: Optional[str] = None) -> List[str]:
        """
        Check if a piece belongs to any active sets

        Args:
            item_id: The BrickLink part ID
            color_id: Optional color ID

        Returns:
            List of set IDs that need this piece, ordered by priority
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            if color_id:
                cursor.execute(
                    """
                    SELECT DISTINCT si.set_id
                    FROM set_inventories si
                    JOIN active_sorting_sets ass ON si.set_id = ass.set_id
                    WHERE ass.run_id = ?
                        AND ass.disabled_at IS NULL
                        AND si.item_id = ?
                        AND si.color_id = ?
                        AND si.quantity_found < si.quantity_needed
                    ORDER BY ass.priority DESC
                    """,
                    (self.run_id, item_id, color_id),
                )
            else:
                cursor.execute(
                    """
                    SELECT DISTINCT si.set_id
                    FROM set_inventories si
                    JOIN active_sorting_sets ass ON si.set_id = ass.set_id
                    WHERE ass.run_id = ?
                        AND ass.disabled_at IS NULL
                        AND si.item_id = ?
                        AND si.quantity_found < si.quantity_needed
                    ORDER BY ass.priority DESC
                    """,
                    (self.run_id, item_id),
                )

            return [row[0] for row in cursor.fetchall()]

        except Exception as e:
            self.logger.error(f"Failed to check piece in sets: {e}")
            return []
        finally:
            conn.close()

    def increment_piece_found(self, set_id: str, item_id: str, color_id: Optional[str] = None) -> bool:
        """
        Increment the found count for a piece in a set

        Args:
            set_id: The set ID
            item_id: The BrickLink part ID
            color_id: Optional color ID

        Returns:
            True if successful, False otherwise
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        now = int(time.time() * 1000)

        try:
            if color_id:
                cursor.execute(
                    """
                    UPDATE set_inventories
                    SET quantity_found = quantity_found + 1, updated_at = ?
                    WHERE set_id = ? AND item_id = ? AND color_id = ?
                    """,
                    (now, set_id, item_id, color_id),
                )
            else:
                cursor.execute(
                    """
                    UPDATE set_inventories
                    SET quantity_found = quantity_found + 1, updated_at = ?
                    WHERE set_id = ? AND item_id = ?
                    """,
                    (now, set_id, item_id),
                )

            conn.commit()
            return True

        except Exception as e:
            self.logger.error(f"Failed to increment piece found: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_set_progress(self, set_id: str) -> Optional[Dict]:
        """
        Get detailed progress information for a set

        Args:
            set_id: The set ID

        Returns:
            Dict with progress details
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT
                    ls.set_id,
                    ls.name,
                    ls.year,
                    ls.num_parts,
                    COUNT(DISTINCT si.id) as total_unique_parts,
                    SUM(si.quantity_needed) as total_parts_needed,
                    SUM(si.quantity_found) as total_parts_found,
                    SUM(CASE WHEN si.quantity_found >= si.quantity_needed THEN 1 ELSE 0 END) as complete_part_types
                FROM lego_sets ls
                LEFT JOIN set_inventories si ON ls.set_id = si.set_id
                WHERE ls.set_id = ?
                GROUP BY ls.set_id
                """,
                (set_id,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            total_parts_needed = row[5] or 0
            total_parts_found = row[6] or 0

            return {
                "set_id": row[0],
                "name": row[1],
                "year": row[2],
                "num_parts": row[3],
                "total_unique_parts": row[4] or 0,
                "total_parts_needed": total_parts_needed,
                "total_parts_found": total_parts_found,
                "complete_part_types": row[7] or 0,
                "completion_percentage": (
                    (total_parts_found / total_parts_needed * 100) if total_parts_needed > 0 else 0
                ),
            }

        except Exception as e:
            self.logger.error(f"Failed to get set progress: {e}")
            return None
        finally:
            conn.close()
