import re
with open('c:\\coding\\my work\\final year\\ForgeGuard\\project_report.html', 'r', encoding='utf-8') as f:
    html = f.read()
html = re.sub(r'<div class="page-number(-center)?">.*?</div>', '', html, flags=re.DOTALL)
with open('c:\\coding\\my work\\final year\\ForgeGuard\\project_report.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Removed page numbers")
