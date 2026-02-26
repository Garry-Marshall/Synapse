import websockets
import uuid
import random
import urllib.request
import urllib.parse
import json
from io import BytesIO
import requests
from PIL import Image
from pathlib import Path
import logging

# Read the configuration
from config.settings import COMFYUI_URL, COMFYUI_WORKFLOW, COMFYUI_PROMPT_NODES, COMFYUI_RAND_SEED_NODES

logger = logging.getLogger(__name__)


def queue_prompt(prompt, client_id):
    """Queue a prompt to ComfyUI with timeout protection."""
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request("http://{}/prompt".format(COMFYUI_URL), data=data)
    # Add timeout to prevent hanging requests
    return json.loads(urllib.request.urlopen(req, timeout=30).read())

def get_image(filename, subfolder, folder_type):
    """Retrieve image from ComfyUI with timeout protection."""
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen("http://{}/view?{}".format(COMFYUI_URL, url_values), timeout=30) as response:
        return response.read()

def get_history(prompt_id):
    """Get generation history with timeout protection."""
    with urllib.request.urlopen("http://{}/history/{}".format(COMFYUI_URL, prompt_id), timeout=30) as response:
        return json.loads(response.read())
    
def upload_image(filepath, subfolder=None, folder_type=None, overwrite=False):
    """Upload image to ComfyUI with timeout protection."""
    url = f"http://{COMFYUI_URL}/upload/image"
    files = {'image': open(filepath, 'rb')}
    data = {
        'overwrite': str(overwrite).lower()
    }
    if subfolder:
        data['subfolder'] = subfolder
    if folder_type:
        data['type'] = folder_type
    response = requests.post(url, files=files, data=data, timeout=30)
    return response.json()


class ImageGenerator:
    def __init__(self):
        self.client_id = str(uuid.uuid4())
        self.uri = f"ws://{COMFYUI_URL}/ws?clientId={self.client_id}"
        self.ws = None

    async def connect(self):
        self.ws = await websockets.connect(self.uri)

    async def get_images(self, prompt):
        if not self.ws:
            await self.connect()

        prompt_id = queue_prompt(prompt, self.client_id)['prompt_id']
        currently_Executing_Prompt = None
        output_images = []
        async for out in self.ws:
            try:
                # Validate JSON before processing
                message = json.loads(out)

                # Validate message structure
                if not isinstance(message, dict):
                    logger.warning(f"Invalid message format: expected dict, got {type(message)}")
                    continue

                if 'type' not in message:
                    logger.warning("Message missing 'type' field")
                    continue

                if message['type'] == 'execution_start':
                    if 'data' not in message or 'prompt_id' not in message.get('data', {}):
                        logger.warning("Invalid execution_start message structure")
                        continue
                    currently_Executing_Prompt = message['data']['prompt_id']

                if message['type'] == 'executing' and prompt_id == currently_Executing_Prompt:
                    if 'data' not in message:
                        logger.warning("Invalid executing message structure")
                        continue
                    data = message['data']
                    if 'node' not in data or 'prompt_id' not in data:
                        logger.warning("Invalid data structure in executing message")
                        continue
                    if data['node'] is None and data['prompt_id'] == prompt_id:
                        break
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse WebSocket message: {e}")
                continue
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}")
                continue
                
        history = get_history(prompt_id)[prompt_id]

        for node_id in history['outputs']:
            node_output = history['outputs'][node_id]
            if 'images' in node_output:
                for image in node_output['images']:
                    image_data = get_image(image['filename'], image['subfolder'], image['type'])
                    pil_image = Image.open(BytesIO(image_data))
                    output_images.append(pil_image)

        return output_images

    async def close(self):
        if self.ws:
            await self.ws.close()

def _validate_workflow_filename(filename: str) -> Path:
    """
    Validate workflow filename to prevent path traversal attacks.

    Args:
        filename: The workflow filename from configuration

    Returns:
        Path: Validated absolute path to the workflow file

    Raises:
        ValueError: If the filename contains path traversal attempts
    """
    # Remove any path separators or parent directory references
    if not filename:
        raise ValueError("Workflow filename cannot be empty")

    # Check for path traversal attempts
    if '/' in filename or '\\' in filename or '..' in filename:
        logger.error(f"Path traversal attempt detected in workflow filename: {filename}")
        raise ValueError("Invalid workflow filename: path separators not allowed")

    # Only allow alphanumeric, dash, underscore, and dot in filename
    allowed_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.')
    if not all(c in allowed_chars for c in filename):
        logger.error(f"Invalid characters in workflow filename: {filename}")
        raise ValueError("Invalid workflow filename: only alphanumeric, dash, underscore, and dot allowed")

    # Construct safe path
    workflow_dir = Path(__file__).parent.parent / 'comfyUI-workflows'
    workflow_path = workflow_dir / filename

    # Resolve to absolute path and verify it's within the workflows directory
    try:
        workflow_path = workflow_path.resolve()
        workflow_dir = workflow_dir.resolve()

        # Ensure the resolved path is actually inside the workflows directory
        if not str(workflow_path).startswith(str(workflow_dir)):
            logger.error(f"Path traversal attempt: {workflow_path} is outside {workflow_dir}")
            raise ValueError("Invalid workflow path: must be within workflows directory")

        # Check file exists
        if not workflow_path.exists():
            logger.error(f"Workflow file not found: {workflow_path}")
            raise ValueError(f"Workflow file not found: {filename}")

        if not workflow_path.is_file():
            logger.error(f"Workflow path is not a file: {workflow_path}")
            raise ValueError(f"Workflow path is not a file: {filename}")

    except (OSError, RuntimeError) as e:
        logger.error(f"Error resolving workflow path: {e}")
        raise ValueError(f"Error accessing workflow file: {filename}")

    return workflow_path


