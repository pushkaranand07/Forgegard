import re
with open('c:\\coding\\my work\\final year\\ForgeGuard\\project_report.html', 'r', encoding='utf-8') as f:
    html = f.read()
for match in re.finditer(r'<div class="([^"]*)".*?(CERTIFICATE|DECLARATION|ACKNOWLEDGMENT|ABSTRACT|TABLE OF CONTENTS|LIST OF FIGURES|LIST OF TABLES)', html, re.DOTALL | re.IGNORECASE):
    # Just look at the previous 300 characters to find the enclosing page div
    context = html[max(0, match.end() - 300):match.end()]
    page_match = re.search(r'<div class="(fm-[^"]*|page[^"]*)"', context)
    if page_match:
        print(f"Section {match.group(2)} is in class {page_match.group(1)}")
