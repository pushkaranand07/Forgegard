import os

def read_scratch(filename):
    with open(os.path.join('scratch', filename), 'r', encoding='utf-8') as f:
        return f.read()

p1 = read_scratch('expansion_p1.html')
p2 = read_scratch('expansion_p2.html')
p3 = read_scratch('expansion_p3.html')

with open('project_report.html', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Inject 2.1.4
p1_chunks = p1.split('<div class="sub-section-heading" style="page-break-inside: avoid;">2.3.3')
sec214 = p1_chunks[0]

# 2. Inject 2.3.3
p1_chunks2 = p1_chunks[1].split('<div class="sub-section-heading" style="page-break-inside: avoid;">2.4.3')
sec233 = '<div class="sub-section-heading" style="page-break-inside: avoid;">2.3.3' + p1_chunks2[0]

# 3. Inject 2.4.3
sec243 = '<div class="sub-section-heading" style="page-break-inside: avoid;">2.4.3' + p1_chunks2[1]

# 4. Inject 2.5.3 (from p3)
p3_chunks = p3.split('<div class="section-heading">2.9')
sec253 = p3_chunks[0]
sec29 = '<div class="section-heading">2.9' + p3_chunks[1]

# 5. Inject 2.6, 2.7, 2.8 (from p2)
p2_chunks = p2.split('<div class="section-heading">2.8')
sec26_27 = p2_chunks[0]
sec28 = '<div class="section-heading">2.8' + p2_chunks[1]

# Integration Points
# Insert 2.1.4 after 2.1.3
marker213 = 'investigators can reliably detect copy-move forgeries even if the attacker manipulated the pasted region.</p>'
text = text.replace(marker213, marker213 + "\n\n" + sec214)

# Insert 2.3.3 after 2.3.2
marker232 = 'signals degrading to near-zero as they passed backwards through so many layers.</p>'
text = text.replace(marker232, marker232 + "\n\n" + sec233)

# Insert 2.4.3 after 2.4.2
marker242 = 'ForgeGuard system seeks to leverage this specific temporal vulnerability by analyzing the inter-frame coherence of detected face crops.</p>'
text = text.replace(marker242, marker242 + "\n\n" + sec243)

# Insert 2.5.3 after 2.5.2
marker252 = 'high forgery probability even in the presence of noise.</p>'
text = text.replace(marker252, marker252 + "\n\n" + sec253)

# Insert 2.6, 2.7, 2.8, 2.9 before 2.10 (Old Summary)
marker_summary = '<div class="section-heading">2.8 Chapter Summary</div>'
text = text.replace(marker_summary, sec26_27 + "\n\n" + sec28 + "\n\n" + sec29 + "\n\n" + '<div class="section-heading">2.10 Chapter Summary</div>')

# Update TOC
toc_marker = '<span>&nbsp;&nbsp;2.8 Chapter Summary</span>'
new_toc = """<span>&nbsp;&nbsp;2.6 Emerging Threats: Diffusion Models</span></div>
      <div class="toc-entry"><span>&nbsp;&nbsp;2.7 Legal and Ethical Dimensions</span></div>
      <div class="toc-entry"><span>&nbsp;&nbsp;2.8 Comparative Analysis Table</span></div>
      <div class="toc-entry"><span>&nbsp;&nbsp;2.9 Identification of Research Gaps</span></div>
      <div class="toc-entry"><span>&nbsp;&nbsp;2.10 Chapter Summary</span></div>"""
text = text.replace(toc_marker, new_toc)

with open('project_report.html', 'w', encoding='utf-8') as f:
    f.write(text)

print("SUCCESS: Integrated expansion")
