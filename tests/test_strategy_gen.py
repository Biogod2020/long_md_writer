import os
import sys
from pathlib import Path

os.environ["GEMINI_AUTH_PASSWORD"] = "123456"

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from src.agents.image_sourcing_agent import ImageSourcingAgent

def test_strategy():
    agent = ImageSourcingAgent(debug=True)
    
    test_cases = [
        {
            "desc": "广州市第二中学应元校区历史悠久的校门图，展现应元路校区的学术氛围和历史感",
            "context": "广州二中的历史可以追溯到清代创办的“学海堂”书院。1930年...校址选在越秀山脚下的应元路..."
        },
        {
            "desc": "广州二中校园文化节中学生展示社团成果、进行才艺表演的热闹画面",
            "context": "每年的体艺节、文化周、心理周等，都是学生展示自我、锻炼能力的绝佳舞台。二中的社团文化极度发达..."
        },
        {
            "desc": "ECG trace showing significant QRS widening from Class I drugs",
            "context": "Class I agents primarily affect the QRS complex by slowing the rate of depolarization. Class Ic drugs, like flecainide, significantly prolong the QRS duration."
        }
    ]
    
    print("Testing Strategy Generation (Keywords Only)...\n")
    for i, tc in enumerate(test_cases):
        print(f"--- Case {i+1} ---")
        print(f"Input Description: {tc['desc']}")
        
        # Manually call client to see raw response if needed
        strategy = agent._generate_search_strategy(tc['desc'], tc['context'])
        
        # We can inspect the client's last response if we add a way, 
        # but for now let's just print if it fell back
        if strategy.get('thinking') is None:
            print("[!] Hitting Fallback - Check API/Proxy")
            
        print(f"Generated Queries: {strategy.get('queries')}")
        print(f"Thinking: {strategy.get('thinking')}")
        print(f"Guidance: {strategy.get('guidance')}\n")


if __name__ == "__main__":
    test_strategy()
