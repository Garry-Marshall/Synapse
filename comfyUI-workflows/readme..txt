The sample workflow uses Flux Dev.
To get provided workflow to work in ComfyUI, download these models:

From: https://huggingface.co/camenduru/FLUX.1-dev/tree/main

Download 'flux1-dev-fp8.safetensor' and place it in \ComfyUI\models\unet\
Download 'FLUX.1-Turbo-Alpha.safetensors' and place it in \ComfyUI\models\loras\
Download 'ae.safetensors' and place it in \ComfyUI\models\vae\
Download 't5xxl_fp8_e4m3fn.safetensors' and place it in \ComfyUI\models\clip\


From: https://huggingface.co/datasets/wuming156/SD3.5AA/tree/main

Download 'stableDiffusion3SD3_textEncoderClipL.safetensor' and place it in \ComfyUI\models\clip\



To get your own workflows to work, use 'Export (API)' in ComfyUI and place the file in the comfyUI-workflows directory.
Edit the file, and look up the number associated with the input prompt.
Change COMFYUI_PROMT_NODES in .env to the corresponding number.
Look for the 'seed' node, and write it's associated number in COMFYUI_RAND_SEED_NODES
Now change COMFYUI_WORKFLOW to match the file name of your workflow.
Restart the bot.
