def process_markdown_for_pyside(text: str) -> str:
    if not text:
        return ""
        
    lines = text.split('\n')
    processed = []
    in_code_block = False
    
    for line in lines:
        stripped = line.rstrip()
        if stripped.startswith('```'):
            in_code_block = not in_code_block
            processed.append(line)
        elif in_code_block:
            processed.append(line)
        else:
            if stripped:
                processed.append(stripped + "  ")
            else:
                processed.append("")
                
    return '\n'.join(processed)
