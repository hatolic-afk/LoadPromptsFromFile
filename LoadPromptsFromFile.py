"""
Hatolic - для ленивых жопок. 2026
ComfyUI Custom Node: Text File Prompt + Conditioning
"""

import torch
import random
import os
import re
import time
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
                "auto_reset": ("BOOLEAN", {"default": True, "label": "Auto Reset After Batch"}),
            },
            "optional": {
                "clip": ("CLIP",),
            }
        }
    
    RETURN_TYPES = ("CONDITIONING", "STRING")
    RETURN_NAMES = ("conditioning", "prompt_preview")
    FUNCTION = "go"
    CATEGORY = "Hatolic"
    
    def __init__(self):
        self.sequential_counter = 0
        self.sequential_start = 0
        self.sequential_file = ""
        self.last_preview = "Ожидание промпта..."
        self.batch_counter = 0  # Счетчик для отслеживания запусков
    
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
                        prompts.append((int(num), f"Prompt #{num}", text))
            else:
                pattern2 = r'(?:^|\n)(?:#+\s*)?(\d+)\.\s*([^\n]*)(.*?)(?=(?:\n(?:#+\s*)?\d+\.)|$)'
                matches = re.findall(pattern2, content, re.DOTALL)
                
                if matches:
                    for num, title, body in matches:
                        body = body.strip()
                        if body:
                            prompts.append((int(num), title.strip(), body))
                else:
                    current_prompt = None
                    current_num = None
                    
                    for line in filtered_lines:
                        match = re.match(r'^(\d+)[\.\)]\s*(?:Prompt:\s*)?(.*)$', line)
                        if match:
                            if current_prompt and current_num is not None:
                                prompts.append((current_num, f"Prompt #{current_num}", current_prompt.strip()))
                            current_num = int(match.group(1))
                            current_prompt = match.group(2).strip()
                        else:
                            if current_prompt is not None:
                                current_prompt += " " + line
                    
                    if current_prompt and current_num is not None:
                        prompts.append((current_num, f"Prompt #{current_num}", current_prompt.strip()))
            
            print(f"[Hatolic] Loaded {len(prompts)} prompts from input/{file_name}")
            
        except Exception as e:
            print(f"[Hatolic] Error reading file: {e}")
        
        return prompts
    
    def get_prompt_from_file(self, file_name, selection_mode, prompt_num, shuffle, seed, auto_reset):
        raw_prompts = self.parse_prompts_from_file(file_name)
        
        if not raw_prompts:
            fallback = "A bathroom turned upside down. The bathtub is filled with rubber ducks wearing tiny sunglasses..."
            return 0, "Fallback", fallback
        
        raw_prompts.sort(key=lambda x: x[0])
        
        prompt_numbers = [p[0] for p in raw_prompts]
        prompt_titles = [p[1] for p in raw_prompts]
        prompt_texts = [p[2] for p in raw_prompts]
        
        # РЕЖИМ ПОСЛЕДОВАТЕЛЬНЫЙ
        if selection_mode == "sequential":
            # Если сменился файл или стартовый номер - сбрасываем счетчик
            if (self.sequential_file != file_name or 
                self.sequential_start != prompt_num):
                self.sequential_counter = 0
                self.sequential_start = prompt_num
                self.sequential_file = file_name
                print(f"[Hatolic] Sequential reset: starting from #{prompt_num}")
            
            # Если включен автозапуск и это первый вызов в новой сессии
            # или мы начали новый батч - сбрасываем счетчик
            if auto_reset and self.batch_counter == 0:
                self.sequential_counter = 0
                print(f"[Hatolic] Auto reset: starting from #{prompt_num}")
            
            # Текущий номер = стартовый + счетчик
            current_num = prompt_num + self.sequential_counter
            self.sequential_counter += 1  # Увеличиваем для следующего вызова
            self.batch_counter += 1  # Увеличиваем счетчик вызовов
            
            # Ищем промпт с таким номером
            try:
                idx = prompt_numbers.index(current_num)
                chosen_prompt = prompt_texts[idx]
                chosen_num = prompt_numbers[idx]
                chosen_title = prompt_titles[idx]
                print(f"[Hatolic] Sequential: #{chosen_num} (step {self.sequential_counter-1})")
                return chosen_num, chosen_title, chosen_prompt
            except ValueError:
                # Если нет такого номера - ищем ближайший больший
                for num in sorted(prompt_numbers):
                    if num >= current_num:
                        idx = prompt_numbers.index(num)
                        chosen_prompt = prompt_texts[idx]
                        chosen_num = prompt_numbers[idx]
                        chosen_title = prompt_titles[idx]
                        print(f"[Hatolic] Sequential: #{chosen_num} (closest to #{current_num})")
                        return chosen_num, chosen_title, chosen_prompt
                
                # Если все номера меньше - берем последний
                print(f"[Hatolic] ⚠️ #{current_num} not found, using last")
                return prompt_numbers[-1], prompt_titles[-1], prompt_texts[-1]
        
        # РЕЖИМ СЛУЧАЙНЫЙ
        if selection_mode == "random":
            rng = random.Random(seed) if seed != 0 else random.Random()
            indices = list(range(len(prompt_texts)))
            if shuffle:
                rng.shuffle(indices)
            chosen_index = rng.choice(indices) if not shuffle else indices[0]
            return prompt_numbers[chosen_index], prompt_titles[chosen_index], prompt_texts[chosen_index]
        
        # РЕЖИМ ПО НОМЕРУ
        else:  # by_number
            try:
                idx = prompt_numbers.index(prompt_num)
                return prompt_numbers[idx], prompt_titles[idx], prompt_texts[idx]
            except ValueError:
                print(f"[Hatolic] ⚠️ #{prompt_num} not found, using first")
                return prompt_numbers[0], prompt_titles[0], prompt_texts[0]
    
    def go(self, prompts_file, selection_mode, prompt_number, shuffle_each_time, seed, auto_reset, clip=None):
        if clip is None:
            raise ValueError("[Hatolic] ❌ No CLIP input. Connect CLIP Loader.")
        
        # Сбрасываем счетчик батча при первом вызове
        # Для отслеживания нового запуска
        if self.batch_counter == 0:
            print(f"[Hatolic] 🚀 New batch session started")
        
        prompt_id, prompt_title, generated_prompt = self.get_prompt_from_file(
            prompts_file, selection_mode, prompt_number, shuffle_each_time, seed, auto_reset
        )
        
        # Создаем превью
        preview = f"========== PROMPT #{prompt_id} ==========\n"
        preview += f"Title: {prompt_title}\n"
        preview += "=" * 40 + "\n\n"
        preview += generated_prompt
        preview += "\n\n" + "=" * 40
        
        self.last_preview = preview
        
        print(f"[Hatolic] Prompt #{prompt_id}: {prompt_title}")
        print(f"[Hatolic] Prompt length: {len(generated_prompt)} chars")
        
        tokens = clip.tokenize(generated_prompt)
        cond, pooled = clip.encode_from_tokens(tokens, return_pooled=True)
        conditioning = [[cond, {"pooled_output": pooled}]]
        
        return (conditioning, preview)


# ============================================================
# ТЕКСТОВЫЙ ПРОСМОТРЩИК
# ============================================================

class TextPreviewNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {
                    "multiline": True,
                    "default": "Ожидание промпта...",
                    "dynamicPrompts": False,
                }),
            }
        }
    
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "display"
    CATEGORY = "Hatolic"
    OUTPUT_NODE = True
    
    def display(self, text):
        return (text,)
    
    @classmethod
    def IS_CHANGED(cls, text):
        return time.time()


# ============================================================
# РЕГИСТРАЦИЯ
# ============================================================

NODE_CLASS_MAPPINGS = {
    "TextFile Prompt Conditioning": TextFile_Prompt_Conditioning,
    "Text Preview": TextPreviewNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TextFile Prompt Conditioning": "📄 Text File → Prompt → Rendering",
    "Text Preview": "🔍 Text Preview",
}