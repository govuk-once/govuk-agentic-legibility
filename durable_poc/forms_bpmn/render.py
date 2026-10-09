"""Dependency-free SVG preview using the exact coordinates written to BPMN DI.

This is a convenience renderer, not a replacement for a BPMN viewer. Use the
provided bpmn.io import verification for an independent rendering check.
"""

from __future__ import annotations

import html
import textwrap

from .converter import Graph


def render_svg(graph: Graph, title: str) -> str:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{graph.width + 80}" height="{graph.height + 110}" viewBox="0 0 {graph.width + 80} {graph.height + 110}">',
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#526579"/></marker></defs>',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="25" y="30" font-family="sans-serif" font-size="20" fill="#153b57">{html.escape(title)}</text>',
    ]

    def label(x, y, text, width=37, size=16):
        lines = textwrap.wrap(text, width)
        parts.append(
            f'<text x="{x}" y="{y}" text-anchor="middle" font-family="sans-serif" font-size="{size}" fill="#153b57">'
        )
        for i, line in enumerate(lines):
            parts.append(
                f'<tspan x="{x}" dy="{0 if i == 0 else size + 3}">{html.escape(line)}</tspan>'
            )
        parts.append("</text>")

    def scope(g, dx=40, dy=60):
        for n in g.nodes.values():
            x, y = n.x + dx, n.y + dy
            if n.children:
                parts.append(
                    f'<rect x="{x}" y="{y}" width="{n.width}" height="{n.height}" rx="12" fill="#f5f8fc" stroke="#6789a6" stroke-width="2"/>'
                )
                label(x + n.width / 2, y + 27, n.name, int((n.width - 50) / 9), 17)
                scope(n.children, x + 40, y + 95)
        for e in g.edges:
            points = " ".join(f"{x + dx},{y + dy}" for x, y in e.points)
            parts.append(
                f'<polyline points="{points}" fill="none" stroke="#526579" stroke-width="2" marker-end="url(#arrow)"/>'
            )
            if e.default:
                x, y = e.points[0]
                parts.append(
                    f'<path d="M{x + dx - 7},{y + dy + 7} l14,10" stroke="#526579" stroke-width="2"/>'
                )
            if e.label:
                x, y, w, h = e.label
                parts.append(
                    f'<rect x="{x + dx}" y="{y + dy - 4}" width="{w}" height="{h + 8}" fill="white" fill-opacity="0.92"/>'
                )
                label(x + dx + w / 2, y + dy + 12, e.name, 43, 14)
        for n in g.nodes.values():
            x, y = n.x + dx, n.y + dy
            if n.children:
                continue
            if n.kind in {"startEvent", "endEvent"}:
                parts.append(
                    f'<circle cx="{x + n.width / 2}" cy="{y + n.height / 2}" r="{n.width / 2}" fill="white" stroke="#24516f" stroke-width="{4 if n.kind == "endEvent" else 2}"/>'
                )
                label(x + n.width / 2, y + n.height + 23, n.name, 26, 14)
            elif n.kind == "exclusiveGateway":
                points = f"{x + n.width / 2},{y} {x + n.width},{y + n.height / 2} {x + n.width / 2},{y + n.height} {x},{y + n.height / 2}"
                parts.append(
                    f'<polygon points="{points}" fill="white" stroke="#24516f" stroke-width="2"/>'
                )
                label(x + n.width / 2, y + n.height / 2 + 7, "×", 2, 26)
                label(x + n.width / 2, y + n.height + 23, n.name, 26, 14)
            else:
                parts.append(
                    f'<rect x="{x}" y="{y}" width="{n.width}" height="{n.height}" rx="10" fill="white" stroke="#24516f" stroke-width="2"/>'
                )
                # Standard user silhouette in the task's upper left corner.
                if n.kind == "userTask":
                    parts.append(
                        f'<circle cx="{x + 14}" cy="{y + 13}" r="3" fill="none" stroke="#24516f"/><path d="M{x + 8},{y + 26} v-5 q6,-9 12,0 v5 z M{x + 14},{y + 17} v9" fill="none" stroke="#24516f"/>'
                    )
                elif n.kind == "scriptTask":
                    label(x + 15, y + 24, "≡", 2, 22)
                lines = textwrap.wrap(n.name, 37)
                label(
                    x + n.width / 2, y + (n.height - len(lines) * 19) / 2 + 16, n.name
                )

    scope(graph)
    parts.append("</svg>")
    return "\n".join(parts)
