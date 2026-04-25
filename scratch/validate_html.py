
from html.parser import HTMLParser

class NestingParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.in_page = False
        
    def handle_starttag(self, tag, attrs):
        if tag != "div": return
        attrs_dict = dict(attrs)
        self.stack.append((tag, attrs_dict))
        if attrs_dict.get("class") == "page":
            if self.in_page:
                print(f"Line {self.getpos()[0]}: nested <div class=page>. Stack has {len(self.stack)} divs.")
            self.in_page = True

    def handle_endtag(self, tag):
        if tag != "div" or not self.stack:
            return
        last_tag, last_attrs = self.stack.pop()
        if last_attrs.get("class") == "page":
            self.in_page = False

parser = NestingParser()
html = open("project_report.html", "r", encoding="utf-8").read()
parser.feed(html)

