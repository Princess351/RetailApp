import tkinter as tk
from tkinter import ttk, messagebox
import mysql.connector
from mysql.connector import Error


class StockMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Stock Level Monitor System")
        self.root.geometry("1250x700")
        self.root.configure(bg="#f0f0f0")

        # DB settings
        self.db_config = {
            "host": "localhost",
            "user": "stock_user",
            "password": "kathmandu5**",   # 👈 replace this with your real MySQL password
            "database": "stock_db"
        }

        self.init_db()
        self.items = self.load_data()

        # GUI setup
        self.create_widgets()
        self.refresh_display()

    # ---------- DATABASE ----------
    def get_connection(self):
        try:
            conn = mysql.connector.connect(**self.db_config)
            return conn
        except Error as e:
            messagebox.showerror("Database Error", f"Error connecting to MySQL:\n{e}")
            return None

    def init_db(self):
        """Create table if not exists."""
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
                "quantity": r[2],
                "min_level": r[3],
                "category": r[4],
                "subcategory": r[5],
                "unit": r[6],
                "price": float(r[7]) if r[7] else 0,
                "description": r[8],
                "is_service": bool(r[9]),
                "duration": r[10],
                "service_cost": float(r[11]) if r[11] else 0,
            })
        return items

    def save_to_db(self, item, update=False):
        conn = self.get_connection()
        if not conn:
            return
        cursor = conn.cursor()
        if update:
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

        stats_frame = tk.Frame(self.root, bg="#f0f0f0")
        stats_frame.pack(fill="x", padx=10, pady=5)

        self.total_label = self.create_stat_card(stats_frame, "Total Items", "0", "#3498db", 0)
        self.low_label = self.create_stat_card(stats_frame, "Low Stock", "0", "#e67e22", 1)
        self.critical_label = self.create_stat_card(stats_frame, "Critical", "0", "#e74c3c", 2)
        self.healthy_label = self.create_stat_card(stats_frame, "Healthy", "0", "#27ae60", 3)

        self.alert_frame = tk.Frame(self.root, bg="#f0f0f0")
        self.alert_frame.pack(fill="x", padx=10, pady=5)

        control_frame = tk.Frame(self.root, bg="#f0f0f0")
        control_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(control_frame, text="Filter:", bg="#f0f0f0").pack(side="left", padx=5)
        self.filter_var = tk.StringVar(value="all")
        for text, val in [("All Items", "all"), ("Low Stock", "low"), ("Critical", "critical")]:
            tk.Radiobutton(
                control_frame, text=text, variable=self.filter_var, value=val,
                command=self.refresh_display, bg="#f0f0f0"
            ).pack(side="left", padx=5)

        tk.Button(
            control_frame, text="➕ Add Item/Service", command=self.add_item,
            bg="#3498db", fg="white", font=("Arial", 10, "bold"), padx=15, pady=5
        ).pack(side="right", padx=5)

        table_frame = tk.Frame(self.root, bg="white")
        table_frame.pack(fill="both", expand=True, padx=10, pady=10)

        vsb = ttk.Scrollbar(table_frame, orient="vertical")
        hsb = ttk.Scrollbar(table_frame, orient="horizontal")

        columns = (
            "Status", "Item", "SKU", "Category", "Subcategory",
            "Quantity", "Min Level", "Unit", "Price", "Stock %"
        )
        self.tree = ttk.Treeview(
            table_frame, columns=columns, show="headings",
            yscrollcommand=vsb.set, xscrollcommand=hsb.set
        )
        vsb.config(command=self.tree.yview)
        hsb.config(command=self.tree.xview)

        for col in columns:
            self.tree.heading(col, text=col)

        for col, w in zip(columns, [80, 150, 100, 120, 120, 100, 100, 80, 100, 100]):
            self.tree.column(col, width=w, anchor="center")

        self.tree.tag_configure("critical", background="#ffcccc")
        self.tree.tag_configure("low", background="#ffe6cc")
        self.tree.tag_configure("good", background="#ccffcc")

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

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
        if item["quantity"] is None or item["min_level"] is None:
            return "UNKNOWN", "low"
        ratio = item["quantity"] / item["min_level"]
        if ratio <= 0.5:
            return "CRITICAL", "critical"
        elif ratio <= 1.0:
            return "LOW", "low"
        else:
            return "GOOD", "good"

    def get_filtered_items(self):
        f = self.filter_var.get()
        if f == "low":
            return [i for i in self.items if not i["is_service"] and i["quantity"] <= i["min_level"]]
        elif f == "critical":
            return [i for i in self.items if not i["is_service"] and i["quantity"] <= i["min_level"] * 0.5]
        return self.items

    def refresh_display(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        total = len(self.items)
        low = len([i for i in self.items if not i["is_service"] and i["quantity"] <= i["min_level"]])
        critical = len([i for i in self.items if not i["is_service"] and i["quantity"] <= i["min_level"] * 0.5])
        healthy = total - low

        self.total_label.config(text=str(total))
        self.low_label.config(text=str(low))
        self.critical_label.config(text=str(critical))
        self.healthy_label.config(text=str(healthy))

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

        for item in self.get_filtered_items():
            status, tag = self.get_stock_status(item)
            percentage = (
                100 if item["is_service"] else min((item["quantity"] / item["min_level"]) * 100, 100)
            )
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

    # ---------- Item Editing ----------
    def add_item(self):
        self.open_item_dialog()

    def edit_item(self, event=None):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select an item to edit")
            return
        vals = self.tree.item(sel[0])["values"]
        itm = next((i for i in self.items if i["sku"] == vals[2]), None)
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

    def open_item_dialog(self, item=None):
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Item/Service" if item is None else "Edit Item/Service")
        dialog.geometry("450x500")
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
            tk.Label(dialog, text=lbl, bg="#ecf0f1").grid(row=i, column=0, padx=10, pady=5, sticky="e")
            if key == "unit":
                field = ttk.Combobox(dialog, values=["pcs", "kg", "ltr", "box"], width=27)
                field.set(item[key] if item else "pcs")
            else:
                field = tk.Entry(dialog, width=30)
                if item and item.get(key) is not None:
                    field.insert(0, str(item[key]))
            field.grid(row=i, column=1, padx=10, pady=5)
            fields.append(field)

        is_service_var = tk.IntVar(value=1 if item and item.get("is_service") else 0)
        cb = tk.Checkbutton(dialog, text="Is Service?", variable=is_service_var, bg="#ecf0f1")
        cb.grid(row=11, column=0, columnspan=2, pady=10)

        def toggle():
            if is_service_var.get():
                for idx in [2, 3, 6]:
                    fields[idx].config(state="disabled")
            else:
                for idx in [2, 3, 6]:
                    fields[idx].config(state="normal")

        cb.config(command=toggle)
        toggle()

        def save():
            try:
                name = fields[0].get().strip()
                sku = fields[1].get().strip()
                quantity = int(fields[2].get()) if not is_service_var.get() else None
                min_level = int(fields[3].get()) if not is_service_var.get() else None
                category = fields[4].get().strip()
                subcategory = fields[5].get().strip()
                unit = fields[6].get().strip() if not is_service_var.get() else ""
                price = float(fields[7].get()) if fields[7].get() else 0
                description = fields[8].get().strip()
                duration = fields[9].get().strip() if is_service_var.get() else ""
                service_cost = float(fields[10].get()) if is_service_var.get() and fields[10].get() else 0
                is_service = bool(is_service_var.get())

                if not all([name, sku, category, subcategory]):
                    messagebox.showerror("Error", "Please fill in all required fields")
                    return

                new_item = {
                    "name": name, "sku": sku, "quantity": quantity, "min_level": min_level,
                    "category": category, "subcategory": subcategory, "unit": unit,
                    "price": price, "description": description, "is_service": is_service,
                    "duration": duration, "service_cost": service_cost,
                }

                if item:
                    self.save_to_db(new_item, update=True)
                    for i, x in enumerate(self.items):
                        if x["sku"] == item["sku"]:
                            self.items[i] = new_item
                            break
                else:
                    if any(i["sku"] == sku for i in self.items):
                        messagebox.showerror("Error", "SKU already exists")
                        return
                    self.save_to_db(new_item)
                    self.items.append(new_item)

                self.refresh_display()
                dialog.destroy()
            except ValueError:
                messagebox.showerror("Error", "Enter valid numbers for quantity, min level, price, or service cost")

        btn_frame = tk.Frame(dialog, bg="#ecf0f1")
        btn_frame.grid(row=12, column=0, columnspan=2, pady=20)
        tk.Button(btn_frame, text="Save", command=save, bg="#27ae60", fg="white", padx=20).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=dialog.destroy, bg="#95a5a6", fg="white", padx=20).pack(side="left", padx=5)

    def show_context_menu(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Edit", command=self.edit_item)
        menu.add_command(label="Delete", command=self.delete_item)
        menu.post(event.x_root, event.y_root)


if __name__ == "__main__":
    root = tk.Tk()
    app = StockMonitorApp(root)
    root.mainloop()
