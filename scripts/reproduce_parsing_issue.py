import json

def extract_json_from_text(text: str):
    start_obj = text.find('{')
    start_arr = text.find('[')
    
    if start_obj == -1 and start_arr == -1:
        return None
    
    start = min(start_obj, start_arr) if (start_obj != -1 and start_arr != -1) else (start_obj if start_obj != -1 else start_arr)
    
    end_obj = text.rfind('}')
    end_arr = text.rfind(']')
    end = max(end_obj, end_arr)
    
    if end == -1 or end < start:
        return None
    
    return text[start:end+1]

md_content = """# Mermaid Stress Test

## Section 1: Clinical Flowcharts
:::visual {"id": "m-flow-triage", "action": "GENERATE_MERMAID", "description": "Emergency department triage flowchart. Start: Patient Arrival -> Triage Nurse Assessment -> {Urgent?} -> [YES] Resuscitation; [NO] Waiting Room. Use subgraphs for different priority levels."}
Triage is the process of determining the priority of patients' treatments.
:::

:::visual {"id": "m-flow-nested-braces", "action": "GENERATE_MERMAID", "description": "A flowchart testing nested braces handling. Node A{Decision} ->|Yes| B{Another Decision}; B ->|Option 1| C[Final 1]; B ->|Option 2| D[Final 2]. Ensure the parser doesn't break on the Mermaid braces."}
Testing the robustness of the JSON parser against Mermaid syntax.
:::
"""

# New search logic from fulfillment.py
search_pos = 0
content = md_content
directives_count = 0

while True:
    print(f"\nSearching from {search_pos}...")
    start_idx = content.find(':::visual', search_pos)
    if start_idx == -1:
        print("No more :::visual found.")
        break
    
    print(f"Found :::visual at {start_idx}")
    json_start = content.find('{', start_idx)
    if json_start == -1:
        print("No { found after :::visual.")
        search_pos = start_idx + 9
        continue
        
    print(f"Found {{ at {json_start}")
    end_search_pos = json_start
    closing_idx = -1
    while True:
        found = content.find(':::', end_search_pos)
        if found == -1:
            print("No more ::: found in block.")
            break
        print(f"Found ::: at {found}")
        if content.startswith(':::visual', found):
            print(f"  Is start of next block at {found}, skipping...")
            end_search_pos = found + 9
            continue
        if found == start_idx:
            print(f"  Is same as start_idx {found}, skipping...")
            end_search_pos = found + 3
            continue
        
        closing_idx = found
        print(f"  Identified as closing ::: at {found}")
        break
    
    if closing_idx == -1:
        print("Final: No closing ::: found.")
        search_pos = start_idx + 9
        continue
        
    raw_block = content[start_idx:closing_idx + 3]
    print(f"Block identified: length {len(raw_block)}")
    
    raw_json = extract_json_from_text(raw_block)
    if raw_json:
        print(f"Extracted JSON: {raw_json[:50]}...")
        directives_count += 1
    else:
        print("JSON extraction failed.")
    
    search_pos = start_idx + len(raw_block)

print(f"\nFinal count: {directives_count}")
