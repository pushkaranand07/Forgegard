import os

def read_scratch(filename):
    with open(os.path.join('scratch', filename), 'r', encoding='utf-8') as f:
        return f.read()

final = read_scratch('final_expansion.html')

with open('project_report.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Split final expansion into pieces
chunks = final.split('<div class="sub-section-heading" style="page-break-inside: avoid;">2.5.4')
sec244 = chunks[0]

chunks2 = chunks[1].split('<div class="section-heading">2.10')
sec254 = '<div class="sub-section-heading" style="page-break-inside: avoid;">2.5.4' + chunks2[0]
sec210 = '<div class="section-heading">2.10' + chunks2[1]

# Integration Points
# Insert 2.4.4 after 2.4.3
marker243 = 'ForgeGuard pipeline, investigators can achieve a much higher level of confidence.</p>'
text = text.replace(marker243, marker243 + "\n\n" + sec244)

# Insert 2.5.4 after 2.5.3
marker253 = 'complexity of modern news footage and public surveillance videos.</p>'
text = text.replace(marker253, marker253 + "\n\n" + sec254)

# Insert 2.10 before 2.11 (Summary)
marker_summary = '<div class="section-heading">2.10 Chapter Summary</div>'
text = text.replace(marker_summary, sec210 + "\n\n" + '<div class="section-heading">2.11 Chapter Summary</div>')

# Update TOC
toc_marker = '<span>&nbsp;&nbsp;2.10 Chapter Summary</span>'
new_toc = """<span>&nbsp;&nbsp;2.10 Future Research Directions</span></div>
      <div class="toc-entry"><span>&nbsp;&nbsp;2.11 Chapter Summary</span></div>"""
text = text.replace(toc_marker, new_toc)

with open('project_report.html', 'w', encoding='utf-8') as f:
    f.write(text)

print("SUCCESS: Final integration complete")
