import logging
import os
import pathlib

logger = logging.getLogger(__name__)

try:
    from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
except ImportError:
    # Running outside a ComfyUI package context (e.g. during tests); skip re-exports.
    NODE_CLASS_MAPPINGS = {}
    NODE_DISPLAY_NAME_MAPPINGS = {}

WEB_DIRECTORY = "./web/js"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]

try:
    import folder_paths
    from server import PromptServer
    from aiohttp import web

    # Register the power-prompt partials directory so get_filename_list works
    # and ComfyUI's COMBO widget can list .yaml/.yml files from it.
    _partials_dir = os.path.join(folder_paths.get_input_directory(), "power-prompt")
    os.makedirs(_partials_dir, exist_ok=True)
    folder_paths.folder_names_and_paths["power_prompt_partials"] = (
        [_partials_dir],
        {".yaml", ".yml"},
    )

    @PromptServer.instance.routes.post("/power_prompt/upload_partial")
    async def _pp_upload_partial(request):
        reader = await request.multipart()
        field = await reader.next()
        if field is None:
            return web.json_response({"filename": None, "error": "No file received"})
        filename = pathlib.Path(field.filename or "").name  # strip path components
        if not filename or not filename.lower().endswith((".yaml", ".yml")):
            return web.json_response({"filename": None, "error": "Only .yaml and .yml files are supported"})
        save_path = pathlib.Path(_partials_dir) / filename
        if save_path.exists():
            return web.json_response({"filename": None, "error": f"File already exists: {filename}"})
        try:
            with open(save_path, "wb") as f:
                while chunk := await field.read_chunk():
                    f.write(chunk)
            return web.json_response({"filename": filename, "error": None})
        except OSError as e:
            return web.json_response({"filename": None, "error": str(e)})

    from .nodes.ui_definition import UIDefinitionRequest, build_ui_definition

    @PromptServer.instance.routes.post("/power_prompt/ui_definition")
    async def _pp_ui_definition(request):
        try:
            body = await request.json()
            req = UIDefinitionRequest.model_validate(body)
        except Exception as e:
            return web.json_response({"controls": [], "error": f"Invalid request: {e}"}, status=400)
        result = build_ui_definition(req.yaml, req.includes)
        return web.json_response(result.model_dump())

except Exception as e:
    logger.warning("Power Prompt: failed to register routes/folder: %s", e)
