
import sys
html = open("project_report.html", "r", encoding="utf-8").read()
depth = 0
for i, line in enumerate(html.split("\n")):
    if "<div" in line: depth += line.count("<div")
    if "</div" in line: depth -= line.count("</div")
    if 560 <= i+1 <= 572:
        print(f"Line {i+1}: Depth is {depth} -> {line.strip()}")

