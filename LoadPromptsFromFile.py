"""
Hatolic - для ленивых жопок. 2026
ComfyUI Custom Nodes:
1. Text File Prompt + Conditioning - читает промпты из файла
2. Ollama Random Prompt + Conditioning - генерирует промпты через Ollama
"""

import torch
import random
import os
import re
import time
import requests
import folder_paths
from datetime import datetime


# ============================================================
# 1. TEXT FILE PROMPT + CONDITIONING
# ============================================================

class TextFile_Prompt_Conditioning:
    @classmethod
    def INPUT_TYPES(cls):
        input_dir = folder_paths.get_input_directory()
        txt_files = []
        if os.path.exists(input_dir):
            for f in os.listdir(input_dir):
                if f.endswith('.txt') and os.path.isfile(os.path.join(input_dir, f)):
                    txt_files.append(f)
        
        if not txt_files:
            txt_files = ["prompts.txt"]
        
        return {
            "required": {
                "prompts_file": (txt_files, {"default": txt_files[0] if txt_files else "prompts.txt"}),
                "selection_mode": (["sequential", "random", "by_number"], {"default": "sequential"}),
                "prompt_number": ("INT", {"default": 1, "min": 1, "max": 99999}),
                "shuffle_each_time": ("BOOLEAN", {"default": False}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
            },
            "optional": {
                "clip": ("CLIP",),
            }
        }
    
    RETURN_TYPES = ("CONDITIONING", "STRING")
    RETURN_NAMES = ("conditioning", "prompt_text")
    FUNCTION = "go"
    CATEGORY = "Hatolic"
    
    def __init__(self):
        self.sequential_counter = 0
        self.last_prompt_number = 0
        self.last_file = ""
        self.last_selection_mode = ""
    
    def parse_prompts_from_file(self, file_name):
        prompts = []
        input_dir = folder_paths.get_input_directory()
        file_path = os.path.join(input_dir, file_name)
        
        try:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            except UnicodeDecodeError:
                with open(file_path, 'r', encoding='cp1251') as f:
                    lines = f.readlines()
            
            filtered_lines = []
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#') or line.startswith('File:'):
                    continue
                filtered_lines.append(line)
            
            content = '\n'.join(filtered_lines)
            
            pattern1 = r'(\d+)\.\s*(?:Prompt:\s*)?(.*?)(?=\n\s*\d+\.|\Z)'
            matches = re.findall(pattern1, content, re.DOTALL)
            
            if matches:
                for num, text in matches:
                    text = text.strip()
                    if text:
                        prompts.append((int(num), text))
            else:
                pattern2 = r'(?:^|\n)(?:#+\s*)?(\d+)\.\s*([^\n]*)(.*?)(?=(?:\n(?:#+\s*)?\d+\.)|$)'
                matches = re.findall(pattern2, content, re.DOTALL)
                
                if matches:
                    for num, title, body in matches:
                        body = body.strip()
                        if body:
                            prompts.append((int(num), body))
                else:
                    current_prompt = None
                    current_num = None
                    
                    for line in filtered_lines:
                        match = re.match(r'^(\d+)[\.\)]\s*(?:Prompt:\s*)?(.*)$', line)
                        if match:
                            if current_prompt and current_num is not None:
                                prompts.append((current_num, current_prompt.strip()))
                            current_num = int(match.group(1))
                            current_prompt = match.group(2).strip()
                        else:
                            if current_prompt is not None:
                                current_prompt += " " + line
                    
                    if current_prompt and current_num is not None:
                        prompts.append((current_num, current_prompt.strip()))
            
            print(f"[Hatolic] Loaded {len(prompts)} prompts from {file_name}")
            
        except Exception as e:
            print(f"[Hatolic] Error: {e}")
        
        return prompts
    
    def get_prompt_from_file(self, file_name, selection_mode, prompt_num, shuffle, seed):
        raw_prompts = self.parse_prompts_from_file(file_name)
        
        if not raw_prompts:
            fallback = "A bathroom turned upside down. The bathtub is filled with rubber ducks wearing tiny sunglasses..."
            print("[Hatolic] No prompts, using fallback")
            return fallback
        
        raw_prompts.sort(key=lambda x: x[0])
        prompt_numbers = [p[0] for p in raw_prompts]
        prompt_texts = [p[1] for p in raw_prompts]
        
        # АВТОМАТИЧЕСКИЙ СБРОС
        if (self.last_file != file_name or 
            self.last_selection_mode != selection_mode or 
            self.last_prompt_number != prompt_num):
            self.sequential_counter = 0
            self.last_file = file_name
            self.last_selection_mode = selection_mode
            self.last_prompt_number = prompt_num
            print(f"[Hatolic] Auto reset: starting from #{prompt_num}")
        
        if selection_mode == "sequential":
            current_num = prompt_num + self.sequential_counter
            self.sequential_counter += 1
            
            print(f"[Hatolic] Sequential: #{current_num}")
            
            if current_num in prompt_numbers:
                idx = prompt_numbers.index(current_num)
                return prompt_texts[idx]
            else:
                next_nums = [n for n in prompt_numbers if n >= current_num]
                if next_nums:
                    next_num = min(next_nums)
                    idx = prompt_numbers.index(next_num)
                    print(f"[Hatolic] Sequential: #{next_num} (closest to {current_num})")
                    return prompt_texts[idx]
                else:
                    print(f"[Hatolic] Sequential: #{current_num} not found, reset to first")
                    self.sequential_counter = 0
                    return prompt_texts[0]
        
        if selection_mode == "random":
            rng = random.Random(seed) if seed != 0 else random.Random()
            indices = list(range(len(prompt_texts)))
            if shuffle:
                rng.shuffle(indices)
            chosen_index = rng.choice(indices) if not shuffle else indices[0]
            print(f"[Hatolic] Random: #{prompt_numbers[chosen_index]}")
            return prompt_texts[chosen_index]
        
        else:
            if prompt_num in prompt_numbers:
                idx = prompt_numbers.index(prompt_num)
                print(f"[Hatolic] By number: #{prompt_num}")
                return prompt_texts[idx]
            else:
                print(f"[Hatolic] #{prompt_num} not found, using first")
                return prompt_texts[0]
    
    def go(self, prompts_file, selection_mode, prompt_number, shuffle_each_time, seed, clip=None):
        if clip is None:
            raise ValueError("[Hatolic] No CLIP input.")
        
        generated_prompt = self.get_prompt_from_file(
            prompts_file, selection_mode, prompt_number, shuffle_each_time, seed
        )
        
        print(f"[Hatolic] Prompt length: {len(generated_prompt)} chars")
        
        tokens = clip.tokenize(generated_prompt)
        cond, pooled = clip.encode_from_tokens(tokens, return_pooled=True)
        conditioning = [[cond, {"pooled_output": pooled}]]
        
        return (conditioning, generated_prompt)


# ============================================================
# 2. OLLAMA RANDOM PROMPT + CONDITIONING
# ============================================================

class Ollama_RandomPrompt_Conditioning:
    @classmethod
    def INPUT_TYPES(cls):
        models_list = cls.get_ollama_models()
        return {
            "required": {
                "ollama_host": ("STRING", {"default": "http://127.0.0.1:11434"}),
                "ollama_model": (models_list, {"default": models_list[0] if models_list else "llama3.2:latest"}),
                "system_prompt": ("STRING", {"multiline": True, "default": "Generate a detailed image prompt, 200-500 words, as a single vivid scene. Natural language, no lists, no tags. Describe anything: a person, a place, an object, an interior, an exterior — completely random each time. Output only the prompt."}),
                "temperature": ("FLOAT", {"default": 0.95, "min": 0.0, "max": 2.0, "step": 0.05}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffff}),
                "max_retries": ("INT", {"default": 3, "min": 1, "max": 5}),
                "save_prompts": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "clip": ("CLIP",),
            }
        }
    
    RETURN_TYPES = ("CONDITIONING", "STRING")
    RETURN_NAMES = ("conditioning", "generated_prompt")
    FUNCTION = "go"
    CATEGORY = "Hatolic"
    
    def __init__(self):
        self.prompt_counter = 0
        self.session_file = None
        self.session_start_time = None
    
    @classmethod
    def get_ollama_models(cls):
        try:
            response = requests.get("http://127.0.0.1:11434/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                models = [model["name"] for model in data.get("models", [])]
                if models:
                    return models
        except:
            pass
        return ["llama3.2:latest"]
    
    def get_session_file(self):
        if self.session_file is None:
            self.session_start_time = datetime.now()
            date_str = self.session_start_time.strftime("%Y-%m-%d_%H-%M-%S")
            self.session_file = f"prompts_{date_str}.txt"
            self.prompt_counter = 0
            
            output_dir = folder_paths.get_output_directory()
            file_path = os.path.join(output_dir, self.session_file)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"# Ollama Prompts Session\n")
                f.write(f"# Started: {self.session_start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("#" + "=" * 70 + "\n\n")
            
            print(f"[Ollama] Session: {self.session_file}")
        
        return self.session_file
    
    def save_prompt_to_file(self, prompt):
        output_dir = folder_paths.get_output_directory()
        file_path = os.path.join(output_dir, self.session_file)
        self.prompt_counter += 1
        
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(f"{self.prompt_counter}. {prompt}\n\n")
        
        print(f"[Ollama] Saved #{self.prompt_counter} to {self.session_file}")
    
    def generate_prompt(self, host, model, system_prompt, temperature, seed, max_retries):
        url = f"{host}/api/chat"
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Generate a random image prompt now. Follow the instructions exactly. Output only the prompt. Nothing else. No greetings, no explanations."}
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": 800,
                "min_p": 0.1,
                "repeat_penalty": 1.1
            }
        }
        
        if seed > 0:
            payload["options"]["seed"] = seed
        
        for attempt in range(max_retries):
            try:
                print(f"[Ollama] Attempt {attempt + 1}")
                response = requests.post(url, json=payload, timeout=120)
                response.raise_for_status()
                result = response.json()
                generated = result.get("message", {}).get("content", "").strip()
                
                if generated and len(generated) > 100:
                    print(f"[Ollama] OK, {len(generated)} chars")
                    return generated
                else:
                    print(f"[Ollama] Too short ({len(generated)} chars), retry")
                    time.sleep(1)
            except Exception as e:
                print(f"[Ollama] Error: {e}")
                time.sleep(2)
        
        print("[Ollama] Fallback")
        return "A bathroom turned upside down. The bathtub is filled with rubber ducks wearing tiny sunglasses, all floating in bright pink bubblegum-scented foam. On the mirror, someone wrote 'You are awesome' in lipstick backwards. A potted cactus on the toilet tank wears a party hat. A single disco ball spins slowly above the sink, throwing sparkles across the ceiling tiles. Wide angle, vibrant neon pink and turquoise lighting, fun and chaotic, late night party aftermath style."
    
    def go(self, ollama_host, ollama_model, system_prompt, temperature, seed, max_retries, save_prompts=True, clip=None):
        generated_prompt = self.generate_prompt(ollama_host, ollama_model, system_prompt, temperature, seed, max_retries)
        
        if save_prompts:
            self.get_session_file()
            self.save_prompt_to_file(generated_prompt)
        
        print(f"[Ollama] Prompt length: {len(generated_prompt)} chars")
        
        if clip is None:
            raise ValueError("[Ollama] No CLIP input. Connect CLIP Loader.")
        
        tokens = clip.tokenize(generated_prompt)
        cond, pooled = clip.encode_from_tokens(tokens, return_pooled=True)
        conditioning = [[cond, {"pooled_output": pooled}]]
        
        return (conditioning, generated_prompt)


# ============================================================
# РЕГИСТРАЦИЯ
# ============================================================

NODE_CLASS_MAPPINGS = {
    "TextFile Prompt Conditioning": TextFile_Prompt_Conditioning,
    "Ollama Random Prompt Conditioning": Ollama_RandomPrompt_Conditioning,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TextFile Prompt Conditioning": "Text File → Prompt → Conditioning",
    "Ollama Random Prompt Conditioning": "Ollama → Random Prompt → Conditioning",
}