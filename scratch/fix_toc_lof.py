report = r'c:\coding\my work\final year\ForgeGuard\project_report.html'

# ── Helper: one TOC row ───────────────────────────────────────────────────────
def toc_chapter(text, page):
    return (f'        <div class="toc-row toc-chapter">'
            f'<span class="toc-text">{text}</span>'
            f'<span class="toc-dots"></span>'
            f'<span class="toc-page">{page}</span></div>\n')

def toc_section(text, page):
    return (f'        <div class="toc-row toc-section">'
            f'<span class="toc-text">{text}</span>'
            f'<span class="toc-dots"></span>'
            f'<span class="toc-page">{page}</span></div>\n')

# ── TOC CSS to inject ─────────────────────────────────────────────────────────
TOC_CSS = """
        /* ── Table of Contents styles ── */
        .toc-row {
            display: flex;
            align-items: baseline;
            margin-bottom: 3pt;
            font-size: 12pt;
            font-family: 'Times New Roman', Times, serif;
        }
        .toc-chapter { font-weight: bold; margin-top: 6pt; }
        .toc-section  { padding-left: 18pt; font-weight: normal; }
        .toc-text     { white-space: nowrap; }
        .toc-dots     { flex: 1; border-bottom: 1px dotted #000;
                        margin: 0 4pt 3pt 4pt; min-width: 20pt; }
        .toc-page     { white-space: nowrap; min-width: 28pt; text-align: right; }
        .toc-chapter .toc-page { font-weight: bold; }

        /* ── List of Figures table ── */
        .lof-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 12pt;
            font-family: 'Times New Roman', Times, serif;
            margin-top: 14pt;
        }
        .lof-table th, .lof-table td {
            border: 1px solid #000;
            padding: 5pt 8pt;
            vertical-align: middle;
        }
        .lof-table th {
            font-weight: bold;
            text-align: center;
            background: #fff;
        }
        .lof-table td:first-child  { text-align: center; width: 18%; }
        .lof-table td:nth-child(2) { text-align: left;   width: 65%; }
        .lof-table td:last-child   { text-align: center; width: 17%; }
"""

