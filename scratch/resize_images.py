import re

path = r"c:\coding\my work\final year\ForgeGuard\project_report.html"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Find Chapter 1 start and Chapter 6 start
ch1_start = content.find('CHAPTER 1')
ch6_start = content.find('CHAPTER 6', ch1_start)

if ch1_start == -1 or ch6_start == -1:
    print("Could not find chapter markers")
    exit()

pre_ch1 = content[:ch1_start]
ch1_to_5 = content[ch1_start:ch6_start]
post_ch5 = content[ch6_start:]

# Regex to find <img tags
# We want to replace width="XXX" with width="500" 
# and style="...width: XXXpx;..." with style="...width: 500px;..."
# Also handle tags without width or style

def resize_img(match):
    tag = match.group(0)
    
    # 1. Update width attribute
    if 'width=' in tag:
        tag = re.sub(r'width="\d+"', 'width="500"', tag)
        tag = re.sub(r'width=\d+', 'width="500"', tag)
    else:
        # Insert width before style or at the end
        if 'style=' in tag:
            tag = tag.replace('style=', 'width="500" style=')
        else:
            tag = tag.replace('>', ' width="500">')
            
    # 2. Update style property
    if 'style=' in tag:
        if 'width:' in tag:
            tag = re.sub(r'width:\s*[^;"]+', 'width: 500px', tag)
        else:
            # Add width to style
            tag = re.sub(r'style="([^"]*)"', r'style="width: 500px; \1"', tag)
    else:
        # Add style
        tag = tag.replace('>', ' style="width: 500px; height: auto; display: block; margin: 0 auto; object-fit: contain;">')

    return tag

# Broad regex for img tags
new_ch1_to_5 = re.sub(r'<img[^>]+>', resize_img, ch1_to_5)

with open(path, "w", encoding="utf-8") as f:
    f.write(pre_ch1 + new_ch1_to_5 + post_ch5)

print("Done")
