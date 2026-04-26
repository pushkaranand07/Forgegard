import re

file_path = r'c:\coding\my work\final year\ForgeGuard\project_report.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Remove the HTML elements
# <div class="page-number-tab">...</div>
# <div class="page-number">...</div>
# <div class="page-number-center">...</div>
patterns = [
    re.compile(r'<div class="page-number-tab">.*?</div>', re.DOTALL),
    re.compile(r'<div class="page-number">.*?</div>', re.DOTALL),
    re.compile(r'<div class="page-number-center">.*?</div>', re.DOTALL)
]

for pattern in patterns:
    content = pattern.sub('', content)

# Remove the CSS blocks if they are my additions or if the user wants them gone
# I'll keep the existing CSS definitions unless they are explicitly my additions
# But the user said "Remove page number from whole file", which might imply cleaning up the whole thing.
# However, if I remove the CSS definitions that were already there, it might be safer to just remove the instances.

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Successfully removed all page number divs from project_report.html.")
