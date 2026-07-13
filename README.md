# ComfyUI Text File Prompt Node

Простой нод для ComfyUI. Читает промпты из txt файла и превращает в CONDITIONING.

## Установка

cd ComfyUI/custom_nodes/
git clone https://github.com/yourusername/comfyui-textfile-prompt.git

Или просто скопируй LoadPromptsFromFile.py в ComfyUI/custom_nodes/

## Быстрый старт

1. Создай prompts.txt в ComfyUI/input/
2. Добавь нод в воркфлоу
3. Подключи CLIP
4. На выходе CONDITIONING + текст промпта

## Формат файла prompts.txt

1. Первый промпт
2. Второй промпт
3. Третий промпт

Строки с # игнорируются.

## Параметры

prompts_file      - файл с промптами
selection_mode    - sequential / random / by_number
prompt_number     - номер для старта или выборки
shuffle_each_time - перемешивать (для random)
seed              - для воспроизводимости

## Режимы

sequential - по порядку: 10, 11, 12...
random     - случайный
by_number  - конкретный номер

Счетчик сбрасывается при изменении любого параметра.

## Пример

CLIP Loader → TextFile Prompt → KSampler
                    ↓
              Prompt Text

## Лицензия

MIT

## Автор

@hatolic
