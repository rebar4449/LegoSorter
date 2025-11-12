import asyncio
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from .client import API
from robot.our_types import SystemLifecycleStage
from robot.our_types.irl_runtime_params import IRLSystemRuntimeParams
from robot.our_types.bricklink import BricklinkPartData
from robot.our_types.bin_state import BinState
from robot.piece.bricklink.api import getPartInfo, getCategoryInfo, getCategories
from robot.piece.bricklink.auth import mkAuth
from robot.piece.bricklink.types import BricklinkCategoryData
from typing import List
from robot.websocket_manager import WebSocketManager
from robot.global_config import GlobalConfig
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_client: Optional[API] = None
websocket_manager: Optional[WebSocketManager] = None


def init_api(controller, gc: Optional[GlobalConfig] = None) -> WebSocketManager:
    global api_client, websocket_manager

    if gc is not None and websocket_manager is None:
        websocket_manager = WebSocketManager(gc)

    if controller is not None:
        api_client = API(controller)

    if websocket_manager is None:
        raise RuntimeError(
            "WebSocketManager not initialized - call init_api with gc first"
        )

    return websocket_manager


@app.put("/pause")
async def pause_system():
    if not api_client:
        raise HTTPException(status_code=503, detail="API not initialized")
    api_client.pause()
    return {"success": True}


@app.put("/resume")
async def resume_system():
    if not api_client:
        raise HTTPException(status_code=503, detail="API not initialized")
    api_client.resume()
    return {"success": True}


@app.put("/run")
async def run_system():
    if not api_client:
        raise HTTPException(status_code=503, detail="API not initialized")
    api_client.run()
    return {"success": True}


@app.get("/irl-runtime-params")
async def get_irl_runtime_params() -> IRLSystemRuntimeParams:
    if not api_client:
        raise HTTPException(status_code=503, detail="API not initialized")
    return api_client.getIRLRuntimeParams()


@app.put("/irl-runtime-params")
async def update_irl_runtime_params(params: IRLSystemRuntimeParams):
    if not api_client:
        raise HTTPException(status_code=503, detail="API not initialized")
    api_client.updateIRLRuntimeParams(params)
    return {"success": True}


@app.get("/bin-state")
async def get_bin_state() -> BinState:
    if not api_client:
        raise HTTPException(status_code=503, detail="API not initialized")
    return api_client.getBinState()


@app.put("/bin-state")
async def update_bin_state(request: dict):
    if not api_client:
        raise HTTPException(status_code=503, detail="API not initialized")

    coordinates = {
        "distribution_module_idx": request["distribution_module_idx"],
        "bin_idx": request["bin_idx"],
    }
    category_id = request.get("category_id")

    api_client.updateBinCategory(coordinates, category_id)
    return {"success": True}


@app.get("/bricklink/part/{part_id}/")
async def get_bricklink_part_info(part_id: str) -> BricklinkPartData:
    try:
        auth = mkAuth()
        part_data = getPartInfo(part_id, auth)

        if not part_data:
            raise HTTPException(status_code=404, detail=f"Part '{part_id}' not found")

        return part_data
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Authentication error: {str(e)}")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch part info: {str(e)}"
        )


@app.get("/bricklink/category/{category_id}")
async def get_bricklink_category_info(category_id: int) -> BricklinkCategoryData:
    try:
        auth = mkAuth()
        category_data = getCategoryInfo(category_id, auth)

        if not category_data:
            raise HTTPException(
                status_code=404, detail=f"Category '{category_id}' not found"
            )

        return category_data
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Authentication error: {str(e)}")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch category info: {str(e)}"
        )


@app.get("/bricklink/categories")
async def get_bricklink_categories() -> List[BricklinkCategoryData]:
    try:
        auth = mkAuth()
        categories = getCategories(auth)
        return categories
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Authentication error: {str(e)}")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch categories: {str(e)}"
        )


# Set management endpoints


class SetSearchRequest(BaseModel):
    query: str


class SetActivateRequest(BaseModel):
    set_num: str
    priority: int = 0


class SetDeactivateRequest(BaseModel):
    set_id: str


@app.get("/sets/search")
async def search_sets(query: str):
    """Search for LEGO sets on Rebrickable"""
    try:
        from robot.external.rebrickable import searchSets

        results = searchSets(query)
        if not results:
            return {"results": []}
        return results
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to search sets: {str(e)}"
        )


@app.post("/sets/add")
async def add_set(set_num: str):
    """Add a set to the database and sync its inventory"""
    if not api_client:
        raise HTTPException(status_code=503, detail="API not initialized")

    try:
        set_id = api_client.addSet(set_num)
        if not set_id:
            raise HTTPException(
                status_code=404, detail=f"Failed to add set {set_num}"
            )
        return {"set_id": set_id, "success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add set: {str(e)}")


@app.post("/sets/activate")
async def activate_set(request: SetActivateRequest):
    """Activate a set for sorting"""
    if not api_client:
        raise HTTPException(status_code=503, detail="API not initialized")

    try:
        success = api_client.activateSet(request.set_num, request.priority)
        if not success:
            raise HTTPException(
                status_code=400, detail=f"Failed to activate set {request.set_num}"
            )
        return {"success": True}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to activate set: {str(e)}"
        )


@app.delete("/sets/{set_id}/deactivate")
async def deactivate_set(set_id: str):
    """Deactivate a set from sorting"""
    if not api_client:
        raise HTTPException(status_code=503, detail="API not initialized")

    try:
        success = api_client.deactivateSet(set_id)
        if not success:
            raise HTTPException(
                status_code=400, detail=f"Failed to deactivate set {set_id}"
            )
        return {"success": True}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to deactivate set: {str(e)}"
        )


@app.get("/sets/active")
async def get_active_sets():
    """Get all currently active sets"""
    if not api_client:
        raise HTTPException(status_code=503, detail="API not initialized")

    try:
        active_sets = api_client.getActiveSets()
        return {"sets": active_sets}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get active sets: {str(e)}"
        )


@app.get("/sets/{set_id}/progress")
async def get_set_progress(set_id: str):
    """Get progress information for a specific set"""
    if not api_client:
        raise HTTPException(status_code=503, detail="API not initialized")

    try:
        progress = api_client.getSetProgress(set_id)
        if not progress:
            raise HTTPException(status_code=404, detail=f"Set {set_id} not found")
        return progress
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get set progress: {str(e)}"
        )


@app.get("/sets/{set_id}/inventory")
async def get_set_inventory(set_id: str):
    """Get full inventory for a set"""
    if not api_client:
        raise HTTPException(status_code=503, detail="API not initialized")

    try:
        inventory = api_client.getSetInventory(set_id)
        return {"inventory": inventory}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get set inventory: {str(e)}"
        )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    if websocket_manager is None:
        await websocket.close()
        return

    websocket_manager.set_event_loop(asyncio.get_event_loop())

    await websocket_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)