def _validate_workflow_nodes(workflow: dict, prompt_nodes: list, seed_nodes: list) -> None:
    """
    Validate that workflow nodes exist and have expected structure.

    Args:
        workflow: The workflow dictionary
        prompt_nodes: List of prompt node IDs from configuration
        seed_nodes: List of seed node IDs from configuration

    Raises:
        ValueError: If validation fails
    """
    if not isinstance(workflow, dict):
        raise ValueError("Workflow must be a dictionary")

    # Validate prompt nodes
    for node_id in prompt_nodes:
        if not node_id:  # Skip empty strings
            continue

        if node_id not in workflow:
            logger.error(f"Prompt node '{node_id}' not found in workflow")
            raise ValueError(f"Invalid workflow: prompt node '{node_id}' not found")

        node = workflow[node_id]
        if not isinstance(node, dict):
            raise ValueError(f"Node '{node_id}' must be a dictionary")

        if "inputs" not in node:
            raise ValueError(f"Node '{node_id}' missing 'inputs' field")

        if not isinstance(node["inputs"], dict):
            raise ValueError(f"Node '{node_id}' inputs must be a dictionary")

        if "text" not in node["inputs"]:
            raise ValueError(f"Node '{node_id}' missing 'text' input field")

    # Validate seed nodes
    for node_id in seed_nodes:
        if not node_id:  # Skip empty strings
            continue

        if node_id not in workflow:
            logger.error(f"Seed node '{node_id}' not found in workflow")
            raise ValueError(f"Invalid workflow: seed node '{node_id}' not found")

        node = workflow[node_id]
        if not isinstance(node, dict):
            raise ValueError(f"Node '{node_id}' must be a dictionary")

        if "inputs" not in node:
            raise ValueError(f"Node '{node_id}' missing 'inputs' field")

        if not isinstance(node["inputs"], dict):
            raise ValueError(f"Node '{node_id}' inputs must be a dictionary")

        if "seed" not in node["inputs"]:
            raise ValueError(f"Node '{node_id}' missing 'seed' input field")


async def generate_flux_image(prompt: str, interaction, channel_id):
    """
    Generate an image using ComfyUI with security validations.

    Args:
        prompt: The text prompt for image generation
        interaction: Discord interaction object
        channel_id: Discord channel ID

    Returns:
        List of generated PIL images

    Raises:
        ValueError: If configuration or workflow validation fails
    """
    # Validate and load workflow with path traversal protection
    try:
        workflow_path = _validate_workflow_filename(COMFYUI_WORKFLOW)
        with open(workflow_path, 'r', encoding='utf-8') as file:
            workflow = json.load(file)
    except (ValueError, OSError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load workflow: {e}")
        raise ValueError(f"Failed to load workflow configuration: {e}")

    # Validate workflow structure
    try:
        _validate_workflow_nodes(workflow, COMFYUI_PROMPT_NODES, COMFYUI_RAND_SEED_NODES)
    except ValueError as e:
        logger.error(f"Workflow validation failed: {e}")
        raise ValueError(f"Invalid workflow configuration: {e}")

    generator = ImageGenerator()
    await generator.connect()

    # Modify the prompt dictionary (now validated)
    if prompt is not None and COMFYUI_PROMPT_NODES and COMFYUI_PROMPT_NODES[0] != '':
        for node in COMFYUI_PROMPT_NODES:
            if node:  # Skip empty strings
                workflow[node]["inputs"]["text"] = prompt

    if COMFYUI_RAND_SEED_NODES and COMFYUI_RAND_SEED_NODES[0] != '':
        for node in COMFYUI_RAND_SEED_NODES:
            if node:  # Skip empty strings
                workflow[node]["inputs"]["seed"] = random.randint(0, 999999999999999)

    images = await generator.get_images(workflow)
    await generator.close()

    return images
