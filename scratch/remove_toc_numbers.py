import re

file_path = r'c:\coding\my work\final year\ForgeGuard\project_report.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern to match the dots and page number spans, including potential newlines/whitespace
# <span class="toc-dots"></span><span class="toc-page">...</span>
pattern = re.compile(r'<span\s+class="toc-dots"></span>\s*<span[^>]*class="toc-page"[^>]*>.*?</span>', re.DOTALL)

new_content = pattern.sub('', content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Successfully removed page numbers and dots from Table of Contents.")
