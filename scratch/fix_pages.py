import re

with open('project_report.html', 'r', encoding='utf-8') as f:
    text = f.read()

start_marker = 'CHAPTER 2 — LITERATURE REVIEW'
end_marker = '<!-- CHAPTER 3 TRANSPARENCY -->'

start_idx = text.find(start_marker)
end_idx = text.find(end_marker)

if start_idx != -1 and end_idx != -1:
    before = text[:start_idx]
    chapter = text[start_idx:end_idx]
    after = text[end_idx:]
    
    # Replace the chunk
    chunk = '  </div>\n\n  <div class="page">\n'
    new_chapter = chapter.replace(chunk, '\n\n')
    
    with open('project_report.html', 'w', encoding='utf-8') as f:
        f.write(before + new_chapter + after)
    print('SUCCESS')
else:
    print('MARKERS NOT FOUND')