# ── Build new TOC page HTML ───────────────────────────────────────────────────
TOC_PAGE1 = (
    '    <div class="page">\n'
    '        <div class="chapter-heading">TABLE OF CONTENTS</div>\n'
    + toc_chapter('Declaration', 'iii')
    + toc_chapter('Certificate from Mentor', 'iv')
    + toc_chapter('Acknowledgement', 'v')
    + toc_chapter('Table of Contents', 'vi')
    + toc_chapter('List of Figures', 'viii')
    + toc_chapter('List of Tables', 'ix')
    + toc_chapter('Abstract / Summary', 'x')
    + toc_chapter('Chapter 1: Introduction to the Organisation', '1')
    + toc_section('1.1 Background of Digital Forgery and Deepfakes', '1')
    + toc_section('1.2 Importance in Cybersecurity and Media Authenticity', '14')
    + toc_section('1.3 Problem Statement', '17')
    + toc_section('1.4 Objectives of ForgeGuard', '19')
    + toc_section('1.5 Scope of the Project', '19')
    + toc_section('1.6 Limitations', '21')
    + toc_section('1.7 Applications', '22')
    + toc_chapter('Chapter 2: Introduction to the Project', '16')
    + toc_section('2.1 Problem Statement', '17')
    + toc_section('2.2 Motivation', '19')
    + toc_section('2.3 Objectives', '21')
    + toc_section('2.4 Project Scope', '22')
    + toc_section('2.5 Limitations', '24')
    + toc_section('2.6 Technology Stack Overview', '25')
    + toc_section('2.7 Project Workflow', '28')
    + toc_section('2.8 Summary', '30')
    + toc_chapter('Chapter 3: Literature Review and Survey', '32')
    + toc_section('3.1 Introduction to the Literature Review', '33')
    + toc_section('3.2 Review of Research Papers', '34')
    + toc_section('3.3 Comparative Analysis of Existing Systems', '48')
    + toc_section('3.4 Gap Analysis', '52')
    + toc_section('3.5 Summary', '54')
    + toc_chapter('Chapter 4: System Analysis and Requirements', '56')
    + toc_section('4.1 Functional Requirements', '57')
    + toc_section('4.2 Non-Functional Requirements', '60')
    + toc_section('4.3 Hardware and Software Specifications', '63')
    + toc_section('4.4 Feasibility Study', '66')
    + toc_section('4.5 Summary', '70')
    + '        <div class="page-number">4</div>\n'
    + '    </div>\n\n'
    + '    <div class="page">\n'
    + toc_chapter('Chapter 5: System Design', '72')
    + toc_section('5.1 Overall System Architecture', '73')
    + toc_section('5.2 Data Flow Diagrams', '76')
    + toc_section('5.3 UML Diagrams', '82')
    + toc_section('5.4 Database Design', '91')
    + toc_section('5.5 API Design', '96')
    + toc_section('5.6 Frontend Design', '101')
    + toc_section('5.7 Summary', '105')
    + '        <div class="page-number">5</div>\n'
    + '    </div>\n\n'
    + '    <div class="page">\n'
    + '        <div class="chapter-heading">TABLE OF CONTENTS (CONTINUED)</div>\n'
    + toc_chapter('Chapter 6: Implementation Details', '107')
    + toc_section('6.1 Project Structure and Module Overview', '108')
    + toc_section('6.2 Image Manipulation Detection Pipeline (IMDModel)', '112')
    + toc_section('6.3 Error Level Analysis (ELA)', '120')
    + toc_section('6.4 Video Deepfake Detection Pipeline', '126')
    + toc_section('6.5 Face Detection Engine', '134')
    + toc_section('6.6 REST API Layer', '140')
    + toc_section('6.7 Frontend Implementation', '148')
    + toc_section('6.8 Database Integration', '155')
    + toc_section('6.9 Exception Handling Framework', '158')
    + toc_section('6.10 Summary', '162')
    + toc_chapter('Chapter 7: Testing and Results', '164')
    + toc_section('7.1 Testing Strategy', '165')
    + toc_section('7.2 Unit Tests', '167')
    + toc_section('7.3 Functional Test Cases', '169')
    + toc_section('7.4 Performance and Accuracy Results', '178')
    + toc_section('7.5 System Screenshots', '183')
    + toc_section('7.6 Summary', '188')
    + toc_chapter('Chapter 8: Conclusion and Future Scope', '190')
    + toc_section('8.1 Summary of Work Done', '191')
    + toc_section('8.2 Achievements', '193')
    + toc_section('8.3 Limitations', '195')
    + toc_section('8.4 Future Enhancements', '197')
    + toc_section('8.5 Conclusion', '200')
    + toc_chapter('Chapter 9: Deployment and Security Analysis', '202')
    + toc_section('9.1 Deployment Architecture', '203')
    + toc_section('9.2 Security Considerations', '207')
    + toc_section('9.3 User Manual', '212')
    + toc_section('9.4 Summary', '217')
    + toc_chapter('Bibliography / References', '219')
    + '        <div class="page-number">6</div>\n'
    + '    </div>\n'
)

# ── Build List of Figures HTML ────────────────────────────────────────────────
def lof_row(num, desc, pg):
    return f'            <tr><td>Figure {num}</td><td>{desc}</td><td>{pg}</td></tr>\n'

