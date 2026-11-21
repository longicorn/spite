"""Self-contained HTML rendering for the report Markdown subset."""
import base64
import html
import io
import re


def diagram(source):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 5), layout='constrained')
    if 'xychart-beta' in source:
        upper = re.search(r'x-axis .*? --> ([\d.]+)', source)
        for color, line in zip(('#2e8b57', '#3266cc', '#d64b40'), re.findall(r'^\s*line \[([^]]+)\]', source, re.M)):
            values = [float(x) for x in line.split(',')]
            ax.plot([float(upper.group(1)) * i / (len(values) - 1) for i in range(len(values))], values, color=color)
        ax.set(xlabel='Periods', ylabel='Probability density', title='Completion time by scenario')
        ax.legend(['Best', 'Nominal', 'Worst'])
    else:
        nodes = dict(re.findall(r'^\s*(\w+)\["(.*?)"\]', source, re.M))
        edges = re.findall(r'^\s*(\w+)\s+(-\.->|-->)\s+(\w+)', source, re.M)
        from collections import defaultdict
        from matplotlib import font_manager
        from matplotlib.ft2font import FT2Font

        labels = {node: html.unescape(label) for node, label in nodes.items()}
        required = {ord(char) for label in labels.values() for char in label if not char.isspace()}
        font = None
        for candidate in font_manager.fontManager.ttflist:
            if 'lastresort' in candidate.name.lower().replace(' ', ''):
                continue
            try:
                if required <= set(FT2Font(candidate.fname).get_charmap()):
                    font = font_manager.FontProperties(fname=candidate.fname)
                    break
            except (OSError, RuntimeError):
                continue
        if font is None and required:
            plt.close(fig)
            raise ValueError('No installed font supports all diagram label characters')

        # Assign each node a dependency level; cycles stay on the last assigned level.
        levels = {node: 0 for node in nodes}
        for _ in range(len(nodes)):
            changed = False
            for start, _, end in edges:
                if start in levels and end in levels and levels[end] <= levels[start]:
                    levels[end] = levels[start] + 1
                    changed = True
            if not changed:
                break
        rows = defaultdict(list)
        for node in nodes:
            rows[levels[node]].append(node)
        positions = {}
        max_columns = max((len(row) for row in rows.values()), default=1)
        for row_index, level in enumerate(sorted(rows)):
            row = rows[level]
            for column, node in enumerate(row):
                positions[node] = (column - (len(row) - 1) / 2, -row_index)
        max_label = max((len(label) for label in labels.values()), default=1)
        width = max(8, min(24, max_columns * max(2.5, max_label * .13)))
        height = max(3, len(rows) * .8 + 1)
        fig.set_size_inches(width, height)
        critical = set(re.findall(r'^\s*class (\w+) critical', source, re.M))
        reviews = set(re.findall(r'^\s*class (\w+) review', source, re.M))
        periods = set(re.findall(r'^\s*class (\w+) period', source, re.M))
        for start, style, end in edges:
            if start in positions and end in positions:
                ax.annotate('', xy=positions[end], xytext=positions[start], zorder=1,
                            arrowprops=dict(arrowstyle='->', linestyle='dashed' if style == '-.->' else 'solid', shrinkA=15, shrinkB=15))
        for node, label in labels.items():
            x, y = positions[node]
            ax.text(x, y, label, ha='center', va='center', fontsize=9, fontproperties=font, zorder=2,
                    bbox=dict(boxstyle='round', facecolor='#ffe4a3' if node in reviews else 'white', edgecolor='#e74c3c' if node in critical else 'black', linestyle='dashed' if node in periods else 'solid'))
        ax.set_xlim(-max_columns / 2, max_columns / 2)
        ax.set_ylim(-len(rows) + .2, .8)
        ax.axis('off')
    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', dpi=120)
    plt.close(fig)
    return base64.b64encode(buffer.getvalue()).decode('ascii')


def render_html(markdown):
    lines = markdown.splitlines()
    output = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line == '```mermaid':
            i += 1
            block = []
            while i < len(lines) and lines[i] != '```':
                block.append(lines[i]); i += 1
            output.append('<img alt="Report diagram" src="data:image/png;base64,' + diagram('\n'.join(block)) + '">')
        elif line.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].startswith('|'):
                cells = [html.escape(cell.strip()) for cell in lines[i].strip('|').split('|')]
                if not all(re.fullmatch(r'[-: ]+', cell) for cell in cells):
                    tag = 'th' if not rows else 'td'
                    rows.append('<tr>' + ''.join(f'<{tag}>{cell}</{tag}>' for cell in cells) + '</tr>')
                i += 1
            output.append('<table>' + ''.join(rows) + '</table>'); continue
        elif line.startswith('#'):
            level = len(line) - len(line.lstrip('#'))
            output.append(f'<h{level}>{html.escape(line[level:].strip())}</h{level}>')
        elif line.strip():
            output.append('<p>' + html.escape(line) + '</p>')
        i += 1
    return '<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Spite report</title><style>body{font:16px/1.5 system-ui,sans-serif;max-width:70rem;margin:2rem auto;padding:0 1rem;color:#222}table{border-collapse:collapse;width:100%}th,td{border:1px solid #aaa;padding:.4rem;text-align:left}img{max-width:100%;height:auto} @media print{body{margin:0;max-width:none}img,table{break-inside:avoid}}</style></head><body>' + '\n'.join(output) + '</body></html>\n'
