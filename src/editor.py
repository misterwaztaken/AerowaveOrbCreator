"""
editor.py

contains the OrbCreator class, builds and themes the editor
window, handles canvas interaction, layers panel, ui selector
dropdown, etc.

(from Aerowave Orb Creator)
"""

from .common import *
from .helpers import *
from .widgets import *
from .intro import *

class OrbCreator:
    # Screens shorter than this get the compact (controls beside the canvas) arrangement (which may need some extra debugging as I haven't really tested it just yet ;))
    COMPACT_BELOW = 850

    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        
        self.canvas_size = 500
        self.orb_radius = 150
        self.layers = []
        self.selected_layer = None
        
        # Interaction state
        self.dragging = False
        self.scaling = False
        self.scaling_x = False
        self.scaling_y = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.snap_threshold = 15
        self.scale_handles = []
        
        self.preview_photo = None 
        self.btn_images = {}
        self.btn_images_flipped = {}

        # Saved UI theme (config.aero)
        self.config = load_config()
        start_theme = self.config.get("theme", "Dark")
        if start_theme not in THEMES:
            start_theme = "Dark"
        self.current_theme = start_theme
        
        self.labels = []
        self.scales = []
        self.managed_buttons = []
        self.managed_button_labels = []
        self.left_widgets = []
        self.right_widgets = []

        # Overlays (UI selector drop-down / pop-up dialog)
        self.dd = None
        self.dlg = None
        self.fsd = None
        self.cpk = None
        self._orb_src = {}
        self._orb_cache = {}
        self._keep = []
        
        self.compact = self.root.winfo_screenheight() < self.COMPACT_BELOW
        self.setup_ui()
        self.apply_theme(start_theme)
        if "theme" not in self.config or self.config.get("theme") != start_theme:
            self.config["theme"] = start_theme
            save_config(self.config)

        # Always fullscreen, never windowed
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)
        self.root.bind("<Escape>", self._on_escape)
        self.root.bind("<F11>", lambda e: "break")
        self.root.bind_all("<Button-1>", self._on_any_click, add="+")
        self.enforce_fullscreen()
        
    def setup_ui(self):
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left Panel (Gradient Canvas)
        self.left_panel = GradientPanel(main_frame)
        self.left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 10), pady=10)
        self.left_panel.bind("<Configure>", lambda e: self.root.after(10, self.sync_widget_colors), add="+")
        
        top_bar = tk.Frame(self.left_panel, bd=0)
        top_bar.pack(fill=tk.X, pady=(0, 10))
        self.left_widgets.append(top_bar)
        
        self.ui_btn = self.create_themed_button(top_bar, "UI Selector", self.toggle_ui_selector, 120)
        self.ui_btn.pack(side=tk.LEFT, padx=5)
        self.create_themed_button(top_bar, "Exit", self.exit_app, 80).pack(side=tk.RIGHT, padx=5)

        brand = tk.Frame(top_bar, bd=0)
        brand.place(relx=0.5, rely=0.5, anchor="center")
        lbl_b1 = tk.Label(brand, text="Aerowave", font=('Segoe UI', 15))
        lbl_b1.pack(side=tk.LEFT)
        lbl_b2 = tk.Label(brand, text=" Orb Creator", font=('Segoe UI', 15, 'bold italic'))
        lbl_b2.pack(side=tk.LEFT)
        self.labels.extend([lbl_b1, lbl_b2])

        # In compact mode the canvas and the controls sit side by side
        if self.compact:
            workspace = tk.Frame(self.left_panel, bd=0)
            workspace.pack(fill=tk.X)
            self.left_widgets.append(workspace)
            side = tk.Frame(self.left_panel, bd=0)
            self.left_widgets.append(side)
            canvas_host, ctl_host = workspace, side
        else:
            workspace = side = None
            canvas_host, ctl_host = self.left_panel, self.left_panel

        # Orb Drawing Canvas
        self.canvas_frame = tk.Frame(self.left_panel, bg='#1a1a1a', bd=0)
        if self.compact:
            self.canvas_frame.pack(in_=workspace, side=tk.LEFT, expand=True, padx=(0, 15), pady=5, anchor="ne")
            side.pack(in_=workspace, side=tk.LEFT, expand=True, padx=(15, 0), anchor="nw")
        else:
            self.canvas_frame.pack(pady=5)
        self.left_widgets.append(self.canvas_frame)
        
        self.canvas = tk.Canvas(self.canvas_frame, width=self.canvas_size, height=self.canvas_size, 
                                bg='#1a1a1a', highlightthickness=0)
        self.canvas.pack(padx=2, pady=2)
        self.draw_checkerboard()
        
        self.snap_line_h = self.canvas.create_line(0, self.canvas_size//2, self.canvas_size, 
                                                   self.canvas_size//2, fill='red', width=1, state='hidden')
        self.snap_line_v = self.canvas.create_line(self.canvas_size//2, 0, self.canvas_size//2, 
                                                   self.canvas_size, fill='red', width=1, state='hidden')
        
        # Controls Frame
        controls_frame = tk.Frame(self.left_panel, bd=0)
        controls_frame.pack(in_=ctl_host, fill=tk.X, pady=5)
        self.left_widgets.append(controls_frame)
        controls_row = tk.Frame(controls_frame, bd=0)
        controls_row.pack()
        
        self.create_themed_button(controls_row, "Orb", self.create_orb, 80).pack(side=tk.LEFT, padx=5)
        self.create_themed_button(controls_row, "Orb Color", self.choose_color, 100).pack(side=tk.LEFT, padx=5)
        self.create_themed_button(controls_row, "Reflection", self.create_reflection, 100).pack(side=tk.LEFT, padx=5)
        self.create_themed_button(controls_row, "Glow", self.create_glow, 80).pack(side=tk.LEFT, padx=5)
        
        # Layer Properties Panel
        prop_outer = tk.Frame(self.left_panel, bd=0)
        prop_outer.pack(in_=ctl_host, fill=tk.X, pady=10, ipadx=5, ipady=5)
        self.left_widgets.append(prop_outer)
        prop_frame = tk.Frame(prop_outer, bd=0)
        prop_frame.pack()
        slider_len = 190 if self.compact else 250
        
        lbl_g_scale = tk.Label(prop_frame, text="Grad Y Scale:")
        lbl_g_scale.grid(row=0, column=0, sticky='e', padx=5, pady=2)
        self.labels.append(lbl_g_scale)
        
        self.var_grad_y_scale = tk.DoubleVar(value=1.0)
        scale_g_y = tk.Scale(prop_frame, variable=self.var_grad_y_scale, from_=0.1, to=5.0, resolution=0.1, orient=tk.HORIZONTAL, command=self.on_prop_change, bd=0, length=slider_len)
        scale_g_y.grid(row=0, column=1, sticky='ew', padx=5)
        self.scales.append(scale_g_y)
        
        lbl_g_pos = tk.Label(prop_frame, text="Grad Y Offset:")
        lbl_g_pos.grid(row=0, column=2, sticky='e', padx=5, pady=2)
        self.labels.append(lbl_g_pos)
        
        self.var_grad_y_pos = tk.DoubleVar(value=0)
        scale_g_pos = tk.Scale(prop_frame, variable=self.var_grad_y_pos, from_=-200, to=200, resolution=1, orient=tk.HORIZONTAL, command=self.on_prop_change, bd=0, length=slider_len)
        scale_g_pos.grid(row=0, column=3, sticky='ew', padx=5)
        self.scales.append(scale_g_pos)
        
        self.create_themed_button(prop_frame, "Custom Gradient Color", self.choose_custom_grad, 160).grid(row=1, column=0, columnspan=2, pady=5)
        self.create_themed_button(prop_frame, "Default Gradient Color", self.default_grad, 160).grid(row=1, column=2, columnspan=2, pady=5)
        
        lbl_glow_bright = tk.Label(prop_frame, text="Glow Brightness:")
        lbl_glow_bright.grid(row=2, column=0, sticky='e', padx=5, pady=5)
        self.labels.append(lbl_glow_bright)
        
        self.var_glow_opacity = tk.DoubleVar(value=220)
        scale_glow = tk.Scale(prop_frame, variable=self.var_glow_opacity, from_=0, to=255, resolution=1, orient=tk.HORIZONTAL, command=self.on_prop_change, bd=0, length=slider_len)
        scale_glow.grid(row=2, column=1, columnspan=3, sticky='ew', padx=5)
        self.scales.append(scale_glow)
        
        prop_frame.grid_columnconfigure(1, weight=1)
        prop_frame.grid_columnconfigure(3, weight=1)

        # Export Frame
        export_frame = tk.Frame(self.left_panel, bd=0)
        export_frame.pack(in_=ctl_host, fill=tk.X, pady=10)
        self.left_widgets.append(export_frame)
        export_row = tk.Frame(export_frame, bd=0)
        export_row.pack()
        
        lbl_exp = tk.Label(export_row, text="Export Res:")
        lbl_exp.pack(side=tk.LEFT, padx=5)
        self.labels.append(lbl_exp)
        
        self.resolution_var = tk.StringVar(value="1080")
        self.res_entry = tk.Entry(export_row, textvariable=self.resolution_var, width=8)
        self.res_entry.pack(side=tk.LEFT, padx=5, ipady=3)
        self.create_themed_button(export_row, "Save Orb", self.save_orb, 100).pack(side=tk.LEFT, padx=15)
        
        # Right Panel (Gradient Canvas)
        self.right_panel = GradientPanel(main_frame, width=250)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.Y, pady=10, padx=(0, 10))
        self.right_panel.pack_propagate(False)
        self.right_panel.bind("<Configure>", lambda e: self.root.after(10, self.sync_widget_colors), add="+")
        
        lbl_layers = tk.Label(self.right_panel, text="LAYERS", font=('Arial', 12, 'bold'))
        lbl_layers.pack(pady=10)
        self.labels.append(lbl_layers)
        self.right_widgets.append(lbl_layers)
        
        self.layers_frame = tk.Frame(self.right_panel, bd=0)
        self.layers_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.right_widgets.append(self.layers_frame)
        
        self.canvas.bind('<Button-1>', self.on_canvas_click)
        self.canvas.bind('<B1-Motion>', self.on_canvas_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_canvas_release)
        
    def create_themed_button(self, parent, text, command, width=120, height=30):
        lbl = tk.Label(parent, text=text, cursor="hand2", font=('Arial', 9, 'bold'), compound="center", bd=0, highlightthickness=0)
        
        def on_press(e):
            lbl.config(image=self.btn_images_flipped[lbl])
        def on_release(e):
            lbl.config(image=self.btn_images[lbl])
            if 0 <= e.x <= lbl.winfo_width() and 0 <= e.y <= lbl.winfo_height():
                command()
                
        lbl.bind("<ButtonPress-1>", on_press)
        lbl.bind("<ButtonRelease-1>", on_release)
        
        self.managed_buttons.append((lbl, text, width, height))
        self.managed_button_labels.append(lbl)
        return lbl

    def get_gradient_color(self, top_hex, bot_hex, ratio):
        r1, g1, b1 = int(top_hex[1:3], 16), int(top_hex[3:5], 16), int(top_hex[5:7], 16)
        r2, g2, b2 = int(bot_hex[1:3], 16), int(bot_hex[3:5], 16), int(bot_hex[5:7], 16)
        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)
        return f"#{r:02x}{g:02x}{b:02x}"

    def apply_bg_to_tree(self, widget, bg_col, t):
        if getattr(widget, 'is_layer_item', False): return
        if widget == self.canvas_frame or widget == self.canvas: return
        if isinstance(widget, tk.Entry): return          # entries get their own theme colours (style_entry)
            
        try:
            if isinstance(widget, tk.Label) and widget in self.managed_button_labels:
                widget.config(bg=bg_col, activebackground=bg_col)
            elif not isinstance(widget, ttk.Combobox):
                widget.config(bg=bg_col)
        except: pass
        
        for child in widget.winfo_children():
            self.apply_bg_to_tree(child, bg_col, t)

    def sync_widget_colors(self):
        t = THEMES[self.current_theme]
        
        h_left = self.left_panel.winfo_height()
        if h_left > 10:
            for widget in self.left_widgets:
                if not widget.winfo_exists(): continue
                wy = widget.winfo_y() + widget.winfo_height() / 2
                ratio = min(1.0, max(0.0, wy / h_left))
                bg_col = self.get_gradient_color(t["ui_top"], t["ui_bot"], ratio)
                self.apply_bg_to_tree(widget, bg_col, t)
                
        try:                                                    # decorations live only in the empty area below the widgets
            bottoms = [w.winfo_y() + w.winfo_height() for w in self.left_widgets if w.winfo_exists() and w.winfo_ismapped()]
            if bottoms:
                self.left_panel.set_decor_top(max(bottoms))
        except tk.TclError:
            pass

        h_right = self.right_panel.winfo_height()
        if h_right > 10:
            for widget in self.right_widgets:
                if not widget.winfo_exists(): continue
                wy = widget.winfo_y() + widget.winfo_height() / 2
                ratio = min(1.0, max(0.0, wy / h_right))
                bg_col = self.get_gradient_color(t["layer_top"], t["layer_bot"], ratio)
                self.apply_bg_to_tree(widget, bg_col, t)

    def apply_theme(self, theme_name):
        t = THEMES[theme_name]
        self.current_theme = theme_name
        self.root.configure(bg=t["ui_top"]) # Window background fallback
        
        self.left_panel.set_colors(t["ui_top"], t["ui_bot"], t.get("decor"))
        self.right_panel.set_colors(t["layer_top"], t["layer_bot"])
        
        for l in self.labels:
            l.configure(fg=t["fg"])
        for s in self.scales:
            s.configure(fg=t["fg"], highlightthickness=0)
            
        self.btn_images.clear()
        self.btn_images_flipped.clear()
        
        for lbl, text, w, h in self.managed_buttons:
            # Normal State Image
            img_norm = create_gradient_rect(w, h, t["btn_top"], t["btn_bot"], t["radius"], 
                                            outline_color=t.get("btn_outline"), mid_color=t.get("btn_mid"), flipped=False)
            photo_norm = ImageTk.PhotoImage(img_norm)
            self.btn_images[lbl] = photo_norm
            
            # Pressed/Flipped State Image
            img_flip = create_gradient_rect(w, h, t["btn_top"], t["btn_bot"], t["radius"], 
                                            outline_color=t.get("btn_outline"), mid_color=t.get("btn_mid"), flipped=True)
            photo_flip = ImageTk.PhotoImage(img_flip)
            self.btn_images_flipped[lbl] = photo_flip
            
            lbl.config(image=photo_norm, fg=t["btn_fg"])
                       
        self.style_entry(self.res_entry)
        self.update_layers_panel()
        self.root.after(20, self.sync_widget_colors)

    def style_entry(self, e, font=('Segoe UI', 10)):
        g = GLASS[self.current_theme]
        acc = "#%02x%02x%02x" % g["accent"]
        e.configure(bg=g["entry_bg"], fg=g["entry_fg"], insertbackground=g["entry_fg"], relief="flat", bd=0,
                    highlightthickness=1, highlightbackground=g["edge"], highlightcolor=acc,
                    selectbackground=g["list_sel"], selectforeground=g["list_sel_fg"], font=font)

    def draw_checkerboard(self):
        square_size = 20
        for i in range(0, self.canvas_size, square_size):
            for j in range(0, self.canvas_size, square_size):
                color = '#1a1a1a' if (i // square_size + j // square_size) % 2 == 0 else '#252525'
                self.canvas.create_rectangle(i, j, i + square_size, j + square_size, fill=color, outline='')

    def on_prop_change(self, *args):
        refl = next((l for l in self.layers if l.type == 'reflection'), None)
        if refl:
            refl.grad_y_scale = self.var_grad_y_scale.get()
            refl.grad_y_offset = self.var_grad_y_pos.get()
            
        glow = next((l for l in self.layers if l.type == 'glow'), None)
        if glow:
            glow.glow_opacity = int(self.var_glow_opacity.get())
            
        self.render_canvas()

    def choose_custom_grad(self):
        refl = next((l for l in self.layers if l.type == 'reflection'), None)
        if not refl:
            return
        orb = next((l for l in self.layers if l.type == 'orb'), None)
        base = orb.color if orb else (255, 255, 255)
        initial = refl.custom_grad_color or tuple(min(255, int(c + (255 - c) * 0.55)) for c in base)

        def done(rgb):
            refl.custom_grad_color = tuple(rgb)
            self.render_canvas()
        self.open_color_picker("Gradient Color", initial, done)

    def default_grad(self):
        refl = next((l for l in self.layers if l.type == 'reflection'), None)
        if refl:
            refl.custom_grad_color = None
            self.render_canvas()

    def create_orb(self):
        self.layers = [l for l in self.layers if l.type != 'orb']
        orb = OrbLayer("Orb", "orb")
        self.layers.insert(0, orb)
        self.update_layers_panel()
        self.render_canvas()

    def create_reflection(self):
        self.layers = [l for l in self.layers if l.type != 'reflection']
        ref = OrbLayer("Reflection", "reflection")
        ref.y = self.canvas_size // 2 - 40
        self.layers.append(ref)
        self.select_layer(ref)
        self.update_layers_panel()
        self.render_canvas()

    def create_glow(self):
        self.layers = [l for l in self.layers if l.type != 'glow']
        glow = OrbLayer("Glow", "glow")
        glow.glow_opacity = int(self.var_glow_opacity.get())
        glow.y = self.canvas_size // 2 + 50
        self.layers.insert(1, glow)
        self.select_layer(glow)
        self.update_layers_panel()
        self.render_canvas()

    def choose_color(self):
        orb_layer = next((l for l in self.layers if l.type == 'orb'), None)
        if not orb_layer: return

        def done(rgb):
            orb_layer.color = tuple(rgb)
            self.render_canvas()
        self.open_color_picker("Orb Color", tuple(orb_layer.color), done)

    def update_layers_panel(self):
        for widget in self.layers_frame.winfo_children():
            widget.destroy()
        for i, layer in enumerate(reversed(self.layers)):
            self.create_layer_item(layer, len(self.layers) - 1 - i)
        self.root.after(10, self.sync_widget_colors)

    def create_layer_item(self, layer, index):
        t = THEMES[self.current_theme]
        selected = (self.selected_layer == layer)
        bg_col = t["layer_sel"] if selected else t["layer_bg"]
        fg_col = "black" if self.current_theme == "Aqua" else "white"
        fg_col = t.get("layer_fg", fg_col)
        if selected:
            fg_col = t.get("layer_sel_fg", fg_col)
        
        frame = tk.Frame(self.layers_frame, bg=bg_col, relief=tk.RAISED, bd=1)
        frame.pack(fill=tk.X, pady=2, padx=5)
        frame.is_layer_item = True
        frame.bind('<Button-1>', lambda e, l=layer: self.select_layer(l))
        
        eye = "👁️" if layer.visible else "⚫"
        eye_btn = tk.Label(frame, text=eye, bg=bg_col, fg=fg_col, cursor='hand2')
        eye_btn.pack(side=tk.RIGHT, padx=5)
        eye_btn.is_layer_item = True
        eye_btn.bind('<Button-1>', lambda e, l=layer: self.toggle_visibility(l))
        
        name_label = tk.Label(frame, text=layer.name, bg=bg_col, fg=fg_col, anchor='w')
        name_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, pady=5)
        name_label.is_layer_item = True
        name_label.bind('<Button-1>', lambda e, l=layer: self.select_layer(l))

    def toggle_visibility(self, layer):
        layer.visible = not layer.visible
        self.update_layers_panel()
        self.render_canvas()

    def select_layer(self, layer):
        self.selected_layer = layer
        if layer.type == 'reflection':
            self.var_grad_y_scale.set(layer.grad_y_scale)
            self.var_grad_y_pos.set(layer.grad_y_offset)
        elif layer.type == 'glow':
            self.var_glow_opacity.set(layer.glow_opacity)
            
        self.update_layers_panel()
        self.render_canvas()

    def render_composition(self, size):
        scale = size / self.canvas_size
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        if not self.layers: return img

        orb_layer = next((l for l in self.layers if l.type == 'orb'), None)
        master_mask = None

        if orb_layer and orb_layer.visible:
            master_mask = Image.new('L', (size, size), 0)
            r = int(self.orb_radius * orb_layer.scale * scale)
            x, y = int(orb_layer.x * scale), int(orb_layer.y * scale)
            ImageDraw.Draw(master_mask).ellipse([x-r, y-r, x+r, y+r], fill=255)

        for layer in self.layers:
            if not layer.visible: continue
            
            layer_img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(layer_img)
            x, y = int(layer.x * scale), int(layer.y * scale)

            if layer.type == 'orb':
                r = int(self.orb_radius * layer.scale * scale)
                draw.ellipse([x-r, y-r, x+r, y+r], fill=layer.color + (255,))
                img = Image.alpha_composite(img, layer_img)

            elif layer.type == 'reflection':
                w = max(1, int(self.orb_radius * 0.75 * layer.scale_x * scale))
                h = max(1, int(self.orb_radius * 0.6 * layer.scale_y * scale))
                base_col = orb_layer.color if orb_layer else (255, 255, 255)
                
                if layer.custom_grad_color:
                    lighter = layer.custom_grad_color
                else:
                    lighter = tuple(min(255, int(c + (255-c)*0.55)) for c in base_col)
                
                H = h * 2
                grad_1d = Image.new('RGBA', (1, H))
                for gy in range(H):
                    centered_y = gy - (H / 2)
                    scaled_y = centered_y / layer.grad_y_scale
                    shifted_y = scaled_y + (H / 2) - layer.grad_y_offset
                    
                    prog = shifted_y / H
                    prog = max(0.0, min(1.0, prog)) 
                    
                    cr = int(255 * (1-prog) + lighter[0] * prog)
                    cg = int(255 * (1-prog) + lighter[1] * prog)
                    cb = int(255 * (1-prog) + lighter[2] * prog)
                    ca = int(255 * (1-prog) + 30 * prog) 
                    grad_1d.putpixel((0, gy), (cr, cg, cb, ca))
                
                grad = grad_1d.resize((w*2, H))
                oval_mask = Image.new('L', (w*2, H), 0)
                ImageDraw.Draw(oval_mask).ellipse([0, 0, w*2-1, H-1], fill=255)
                grad.putalpha(ImageChops.multiply(grad.getchannel('A'), oval_mask))
                
                layer_img.paste(grad, (x-w, y-h), grad)
                
                if master_mask:
                    layer_img.putalpha(ImageChops.multiply(layer_img.getchannel('A'), master_mask))
                img = Image.alpha_composite(img, layer_img)

            elif layer.type == 'glow':
                r = int(self.orb_radius * 0.65 * layer.scale * scale)
                draw.ellipse([x-r, y-r, x+r, y+r], fill=(255, 255, 255, int(layer.glow_opacity)))
                layer_img = layer_img.filter(ImageFilter.GaussianBlur(radius=r*0.4))
                
                if master_mask:
                    layer_img.putalpha(ImageChops.multiply(layer_img.getchannel('A'), master_mask))
                img = Image.alpha_composite(img, layer_img)

        return img

    def render_canvas(self):
        self.canvas.delete('render')
        self.canvas.delete('bbox')
        
        comp = self.render_composition(self.canvas_size)
        self.preview_photo = ImageTk.PhotoImage(comp)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.preview_photo, tags='render')
        
        if self.selected_layer and self.selected_layer.visible:
            self.draw_bounding_box(self.selected_layer)

    def get_layer_bounds(self, layer):
        if layer.type == 'orb':
            r = self.orb_radius * layer.scale
            return (layer.x - r, layer.y - r, layer.x + r, layer.y + r)
        elif layer.type == 'reflection':
            w = self.orb_radius * 0.75 * layer.scale_x
            h = self.orb_radius * 0.6 * layer.scale_y
            return (layer.x - w, layer.y - h, layer.x + w, layer.y + h)
        elif layer.type == 'glow':
            r = self.orb_radius * 0.65 * layer.scale
            return (layer.x - r, layer.y - r, layer.x + r, layer.y + r)

    def draw_bounding_box(self, layer):
        bounds = self.get_layer_bounds(layer)
        if not bounds: return
        x1, y1, x2, y2 = bounds
        
        self.canvas.create_rectangle(x1, y1, x2, y2, outline='cyan', width=1, dash=(4, 4), tags='bbox')
        
        corners = [(x1, y1, 'corner'), (x2, y1, 'corner'), (x2, y2, 'corner'), (x1, y2, 'corner')]
        if layer.type == 'reflection':
            corners.extend([((x1+x2)/2, y1, 'top'), (x2, (y1+y2)/2, 'right'), 
                            ((x1+x2)/2, y2, 'bottom'), (x1, (y1+y2)/2, 'left')])
            
        self.scale_handles = []
        for hx, hy, htype in corners:
            h = self.canvas.create_rectangle(hx-4, hy-4, hx+4, hy+4, fill='cyan', outline='white', tags='bbox')
            self.scale_handles.append((h, htype))

    def on_canvas_click(self, event):
        if not self.selected_layer: return
        
        for handle, htype in self.scale_handles:
            coords = self.canvas.coords(handle)
            if coords and (coords[0]-5 <= event.x <= coords[2]+5) and (coords[1]-5 <= event.y <= coords[3]+5):
                self.scaling = (htype == 'corner')
                self.scaling_x = (htype in ['left', 'right'])
                self.scaling_y = (htype in ['top', 'bottom'])
                
                self.initial_scale = self.selected_layer.scale
                self.initial_scale_x = self.selected_layer.scale_x
                self.initial_scale_y = self.selected_layer.scale_y
                self.scale_start_dist = math.hypot(event.x - self.selected_layer.x, event.y - self.selected_layer.y)
                self.scale_start_x = event.x
                self.scale_start_y = event.y
                return
                
        bounds = self.get_layer_bounds(self.selected_layer)
        if bounds and (bounds[0] <= event.x <= bounds[2]) and (bounds[1] <= event.y <= bounds[3]):
            self.dragging = True
            self.drag_offset_x = event.x - self.selected_layer.x
            self.drag_offset_y = event.y - self.selected_layer.y

    def on_canvas_drag(self, event):
        if not self.selected_layer: return
        
        if self.scaling:
            dist = math.hypot(event.x - self.selected_layer.x, event.y - self.selected_layer.y)
            if self.scale_start_dist > 0:
                factor = dist / self.scale_start_dist
                if self.selected_layer.type == 'reflection':
                    self.selected_layer.scale_x = max(0.1, self.initial_scale_x * factor)
                    self.selected_layer.scale_y = max(0.1, self.initial_scale_y * factor)
                else:
                    self.selected_layer.scale = max(0.1, self.initial_scale * factor)
        
        elif self.scaling_x and self.scale_start_x != self.selected_layer.x:
            factor = abs(event.x - self.selected_layer.x) / abs(self.scale_start_x - self.selected_layer.x)
            self.selected_layer.scale_x = max(0.1, self.initial_scale_x * factor)
            
        elif self.scaling_y and self.scale_start_y != self.selected_layer.y:
            factor = abs(event.y - self.selected_layer.y) / abs(self.scale_start_y - self.selected_layer.y)
            self.selected_layer.scale_y = max(0.1, self.initial_scale_y * factor)
            
        elif self.dragging:
            nx, ny = event.x - self.drag_offset_x, event.y - self.drag_offset_y
            center = self.canvas_size // 2
            
            if abs(nx - center) < self.snap_threshold:
                nx = center
                self.canvas.itemconfig(self.snap_line_v, state='normal')
            else:
                self.canvas.itemconfig(self.snap_line_v, state='hidden')
                
            if abs(ny - center) < self.snap_threshold:
                ny = center
                self.canvas.itemconfig(self.snap_line_h, state='normal')
            else:
                self.canvas.itemconfig(self.snap_line_h, state='hidden')
                
            self.selected_layer.x, self.selected_layer.y = nx, ny
            
        self.render_canvas()

    def on_canvas_release(self, event):
        self.dragging = self.scaling = self.scaling_x = self.scaling_y = False
        self.canvas.itemconfig(self.snap_line_h, state='hidden')
        self.canvas.itemconfig(self.snap_line_v, state='hidden')

    # ==================================================================================
    #  Fullscreen / exit
    # ==================================================================================
    def enforce_fullscreen(self):
        try:
            if not self.root.attributes("-fullscreen"):
                self.root.attributes("-fullscreen", True)
        except tk.TclError:
            pass
        self.root.after(700, self.enforce_fullscreen)

    def exit_app(self):
        """Exit button / Alt+F4: play the outro animation, then quit."""
        if getattr(self, "_exiting", False):
            return
        self._exiting = True
        for fn in (lambda: self.close_ui_selector(immediate=True), lambda: self._dlg_close(immediate=True),
                   lambda: self._fsd_destroy(), lambda: self._cpk_destroy()):
            try:
                fn()
            except Exception:
                pass
        intro = getattr(self.root, "intro", None)
        if intro is not None and getattr(intro, "running", False):      # still in the intro: just leave
            self._really_exit()
            return
        try:
            AeroOutro(self.root, self._really_exit).start()
        except Exception:
            self._really_exit()

    def _really_exit(self):
        try:
            if winsound is not None:
                winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def _on_escape(self, e=None):
        if getattr(self, 'cpk', None) is not None:
            self._cpk_close(None)
        elif getattr(self, 'fsd', None) is not None:
            self._fsd_escape()
        elif self.dlg is not None:
            self._dlg_close()
        elif self.dd is not None:
            self.close_ui_selector()
        return "break"

    def _on_any_click(self, e):
        if self.dd is not None and e.widget is not self.dd["canvas"] and e.widget is not self.ui_btn:
            self.close_ui_selector()

    # ==================================================================================
    #  Screen snapshot (used for the frosted-glass look of overlays)
    # ==================================================================================
    def snapshot_root(self):
        if ImageGrab is None:
            return None
        try:
            self.root.update_idletasks()
            self.root.update()
            rx, ry = self.root.winfo_rootx(), self.root.winfo_rooty()
            rw, rh = self.root.winfo_width(), self.root.winfo_height()
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            shot = ImageGrab.grab().convert("RGB")
            fx, fy = shot.width / float(sw), shot.height / float(sh)
            shot = shot.crop((int(rx * fx), int(ry * fy), int((rx + rw) * fx), int((ry + rh) * fy)))
            if shot.size != (rw, rh):
                shot = shot.resize((rw, rh), Image.LANCZOS)
            return shot
        except Exception:
            return None

    def _fallback_snapshot(self, rw, rh):
        t = THEMES[self.current_theme]
        img = Image.new("RGB", (1, rh))
        c1, c2 = hex_to_rgb(t["ui_top"]), hex_to_rgb(t["ui_bot"])
        for y in range(rh):
            k = y / max(1, rh - 1)
            img.putpixel((0, y), tuple(int(c1[i] + (c2[i] - c1[i]) * k) for i in range(3)))
        return img.resize((rw, rh))

    # ==================================================================================
    #  UI Selector drop-down
    # ==================================================================================
    DD_PW, DD_SLOT, DD_PAD, DD_ORB, DD_ORB_HOVER = 150, 104, 14, 90, 100

    def _theme_orb(self, name, size):
        key = (name, size)
        if key in self._orb_cache:
            return self._orb_cache[key]
        if name not in self._orb_src:
            src = None
            p = asset_path("image/" + THEME_ORBS[name])
            if p:
                try:
                    im = Image.open(p).convert("RGBA")
                    bb = im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
                    src = im.crop(bb) if bb else im
                except Exception:
                    src = None
            if src is None:                                     # artwork missing: draw a simple orb
                t = THEMES[name]
                N = 400
                src = Image.new("RGBA", (N, N), (0, 0, 0, 0))
                orb = create_gradient_rect(N, N, t["btn_top"], t["btn_bot"], N // 2, outline_color=t.get("btn_outline"))
                src.alpha_composite(orb)
                ImageDraw.Draw(src).text((N // 2, N // 2), name, font=get_font(70, True), fill=(255, 255, 255, 255), anchor="mm")
            self._orb_src[name] = src
        out = self._orb_src[name].resize((size, size), Image.LANCZOS)
        self._orb_cache[key] = out
        return out

    def toggle_ui_selector(self):
        if self.dd is not None:
            self.close_ui_selector()
        else:
            self.open_ui_selector()

    def open_ui_selector(self):
        if self.dd is not None or self.dlg is not None or self.fsd is not None or self.cpk is not None:
            return
        snap = self.snapshot_root()
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        if snap is None:
            snap = self._fallback_snapshot(rw, rh)
        btn = self.ui_btn
        bx = btn.winfo_rootx() - self.root.winfo_rootx()
        by = btn.winfo_rooty() - self.root.winfo_rooty()
        PW = self.DD_PW
        PH = self.DD_PAD * 2 + self.DD_SLOT * len(THEME_ORDER) - 8
        x, y, M = bx, by + btn.winfo_height() + 8, 66
        rx0, ry0 = max(0, x - M), max(0, y - M)
        rx1, ry1 = min(rw, x + PW + M), min(rh, y + PH + M)
        backdrop = snap.crop((rx0, ry0, rx1, ry1))
        box = (x - rx0, y - ry0, x - rx0 + PW, y - ry0 + PH)
        st = GLASS[self.current_theme]
        panel = glass_panel(backdrop, box, 18, st)

        cv = tk.Canvas(self.root, width=rx1 - rx0, height=ry1 - ry0, highlightthickness=0, bd=0, cursor="hand2")
        cv.place(x=rx0, y=ry0)
        tk.Misc.tkraise(cv)
        photo = ImageTk.PhotoImage(backdrop)
        item = cv.create_image(0, 0, anchor="nw", image=photo)
        self.dd = dict(canvas=cv, photo=photo, item=item, backdrop=backdrop, panel=panel, box=box,
                       hover=None, origin=(rx0, ry0), closing=False)
        cv.bind("<Motion>", self._dd_motion)
        cv.bind("<Leave>", lambda e: self._dd_set_hover(None))
        cv.bind("<ButtonPress-1>", self._dd_click)

        final = self._dd_draw(None)
        self._dd_fade(backdrop, final, 7, opening=True)

    def _dd_slot_rect(self, i):
        x0, y0, x1, y1 = self.dd["box"]
        top = y0 + self.DD_PAD + i * self.DD_SLOT
        return (x0 + 10, top, x1 - 10, top + self.DD_SLOT - 8)

    def _dd_draw(self, hover):
        dd = self.dd
        img = dd["panel"].convert("RGBA")
        st = GLASS[self.current_theme]
        for i, name in enumerate(THEME_ORDER):
            sx0, sy0, sx1, sy1 = self._dd_slot_rect(i)
            selected = (name == self.current_theme)
            if selected or hover == i:
                S = 3
                w, h = sx1 - sx0, sy1 - sy0
                pill = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
                pd = ImageDraw.Draw(pill)
                if selected:
                    pd.rounded_rectangle([0, 0, w * S - 1, h * S - 1], radius=16 * S,
                                         fill=st["accent"] + (70,), outline=st["accent"] + (230,), width=2 * S)
                else:
                    pd.rounded_rectangle([0, 0, w * S - 1, h * S - 1], radius=16 * S,
                                         fill=st["pill"] + (58,), outline=st["pill"] + (120,), width=S)
                pill = pill.resize((w, h), Image.LANCZOS)
                img.alpha_composite(pill, (sx0, sy0))
            size = self.DD_ORB_HOVER if hover == i else self.DD_ORB
            orb = self._theme_orb(name, size)
            cx, cy = (sx0 + sx1) // 2, (sy0 + sy1) // 2
            if hover == i:
                glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
                ImageDraw.Draw(glow).ellipse([cx - size // 2 - 4, cy - size // 2 - 4, cx + size // 2 + 4, cy + size // 2 + 4],
                                             fill=st["accent"] + (110,))
                glow = glow.filter(ImageFilter.GaussianBlur(9))
                img.alpha_composite(glow)
            img.alpha_composite(orb, (cx - size // 2, cy - size // 2))
        return img.convert("RGB")

    def _dd_show(self, im):
        dd = self.dd
        if dd is None:
            return
        dd["photo"] = ImageTk.PhotoImage(im)
        dd["canvas"].itemconfig(dd["item"], image=dd["photo"])

    def _dd_fade(self, a_img, b_img, frames, opening):
        dd = self.dd
        if dd is None:
            return
        state = {"i": 0}

        def step():
            d = self.dd
            if d is None or d is not dd:
                return
            state["i"] += 1
            k = smooth(state["i"] / float(frames))
            self._dd_show(Image.blend(a_img, b_img, k if opening else 1.0 - k))
            if state["i"] < frames:
                self.root.after(14, step)
            elif not opening:
                self._dd_destroy()
        step()

    def _dd_index_at(self, x, y):
        for i in range(len(THEME_ORDER)):
            sx0, sy0, sx1, sy1 = self._dd_slot_rect(i)
            if sx0 <= x <= sx1 and sy0 <= y <= sy1:
                return i
        return None

    def _dd_motion(self, e):
        self._dd_set_hover(self._dd_index_at(e.x, e.y))

    def _dd_set_hover(self, idx):
        dd = self.dd
        if dd is None or dd["closing"] or dd["hover"] == idx:
            return
        dd["hover"] = idx
        self._dd_show(self._dd_draw(idx))

    def _dd_click(self, e):
        idx = self._dd_index_at(e.x, e.y)
        if idx is not None:
            self.close_ui_selector(immediate=True)
            self.set_theme(THEME_ORDER[idx])
        else:
            self.close_ui_selector()

    def _dd_destroy(self):
        dd, self.dd = self.dd, None
        if dd:
            try:
                dd["canvas"].destroy()
            except tk.TclError:
                pass

    def close_ui_selector(self, immediate=False):
        dd = self.dd
        if dd is None or dd["closing"]:
            return
        if immediate:
            self._dd_destroy()
            return
        dd["closing"] = True
        self._dd_fade(dd["backdrop"], self._dd_draw(dd["hover"]), 5, opening=False)

    def set_theme(self, name):
        if name not in THEMES:
            return
        self.apply_theme(name)
        self.config["theme"] = name
        save_config(self.config)

    # ==================================================================================
    #  Aero pop-up dialog (themed, frosted glass over a blurred snapshot of the editor)
    # ==================================================================================
    def show_aero_dialog(self, title, message, details=(), kind="success", thumb=None, buttons=None):
        if self.dlg is not None:
            self._dlg_close(immediate=True)
        self.close_ui_selector(immediate=True)
        snap = self.snapshot_root()
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        if snap is None:
            snap = self._fallback_snapshot(rw, rh)
        st = GLASS[self.current_theme]
        t = THEMES[self.current_theme]
        dim = make_dim(snap, st)

        PW, PH = 640, 290
        x0, y0 = (rw - PW) // 2, (rh - PH) // 2 - 10
        box = (x0, y0, x0 + PW, y0 + PH)
        scene = glass_panel(dim, box, 24, st).convert("RGBA")

        # --- artwork + text ---------------------------------------------------------
        TX = x0 + 236
        d = ImageDraw.Draw(scene)
        if thumb is not None:
            tsz = 156
            tw = thumb.copy()
            tw.thumbnail((tsz, tsz), Image.LANCZOS)
            cx, cy = x0 + 36 + tsz // 2, y0 + (PH - 54) // 2 + 8
            glow = Image.new("RGBA", scene.size, (0, 0, 0, 0))
            ImageDraw.Draw(glow).ellipse([cx - 74, cy - 70, cx + 74, cy + 78], fill=st["accent"] + (120,))
            scene.alpha_composite(glow.filter(ImageFilter.GaussianBlur(20)))
            scene.alpha_composite(tw, (cx - tw.width // 2, cy - tw.height // 2))
            badge = badge_orb(46, st["accent"] if kind == "success" else (222, 64, 56), "ok" if kind == "success" else "err")
            scene.alpha_composite(badge, (cx + tw.width // 2 - 34, cy + tw.height // 2 - 34))
        else:
            color = st["accent"] if kind == "success" else (222, 64, 56)
            big = badge_orb(110, color, "ok" if kind == "success" else "err")
            scene.alpha_composite(big, (x0 + 62, y0 + (PH - 54) // 2 - 47))

        d = ImageDraw.Draw(scene)
        f_title, f_msg, f_det = get_font(32, True), get_font(17), get_font(14)
        ty = y0 + 40
        d.text((TX, ty), title, font=f_title, fill=st["text"] + (255,))
        ty += 56
        for line in wrap_text(d, message, f_msg, PW - 236 - 36):
            d.text((TX, ty), line, font=f_msg, fill=st["text"] + (255,))
            ty += 25
        ty += 10
        for line in details:
            line = ellipsize(d, line, f_det, PW - 236 - 36)
            d.text((TX, ty), line, font=f_det, fill=st["sub"] + (255,))
            ty += 21
        final = scene.convert("RGB")

        # --- overlay canvas ---------------------------------------------------------
        cv = tk.Canvas(self.root, width=rw, height=rh, highlightthickness=0, bd=0)
        cv.place(x=0, y=0)
        tk.Misc.tkraise(cv)
        photo = ImageTk.PhotoImage(snap)
        item = cv.create_image(0, 0, anchor="nw", image=photo)
        self.dlg = dict(canvas=cv, photo=photo, item=item, snap=snap, final=final, closing=False, buttons=[], cb_close=None)

        if not buttons:
            buttons = [("OK", None)]
        self._dlg_build_buttons(buttons, box, final, t)
        self.root.bind("<Return>", lambda e: self._dlg_default())
        self.root.bind("<space>", lambda e: self._dlg_default())
        cv.focus_set()
        self._dlg_fade(snap, final, 9, opening=True)

    def _dlg_build_buttons(self, buttons, box, final, t):
        dlg = self.dlg
        bw, bh, gap = 150, 34, 14
        total = len(buttons) * bw + (len(buttons) - 1) * gap
        x = box[2] - 34 - total
        y = box[3] - 28 - bh
        dlg["plan"] = []
        for i, (label, cb) in enumerate(buttons):
            rect = (x, y, x + bw, y + bh)
            bg = final.crop(rect).convert("RGBA")
            states = {}
            norm = create_gradient_rect(bw, bh, t["btn_top"], t["btn_bot"], t["radius"], outline_color=t.get("btn_outline"), mid_color=t.get("btn_mid"))
            pressed = create_gradient_rect(bw, bh, t["btn_top"], t["btn_bot"], t["radius"], outline_color=t.get("btn_outline"), mid_color=t.get("btn_mid"), flipped=True)
            ov = Image.new("RGBA", (bw, bh), (255, 255, 255, 40))
            ov.putalpha(ImageChops.multiply(ov.getchannel("A"), norm.getchannel("A")))
            hover = Image.alpha_composite(norm, ov)
            for key, im in (("n", norm), ("h", hover), ("p", pressed)):
                comp = bg.copy()
                comp.alpha_composite(im)
                states[key] = comp.convert("RGB")
            dlg["plan"].append(dict(label=label, cb=cb, rect=rect, states=states, fg=t["btn_fg"]))
            x += bw + gap

    def _dlg_place_buttons(self):
        dlg = self.dlg
        cv = dlg["canvas"]
        for i, b in enumerate(dlg["plan"]):
            x0, y0, x1, y1 = b["rect"]
            photos = {k: ImageTk.PhotoImage(im) for k, im in b["states"].items()}
            tag = f"btn{i}"
            img_item = cv.create_image(x0, y0, anchor="nw", image=photos["n"], tags=("btn", tag))
            cv.create_text((x0 + x1) // 2, (y0 + y1) // 2, text=b["label"], fill=b["fg"], font=("Arial", 9, "bold"), tags=("btn", tag))
            b["photos"], b["img_item"], b["down"] = photos, img_item, False
            cv.tag_bind(tag, "<Enter>", lambda e, b=b: cv.itemconfig(b["img_item"], image=b["photos"]["h"]))
            cv.tag_bind(tag, "<Leave>", lambda e, b=b: (cv.itemconfig(b["img_item"], image=b["photos"]["n"]), b.__setitem__("down", False)))
            cv.tag_bind(tag, "<ButtonPress-1>", lambda e, b=b: (cv.itemconfig(b["img_item"], image=b["photos"]["p"]), b.__setitem__("down", True)))
            cv.tag_bind(tag, "<ButtonRelease-1>", lambda e, b=b: self._dlg_release(b))
        cv.configure(cursor="arrow")

    def _dlg_release(self, b):
        was_down = b.get("down")
        cv = self.dlg["canvas"] if self.dlg else None
        if cv is None:
            return
        cv.itemconfig(b["img_item"], image=b["photos"]["h"])
        if was_down:
            cb = b["cb"]
            self._dlg_close()
            if cb:
                self.root.after(40, cb)

    def _dlg_default(self):
        if self.dlg and self.dlg.get("plan"):
            b = self.dlg["plan"][-1]
            cb = b["cb"]
            self._dlg_close()
            if cb:
                self.root.after(40, cb)

    def _dlg_show(self, im):
        dlg = self.dlg
        if dlg is None:
            return
        dlg["photo"] = ImageTk.PhotoImage(im)
        dlg["canvas"].itemconfig(dlg["item"], image=dlg["photo"])

    def _dlg_fade(self, a_img, b_img, frames, opening):
        dlg = self.dlg
        state = {"i": 0}

        def step():
            if self.dlg is not dlg or dlg is None:
                return
            state["i"] += 1
            k = smooth(state["i"] / float(frames))
            self._dlg_show(Image.blend(a_img, b_img, k if opening else 1.0 - k))
            if state["i"] < frames:
                self.root.after(14, step)
            elif opening:
                self._dlg_place_buttons()
            else:
                self._dlg_destroy()
        step()

    def _dlg_close(self, immediate=False):
        dlg = self.dlg
        if dlg is None or dlg["closing"]:
            return
        dlg["closing"] = True
        try:
            dlg["canvas"].delete("btn")
        except tk.TclError:
            pass
        for seq in ("<Return>", "<space>"):
            self.root.unbind(seq)
        if immediate:
            self._dlg_destroy()
        else:
            self._dlg_fade(dlg["snap"], dlg["final"], 6, opening=False)

    def _dlg_destroy(self):
        dlg, self.dlg = self.dlg, None
        if dlg:
            try:
                dlg["canvas"].destroy()
            except tk.TclError:
                pass

    # ==================================================================================
    #  Saving
    # ==================================================================================
    @staticmethod
    def _reveal_in_folder(path):
        try:
            path = os.path.normpath(path)
            if sys.platform.startswith("win"):
                subprocess.Popen(["explorer", "/select,", path])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", path])
            else:
                subprocess.Popen(["xdg-open", os.path.dirname(path)])
        except Exception:
            pass

    # ==================================================================================
    #  Themed colour picker (colour wheel, brightness bar, hex/RGB, 10 recent colours)
    # ==================================================================================
    CP_D, CP_PAD = 300, 8                      # wheel diameter, rim padding
    CP_BAR_W, CP_BAR_H = 240, 24

    def _recent_colors(self):
        out = []
        for hx in self.config.get("recent_colors", []):
            try:
                h = str(hx).strip().lstrip("#")
                if len(h) == 6:
                    out.append((int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)))
            except ValueError:
                continue
        return out[:10]

    def _remember_color(self, rgb):
        hx = "#%02x%02x%02x" % tuple(rgb)
        old = [h for h in self.config.get("recent_colors", []) if str(h).lower() != hx]
        self.config["recent_colors"] = ([hx] + old)[:10]
        save_config(self.config)

    def open_color_picker(self, title, initial, on_pick):
        if self.cpk is not None or self.fsd is not None or self.dlg is not None:
            return
        self.close_ui_selector(immediate=True)
        snap = self.snapshot_root()
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        if snap is None:
            snap = self._fallback_snapshot(rw, rh)
        st = GLASS[self.current_theme]
        dim = make_dim(snap, st)
        PW, PH = 740, min(500, rh - 50)
        x0, y0 = (rw - PW) // 2, (rh - PH) // 2
        box = (x0, y0, x0 + PW, y0 + PH)
        scene = glass_panel(dim, box, 22, st).convert("RGBA")
        d = ImageDraw.Draw(scene)
        d.text((x0 + 30, y0 + 16), "Choose " + title, font=get_font(25, True), fill=st["text"] + (255,))

        # recent colours are baked into the panel (they don't change while the picker is open)
        recents = self._recent_colors()
        rects = []
        for i in range(10):
            cx, cy = x0 + 380 + (i % 5) * 64, y0 + 316 + (i // 5) * 42
            if i < len(recents):
                scene.alpha_composite(swatch_image(recents[i], 56, 34, 8), (cx, cy))
            else:
                scene.alpha_composite(empty_slot_image(56, 34, 8, st["text"]), (cx, cy))
            rects.append((cx, cy, cx + 56, cy + 34))
        final = scene.convert("RGB")

        cv = tk.Canvas(self.root, width=rw, height=rh, highlightthickness=0, bd=0)
        cv.place(x=0, y=0)
        tk.Misc.tkraise(cv)
        photo = ImageTk.PhotoImage(snap)
        item = cv.create_image(0, 0, anchor="nw", image=photo)
        h, s_, v = colorsys.rgb_to_hsv(*[c / 255.0 for c in initial])
        self.cpk = dict(canvas=cv, photo=photo, item=item, snap=snap, final=final, box=box, closing=False,
                        on_pick=on_pick, buttons=[], widgets=[], initial=tuple(initial), h=h, s=s_, v=v,
                        recents=recents, recent_rects=rects, drag=None, hover=None, lock=False, keep={})
        self._cpk_fade(snap, final, 9, opening=True)

    def _cpk_fade(self, a_img, b_img, frames, opening):
        cpk = self.cpk
        state = {"i": 0}

        def step():
            if self.cpk is not cpk or cpk is None:
                return
            state["i"] += 1
            k = smooth(state["i"] / float(frames))
            cpk["photo"] = ImageTk.PhotoImage(Image.blend(a_img, b_img, k if opening else 1.0 - k))
            cpk["canvas"].itemconfig(cpk["item"], image=cpk["photo"])
            if state["i"] < frames:
                self.root.after(14, step)
            elif opening:
                try:
                    self._cpk_build()
                except Exception:                             # since we don't need the software to fart befoer the user, never leave the user stuck: native chooser as a fallback 
                    init, cb = cpk["initial"], cpk["on_pick"]
                    self._cpk_destroy()
                    col = colorchooser.askcolor(color="#%02x%02x%02x" % init)
                    if col and col[0]:
                        cb(tuple(int(c) for c in col[0]))
            else:
                cb, rgb = cpk.get("after"), cpk.get("result")
                self._cpk_destroy()
                if cb and rgb:
                    self.root.after(30, lambda: cb(rgb))
        step()

    def _cpk_destroy(self):
        cpk, self.cpk = self.cpk, None
        if cpk:
            for w in cpk.get("widgets", []):
                try:
                    w.destroy()
                except tk.TclError:
                    pass
            try:
                cpk["canvas"].destroy()
            except tk.TclError:
                pass
            for seq in ("<Return>",):
                try:
                    self.root.unbind(seq)
                except tk.TclError:
                    pass

    def _cpk_rgb(self):
        c = self.cpk
        return tuple(int(round(x * 255)) for x in colorsys.hsv_to_rgb(c["h"], c["s"], c["v"]))

    def _cpk_close(self, rgb):
        cpk = self.cpk
        if cpk is None or cpk["closing"]:
            return
        cpk["closing"] = True
        cpk["result"] = rgb
        cpk["after"] = cpk["on_pick"] if rgb else None
        if rgb:
            self._remember_color(rgb)
        for w in cpk["widgets"]:
            try:
                w.destroy()
            except tk.TclError:
                pass
        cpk["widgets"] = []
        cpk["canvas"].delete("ui")
        self._cpk_fade(cpk["snap"], cpk["final"], 6, opening=False)

    def _cpk_ok(self):
        if self.cpk and not self.cpk["closing"]:
            self._cpk_close(self._cpk_rgb())

    def _cpk_build(self):
        c = self.cpk
        cv, (bx0, by0, bx1, by1) = c["canvas"], c["box"]
        PW, PH = bx1 - bx0, by1 - by0
        st = GLASS[self.current_theme]
        txt = "#%02x%02x%02x" % st["text"]
        sub = "#%02x%02x%02x" % st["sub"]
        acc = "#%02x%02x%02x" % st["accent"]
        D, pad = self.CP_D, self.CP_PAD

        # --- wheel -----------------------------------------------------------------
        c["wx"], c["wy"] = bx0 + 36, by0 + 68
        c["cx"], c["cy"] = c["wx"] + D // 2, c["wy"] + D // 2
        region = (c["wx"] - pad, c["wy"] - pad, c["wx"] + D + pad, c["wy"] + D + pad)
        bg = c["final"].crop(region).convert("RGBA")
        sh = Image.new("L", bg.size, 0)
        ImageDraw.Draw(sh).ellipse([pad + 2, pad + 7, pad + D + 2, pad + D + 7], fill=110)
        sh = sh.filter(ImageFilter.GaussianBlur(7))
        bg = Image.composite(Image.new("RGBA", bg.size, (0, 0, 0, 255)), bg, sh)
        c["wheel_bg"] = bg
        c["ring"] = wheel_ring(D, pad)
        c["wheel_item"] = cv.create_image(region[0], region[1], anchor="nw", tags="ui")

        # --- brightness bar ----------------------------------------------------------
        c["bx0"], c["by0"] = bx0 + 66, by0 + 398
        c["bar_bg"] = c["final"].crop((c["bx0"], c["by0"], c["bx0"] + self.CP_BAR_W, c["by0"] + self.CP_BAR_H)).convert("RGBA")
        c["bar_item"] = cv.create_image(c["bx0"], c["by0"], anchor="nw", tags="ui")
        mid = c["by0"] + self.CP_BAR_H // 2
        cv.create_text(bx0 + 44, mid, text="\u2212", fill=txt, font=("Arial", 18, "bold"), tags="ui")
        cv.create_text(bx0 + 330, mid, text="+", fill=txt, font=("Arial", 18, "bold"), tags="ui")
        c["handle"] = cv.create_rectangle(0, 0, 0, 0, fill="#ffffff", outline="#202020", width=2, tags="ui")

        # --- markers -------------------------------------------------------------------
        c["m_out"] = cv.create_oval(0, 0, 0, 0, outline="#000000", width=3, tags="ui")
        c["m_in"] = cv.create_oval(0, 0, 0, 0, outline="#ffffff", width=2, tags="ui")

        # --- right column: current / new, hex, rgb, recents ----------------------------
        rx = bx0 + 380
        cv.create_text(rx, by0 + 80, anchor="w", text="Current", fill=sub, font=("Segoe UI", 9), tags="ui")
        cv.create_text(rx + 170, by0 + 80, anchor="w", text="New", fill=sub, font=("Segoe UI", 9, "bold"), tags="ui")
        c["cur_rect"] = (rx, by0 + 92, rx + 150, by0 + 172)
        c["new_rect"] = (rx + 170, by0 + 92, rx + 320, by0 + 172)
        cur = c["final"].crop(c["cur_rect"]).convert("RGBA")
        cur.alpha_composite(swatch_image(c["initial"], 150, 80, 12))
        c["cur_photo"] = ImageTk.PhotoImage(cur.convert("RGB"))
        cv.create_image(c["cur_rect"][0], c["cur_rect"][1], anchor="nw", image=c["cur_photo"], tags="ui")
        c["new_bg"] = c["final"].crop(c["new_rect"]).convert("RGBA")
        c["new_item"] = cv.create_image(c["new_rect"][0], c["new_rect"][1], anchor="nw", tags="ui")

        def place(widget, x, y, w, h):
            cv.create_window(x, y, window=widget, anchor="nw", width=w, height=h, tags="ui")
            c["widgets"].append(widget)

        cv.create_text(rx, by0 + 211, anchor="w", text="Hex", fill=txt, font=("Segoe UI", 10), tags="ui")
        c["hex"] = tk.Entry(cv)
        self.style_entry(c["hex"], font=("Consolas", 10))
        place(c["hex"], rx + 44, by0 + 196, 118, 30)
        c["hex"].bind("<KeyRelease>", lambda e: self._cpk_entry("hex"))
        c["hex"].bind("<Return>", lambda e: self._cpk_ok())
        c["rgb"] = []
        for k, (lab, ox) in enumerate((("R", 0), ("G", 108), ("B", 216))):
            cv.create_text(rx + ox, by0 + 253, anchor="w", text=lab, fill=txt, font=("Segoe UI", 10), tags="ui")
            ent = tk.Entry(cv)
            self.style_entry(ent, font=("Consolas", 10))
            place(ent, rx + ox + 18, by0 + 238, 60, 30)
            ent.bind("<KeyRelease>", lambda e: self._cpk_entry("rgb"))
            ent.bind("<Return>", lambda e: self._cpk_ok())
            c["rgb"].append(ent)

        cv.create_text(rx, by0 + 298, anchor="w", text="Recent colors", fill=sub, font=("Segoe UI", 9), tags="ui")
        c["hover_item"] = cv.create_rectangle(0, 0, 0, 0, outline=acc, width=2, state="hidden", tags="ui")

        # --- buttons ---------------------------------------------------------------------
        by = by0 + PH - 50
        self._cv_button((bx1 - 30 - 130, by, bx1 - 30, by + 34), "Cancel", lambda: self._cpk_close(None), ov=c)
        self._cv_button((bx1 - 30 - 130 - 12 - 130, by, bx1 - 30 - 130 - 12, by + 34), "OK", self._cpk_ok, ov=c)

        cv.bind("<ButtonPress-1>", self._cpk_press)
        cv.bind("<B1-Motion>", self._cpk_motion)
        cv.bind("<Motion>", self._cpk_motion)
        cv.bind("<ButtonRelease-1>", lambda e: c.__setitem__("drag", None))
        self.root.bind("<Return>", lambda e: self._cpk_ok())
        self._cpk_update("init")

    # ---- rendering + state ---------------------------------------------------------
    def _cpk_update(self, src):
        c = self.cpk
        if c is None:
            return
        cv = c["canvas"]
        rgb = self._cpk_rgb()
        if src != "bar":                                       # hue / saturation changed -> bar gradient follows
            full = tuple(int(round(x * 255)) for x in colorsys.hsv_to_rgb(c["h"], c["s"], 1.0))
            img = c["bar_bg"].copy()
            img.alpha_composite(brightness_bar(self.CP_BAR_W, self.CP_BAR_H, full))
            c["bar_photo"] = ImageTk.PhotoImage(img.convert("RGB"))
            cv.itemconfig(c["bar_item"], image=c["bar_photo"])
        if src != "wheel":                                     # brightness changed -> wheel re-lit
            img = c["wheel_bg"].copy()
            img.alpha_composite(hsv_wheel(self.CP_D, c["v"]), (self.CP_PAD, self.CP_PAD))
            img.alpha_composite(c["ring"])
            c["wheel_photo"] = ImageTk.PhotoImage(img.convert("RGB"))
            cv.itemconfig(c["wheel_item"], image=c["wheel_photo"])
        sw = c["new_bg"].copy()
        sw.alpha_composite(swatch_image(rgb, 150, 80, 12))
        c["new_photo"] = ImageTk.PhotoImage(sw.convert("RGB"))
        cv.itemconfig(c["new_item"], image=c["new_photo"])

        ang = c["h"] * 2 * math.pi
        mx = c["cx"] + c["s"] * (self.CP_D / 2.0) * math.cos(ang)
        my = c["cy"] - c["s"] * (self.CP_D / 2.0) * math.sin(ang)
        cv.coords(c["m_out"], mx - 9, my - 9, mx + 9, my + 9)
        cv.coords(c["m_in"], mx - 8, my - 8, mx + 8, my + 8)
        hx = c["bx0"] + c["v"] * self.CP_BAR_W
        cv.coords(c["handle"], hx - 4, c["by0"] - 4, hx + 4, c["by0"] + self.CP_BAR_H + 4)

        c["lock"] = True                                       # keep the text boxes in sync, except the one being typed in
        if src != "entry_hex":
            c["hex"].delete(0, "end")
            c["hex"].insert(0, "#%02X%02X%02X" % rgb)
        if src != "entry_rgb":
            for ent, val in zip(c["rgb"], rgb):
                ent.delete(0, "end")
                ent.insert(0, str(val))
        c["lock"] = False

    def _cpk_set_rgb(self, rgb, src):
        c = self.cpk
        h, s_, v = colorsys.rgb_to_hsv(*[x / 255.0 for x in rgb])
        if s_ > 0.0 and v > 0.0:
            c["h"] = h
        if v > 0.0:
            c["s"] = s_
        c["v"] = v
        self._cpk_update(src)

    def _cpk_entry(self, kind):
        c = self.cpk
        if c is None or c["lock"]:
            return
        try:
            if kind == "hex":
                t = c["hex"].get().strip().lstrip("#")
                if len(t) == 3:
                    t = "".join(ch * 2 for ch in t)
                if len(t) != 6:
                    return
                rgb = (int(t[0:2], 16), int(t[2:4], 16), int(t[4:6], 16))
            else:
                rgb = tuple(max(0, min(255, int(e.get().strip()))) for e in c["rgb"])
        except ValueError:
            return
        self._cpk_set_rgb(rgb, "entry_" + kind)

    def _cpk_wheel_xy(self, x, y):
        c = self.cpk
        dx, dy = x - c["cx"], y - c["cy"]
        r = min(1.0, math.hypot(dx, dy) / (self.CP_D / 2.0))
        c["h"] = (math.atan2(-dy, dx) / (2 * math.pi)) % 1.0
        c["s"] = r
        self._cpk_update("wheel")

    def _cpk_bar_x(self, x):
        c = self.cpk
        c["v"] = max(0.0, min(1.0, (x - c["bx0"]) / float(self.CP_BAR_W)))
        self._cpk_update("bar")

    def _cpk_recent_at(self, x, y):
        for i, r in enumerate(self.cpk["recent_rects"]):
            if r[0] <= x <= r[2] and r[1] <= y <= r[3] and i < len(self.cpk["recents"]):
                return i
        return None

    def _cpk_press(self, e):
        c = self.cpk
        if c is None or c["closing"]:
            return
        if math.hypot(e.x - c["cx"], e.y - c["cy"]) <= self.CP_D / 2.0 + 6:
            c["drag"] = "wheel"
            self._cpk_wheel_xy(e.x, e.y)
        elif c["bx0"] - 10 <= e.x <= c["bx0"] + self.CP_BAR_W + 10 and c["by0"] - 8 <= e.y <= c["by0"] + self.CP_BAR_H + 8:
            c["drag"] = "bar"
            self._cpk_bar_x(e.x)
        else:
            i = self._cpk_recent_at(e.x, e.y)
            if i is not None:
                self._cpk_set_rgb(c["recents"][i], "recent")

    def _cpk_motion(self, e):
        c = self.cpk
        if c is None or c["closing"]:
            return
        if c["drag"] == "wheel":
            self._cpk_wheel_xy(e.x, e.y)
        elif c["drag"] == "bar":
            self._cpk_bar_x(e.x)
        else:
            i = self._cpk_recent_at(e.x, e.y)
            if i != c["hover"]:
                c["hover"] = i
                if i is None:
                    c["canvas"].itemconfig(c["hover_item"], state="hidden")
                else:
                    r = c["recent_rects"][i]
                    c["canvas"].coords(c["hover_item"], r[0] - 2, r[1] - 2, r[2] + 2, r[3] + 2)
                    c["canvas"].itemconfig(c["hover_item"], state="normal")

    # ==================================================================================
    #  Themed "Save As" browser (replaces the native Windows file dialog)
    # ==================================================================================
    def _start_dir(self):
        cur = self.config.get("last_dir")
        while cur and not os.path.isdir(cur):
            parent = os.path.dirname(cur)
            if parent == cur:
                cur = None
                break
            cur = parent
        if cur:
            return cur
        pics = os.path.join(os.path.expanduser("~"), "Pictures")
        return pics if os.path.isdir(pics) else os.path.expanduser("~")

    @staticmethod
    def _places():
        home = os.path.expanduser("~")
        out, seen = [], set()

        def add(label, *parts):
            for base in (home, os.path.join(home, "OneDrive")):
                p = os.path.join(base, *parts)
                if os.path.isdir(p) and p not in seen:
                    seen.add(p)
                    out.append((label, p, "folder"))
                    return
        add("Desktop", "Desktop")
        add("Documents", "Documents")
        add("Pictures", "Pictures")
        add("Downloads", "Downloads")
        out.append(("Home", home, "folder"))
        out.append(("Orb Creator folder", app_dir(), "folder"))
        if sys.platform.startswith("win"):
            import string
            for L in string.ascii_uppercase:
                p = L + ":\\"
                if os.path.exists(p):
                    out.append((p, p, "drive"))
        else:
            out.append(("/", "/", "drive"))
        return out

    @staticmethod
    def _scan_dir(path):
        """Folders + .png files of a directory, folders first. Returns (items, error)."""
        items = []
        try:
            with os.scandir(path) as it:
                for e in it:
                    if e.name.startswith("."):
                        continue
                    try:
                        st = e.stat()
                        isdir = e.is_dir()
                    except OSError:
                        continue
                    if sys.platform.startswith("win") and (getattr(st, "st_file_attributes", 0) & 0x2):
                        continue                                    # hidden on Windows
                    if isdir:
                        items.append((True, e.name, st.st_mtime, 0))
                    elif e.name.lower().endswith(".png"):
                        items.append((False, e.name, st.st_mtime, st.st_size))
        except OSError as ex:
            return None, str(ex)
        items.sort(key=lambda r: (not r[0], r[1].lower()))
        return items, None

    def open_save_browser(self, start_dir, initial_name, on_pick):
        if self.fsd is not None or self.dlg is not None or self.cpk is not None:
            return
        self.close_ui_selector(immediate=True)
        snap = self.snapshot_root()
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        if snap is None:
            snap = self._fallback_snapshot(rw, rh)
        st = GLASS[self.current_theme]
        dim = make_dim(snap, st)
        PW, PH = min(960, rw - 80), min(610, rh - 70)
        x0, y0 = (rw - PW) // 2, (rh - PH) // 2
        box = (x0, y0, x0 + PW, y0 + PH)
        scene = glass_panel(dim, box, 22, st).convert("RGBA")
        d = ImageDraw.Draw(scene)
        d.text((x0 + 30, y0 + 16), "Save Aero Orb", font=get_font(25, True), fill=st["text"] + (255,))
        final = scene.convert("RGB")

        cv = tk.Canvas(self.root, width=rw, height=rh, highlightthickness=0, bd=0)
        cv.place(x=0, y=0)
        tk.Misc.tkraise(cv)
        photo = ImageTk.PhotoImage(snap)
        item = cv.create_image(0, 0, anchor="nw", image=photo)
        self.fsd = dict(canvas=cv, photo=photo, item=item, snap=snap, final=final, box=box, closing=False,
                        on_pick=on_pick, start_dir=start_dir, initial=initial_name, buttons=[], widgets=[],
                        cwd=None, hist=[], rows={}, mode="file", confirm=None, keep=[])
        self._fsd_fade(snap, final, 9, opening=True)

    def _fsd_fade(self, a_img, b_img, frames, opening):
        fsd = self.fsd
        state = {"i": 0}

        def step():
            if self.fsd is not fsd or fsd is None:
                return
            state["i"] += 1
            k = smooth(state["i"] / float(frames))
            fsd["photo"] = ImageTk.PhotoImage(Image.blend(a_img, b_img, k if opening else 1.0 - k))
            fsd["canvas"].itemconfig(fsd["item"], image=fsd["photo"])
            if state["i"] < frames:
                self.root.after(14, step)
            elif opening:
                try:
                    self._fsd_build()
                except Exception as ex:                       # never leave the user stuck: fall back to the native dialog (mentioned the farting of the software in previous comment)
                    self._fsd_destroy()
                    self._native_save_fallback()
            else:
                cb, path = fsd.get("after"), fsd.get("result")
                self._fsd_destroy()
                if cb:
                    self.root.after(30, lambda: cb(path))
        step()

    def _fsd_destroy(self):
        fsd, self.fsd = self.fsd, None
        if fsd:
            for w in fsd.get("widgets", []):
                try:
                    w.destroy()
                except tk.TclError:
                    pass
            try:
                fsd["canvas"].destroy()
            except tk.TclError:
                pass

    def _native_save_fallback(self):
        pending = getattr(self, "_pending_export", None)
        if not pending:
            return
        filename = filedialog.asksaveasfilename(parent=self.root, title="Save Aero Orb", defaultextension=".png",
                                                initialdir=self._start_dir(), filetypes=[("PNG", "*.png")])
        if filename:
            self._export_orb(filename, pending)

    def _fsd_close(self, path=None):
        fsd = self.fsd
        if fsd is None or fsd["closing"]:
            return
        fsd["closing"] = True
        fsd["result"] = path
        fsd["after"] = fsd["on_pick"] if path else None
        for w in fsd["widgets"]:
            try:
                w.destroy()
            except tk.TclError:
                pass
        fsd["widgets"] = []
        fsd["canvas"].delete("ui")
        self._fsd_fade(fsd["snap"], fsd["final"], 6, opening=False)

    def _fsd_escape(self):
        fsd = self.fsd
        if fsd is None:
            return
        if fsd.get("mode") == "folder":
            self._fsd_set_mode("file")
        else:
            self._fsd_close(None)

    # ---- widgets ---------------------------------------------------------------------
    def _cv_button(self, rect, label, cb, font=("Arial", 9, "bold"), ov=None):
        fsd = ov or self.fsd
        cv, base, t = fsd["canvas"], fsd["final"], THEMES[self.current_theme]
        x0, y0, x1, y1 = rect
        bw, bh = x1 - x0, y1 - y0
        bg = base.crop(rect).convert("RGBA")
        kw = dict(outline_color=t.get("btn_outline"), mid_color=t.get("btn_mid"))
        norm = create_gradient_rect(bw, bh, t["btn_top"], t["btn_bot"], t["radius"], **kw)
        pressed = create_gradient_rect(bw, bh, t["btn_top"], t["btn_bot"], t["radius"], flipped=True, **kw)
        ov = Image.new("RGBA", (bw, bh), (255, 255, 255, 40))
        ov.putalpha(ImageChops.multiply(ov.getchannel("A"), norm.getchannel("A")))
        photos = {}
        for key, im in (("n", norm), ("h", Image.alpha_composite(norm, ov)), ("p", pressed)):
            comp = bg.copy()
            comp.alpha_composite(im)
            photos[key] = ImageTk.PhotoImage(comp.convert("RGB"))
        tag = "b%d" % len(fsd["buttons"])
        img = cv.create_image(x0, y0, anchor="nw", image=photos["n"], tags=("ui", tag))
        txt = cv.create_text((x0 + x1) // 2, (y0 + y1) // 2, text=label, fill=t["btn_fg"], font=font, tags=("ui", tag))
        rec = dict(photos=photos, img=img, text=txt, down=False)

        def enter(e):
            cv.itemconfig(img, image=photos["h"])

        def leave(e):
            cv.itemconfig(img, image=photos["n"])
            rec["down"] = False

        def press(e):
            cv.itemconfig(img, image=photos["p"])
            rec["down"] = True

        def release(e):
            cv.itemconfig(img, image=photos["h"])
            if rec["down"]:
                rec["down"] = False
                cb()
        cv.tag_bind(tag, "<Enter>", enter)
        cv.tag_bind(tag, "<Leave>", leave)
        cv.tag_bind(tag, "<ButtonPress-1>", press)
        cv.tag_bind(tag, "<ButtonRelease-1>", release)
        fsd["buttons"].append(rec)
        return rec

    def _fsd_style(self):
        g = GLASS[self.current_theme]
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")                           # the only theme whose colours we can fully control
        except tk.TclError:
            pass
        nm = "Aero.Treeview"
        style.configure(nm, background=g["list_bg"], fieldbackground=g["list_bg"], foreground=g["list_fg"],
                        rowheight=26, borderwidth=0, relief="flat", font=("Segoe UI", 10))
        style.map(nm, background=[("selected", g["list_sel"])], foreground=[("selected", g["list_sel_fg"])])
        style.layout(nm, [("Treeview.treearea", {"sticky": "nswe"})])
        style.configure(nm + ".Heading", background=g["list_head"], foreground=g["list_fg"], relief="flat",
                        borderwidth=0, font=("Segoe UI", 9, "bold"))
        style.map(nm + ".Heading", background=[("active", g["list_head"])])
        style.configure("Aero.Vertical.TScrollbar", background=g["list_head"], troughcolor=g["list_bg"],
                        bordercolor=g["list_bg"], lightcolor=g["list_head"], darkcolor=g["list_head"],
                        arrowcolor=g["list_fg"], relief="flat", gripcount=0)
        style.map("Aero.Vertical.TScrollbar", background=[("active", g["edge"])])

    def _fsd_build(self):
        fsd = self.fsd
        cv, (bx0, by0, bx1, by1) = fsd["canvas"], fsd["box"]
        PW, PH = bx1 - bx0, by1 - by0
        g = GLASS[self.current_theme]
        txt_col = "#%02x%02x%02x" % g["text"]
        sub_col = "#%02x%02x%02x" % g["sub"]
        self._fsd_style()
        fsd["icons"] = {k: ImageTk.PhotoImage(make_icon(k)) for k in ("folder", "drive", "png")}

        def place(widget, x, y, w, h):
            cv.create_window(bx0 + x, by0 + y, window=widget, anchor="nw", width=w, height=h, tags="ui")
            fsd["widgets"].append(widget)

        # toolbar: back / up / path
        self._cv_button((bx0 + 30, by0 + 66, bx0 + 68, by0 + 96), "\u2190", self._fsd_back, ("Arial", 12, "bold"))
        self._cv_button((bx0 + 74, by0 + 66, bx0 + 112, by0 + 96), "\u2191", self._fsd_up, ("Arial", 12, "bold"))
        path_e = tk.Entry(cv)
        self.style_entry(path_e)
        place(path_e, 122, 66, PW - 122 - 30, 30)
        path_e.bind("<Return>", lambda e: self._fsd_go(path_e.get().strip().strip('"')) or None)
        fsd["path_entry"] = path_e

        list_top, list_bot = 108, PH - 146
        # places sidebar
        side_frame = tk.Frame(cv, bg=g["edge"], bd=0, highlightthickness=0)
        side = ttk.Treeview(side_frame, show="tree", selectmode="browse", style="Aero.Treeview")
        side.pack(fill="both", expand=True, padx=1, pady=1)
        place(side_frame, 30, list_top, 196, list_bot - list_top)
        fsd["place_map"] = {}
        for i, (label, p, kind) in enumerate(self._places()):
            iid = "p%d" % i
            side.insert("", "end", iid=iid, text="  " + label, image=fsd["icons"][kind], tags=("odd" if i % 2 else "even",))
            fsd["place_map"][iid] = p
        side.tag_configure("odd", background=g["list_alt"])
        side.tag_configure("even", background=g["list_bg"])
        side.bind("<<TreeviewSelect>>", self._fsd_on_place)
        fsd["side"] = side

        # file list + scrollbar
        file_frame = tk.Frame(cv, bg=g["edge"], bd=0, highlightthickness=0)
        inner = tk.Frame(file_frame, bg=g["list_bg"], bd=0)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        tree = ttk.Treeview(inner, columns=("modified", "size"), show="tree headings", selectmode="browse", style="Aero.Treeview")
        sb = ttk.Scrollbar(inner, orient="vertical", command=tree.yview, style="Aero.Vertical.TScrollbar")
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        tree.heading("#0", text="Name", anchor="w")
        tree.heading("modified", text="Date modified", anchor="w")
        tree.heading("size", text="Size", anchor="e")
        tree.column("#0", width=300, stretch=True)
        tree.column("modified", width=160, stretch=False, anchor="w")
        tree.column("size", width=90, stretch=False, anchor="e")
        tree.tag_configure("odd", background=g["list_alt"])
        tree.tag_configure("even", background=g["list_bg"])
        place(file_frame, 236, list_top, PW - 236 - 30, list_bot - list_top)
        tree.bind("<<TreeviewSelect>>", self._fsd_on_select)
        tree.bind("<Double-1>", self._fsd_on_double)
        tree.bind("<Return>", lambda e: self._fsd_on_enter())
        fsd["tree"] = tree

        # status + file name + type
        fsd["status"] = cv.create_text(bx0 + 30, by0 + PH - 131, anchor="w", text="", fill=sub_col, font=("Segoe UI", 9), tags="ui")
        fsd["name_label"] = cv.create_text(bx0 + 30, by0 + PH - 101, anchor="w", text="File name:", fill=txt_col, font=("Segoe UI", 10), tags="ui")
        name_e = tk.Entry(cv)
        self.style_entry(name_e)
        place(name_e, 136, PH - 116, PW - 136 - 30, 30)
        fsd["name_entry"] = name_e
        name_e.bind("<Return>", lambda e: self._fsd_primary())
        name_e.bind("<Key>", lambda e: self._fsd_reset_confirm() if e.keysym not in ("Return", "Escape") else None)
        cv.create_text(bx0 + 30, by0 + PH - 69, anchor="w", text="Save as type:", fill=txt_col, font=("Segoe UI", 10), tags="ui")
        cv.create_text(bx0 + 136, by0 + PH - 69, anchor="w", text="PNG image (*.png)", fill=sub_col, font=("Segoe UI", 10), tags="ui")

        # buttons
        by = by0 + PH - 50
        fsd["btn_new"] = self._cv_button((bx0 + 30, by, bx0 + 170, by + 34), "New Folder", lambda: self._fsd_set_mode("folder"))
        fsd["btn_cancel"] = self._cv_button((bx1 - 30 - 130, by, bx1 - 30, by + 34), "Cancel", self._fsd_escape)
        fsd["btn_primary"] = self._cv_button((bx1 - 30 - 130 - 12 - 130, by, bx1 - 30 - 130 - 12, by + 34), "Save", self._fsd_primary)

        self._fsd_go(fsd["start_dir"])
        name_e.insert(0, fsd["initial"])
        name_e.focus_set()
        stem = os.path.splitext(fsd["initial"])[0]
        name_e.selection_range(0, len(stem))
        name_e.icursor(len(stem))

    # ---- behaviour -------------------------------------------------------------------
    def _fsd_status(self, msg, kind="info"):
        fsd = self.fsd
        if fsd is None:
            return
        g = GLASS[self.current_theme]
        col = {"info": "#%02x%02x%02x" % g["sub"], "error": "#d8362a", "warn": "#d86a00" if self.current_theme != "Dark" else "#ffb066"}[kind]
        fsd["canvas"].itemconfig(fsd["status"], text=msg, fill=col)

    def _fsd_reset_confirm(self):
        fsd = self.fsd
        if fsd and fsd.get("confirm"):
            fsd["confirm"] = None
            fsd["canvas"].itemconfig(fsd["btn_primary"]["text"], text="Save" if fsd["mode"] == "file" else "Create")
            self._fsd_status("")

    def _fsd_go(self, path, push=True):
        fsd = self.fsd
        if fsd is None:
            return False
        p = os.path.abspath(os.path.expanduser(path))
        items, err = self._scan_dir(p)
        if items is None:
            self._fsd_status("Can't open that folder.", "error")
            return False
        if push and fsd["cwd"] and fsd["cwd"] != p:
            fsd["hist"].append(fsd["cwd"])
        fsd["cwd"] = p
        tree = fsd["tree"]
        tree.delete(*tree.get_children())
        fsd["rows"] = {}
        for i, (isdir, name, mt, size) in enumerate(items):
            try:
                when = time.strftime("%Y-%m-%d  %H:%M", time.localtime(mt))
            except (OSError, ValueError, OverflowError):
                when = ""
            iid = str(i)
            tree.insert("", "end", iid=iid, text=" " + name, image=fsd["icons"]["folder" if isdir else "png"],
                        values=(when, "" if isdir else human_size(size)), tags=("odd" if i % 2 else "even",))
            fsd["rows"][iid] = (isdir, name)
        pe = fsd["path_entry"]
        pe.delete(0, "end")
        pe.insert(0, p)
        nf = sum(1 for r in items if r[0])
        self._fsd_reset_confirm()
        self._fsd_status("%d folder%s, %d PNG file%s" % (nf, "" if nf == 1 else "s", len(items) - nf, "" if len(items) - nf == 1 else "s"))
        return False

    def _fsd_up(self):
        fsd = self.fsd
        if fsd and fsd["cwd"]:
            parent = os.path.dirname(fsd["cwd"].rstrip("\\/")) or fsd["cwd"]
            if parent and parent != fsd["cwd"]:
                self._fsd_go(parent)

    def _fsd_back(self):
        fsd = self.fsd
        if fsd and fsd["hist"]:
            self._fsd_go(fsd["hist"].pop(), push=False)

    def _fsd_on_place(self, e):
        fsd = self.fsd
        sel = fsd["side"].selection() if fsd else ()
        if sel:
            self._fsd_go(fsd["place_map"][sel[0]])

    def _fsd_set_name(self, name):
        e = self.fsd["name_entry"]
        e.delete(0, "end")
        e.insert(0, name)

    def _fsd_on_select(self, e):
        fsd = self.fsd
        sel = fsd["tree"].selection() if fsd else ()
        if sel and fsd["mode"] == "file":
            isdir, name = fsd["rows"][sel[0]]
            if not isdir:
                self._fsd_set_name(name)
                self._fsd_reset_confirm()

    def _fsd_on_double(self, e):
        fsd = self.fsd
        iid = fsd["tree"].identify_row(e.y)
        if not iid:
            return
        isdir, name = fsd["rows"][iid]
        if isdir:
            self._fsd_go(os.path.join(fsd["cwd"], name))
        elif fsd["mode"] == "file":
            self._fsd_set_name(name)
            self._fsd_primary()

    def _fsd_on_enter(self):
        fsd = self.fsd
        sel = fsd["tree"].selection()
        if sel:
            isdir, name = fsd["rows"][sel[0]]
            if isdir:
                self._fsd_go(os.path.join(fsd["cwd"], name))
            else:
                self._fsd_primary()

    def _fsd_set_mode(self, mode):
        fsd = self.fsd
        if fsd is None or fsd["mode"] == mode:
            return
        cv = fsd["canvas"]
        fsd["confirm"] = None
        if mode == "folder":
            fsd["file_name_backup"] = fsd["name_entry"].get()
            fsd["mode"] = "folder"
            cv.itemconfig(fsd["name_label"], text="Folder name:")
            cv.itemconfig(fsd["btn_primary"]["text"], text="Create")
            self._fsd_set_name("New folder")
            fsd["name_entry"].focus_set()
            fsd["name_entry"].selection_range(0, "end")
            self._fsd_status("Type a name and press Create to make a new folder here.")
        else:
            fsd["mode"] = "file"
            cv.itemconfig(fsd["name_label"], text="File name:")
            cv.itemconfig(fsd["btn_primary"]["text"], text="Save")
            self._fsd_set_name(fsd.get("file_name_backup", fsd["initial"]))
            fsd["name_entry"].focus_set()
            self._fsd_status("")

    @staticmethod
    def _bad_name(name):
        return (not name) or any(c in name for c in '<>:"/\\|?*') or name in (".", "..")

    def _fsd_primary(self):
        fsd = self.fsd
        if fsd is None or fsd["closing"]:
            return
        name = fsd["name_entry"].get().strip()
        if fsd["mode"] == "folder":
            if self._bad_name(name):
                self._fsd_status("A folder name can't be empty or contain  < > : \" / \\ | ? *", "error")
                return
            target = os.path.join(fsd["cwd"], name)
            try:
                os.mkdir(target)
            except OSError as ex:
                self._fsd_status("Couldn't create the folder: %s" % (ex.strerror or ex), "error")
                return
            self._fsd_set_mode("file")
            self._fsd_go(target)
            return
        if not name:
            self._fsd_status("Enter a file name.", "error")
            return
        if not name.lower().endswith(".png"):
            name += ".png"
        path = name if os.path.isabs(name) else os.path.join(fsd["cwd"], name)
        if self._bad_name(os.path.basename(path)):
            self._fsd_status("A file name can't contain  < > : \" / \\ | ? *", "error")
            return
        if not os.path.isdir(os.path.dirname(path)):
            self._fsd_status("That folder doesn't exist.", "error")
            return
        if os.path.isdir(path):
            self._fsd_go(path)
            return
        if os.path.exists(path) and fsd.get("confirm") != path:
            fsd["confirm"] = path
            fsd["canvas"].itemconfig(fsd["btn_primary"]["text"], text="Replace")
            self._fsd_status("\u201c%s\u201d already exists. Press Replace to overwrite it." % os.path.basename(path), "warn")
            return
        self._fsd_close(path)

    # ==================================================================================
    #  Saving
    # ==================================================================================
    def save_orb(self):
        try:
            res = int(self.resolution_var.get())
            if not (100 <= res <= 10000): raise ValueError
        except ValueError:
            self.show_aero_dialog("Invalid Resolution", "Resolution must be a whole number between 100 and 10000.", kind="error")
            return
        self._pending_export = res
        try:
            self.open_save_browser(self._start_dir(), "orb.png", lambda p: self._export_orb(p, res))
        except Exception:
            self._fsd_destroy()
            self._native_save_fallback()

    def _export_orb(self, filename, res):
        try:
            final_img = self.render_composition(res)
            final_img.save(filename, 'PNG')
        except Exception as ex:
            self.show_aero_dialog("Couldn't Save", "The orb could not be exported.", details=[str(ex)], kind="error")
            return

        # remember the folder for next time
        self.config["last_dir"] = os.path.dirname(os.path.abspath(filename))
        save_config(self.config)

        # small preview of what was just exported
        thumb = self.render_composition(320)
        bb = thumb.getchannel("A").point(lambda v: 255 if v > 4 else 0).getbbox()
        if bb:
            pad = 6
            thumb = thumb.crop((max(0, bb[0] - pad), max(0, bb[1] - pad), min(320, bb[2] + pad), min(320, bb[3] + pad)))
        else:
            thumb = None

        Sound.play(asset_path("sfx/saved.wav"))
        self.show_aero_dialog(
            "Orb Saved!", "Aero Orb Exported Successfully!",
            details=[os.path.basename(filename), f"{res} \u00d7 {res} px  \u2022  PNG"],
            kind="success", thumb=thumb,
            buttons=[("Show in Folder", lambda p=filename: self._reveal_in_folder(p)), ("OK", None)])


