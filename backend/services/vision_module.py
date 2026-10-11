import os
from PIL import Image
from dotenv import load_dotenv
from huggingface_hub import login

load_dotenv()

hf_token = os.getenv("HUGGINGFACEHUB_API_TOKEN")


try:
    import torch
    from transformers import Blip2Processor, Blip2ForConditionalGeneration

    processor = Blip2Processor.from_pretrained("Salesforce/blip2-opt-2.7b")
    model = Blip2ForConditionalGeneration.from_pretrained("Salesforce/blip2-opt-2.7b", load_in_8bit=True, device_map="auto")

    MODEL_LOADED = True
except Exception as e:
    print(f"Advertencia: No se pudo cargar el modelo local de visión BLIP-2: {e}")
    MODEL_LOADED = False


def caption_image(image_path: str) -> dict:
    if not MODEL_LOADED:
        return {"error": "El modelo BLIP-2 no está cargado correctamente."}

    try:
        image = Image.open(image_path).convert("RGB")
        inputs = processor(images=image, return_tensors="pt")

        # Genera una descripción.
        out_ids = model.generate(**inputs, max_new_tokens=50)
        caption = processor.decode(out_ids[0], skip_special_tokens=True)

        return {"caption": caption}
    except Exception as e:
        print(f"Error generando caption: {e}")
        return {"error": str(e)}
