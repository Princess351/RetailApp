import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import mysql.connector
from mysql.connector import Error
import csv
from datetime import datetime

# Optional: charting
try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False


class StockMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Stock Level Monitor System")
        self.root.geometry("1250x700")
        self.light_bg = "#f0f0f0"
        self.dark_bg = "#2b2b2b"
        self.current_theme = "light"
        self.root.configure(bg=self.light_bg)

        # DB settings (update as needed)
        self.db_config = {
            "host": "localhost",
            "user": "stock_user",
            "password": "kathmandu5**",   # keep secure in production
            "database": "stock_db"
        }

        # sorting state
        self.sort_reverse = {}

        # load DB + items
        self.init_db()
        self.items = self.load_data()

        # UI
        self.create_widgets()
        self.refresh_display()
        # Show low-stock popup once at start if needed
        self.low_stock_popup_once()

    # ---------- DATABASE ----------
    def get_connection(self):
        try:
            conn = mysql.connector.connect(**self.db_config)
            return conn
        except Error as e:
            messagebox.showerror("Database Error", f"Error connecting to MySQL:\n{e}")
            return None

    def init_db(self):
        conn = self.get_connection()
        if not conn:
            return
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_items (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                sku VARCHAR(100) UNIQUE NOT NULL,
                quantity INT,
                min_level INT,
                category VARCHAR(255) NOT NULL,
                subcategory VARCHAR(255) NOT NULL,
                unit VARCHAR(50),
                price DECIMAL(10,2),
                description TEXT,
                is_service BOOLEAN DEFAULT 0,
                duration VARCHAR(100),
                service_cost DECIMAL(10,2)
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()

    def load_data(self):
        conn = self.get_connection()
        if not conn:
            return []
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name, sku, quantity, min_level, category, subcategory, unit,
                   price, description, is_service, duration, service_cost
            FROM stock_items
        """)
        rows = cursor.fetchall()
        conn.close()
        items = []
        for r in rows:
            items.append({
                "name": r[0],
                "sku": r[1],
                "quantity": int(r[2]) if r[2] is not None else None,
                "min_level": int(r[3]) if r[3] is not None else None,
                "category": r[4],
                "subcategory": r[5],
                "unit": r[6],
                "price": float(r[7]) if r[7] is not None else 0.0,
                "description": r[8] or "",
                "is_service": bool(r[9]),
                "duration": r[10] or "",
                "service_cost": float(r[11]) if r[11] is not None else 0.0,
            })
        return items

    def save_to_db(self, item, update=False, original_sku=None):
        conn = self.get_connection()
        if not conn:
            return False
        cursor = conn.cursor()
        try:
            if update:
                # Don't allow SKU change on update for simplicity
                cursor.execute("""
                    UPDATE stock_items
                    SET name=%s, quantity=%s, min_level=%s, category=%s, subcategory=%s,
                        unit=%s, price=%s, description=%s, is_service=%s, duration=%s, service_cost=%s
                    WHERE sku=%s
                """, (
                    item["name"], item["quantity"], item["min_level"], item["category"],
                    item["subcategory"], item["unit"], item["price"], item["description"],
                    int(item["is_service"]), item["duration"], item["service_cost"], item["sku"]
                ))
            else:
                cursor.execute("""
                    INSERT INTO stock_items (name, sku, quantity, min_level, category, subcategory,
                                             unit, price, description, is_service, duration, service_cost)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    item["name"], item["sku"], item["quantity"], item["min_level"],
                    item["category"], item["subcategory"], item["unit"], item["price"],
                    item["description"], int(item["is_service"]), item["duration"], item["service_cost"]
                ))
            conn.commit()
            return True
        except Error as e:
            messagebox.showerror("DB Error", f"Database operation failed: {e}")
            return False
        finally:
            cursor.close()
            conn.close()

    def delete_from_db(self, sku):
        conn = self.get_connection()
        if not conn:
            return
        cursor = conn.cursor()
        cursor.execute("DELETE FROM stock_items WHERE sku=%s", (sku,))
        conn.commit()
        cursor.close()
        conn.close()

    # ---------- GUI ----------
    def create_widgets(self):
        # Title
        title_frame = tk.Frame(self.root, bg="#2c3e50", height=80)
        title_frame.pack(fill="x", padx=10, pady=10)
        title_frame.pack_propagate(False)
        tk.Label(
            title_frame,
            text="Stock Level Monitor System",
            font=("Arial", 24, "bold"),
            bg="#2c3e50",
            fg="white",
        ).pack(pady=20)

        # Stats
        stats_frame = tk.Frame(self.root, bg=self.light_bg)
        stats_frame.pack(fill="x", padx=10, pady=5)

        self.total_label = self.create_stat_card(stats_frame, "Total Items", "0", "#3498db", 0)
        self.low_label = self.create_stat_card(stats_frame, "Low Stock", "0", "#e67e22", 1)
        self.critical_label = self.create_stat_card(stats_frame, "Critical", "0", "#e74c3c", 2)
        self.healthy_label = self.create_stat_card(stats_frame, "Healthy", "0", "#27ae60", 3)

        # Alerts
        self.alert_frame = tk.Frame(self.root, bg=self.light_bg)
        self.alert_frame.pack(fill="x", padx=10, pady=5)

        # Controls
        control_frame = tk.Frame(self.root, bg=self.light_bg)
        control_frame.pack(fill="x", padx=10, pady=5)

        # Filter radio
        tk.Label(control_frame, text="Filter:", bg=self.light_bg).pack(side="left", padx=5)
        self.filter_var = tk.StringVar(value="all")
        for text, val in [("All Items", "all"), ("Low Stock", "low"), ("Critical", "critical")]:
            tk.Radiobutton(
                control_frame, text=text, variable=self.filter_var, value=val,
                command=self.refresh_display, bg=self.light_bg
            ).pack(side="left", padx=5)

        # Category filter
        tk.Label(control_frame, text="Category:", bg=self.light_bg).pack(side="left", padx=8)
        self.category_var = tk.StringVar(value="All")
        self.category_cb = ttk.Combobox(control_frame, textvariable=self.category_var, width=18)
        self.category_cb.pack(side="left", padx=5)
        self.category_cb.bind("<<ComboboxSelected>>", lambda e: self.refresh_display())
        self.update_category_filter()

        # Search
        tk.Label(control_frame, text="Search:", bg=self.light_bg).pack(side="left", padx=8)
        self.search_var = tk.StringVar()
        tk.Entry(control_frame, textvariable=self.search_var, width=20).pack(side="left", padx=5)
        tk.Button(control_frame, text="🔍 Go", command=self.search_items, bg="#8e44ad", fg="white").pack(side="left", padx=5)
        tk.Button(control_frame, text="Reset", command=self.reset_filters, bg="#95a5a6", fg="white").pack(side="left", padx=5)

        # Right-side buttons
        tk.Button(control_frame, text="➕ Add Item/Service", command=self.add_item, bg="#3498db", fg="white").pack(side="right", padx=5)
        tk.Button(control_frame, text="⬇ Export CSV", command=self.export_csv, bg="#2ecc71", fg="white").pack(side="right", padx=5)
        tk.Button(control_frame, text="⬆ Import CSV", command=self.import_csv, bg="#f39c12", fg="white").pack(side="right", padx=5)
        tk.Button(control_frame, text="📊 Chart", command=self.show_chart, bg="#34495e", fg="white").pack(side="right", padx=5)
        tk.Button(control_frame, text="Dark Mode", command=self.toggle_theme, bg="#7f8c8d", fg="white").pack(side="right", padx=5)

        # Table frame
        table_frame = tk.Frame(self.root, bg="white")
        table_frame.pack(fill="both", expand=True, padx=10, pady=10)

        vsb = ttk.Scrollbar(table_frame, orient="vertical")
        hsb = ttk.Scrollbar(table_frame, orient="horizontal")

        columns = (
            "Status", "Item", "SKU", "Category", "Subcategory",
            "Quantity", "Min Level", "Unit", "Price", "Stock %"
        )
        self.columns = columns
        self.tree = ttk.Treeview(
            table_frame, columns=columns, show="headings",
            yscrollcommand=vsb.set, xscrollcommand=hsb.set
        )
        vsb.config(command=self.tree.yview)
        hsb.config(command=self.tree.xview)

        for col in columns:
            # heading supports command for clickable sorting
            self.tree.heading(col, text=col, command=lambda c=col: self.sort_column(c))
        for col, w in zip(columns, [80, 200, 120, 120, 120, 100, 100, 80, 100, 100]):
            self.tree.column(col, width=w, anchor="center")

        self.tree.tag_configure("critical", background="#ffcccc")
        self.tree.tag_configure("low", background="#ffe6cc")
        self.tree.tag_configure("good", background="#ccffcc")

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Bindings
        self.tree.bind("<Button-3>", self.show_context_menu)
        self.tree.bind("<Double-1>", self.edit_item)

    def create_stat_card(self, parent, title, value, color, column):
        frame = tk.Frame(parent, bg=color, relief="raised", bd=2)
        frame.grid(row=0, column=column, padx=5, pady=5, sticky="ew")
        parent.grid_columnconfigure(column, weight=1)
        tk.Label(frame, text=title, bg=color, fg="white").pack(pady=5)
        label = tk.Label(frame, text=value, font=("Arial", 20, "bold"), bg=color, fg="white")
        label.pack(pady=5)
        return label

    # ---------- Logic ----------
    def get_stock_status(self, item):
        if item["is_service"]:
            return "SERVICE", "good"
        if item["quantity"] is None or item["min_level"] is None or item["min_level"] == 0:
            return "UNKNOWN", "low"
        ratio = item["quantity"] / item["min_level"]
        if ratio <= 0.5:
            return "CRITICAL", "critical"
        elif ratio <= 1.0:
            return "LOW", "low"
        else:
            return "GOOD", "good"

    def update_category_filter(self):
        cats = sorted({i["category"] for i in self.items if i.get("category")})
        vals = ["All"] + cats
        self.category_cb['values'] = vals
        if self.category_var.get() not in vals:
            self.category_var.set("All")

    def get_filtered_items(self):
        f = self.filter_var.get()
        items = list(self.items)  # copy
        # category filter
        cat = self.category_var.get()
        if cat and cat != "All":
            items = [i for i in items if i["category"] == cat]

        # search filter
        search_text = self.search_var.get().lower().strip()
        if search_text:
            items = [i for i in items if (search_text in i["name"].lower() or search_text in i["sku"].lower() or search_text in (i.get("category") or "").lower())]

        # stock filters
        if f == "low":
            return [i for i in items if not i["is_service"] and i["quantity"] is not None and i["min_level"] is not None and i["quantity"] <= i["min_level"]]
        elif f == "critical":
            return [i for i in items if not i["is_service"] and i["quantity"] is not None and i["min_level"] is not None and i["quantity"] <= i["min_level"] * 0.5]
        return items

    def refresh_display(self):
        # clear tree
        for i in self.tree.get_children():
            self.tree.delete(i)

        total = len(self.items)
        low = len([i for i in self.items if not i["is_service"] and i["quantity"] is not None and i["min_level"] is not None and i["quantity"] <= i["min_level"]])
        critical = len([i for i in self.items if not i["is_service"] and i["quantity"] is not None and i["min_level"] is not None and i["quantity"] <= i["min_level"] * 0.5])
        healthy = total - low

        self.total_label.config(text=str(total))
        self.low_label.config(text=str(low))
        self.critical_label.config(text=str(critical))
        self.healthy_label.config(text=str(healthy))

        # alerts
        for w in self.alert_frame.winfo_children():
            w.destroy()
        if critical > 0:
            alert = tk.Frame(self.alert_frame, bg="#e74c3c", relief="raised", bd=2)
            alert.pack(fill="x", pady=5)
            tk.Label(
                alert,
                text=f"⚠️ CRITICAL ALERT: {critical} item(s) at critical levels!",
                font=("Arial", 12, "bold"), bg="#e74c3c", fg="white"
            ).pack(pady=10)

        # populate tree from filtered items
        for item in self.get_filtered_items():
            status, tag = self.get_stock_status(item)
            if item["is_service"]:
                percentage = 100
            else:
                if item["min_level"] and item["min_level"] > 0 and item["quantity"] is not None:
                    percentage = min((item["quantity"] / item["min_level"]) * 100, 100)
                else:
                    percentage = 0
            self.tree.insert(
                "", "end",
                values=(
                    status, item["name"], item["sku"], item["category"],
                    item["subcategory"], item["quantity"] if not item["is_service"] else "",
                    item["min_level"] if not item["is_service"] else "",
                    item["unit"] if not item["is_service"] else "",
                    f"${item['price']:.2f}" if item["price"] else "",
                    f"{percentage:.0f}%" if not item["is_service"] else "",
                ),
                tags=(tag,)
            )

        # refresh category filter choices
        self.update_category_filter()

    # ---------- Search / Reset ----------
    def search_items(self):
        self.refresh_display()

    def reset_filters(self):
        self.search_var.set("")
        self.filter_var.set("all")
        self.category_var.set("All")
        self.refresh_display()

    # ---------- Export / Import ----------
    def export_csv(self):
        filename = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], title="Save CSV")
        if not filename:
            return
        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Name", "SKU", "Category", "Subcategory", "Quantity", "Min Level", "Unit", "Price", "Description", "Is Service", "Duration", "Service Cost"])
                for item in self.items:
                    writer.writerow([
                        item["name"], item["sku"], item["category"], item["subcategory"],
                        item["quantity"], item["min_level"], item["unit"], item["price"],
                        item["description"], int(item["is_service"]), item["duration"], item["service_cost"]
                    ])
            messagebox.showinfo("Exported", f"CSV exported to {filename}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def import_csv(self):
        fname = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")], title="Select CSV to import")
        if not fname:
            return
        try:
            with open(fname, newline='', encoding="utf-8") as f:
                reader = csv.DictReader(f)
                added = 0
                failed = 0
                for row in reader:
                    # basic mapping with safe parsing
                    sku = row.get("SKU") or row.get("sku") or row.get("Sku")
                    if not sku:
                        failed += 1
                        continue
                    new_item = {
                        "name": row.get("Name") or row.get("name") or "",
                        "sku": sku,
                        "quantity": int(row.get("Quantity")) if row.get("Quantity") else (None if (row.get("Is Service") and int(row.get("Is Service"))==1) else 0),
                        "min_level": int(row.get("Min Level")) if row.get("Min Level") else (None if (row.get("Is Service") and int(row.get("Is Service"))==1) else 0),
                        "category": row.get("Category") or row.get("category") or "Uncategorized",
                        "subcategory": row.get("Subcategory") or row.get("subcategory") or "",
                        "unit": row.get("Unit") or "",
                        "price": float(row.get("Price")) if row.get("Price") else 0.0,
                        "description": row.get("Description") or "",
                        "is_service": bool(int(row.get("Is Service"))) if row.get("Is Service") else False,
                        "duration": row.get("Duration") or "",
                        "service_cost": float(row.get("Service Cost")) if row.get("Service Cost") else 0.0
                    }
                    # skip if SKU already exists
                    if any(i["sku"] == new_item["sku"] for i in self.items):
                        failed += 1
                        continue
                    ok = self.save_to_db(new_item, update=False)
                    if ok:
                        self.items.append(new_item)
                        added += 1
                    else:
                        failed += 1
                self.refresh_display()
                messagebox.showinfo("Import Result", f"Added: {added}, Failed/skipped: {failed}")
        except Exception as e:
            messagebox.showerror("Import Error", str(e))

    # ---------- Item Editing ----------
    def add_item(self):
        self.open_item_dialog()

    def edit_item(self, event=None):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select an item to edit")
            return
        vals = self.tree.item(sel[0])["values"]
        sku_val = vals[2]
        itm = next((i for i in self.items if i["sku"] == sku_val), None)
        if itm:
            self.open_item_dialog(itm)

    def delete_item(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select an item to delete")
            return
        if messagebox.askyesno("Confirm", "Are you sure you want to delete this item?"):
            vals = self.tree.item(sel[0])["values"]
            sku = vals[2]
            self.delete_from_db(sku)
            self.items = [i for i in self.items if i["sku"] != sku]
            self.refresh_display()

    def refill_stock(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select an item to refill")
            return
        vals = self.tree.item(sel[0])["values"]
        sku = vals[2]
        item = next((i for i in self.items if i["sku"] == sku), None)
        if not item:
            messagebox.showwarning("Error", "Item not found")
            return
        if item["is_service"]:
            messagebox.showwarning("Error", "Cannot refill a service")
            return
        qty = simpledialog.askinteger("Refill Stock", "Enter quantity to add:", minvalue=1)
        if qty:
            item["quantity"] = (item["quantity"] or 0) + qty
            ok = self.save_to_db(item, update=True)
            if ok:
                self.refresh_display()

    def open_item_dialog(self, item=None):
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Item/Service" if item is None else "Edit Item/Service")
        dialog.geometry("480x560")
        dialog.configure(bg="#ecf0f1")
        dialog.transient(self.root)
        dialog.grab_set()

        labels = [
            "Item Name:", "SKU:", "Quantity:", "Min Level:", "Category:", "Subcategory:",
            "Unit:", "Price:", "Description:", "Duration:", "Service Cost:"
        ]
        keys = [
            "name", "sku", "quantity", "min_level", "category", "subcategory", "unit",
            "price", "description", "duration", "service_cost"
        ]

        fields = []
        for i, (lbl, key) in enumerate(zip(labels, keys)):
            tk.Label(dialog, text=lbl, bg="#ecf0f1").grid(row=i, column=0, padx=10, pady=6, sticky="e")
            if key == "unit":
                field = ttk.Combobox(dialog, values=["pcs", "kg", "ltr", "box"], width=30)
                field.set(item[key] if item and item.get(key) else "pcs")
            else:
                field = tk.Entry(dialog, width=34)
                if item and item.get(key) is not None:
                    field.insert(0, str(item.get(key)))
            field.grid(row=i, column=1, padx=10, pady=6)
            fields.append(field)

        is_service_var = tk.IntVar(value=1 if item and item.get("is_service") else 0)
        cb = tk.Checkbutton(dialog, text="Is Service?", variable=is_service_var, bg="#ecf0f1")
        cb.grid(row=11, column=0, columnspan=2, pady=6)

        def toggle():
            state = "disabled" if is_service_var.get() else "normal"
            for idx in [2, 3, 6]:  # quantity, min_level, unit
                fields[idx].config(state=state)
            # if service -> duration & service cost enabled else disabled
            if is_service_var.get():
                fields[9].config(state="normal")
                fields[10].config(state="normal")
            else:
                fields[9].config(state="normal")
                fields[10].config(state="normal")
        cb.config(command=toggle)
        toggle()

        # barcode quick-fill: a small entry to simulate barcode scanning
        tk.Label(dialog, text="Scan/Enter SKU:", bg="#ecf0f1").grid(row=12, column=0, padx=10, pady=6, sticky="e")
        barcode_entry = tk.Entry(dialog, width=34)
        barcode_entry.grid(row=12, column=1, padx=10, pady=6)
        def barcode_fill():
            code = barcode_entry.get().strip()
            if not code:
                return
            # if SKU exists, load that item into fields for quick edit
            found = next((it for it in self.items if it["sku"] == code), None)
            if found:
                # populate fields with found item (use string form)
                for idx, key in enumerate(keys):
                    val = found.get(key)
                    fields[idx].delete(0, tk.END)
                    fields[idx].insert(0, "" if val is None else str(val))
                is_service_var.set(1 if found.get("is_service") else 0)
                toggle()
            else:
                # auto-fill SKU field for new item
                fields[1].delete(0, tk.END)
                fields[1].insert(0, code)
        tk.Button(dialog, text="Fill", command=barcode_fill).grid(row=12, column=2, padx=5)

        def save():
            try:
                name = fields[0].get().strip()
                sku = fields[1].get().strip()
                quantity = int(fields[2].get()) if not is_service_var.get() and fields[2].get() != "" else None
                min_level = int(fields[3].get()) if not is_service_var.get() and fields[3].get() != "" else None
                category = fields[4].get().strip() or "Uncategorized"
                subcategory = fields[5].get().strip() or ""
                unit = fields[6].get().strip() if not is_service_var.get() else ""
                price = float(fields[7].get()) if fields[7].get() else 0.0
                description = fields[8].get().strip()
                duration = fields[9].get().strip() if is_service_var.get() else ""
                service_cost = float(fields[10].get()) if is_service_var.get() and fields[10].get() else 0.0
                is_service = bool(is_service_var.get())

                if not all([name, sku, category, subcategory is not None]):
                    # require name, sku and category; subcategory can be empty string
                    if not name or not sku or not category:
                        messagebox.showerror("Error", "Please fill in required fields (Name, SKU, Category)")
                        return

                new_item = {
                    "name": name, "sku": sku, "quantity": quantity, "min_level": min_level,
                    "category": category, "subcategory": subcategory, "unit": unit,
                    "price": price, "description": description, "is_service": is_service,
                    "duration": duration, "service_cost": service_cost,
                }

                if item:
                    # updating existing item. Prevent SKU change
                    if sku != item["sku"]:
                        messagebox.showerror("Error", "Changing SKU is not allowed on edit")
                        return
                    ok = self.save_to_db(new_item, update=True)
                    if ok:
                        for i, x in enumerate(self.items):
                            if x["sku"] == item["sku"]:
                                self.items[i] = new_item
                                break
                else:
                    if any(i["sku"] == sku for i in self.items):
                        messagebox.showerror("Error", "SKU already exists")
                        return
                    ok = self.save_to_db(new_item, update=False)
                    if ok:
                        self.items.append(new_item)

                self.refresh_display()
                dialog.destroy()
            except ValueError:
                messagebox.showerror("Error", "Enter valid numbers for quantity, min level, price, or service cost")

        btn_frame = tk.Frame(dialog, bg="#ecf0f1")
        btn_frame.grid(row=13, column=0, columnspan=3, pady=14)
        tk.Button(btn_frame, text="Save", command=save, bg="#27ae60", fg="white", padx=20).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Cancel", command=dialog.destroy, bg="#95a5a6", fg="white", padx=20).pack(side="left", padx=6)

    # ---------- Context Menu ----------
    def show_context_menu(self, event):
        # select row under pointer
        iid = self.tree.identify_row(event.y)
        if iid:
            # set selection to this row
            self.tree.selection_set(iid)
        sel = self.tree.selection()
        if not sel:
            return
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Edit", command=self.edit_item)
        menu.add_command(label="Delete", command=self.delete_item)
        menu.add_command(label="Refill Stock", command=self.refill_stock)
        menu.post(event.x_root, event.y_root)

    # ---------- Sorting ----------
    def sort_column(self, col):
        # toggle direction
        reverse = self.sort_reverse.get(col, False)
        self.sort_reverse[col] = not reverse

        # map displayed column to item key
        col_map = {
            "Status": lambda it: self.get_stock_status(it)[0],
            "Item": lambda it: (it["name"] or "").lower(),
            "SKU": lambda it: (it["sku"] or "").lower(),
            "Category": lambda it: (it["category"] or "").lower(),
            "Subcategory": lambda it: (it["subcategory"] or "").lower(),
            "Quantity": lambda it: (it["quantity"] if it["quantity"] is not None else -9999999),
            "Min Level": lambda it: (it["min_level"] if it["min_level"] is not None else -9999999),
            "Unit": lambda it: (it["unit"] or "").lower(),
            "Price": lambda it: (it["price"] if it["price"] is not None else 0.0),
            "Stock %": lambda it: ( (it["quantity"] / it["min_level"]) if (it["min_level"] and it["min_level"]>0 and it["quantity"] is not None) else -9999999)
        }
        keyfunc = col_map.get(col, lambda it: it.get(col, ""))
        try:
            self.items.sort(key=keyfunc, reverse=self.sort_reverse[col])
            self.refresh_display()
        except Exception as e:
            messagebox.showerror("Sort Error", str(e))

    # ---------- Chart ----------
    def show_chart(self):
        if not MATPLOTLIB_AVAILABLE:
            messagebox.showwarning("Missing library", "matplotlib not available. Install matplotlib to view charts.")
            return
        # sample bar chart of quantities by item (limited to top 20 for readability)
        data_items = [i for i in self.items if not i["is_service"] and i["quantity"] is not None]
        if not data_items:
            messagebox.showinfo("No Data", "No stocked items to chart.")
            return
        # sort by quantity ascending
        data_items.sort(key=lambda x: x.get("quantity") or 0)
        labels = [f"{i['name']} ({i['sku']})" for i in data_items][-20:]
        quantities = [i['quantity'] for i in data_items][-20:]
        plt.figure(figsize=(10, 6))
        plt.barh(labels, quantities)
        plt.xlabel("Quantity")
        plt.title("Stock Quantities (top 20 shown)")
        plt.tight_layout()
        plt.show()

    # ---------- Misc ----------
    def low_stock_popup_once(self):
        # show a popup once at startup if any low stock items
        low_items = [i for i in self.items if not i["is_service"] and i["quantity"] is not None and i["min_level"] is not None and i["quantity"] <= i["min_level"]]
        if low_items:
            messagebox.showwarning("Low Stock Alert", f"{len(low_items)} item(s) are at or below min level. Check dashboard.")

    def toggle_theme(self):
        # simple light/dark toggle (changes bg and some widget colors)
        if self.current_theme == "light":
            self.current_theme = "dark"
            bg = self.dark_bg
            fg = "white"
        else:
            self.current_theme = "light"
            bg = self.light_bg
            fg = "black"
        self.root.configure(bg=bg)
        # change a few frames/labels - easiest approach is to rebuild UI
        # simpler: destroy and recreate all widgets (keeps data)
        for widget in self.root.winfo_children():
            widget.destroy()
        self.create_widgets()
        self.refresh_display()

# ---------- run ----------
if __name__ == "__main__":
    root = tk.Tk()
    app = StockMonitorApp(root)
    root.mainloop()
