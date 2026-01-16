import websockets
import uuid
import random
import urllib.request
import urllib.parse
import json
from io import BytesIO
import requests
from PIL import Image


# Read the configuration
from config.settings import COMFYUI_URL, COMFYUI_WORKFLOW, COMFYUI_PROMPT_NODES, COMFYUI_RAND_SEED_NODES


def queue_prompt(prompt, client_id):
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')
    req =  urllib.request.Request("http://{}/prompt".format(COMFYUI_URL), data=data)
    return json.loads(urllib.request.urlopen(req).read())

def get_image(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen("http://{}/view?{}".format(COMFYUI_URL, url_values)) as response:
        return response.read()

def get_history(prompt_id):
    with urllib.request.urlopen("http://{}/history/{}".format(COMFYUI_URL, prompt_id)) as response:
        return json.loads(response.read())
    
def upload_image(filepath, subfolder=None, folder_type=None, overwrite=False):
    url = f"http://{COMFYUI_URL}/upload/image"
    files = {'image': open(filepath, 'rb')}
    data = {
        'overwrite': str(overwrite).lower()
    }
    if subfolder:
        data['subfolder'] = subfolder
    if folder_type:
        data['type'] = folder_type
    response = requests.post(url, files=files, data=data)
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
            message = json.loads(out)
            if message['type'] == 'execution_start':
                currently_Executing_Prompt = message['data']['prompt_id']

            if message['type'] == 'executing' and prompt_id == currently_Executing_Prompt:
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break
                
        history = get_history(prompt_id)[prompt_id]

        for node_id in history['outputs']:
            node_output = history['outputs'][node_id]
            if 'images' in node_output:
                for image in node_output['images']:
                    image_data = get_image(image['filename'], image['subfolder'], image['type'])
                    if 'final_output' in image['filename']:
                        pil_image = Image.open(BytesIO(image_data))
                        output_images.append(pil_image)

        return output_images

    async def close(self):
        if self.ws:
            await self.ws.close()

async def generate_flux_image(prompt: str,interaction,channel_id):
    with open(COMFYUI_WORKFLOW, 'r') as file:
        workflow = json.load(file)
      
    generator = ImageGenerator()
    await generator.connect()

    #prompt_nodes = config.get('LOCAL_TEXT2IMG', 'PROMPT_NODES').split(',')
    #neg_prompt_nodes = config.get('LOCAL_TEXT2IMG', 'NEG_PROMPT_NODES_SD3').split(',')
    #rand_seed_nodes = config.get('LOCAL_TEXT2IMG', 'RAND_SEED_NODES_FLUX').split(',') 

    # Modify the prompt dictionary
    if(prompt != None and COMFYUI_PROMPT_NODES[0] != ''):
      for node in COMFYUI_PROMPT_NODES:
          workflow[node]["inputs"]["text"] = prompt
    if(COMFYUI_RAND_SEED_NODES[0] != ''):
      for node in COMFYUI_RAND_SEED_NODES:
          workflow[node]["inputs"]["seed"] = random.randint(0,999999999999999)

    images = await generator.get_images(workflow)
    await generator.close()

    return images
