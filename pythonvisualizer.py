import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.widgets import Button, CheckButtons, Slider, TextBox
from matplotlib.lines import Line2D
import tkinter as tk
from tkinter import messagebox

import numpy as np
import re
import json
import math
import time as _time


class MapColoringVisualizer:
    def __init__(self):
        plt.style.use('dark_background')
        self.fig, self.ax = plt.subplots(figsize=(14, 10))
        self.fig.canvas.manager.set_window_title("Map Coloring Visualizer")
        self.fig.patch.set_facecolor('#1a1a1a')
        self.ax.set_facecolor('#2d2d2d')

        self.nodes = {}
        self.node_counter = 0
        self.node_radius = 0.8

        self.map_colors = [
            '#D61913', '#EE27F5', '#27EBF5', '#1DD613'
        ]  
        self.color_names = [
            'Red', 'Purple', 'Cyan', 'Green'
        
        ]

        self.use_mrv = True
        self.use_degree = True
        self.degree_first = False  # Default = MRV first, Degree as tie-breaker

        self.animation_delay = 0.25  
        self.dragging_id = None
        self.drag_offset = (0.0, 0.0)
        self.edit_edges_mode = False
        self.edge_first = None

        self.selected_for_domain = None
        self.show_domain_panel = True 
        self.ax_domain = None          

        self.ax_pos_on = None
        self.ax_pos_off = [0.06, 0.36, 0.90, 0.52]  

        self.node_patches = {}   
        self.node_labels = {}    
        self.edge_lines = {}     
        self.status_text = None
        self.edit_ring = None    

        self._last_motion_ts = 0.0   
        self._motion_hz = 120.0      


        self._bg = None
        self._blit_enabled = True

        self._build_ui()
        plt.show()

    def _build_ui(self):
        plt.subplots_adjust(bottom=0.36, top=0.88, right=0.96, left=0.06)

        self._style_axes_once()

        self.fig.suptitle("Map Coloring Problem Visualizer",
                          fontsize=22, color='white', fontweight='bold', y=0.94)

        instructions = (
            "How to use:\n"
            "• Add Region; drag nodes to arrange.\n"
            "• Edit Borders: click two nodes to toggle an edge.\n"
            "• MRV / Degree toggles (top-left).\n"
            "• Order button switches MRV→Degree vs Degree→MRV.\n"
            "• Delay slider (below toggles).\n"
            "• Click any node to view its domain (right panel).\n"
            "• Modify Domain below (max 4 colors), then Apply.\n"
            "• Auto Color runs backtracking + forward checking."
        )
        self.instructions_artist = self.fig.text(
            0.98, 0.98, instructions, fontsize=10, color='#cccccc',
            va='top', ha='right',
            bbox=dict(boxstyle="round,pad=0.4", facecolor='#3a3a3a',
                      alpha=0.9, edgecolor='#5a5a5a', linewidth=1)
        )

        self._setup_topleft_controls()   
        self._setup_bottom_controls()    
        self._setup_domain_panel()       
        self._connect_events()

        self.ax_pos_on = list(self.ax.get_position().bounds)
        self._apply_ax_position()

        self._build_scene()
        self._capture_bg()
        self._update_status()

    def _style_axes_once(self):
        self.ax.set_xlim(-1, 11)
        self.ax.set_ylim(-1, 9)
        self.ax.set_aspect('equal')
        self.ax.set_xticks([]); self.ax.set_yticks([])
        self.ax.grid(True, alpha=0.1, color='white')

    def _setup_topleft_controls(self):
        self.ax_checks = plt.axes([0.06, 0.68, 0.22, 0.10], facecolor='#2b2b2b')
        self.checks = CheckButtons(self.ax_checks, ['MRV', 'Degree'], [self.use_mrv, self.use_degree])
        self.checks.on_clicked(self._toggle_checks)

        for lab in self.checks.labels:
            lab.set_color('white')
            lab.set_fontweight('bold')
            lab.set_fontsize(12)

        for s in self.ax_checks.spines.values():
            s.set_color('#444444')
            s.set_linewidth(1)

        for rect in self._get_check_rects():
            rect.set_edgecolor('white')
            rect.set_linewidth(1.5)
        for ln in self._get_check_lines():
            ln.set_color('white')
            ln.set_linewidth(1.5)

        self._refresh_toggle_styles()

        ax_order = plt.axes([0.05, 0.40, 0.22, 0.06])
        self.btn_order = Button(ax_order,
                                'Order: MRV→Degree',
                                color='#4a4a4a', hovercolor='#6a6a6a')
        self.btn_order.on_clicked(self._toggle_order)

        ax_slider = plt.axes([0.06, 0.62, 0.20, 0.035], facecolor='#2b2b2b')
        self.delay_slider = Slider(ax_slider, 'Delay (s)', 0.0, 1.0, valinit=self.animation_delay)
        self.delay_slider.label.set_color('white')
        self.delay_slider.valtext.set_color('white')
        self.delay_slider.on_changed(lambda v: setattr(self, 'animation_delay', float(v)))
        for s in ax_slider.spines.values():
            s.set_color('#444444'); s.set_linewidth(1)

    def _setup_bottom_controls(self):
        button_color = '#4a4a4a'
        hover_color = '#6a6a6a'

        ax_add = plt.axes([0.07, 0.24, 0.14, 0.06])
        self.btn_add = Button(ax_add, 'Add Region', color=button_color, hovercolor=hover_color)
        self.btn_add.on_clicked(self._add_node)

        ax_auto = plt.axes([0.25, 0.24, 0.14, 0.06])
        self.btn_auto = Button(ax_auto, 'Auto Color', color=button_color, hovercolor=hover_color)
        self.btn_auto.on_clicked(self._auto_color)

        ax_clear_colors = plt.axes([0.43, 0.24, 0.14, 0.06])
        self.btn_clear_colors = Button(ax_clear_colors, 'Clear Colors', color=button_color, hovercolor=hover_color)
        self.btn_clear_colors.on_clicked(self._clear_colors_only)

        ax_clear = plt.axes([0.61, 0.24, 0.14, 0.06])
        self.btn_clear = Button(ax_clear, 'Clear All', color=button_color, hovercolor=hover_color)
        self.btn_clear.on_clicked(self._clear_all)

        ax_edit = plt.axes([0.79, 0.24, 0.14, 0.06])
        self.btn_edit = Button(ax_edit, 'Edit Borders: OFF', color=button_color, hovercolor=hover_color)
        self.btn_edit.on_clicked(self._toggle_edit_edges)

        ax_dom_toggle = plt.axes([0.79, 0.30, 0.14, 0.05])
        self.btn_dom_toggle = Button(ax_dom_toggle, 'Domain Panel: ON', color='#3d6d3d', hovercolor='#4c8c4c')
        self.btn_dom_toggle.on_clicked(self._toggle_domain_panel)

        self.fig.text(0.0675, 0.10, 'Domain Node ID', fontsize=10, color='white', fontweight='bold')
        ax_dom_id = plt.axes([0.07, 0.135, 0.09, 0.05], facecolor='#f0f0f0')
        self.box_dom_id = TextBox(ax_dom_id, '', initial='', color='#f0f0f0', hovercolor='#ffffff')

        self.fig.text(0.18, 0.10, 'Colors (names or numbers: Red,Purple,Cyan,Green or 1,2,3,4)', fontsize=10, color='white', fontweight='bold')
        ax_dom_colors = plt.axes([0.18, 0.135, 0.35, 0.05], facecolor='#f0f0f0')
        self.box_dom_colors = TextBox(ax_dom_colors, '', initial='Red,Purple,Cyan,Green', color='#f0f0f0', hovercolor='#ffffff')

        ax_apply = plt.axes([0.55, 0.135, 0.12, 0.05])
        self.btn_apply = Button(ax_apply, 'Apply Domain', color=button_color, hovercolor=hover_color)
        self.btn_apply.on_clicked(self._apply_domain)

        ax_reset = plt.axes([0.69, 0.135, 0.12, 0.05])
        self.btn_reset = Button(ax_reset, 'Reset Domain', color=button_color, hovercolor=hover_color)
        self.btn_reset.on_clicked(self._reset_domain)

        ax_reset_all = plt.axes([0.83, 0.135, 0.12, 0.05])
        self.btn_reset_all = Button(ax_reset_all, 'Reset All Domains', color=button_color, hovercolor=hover_color)
        self.btn_reset_all.on_clicked(self._reset_all_domains)

        for tb in [self.box_dom_id, self.box_dom_colors]:
            try:
                tb.text_disp.set_color('black')
            except Exception:
                pass

    def _domain_cols_for(self, n):
       
        return 1 if n <= 3 else (2 if n <= 6 else 3)

    def _compute_domain_panel_rect(self, domain_size):
        cols = self._domain_cols_for(domain_size)
        base_width = 0.16
        extra_per_col = 0.06
        width = base_width + (cols - 1) * extra_per_col
        right_margin = 0.02
        left = max(0.06, 1.0 - width - right_margin)
        bottom = 0.44
        height = 0.30
        return [left, bottom, width, height]

    def _reposition_domain_panel(self):
        if not self.ax_domain:
            return
        if self.show_domain_panel and self.selected_for_domain in self.nodes:
            ds = len(self.nodes[self.selected_for_domain]['domain'])
        else:
            ds = 4
        self.ax_domain.set_position(self._compute_domain_panel_rect(ds))

    def _apply_ax_position(self):
        if self.show_domain_panel:
            if self.ax_pos_on:
                self.ax.set_position(self.ax_pos_on)
        else:
            self.ax.set_position(self.ax_pos_off)

    def _get_check_rects(self):
        cb = self.checks
        for name in ("rectangles", "boxes", "_rectangles", "_boxes"):
            rects = getattr(cb, name, None)
            if rects:
                return list(rects)
        rects = [p for p in self.ax_checks.patches if isinstance(p, patches.Rectangle)]
        return rects[:len(self.checks.labels)]

    def _get_check_lines(self):
        lines = getattr(self.checks, "lines", None)
        if lines:
            flat = []
            for item in lines:
                if isinstance(item, (tuple, list)):
                    flat.extend(item)
                else:
                    flat.append(item)
            return flat
        return [ln for ln in self.ax_checks.lines if isinstance(ln, Line2D)]
    def _get_color_name(self, hex_color):
        try:
            idx = self.map_colors.index(hex_color.upper())
            return self.color_names[idx]
        except ValueError:
            return hex_color
    def _create_domain_axes_if_needed(self):
        if self.ax_domain or not self.show_domain_panel:
            return
        self.ax_domain = plt.axes([0.75, 0.44, 0.30, 0.30], facecolor='#202020')
        self.ax_domain.set_xticks([]); self.ax_domain.set_yticks([])
        for spine in self.ax_domain.spines.values():
            spine.set_color('#666666')
        self._reposition_domain_panel()

    def _setup_domain_panel(self):
        if self.show_domain_panel:
            self._create_domain_axes_if_needed()
            self._render_domain_panel(None)


    def _connect_events(self):
        self.fig.canvas.mpl_connect('button_press_event', self._on_press)
        self.fig.canvas.mpl_connect('motion_notify_event', self._on_motion)
        self.fig.canvas.mpl_connect('button_release_event', self._on_release)
        self.fig.canvas.mpl_connect('resize_event', lambda evt: (self._reposition_domain_panel(), self.fig.canvas.draw_idle()))

    def _build_scene(self):
        """Build (or rebuild) the whole scene once. Use when topology changes."""
        self.ax.cla()
        self._style_axes_once()

        self.node_patches.clear()
        self.node_labels.clear()
        self.edge_lines.clear()


        drawn = set()
        for a, data in self.nodes.items():
            x1, y1 = data['pos']
            for b in data['connections']:
                if b not in self.nodes: continue
                e = tuple(sorted((a, b)))
                if e in drawn: continue
                x2, y2 = self.nodes[b]['pos']
                ln = self.ax.plot([x1, x2], [y1, y2], color='white', linewidth=2, alpha=0.85)[0]
                self.edge_lines[e] = ln
                drawn.add(e)

        for nid, data in self.nodes.items():
            x, y = data['pos']
            color = data['color']
            c = patches.Circle((x, y), self.node_radius, facecolor=color, edgecolor='white', linewidth=3, zorder=2)
            self.ax.add_patch(c)
            self.node_patches[nid] = c

            label = str(nid)
            if 'domain' in data and len(data['domain']) != len(self.map_colors):
                label += f" ({len(data['domain'])})"
            t = self.ax.text(x, y, label, ha='center', va='center',
                             fontsize=14, fontweight='bold', color='white', zorder=4)
            self.node_labels[nid] = t

        self.status_text = self.ax.text(
            0.02, 0.98, "", transform=self.ax.transAxes,
            fontsize=12, color='white', fontweight='bold',
            bbox=dict(boxstyle="round,pad=0.4", facecolor='#4a4a4a',
                      alpha=0.9, edgecolor='#6a6a6a', linewidth=1),
            va='top'
        )

        self.edit_ring = patches.Circle(
            (0, 0), self.node_radius*1.15, fill=False,
            edgecolor='#FFD166', linewidth=3, linestyle='--',
            zorder=3, visible=False
        )
        self.ax.add_patch(self.edit_ring)

        self.fig.canvas.draw_idle()

    def _update_status(self):
        used = len({d['color'] for d in self.nodes.values() if d['color'] != '#888888'})
        status = f"Regions: {len(self.nodes)}"
        if used: status += f" | Colors: {used}"
        status += f" | MRV={'ON' if self.use_mrv else 'OFF'}"
        status += f" | Degree={'ON' if self.use_degree else 'OFF'}"
        status += f" | Order={'Deg→MRV' if self.degree_first else 'MRV→Deg'}"
        if self.status_text:
            self.status_text.set_text(status)
            self.fig.canvas.draw_idle()

    def _capture_bg(self):
        if not self._blit_enabled:
            return
        self.fig.canvas.draw()
        self._bg = self.fig.canvas.copy_from_bbox(self.ax.bbox)

    def _blit_artists(self, artists):
        if not (self._blit_enabled and self._bg is not None):
            self.fig.canvas.draw_idle()
            return
        canvas = self.fig.canvas
        canvas.restore_region(self._bg)
        for a in artists:
            try:
                self.ax.draw_artist(a)
            except Exception:
                pass
        canvas.blit(self.ax.bbox)
        canvas.flush_events()

    def _update_node_position(self, nid):
        if nid not in self.node_patches: return
        x, y = self.nodes[nid]['pos']
        self.node_patches[nid].center = (x, y)
        self.node_labels[nid].set_position((x, y))
        dirty = [self.node_patches[nid], self.node_labels[nid]]

        for nb in self.nodes[nid]['connections']:
            e = tuple(sorted((nid, nb)))
            if e in self.edge_lines:
                x1, y1 = self.nodes[e[0]]['pos']
                x2, y2 = self.nodes[e[1]]['pos']
                ln = self.edge_lines[e]
                ln.set_data([x1, x2], [y1, y2])
                dirty.append(ln)

        self._blit_artists(dirty)

    def _update_node_color(self, nid, color):
        if nid in self.node_patches:
            self.node_patches[nid].set_facecolor(color)
            self._blit_artists([self.node_patches[nid]])
        self._update_status()

    def _update_node_label_text(self, nid):
        if nid in self.node_labels:
            data = self.nodes[nid]
            label = str(nid)
            if 'domain' in data and len(data['domain']) != len(self.map_colors):
                label += f" ({len(data['domain'])})"
            self.node_labels[nid].set_text(label)
            self._blit_artists([self.node_labels[nid]])

    def _add_edge_artist(self, a, b):
        e = tuple(sorted((a, b)))
        if e in self.edge_lines:  
            return
        x1, y1 = self.nodes[e[0]]['pos']
        x2, y2 = self.nodes[e[1]]['pos']
        ln = self.ax.plot([x1, x2], [y1, y2], color='white', linewidth=2, alpha=0.85)[0]
        self.edge_lines[e] = ln
        self._capture_bg() 
        if self.edit_ring and self.edit_ring.get_visible():
            self._blit_artists([self.edit_ring])

    def _remove_edge_artist(self, a, b):
        e = tuple(sorted((a, b)))
        ln = self.edge_lines.pop(e, None)
        if ln:
            ln.remove()
            self._capture_bg()
            if self.edit_ring and self.edit_ring.get_visible():
                self._blit_artists([self.edit_ring])

    def _on_press(self, event):
        if event.inaxes != self.ax or event.xdata is None or event.ydata is None:
            return
        nid = self._find_node_at(event.xdata, event.ydata)
        if nid is None:
            return

        self.selected_for_domain = nid
        if self.show_domain_panel and self.ax_domain:
            self._render_domain_panel(nid)

        if self.edit_edges_mode:
            if self.edge_first is None:
                self.edge_first = nid
                self._update_edit_ring()
            else:
                a, b = self.edge_first, nid
                if a != b:
                    if b in self.nodes[a]['connections']:
                        self.nodes[a]['connections'].remove(b)
                        self.nodes[b]['connections'].remove(a)
                        self._remove_edge_artist(a, b)
                        print(f"Removed edge {a}-{b}")
                    else:
                        self.nodes[a]['connections'].add(b)
                        self.nodes[b]['connections'].add(a)
                        self._add_edge_artist(a, b)
                        print(f"Added edge {a}-{b}")
                self.edge_first = None
                self._update_edit_ring()
            self._update_status()
            return

        cx, cy = self.nodes[nid]['pos']
        self.dragging_id = nid
        self.drag_offset = (event.xdata - cx, event.ydata - cy)
        self._capture_bg()

    def _on_motion(self, event):
        if self.dragging_id is None or event.xdata is None or event.ydata is None:
            return
        now = _time.time()
        if (now - self._last_motion_ts) < (1.0 / self._motion_hz):
            return
        self._last_motion_ts = now

        dx, dy = self.drag_offset
        x = max(1, min(9, event.xdata - dx))
        y = max(1, min(7, event.ydata - dy))
        self.nodes[self.dragging_id]['pos'] = (x, y)
        self._update_node_position(self.dragging_id)

    def _on_release(self, event):
        self.dragging_id = None
        self._capture_bg()

    def _update_edit_ring(self):
        if self.edit_ring is None:
            return
        if self.edit_edges_mode and self.edge_first is not None:
            x, y = self.nodes[self.edge_first]['pos']
            self.edit_ring.center = (x, y)
            self.edit_ring.set_visible(True)
        else:
            self.edit_ring.set_visible(False)
        self._capture_bg()
        self._blit_artists([self.edit_ring])

    def _refresh_toggle_styles(self):
        states = [self.use_mrv, self.use_degree]
        rects = self._get_check_rects()
        for rect, state in zip(rects, states):
            rect.set_facecolor('#2FAA60' if state else '#A64040')
            rect.set_alpha(0.9)
            rect.set_edgecolor('white')
            rect.set_linewidth(1.5)
        self.ax_checks.set_facecolor('#1f1f1f')
        self.fig.canvas.draw_idle()

    def _smart_pos(self):
        n = self.node_counter
        if n == 0: return 5, 4
        phi = (np.sqrt(5) + 1) / 2
        angle = 2 * np.pi * n / (phi**2)
        radius = 0.6 * np.sqrt(n)
        x = 5 + radius * np.cos(angle)
        y = 4 + radius * np.sin(angle)
        return max(1, min(9, x)), max(1, min(7, y))

    def _find_node_at(self, x, y):
        for nid in sorted(self.nodes.keys(), reverse=True):
            nx, ny = self.nodes[nid]['pos']
            if (x - nx)**2 + (y - ny)**2 <= self.node_radius**2:
                return nid
        return None

    def _neighbors(self):
        return {nid: set(d['connections']) for nid, d in self.nodes.items()}

    def _initial_domains(self):
        return {nid: list(d['domain']) for nid, d in self.nodes.items()}

    def _toggle_checks(self, label):
        if label == 'MRV':
            self.use_mrv = not self.use_mrv
        elif label == 'Degree':
            self.use_degree = not self.use_degree
        self._refresh_toggle_styles()
        self._update_status()

    def _toggle_order(self, event):
        self.degree_first = not self.degree_first
        self.btn_order.label.set_text('Order: Degree→MRV' if self.degree_first else 'Order: MRV→Degree')
        self._update_status()

    def _toggle_edit_edges(self, event):
        self.edit_edges_mode = not self.edit_edges_mode
        if not self.edit_edges_mode:
            self.edge_first = None
        self.btn_edit.label.set_text(f"Edit Borders: {'ON' if self.edit_edges_mode else 'OFF'}")
        self._update_edit_ring()
        self._update_status()

    def _toggle_domain_panel(self, event):
        self.show_domain_panel = not self.show_domain_panel
        self.btn_dom_toggle.label.set_text(f"Domain Panel: {'ON' if self.show_domain_panel else 'OFF'}")
        if self.show_domain_panel:
            self.btn_dom_toggle.color = '#3d6d3d'; self.btn_dom_toggle.hovercolor = '#4c8c4c'
        else:
            self.btn_dom_toggle.color = '#6d3d3d'; self.btn_dom_toggle.hovercolor = '#8c4c4c'

        self._apply_ax_position()
        if not self.show_domain_panel and self.ax_domain:
            self.ax_domain.remove()
            self.ax_domain = None
        elif self.show_domain_panel and not self.ax_domain:
            self._create_domain_axes_if_needed()
            self._render_domain_panel(self.selected_for_domain)

        self._capture_bg()
        self._update_status()

    def _add_node(self, event):
        self.node_counter += 1
        nid = self.node_counter
        self.nodes[nid] = {
            'pos': self._smart_pos(),
            'connections': set(),
            'color': '#888888',
            'domain': list(self.map_colors)
        }
        self._build_scene()
        self._capture_bg()
        self._update_status()

    def _clear_colors_only(self, event):
        for nid in self.nodes:
            self.nodes[nid]['color'] = '#888888'
            self._update_node_color(nid, '#888888')
        self._capture_bg()
        print("Colors cleared (nodes and edges unchanged).")

    def _clear_all(self, event):
        self.nodes.clear()
        self.node_counter = 0
        self.edit_edges_mode = False
        self.edge_first = None
        self.selected_for_domain = None
        self._build_scene()
        self._capture_bg()
        self._update_status()

    def _get_hex_from_name_or_number(self, token):
        token = token.strip()
        if not token:
            return None
        
        if token.isdigit():
            idx = int(token) - 1
            if 0 <= idx < len(self.map_colors):
                return self.map_colors[idx]
            return None
        
        token_lower = token.lower()
        for i, name in enumerate(self.color_names):
            if name.lower() == token_lower:
                return self.map_colors[i]
        
        if re.fullmatch(r'#?[0-9A-Fa-f]{6}', token):
            return token if token.startswith('#') else f'#{token}'
        
        return None

    def _apply_domain(self, event):
        nid_text = self.box_dom_id.text.strip()
        col_text = self.box_dom_colors.text.strip()
        if not nid_text or not col_text:
            print("Enter Node ID and colors.")
            return
        try:
            nid = int(nid_text)
        except:
            print("Invalid Node ID.")
            return
        if nid not in self.nodes:
            print(f"Node {nid} does not exist.")
            return
        tokens = [t for t in re.split(r'[,\s]+', col_text) if t]
        colors = []
        for t in tokens:
            c = self._get_hex_from_name_or_number(t)
            if c: colors.append(c.upper())
        colors = list(dict.fromkeys(colors))[:4]  
        if not colors:
            print("No valid colors parsed.")
            return
        self.nodes[nid]['domain'] = colors
        if self.nodes[nid]['color'] not in colors:
            self.nodes[nid]['color'] = '#888888'
            self._update_node_color(nid, '#888888')
        if self.selected_for_domain == nid and self.show_domain_panel and self.ax_domain:
            self._render_domain_panel(nid)
        self._update_node_label_text(nid)
        self._capture_bg()
        self._update_status()
        print(f"Domain for node {nid} set to {colors} (max 4).")

    def _reset_domain(self, event):
        nid_text = self.box_dom_id.text.strip()
        try:
            nid = int(nid_text)
        except:
            print("Enter a valid Node ID to reset.")
            return
        if nid in self.nodes:
            self.nodes[nid]['domain'] = list(self.map_colors)
            if self.selected_for_domain == nid and self.show_domain_panel and self.ax_domain:
                self._render_domain_panel(nid)
            self._update_node_label_text(nid)
            self._capture_bg()
            self._update_status()
            print(f"Domain for node {nid} reset to full 4-color palette.")

    def _reset_all_domains(self, event):
        for nid in self.nodes:
            self.nodes[nid]['domain'] = list(self.map_colors)
            self._update_node_label_text(nid)
        if self.selected_for_domain is not None and self.show_domain_panel and self.ax_domain:
            self._render_domain_panel(self.selected_for_domain)
        self._capture_bg()
        self._update_status()
        print("All domains reset to full 4-color palette.")

    def _render_domain_panel(self, nid):
        if not self.show_domain_panel or not self.ax_domain:
            return

        ds = len(self.nodes[nid]['domain']) if (nid in self.nodes) else 0
        self.ax_domain.set_position(self._compute_domain_panel_rect(max(1, ds)))

        self.ax_domain.cla()
        self.ax_domain.set_facecolor('#202020')
        self.ax_domain.set_xticks([]); self.ax_domain.set_yticks([])
        for spine in self.ax_domain.spines.values():
            spine.set_color('#666666')

        title = "Selected Domain:"
        if nid is not None and nid in self.nodes:
            title += f" Node {nid}"
        self.ax_domain.text(0.03, 0.97, title, transform=self.ax_domain.transAxes,
                            fontsize=11, color='white', weight='bold', va='top')

        if nid is None or nid not in self.nodes:
            self.ax_domain.text(0.03, 0.10, "Click a node to view its domain.",
                                transform=self.ax_domain.transAxes,
                                fontsize=10, color='#cccccc', va='bottom')
            self.fig.canvas.draw_idle()
            return

        dom = self.nodes[nid]['domain']
        if not dom:
            self.ax_domain.text(0.03, 0.10, "(empty domain)",
                                transform=self.ax_domain.transAxes,
                                fontsize=10, color='#cccccc', va='bottom')
            self.fig.canvas.draw_idle()
            return

        n = len(dom)
        pad = 0.04
        top_title_space = 0.16
        cols = self._domain_cols_for(n)
        rows = math.ceil(n / cols)

        usable_h = 1.0 - top_title_space - pad
        cell_w = (1.0 - (cols + 1) * pad) / cols
        cell_h = (usable_h - (rows - 1) * pad) / rows
        base_y = pad

        swatch_w = cell_w * 0.42
        swatch_h = cell_h * 0.55
        label_y = 0.84
        fs = max(8, min(12, 7 + 6 * cell_h))

        def palette_index(hex_color):
            h = hex_color.upper()
            try:
                return self.map_colors.index(h) + 1
            except ValueError:
                return None

        for i, c in enumerate(dom):
            r = rows - 1 - (i // cols)
            k = i % cols
            x_cell = pad + k * (cell_w + pad)
            y_cell = base_y + r * (cell_h + pad)

            idx = palette_index(c)
            color_name = self._get_color_name(c)
            label_text = f"{idx}: {color_name}" if idx else color_name

            self.ax_domain.text(x_cell + cell_w / 2,
                                y_cell + cell_h * label_y,
                                label_text, ha='center', va='center',
                                fontsize=fs, color='white')

            x_s = x_cell + (cell_w - swatch_w) / 2
            y_s = y_cell + (cell_h * 0.15)
            rect = patches.Rectangle((x_s, y_s), swatch_w, swatch_h,
                                     facecolor=c, edgecolor='white', linewidth=1.2)
            self.ax_domain.add_patch(rect)

            if idx:
                self.ax_domain.text(x_s + swatch_w - 0.02, y_s + swatch_h - 0.02,
                                    str(idx), ha='right', va='top',
                                    fontsize=max(7, fs - 2), color='white',
                                    bbox=dict(boxstyle="round,pad=0.15",
                                              facecolor='black', alpha=0.6,
                                              edgecolor='white', linewidth=0.8))

        self.fig.canvas.draw_idle()

    def _select_next_var(self, assignment, domains, neighbors):
        unassigned = [v for v in self.nodes if v not in assignment]
        if not unassigned:
            return None

        def dyn_degree(v):
            return sum(nb not in assignment for nb in neighbors[v])

        if self.use_mrv and self.use_degree:
            if self.degree_first:
                maxdeg = max(dyn_degree(v) for v in unassigned)
                pool = [v for v in unassigned if dyn_degree(v) == maxdeg]
                return min(pool, key=lambda v: len(domains[v]))
            else:
                mrv = min(len(domains[v]) for v in unassigned)
                pool = [v for v in unassigned if len(domains[v]) == mrv]
                return max(pool, key=dyn_degree)
        elif self.use_mrv:
            return min(unassigned, key=lambda v: len(domains[v]))
        elif self.use_degree:
            return max(unassigned, key=dyn_degree)
        else:
            return min(unassigned)

    def _is_consistent(self, var, color, assignment, neighbors):
        return all(assignment.get(nb) != color for nb in neighbors[var])

    def _forward_check(self, var, color, domains, neighbors):
        pruned = []
        for nb in neighbors[var]:
            if color in domains[nb] and nb not in [var]:
                if len(domains[nb]) == 1:
                    return None  
                if nb not in domains:
                    continue
                if color in domains[nb]:
                    domains[nb].remove(color)
                    pruned.append((nb, color))
        return pruned

    def _undo_pruned(self, pruned, domains):
        for v, c in pruned or []:
            if c not in domains[v]:
                domains[v].append(c)

    def _backtrack(self, assignment, domains, neighbors):
        if len(assignment) == len(self.nodes):
            return assignment
        var = self._select_next_var(assignment, domains, neighbors)
        if var is None:
            return assignment
        for color in list(domains[var]):
            if not self._is_consistent(var, color, assignment, neighbors):
                continue
            assignment[var] = color
            self.nodes[var]['color'] = color
            self._update_node_color(var, color)
            plt.pause(self.animation_delay)

            pruned = self._forward_check(var, color, domains, neighbors)
            if pruned is not None:
                res = self._backtrack(assignment, domains, neighbors)
                if res is not None:
                    return res
            del assignment[var]
            self.nodes[var]['color'] = '#888888'
            self._update_node_color(var, '#888888')
            self._undo_pruned(pruned, domains)
            plt.pause(max(self.animation_delay*0.6, 0.02))
        return None

    def _auto_color(self, event):
        if not self.nodes:
            return
        for nid in self.nodes:
            if self.nodes[nid]['color'] != '#888888':
                self.nodes[nid]['color'] = '#888888'
                self._update_node_color(nid, '#888888')
        plt.pause(max(self.animation_delay*0.5, 0.02))
        self._capture_bg()  

        neighbors = self._neighbors()
        domains = self._initial_domains()
        assignment = {}
        sol = self._backtrack(assignment, domains, neighbors)
        if sol is None:
            messagebox.showwarning("No Solution Found", 
                      "No valid coloring exists with the current node domains and color palette.\n\n" +
                      "Try:\n" +
                      "• Expanding domains for some nodes\n" +
                      "• Removing some edges\n" +
                      "• Using fewer color constraints")


if __name__ == "__main__":
    MapColoringVisualizer()