LOF_FIGURES = [
    ('1.1','GTB4CEC College Campus / Logo','2'),
    ('1.2','Organisational Chart of GTB4CEC','6'),
    ('1.3','Department of CSE \u2013 Lab and Infrastructure','10'),
    ('2.1','Deepfake Examples \u2013 Real vs. Generated Faces','18'),
    ('2.2','Project Workflow Flowchart','29'),
    ('2.3','Technology Stack Diagram','26'),
    ('3.1','Research Trend \u2013 Publications on Deepfake Detection (2017\u20132024)','35'),
    ('3.2','Comparative Chart \u2013 Existing Deepfake Detection Tools','50'),
    ('4.1','Feasibility Analysis \u2013 Pie Chart','68'),
    ('4.2','Requirements Summary Table Diagram','62'),
    ('5.1','ForgeGuard High-Level System Architecture','74'),
    ('5.2','Level 0 \u2013 Context DFD','77'),
    ('5.3','Level 1 \u2013 System DFD (Image Module)','79'),
    ('5.4','Level 2 \u2013 DFD (Image Pipeline Details)','81'),
    ('5.5','Use Case Diagram \u2013 ForgeGuard','83'),
    ('5.6','Class Diagram \u2013 Core Pipeline Classes','86'),
    ('5.7','Sequence Diagram \u2013 Image Detection Flow','89'),
    ('5.8','Entity-Relationship (ER) Diagram','92'),
    ('5.9','API Response Structure','98'),
    ('6.1','Project Directory Structure','109'),
    ('6.2','IMDModel Architecture \u2013 CNN Layers','114'),
    ('6.3','ELA Process \u2013 Original vs. Re-compressed vs. Difference','121'),
    ('6.4','EfficientNet B7 Scaling Architecture','128'),
    ('6.5','MTCNN Face Detection Pipeline','135'),
    ('6.6','ForgeGuard Home Page \u2013 Screenshot','149'),
    ('6.7','Image Upload Page \u2013 Screenshot','150'),
    ('6.8','Image Result Page \u2013 AUTHENTIC Result','151'),
    ('6.9','Image Result Page \u2013 TAMPERED Result','152'),
    ('6.10','Video Upload Page \u2013 Screenshot','153'),
    ('6.11','API Test via Postman \u2013 Detect Image','154'),
    ('6.12','API Test via Postman \u2013 Detect Video','155'),
    ('7.1','Test Case Execution Summary','170'),
    ('7.2','Accuracy Comparison \u2013 Bar Chart','180'),
    ('7.3','Processing Time vs. File Size \u2013 Graph','182'),
    ('7.4','Confusion Matrix \u2013 Image Detection','179'),
    ('7.5','Screenshot \u2013 No Face Detected Response','185'),
    ('9.1','Deployment Architecture Diagram','204'),
    ('9.2','Request-Response Security Flow','209'),
]

LOF_HTML = (
    '    <div class="page">\n'
    '        <div class="chapter-heading">LIST OF FIGURES</div>\n'
    '        <table class="lof-table">\n'
    '            <tr><th>Figure No.</th><th>Figure Description</th><th>Page No.</th></tr>\n'
    + ''.join(lof_row(*r) for r in LOF_FIGURES[:28])
    + '        </table>\n'
    '        <div class="page-number">7</div>\n'
    '    </div>\n\n'
    '    <div class="page">\n'
    '        <table class="lof-table">\n'
    '            <tr><th>Figure No.</th><th>Figure Description</th><th>Page No.</th></tr>\n'
    + ''.join(lof_row(*r) for r in LOF_FIGURES[28:])
    + '        </table>\n'
    '        <div class="page-number">8</div>\n'
    '    </div>\n'
)

# ── Old block markers ─────────────────────────────────────────────────────────
OLD_TOC_START = '    <div class="page">\n        <div class="chapter-heading">TABLE OF CONTENTS</div>'
OLD_LOF_END_MARKER = '        <div class="page-number">8</div>\n    </div>\n'

with open(report, 'r', encoding='utf-8') as f:
    html = f.read()

# Find & replace old TOC+LOF block
toc_start_idx = html.find(OLD_TOC_START)
lof_end_idx = html.find(OLD_LOF_END_MARKER, toc_start_idx) + len(OLD_LOF_END_MARKER)

if toc_start_idx == -1:
    print('ERROR: Could not find TOC start')
elif lof_end_idx == -1:
    print('ERROR: Could not find LOF end')
else:
    html = html[:toc_start_idx] + TOC_PAGE1 + '\n' + LOF_HTML + html[lof_end_idx:]
    # Inject CSS before </style>
    if TOC_CSS not in html:
        html = html.replace('    </style>', TOC_CSS + '    </style>', 1)
    with open(report, 'w', encoding='utf-8') as f:
        f.write(html)
    print('SUCCESS: TOC and List of Figures rebuilt.')
