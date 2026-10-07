from PIL import Image
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
from peft import PeftModel
import torch
import os
from qwen_vl_utils import process_vision_info

# Load base model on CPU first
print("Loading base model...")
base_model = Qwen2VLForConditionalGeneration.from_pretrained(
    "./qwen2vl_model",
    torch_dtype=torch.float32,
    device_map="cpu",
    low_cpu_mem_usage=True,
)

# Load Qaari adapter
print("Loading Qaari adapter...")
model = PeftModel.from_pretrained(base_model, "oddadmix/Qaari-0.1-Urdu-OCR-VL-2B-Instruct")
model = model.merge_and_unload()

# Move to MPS after merging
print("Moving to MPS...")
model = model.to(torch.float16).to("mps")
print("Model ready!")

processor = AutoProcessor.from_pretrained("./qwen2vl_model")

# Run OCR
image_path = os.path.expanduser("~/Desktop/docs/FYP/rental agreements/2.jpeg")

prompt = "Below is the image of one page of a document. Just return the plain text representation of this document as if you were reading it naturally. Do not hallucinate."

messages = [
    {
        "role": "user",
        "content": [
            {"type": "image", "image": f"file://{os.path.abspath(image_path)}"},
            {"type": "text", "text": prompt},
        ],
    }
]

text = processor.apply_chat_template(
    messages, tokenize=False, add_generation_prompt=True
)

image_inputs, video_inputs = process_vision_info(messages)

inputs = processor(
    text=[text],
    images=image_inputs,
    videos=video_inputs,
    padding=True,
    return_tensors="pt",
).to("mps")

generated_ids = model.generate(**inputs, max_new_tokens=2000)

generated_ids_trimmed = [
    out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
]

output_text = processor.batch_decode(
    generated_ids_trimmed,
    skip_special_tokens=True,
    clean_up_tokenization_spaces=False
)[0]

print(output_text)