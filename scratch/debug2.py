import re

file_path = r'c:\coding\my work\final year\ForgeGuard\project_report.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

matches = list(re.finditer(r'page-number', content))
if matches:
    print(f"Found {len(matches)} occurrences of 'page-number'")
    for i, m in enumerate(matches[:5]):
        start = max(0, m.start() - 100)
        end = min(len(content), m.end() + 200)
        print(f"\n--- Match {i+1} ---")
        print(repr(content[start:end]))
else:
    print("No occurrences of 'page-number' found anywhere.")
