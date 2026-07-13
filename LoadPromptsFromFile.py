"""
Hatolic - для ленивых жопок. 2026
ComfyUI Custom Node: Text File Prompt + Conditioning
Читает промпты из текстового файла
"""

import torch
import random
import os
import re
import folder_paths


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
        self.last_file = ""
        self.last_prompt_number = 0
        self.last_selection_mode = ""
        self.last_seed = 0
        self.last_shuffle = False
    
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
        
        params_changed = (
            self.last_file != file_name or
            self.last_prompt_number != prompt_num or
            self.last_selection_mode != selection_mode or
            self.last_seed != seed or
            self.last_shuffle != shuffle
        )
        
        if params_changed:
            self.sequential_counter = 0
            self.last_file = file_name
            self.last_prompt_number = prompt_num
            self.last_selection_mode = selection_mode
            self.last_seed = seed
            self.last_shuffle = shuffle
            print(f"[Hatolic] Params changed, reset counter to 0. Starting from #{prompt_num}")
        
        if selection_mode == "sequential":
            current_num = prompt_num + self.sequential_counter
            self.sequential_counter += 1
            
            try:
                idx = prompt_numbers.index(current_num)
                print(f"[Hatolic] Sequential: #{current_num}")
                return prompt_texts[idx]
            except ValueError:
                for num in sorted(prompt_numbers):
                    if num >= current_num:
                        idx = prompt_numbers.index(num)
                        print(f"[Hatolic] Sequential: #{num} (closest to #{current_num})")
                        return prompt_texts[idx]
                print(f"[Hatolic] Sequential: #{prompt_numbers[0]} (fallback)")
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
            try:
                idx = prompt_numbers.index(prompt_num)
                print(f"[Hatolic] By number: #{prompt_num}")
                return prompt_texts[idx]
            except ValueError:
                print(f"[Hatolic] #{prompt_num} not found, using first")
                return prompt_texts[0]
    
    def go(self, prompts_file, selection_mode, prompt_number, shuffle_each_time, seed, clip=None):
        if clip is None:
            raise ValueError("[Hatolic] ❌ No CLIP input.")
        
        generated_prompt = self.get_prompt_from_file(
            prompts_file, selection_mode, prompt_number, shuffle_each_time, seed
        )
        
        print(f"[Hatolic] Prompt length: {len(generated_prompt)} chars")
        
        tokens = clip.tokenize(generated_prompt)
        cond, pooled = clip.encode_from_tokens(tokens, return_pooled=True)
        conditioning = [[cond, {"pooled_output": pooled}]]
        
        return (conditioning, generated_prompt)


# ============================================================
# РЕГИСТРАЦИЯ
# ============================================================

NODE_CLASS_MAPPINGS = {
    "TextFile Prompt Conditioning": TextFile_Prompt_Conditioning,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TextFile Prompt Conditioning": "📄 Text File → Prompt → Conditioning",
}