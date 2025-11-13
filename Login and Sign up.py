import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
import secrets, hashlib, binascii
from datetime import datetime
import mysql.connector

# ---------- Security ----------
PBKDF2_ITER = 150_000
SALT_LEN = 16
HASH_LEN = 32

def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_bytes(SALT_LEN)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, PBKDF2_ITER, dklen=HASH_LEN)
    return salt, pwd_hash

def verify_password(password, salt, pwd_hash):
    test = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, PBKDF2_ITER, dklen=HASH_LEN)
    return secrets.compare_digest(test, pwd_hash)

def b2h(b): return binascii.hexlify(b).decode()
def h2b(h): return binascii.unhexlify(h.encode())

# ---------- Database ----------
class DB:
    def __init__(self):
        # First, connect without specifying the database to check/create it
        temp_conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="suman"
        )
        temp_cursor = temp_conn.cursor()
        
        # Check if the database exists
        temp_cursor.execute("SHOW DATABASES LIKE 'retail_db'")
        if not temp_cursor.fetchone():
            # Create the database if it doesn't exist
            temp_cursor.execute("CREATE DATABASE retail_db")
            print("Database 'retail_db' created successfully.")
        
        temp_conn.close()
        
        # Now connect to the database
        self.conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="suman",
            database="retail_db"
        )
        self.cursor = self.conn.cursor()
        self.create_tables()
        self.ensure_admin()
        self.add_sample_products()
    def create_tables(self):
        # Users table
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INT PRIMARY KEY AUTO_INCREMENT,
            full_name VARCHAR(255), email VARCHAR(255) UNIQUE, username VARCHAR(255) UNIQUE,
            salt VARCHAR(128), pwd_hash VARCHAR(128),
            role VARCHAR(50), requested_role VARCHAR(50),
            status VARCHAR(50), created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        
        # Products table
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS products(
            id INT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            price FLOAT NOT NULL,
            stock INT DEFAULT 0,
            category VARCHAR(100),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        
        # Cart table
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS cart(
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT,
            product_id INT,
            quantity INT DEFAULT 1,
            added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )""")
        
        self.conn.commit()

    def ensure_admin(self):
        self.cursor.execute("SELECT * FROM users WHERE username=%s", ("admin",))
        if not self.cursor.fetchone():
            salt, h = hash_password("Admin@123")
            self.cursor.execute("""INSERT INTO users(full_name,email,username,salt,pwd_hash,role,requested_role,status)
                         VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                      ("Default Administrator","admin@example.com","admin",b2h(salt),b2h(h),"admin","admin","active"))
            self.conn.commit()

    def add_sample_products(self):
        self.cursor.execute("SELECT COUNT(*) FROM products")
        if self.cursor.fetchone()[0] == 0:
            products = [
                ("Laptop", "High-performance laptop for work and gaming", 999.99, 15, "Electronics"),
                ("Wireless Mouse", "Ergonomic wireless mouse", 29.99, 50, "Electronics"),
                ("Office Chair", "Comfortable ergonomic office chair", 199.99, 20, "Furniture"),
                ("Desk Lamp", "LED desk lamp with adjustable brightness", 39.99, 35, "Furniture"),
                ("Notebook Set", "Set of 5 premium notebooks", 14.99, 100, "Stationery"),
                ("Pen Set", "Professional pen set", 24.99, 75, "Stationery"),
                ("Water Bottle", "Insulated stainless steel water bottle", 19.99, 60, "Accessories"),
                ("Backpack", "Laptop backpack with USB charging port", 49.99, 40, "Accessories"),
            ]
            self.cursor.executemany("INSERT INTO products(name,description,price,stock,category) VALUES(%s,%s,%s,%s,%s)", products)
            self.conn.commit()

    def add_user(self, name, email, username, password, requested_role):
        try:
            salt, h = hash_password(password)
            # Customers are auto-approved
            if requested_role == "customer":
                role = "customer"
                status = "active"
            else:
                role = "unassigned"
                status = "pending"
            
            self.cursor.execute("""INSERT INTO users(full_name,email,username,salt,pwd_hash,role,requested_role,status)
                                 VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                              (name,email,username,b2h(salt),b2h(h),role,requested_role,status))
            self.conn.commit()
            return True
        except mysql.connector.IntegrityError:
            return False

    def auth(self, username, pwd):
        self.cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
        u = self.cursor.fetchone()
        if not u: return None
        if verify_password(pwd, h2b(u[4]), h2b(u[5])):
            return {
                "id": u[0],"full_name": u[1],"email": u[2],"username": u[3],
                "role": u[6],"requested_role": u[7],"status": u[8]
            }
        return None

    def list_pending(self):
        self.cursor.execute("SELECT id,full_name,email,username,requested_role,created_at FROM users WHERE status='pending'")
        return self.cursor.fetchall()

    def list_all(self):
        self.cursor.execute("SELECT id,full_name,email,username,role,requested_role,status,created_at FROM users WHERE role!='customer' ORDER BY created_at DESC")
        return self.cursor.fetchall()

    def list_customers(self):
        self.cursor.execute("SELECT id,full_name,email,username,created_at FROM users WHERE role='customer' ORDER BY created_at DESC")
        return self.cursor.fetchall()

    def update_role(self, uid, new_role, status="active"):
        self.cursor.execute("UPDATE users SET role=%s,status=%s WHERE id=%s", (new_role,status,uid))
        self.conn.commit()

    def reject_user(self, uid):
        self.cursor.execute("UPDATE users SET status='rejected' WHERE id=%s", (uid,))
        self.conn.commit()

    def delete_user(self, uid):
        self.cursor.execute("DELETE FROM users WHERE id=%s", (uid,))
        self.conn.commit()

    def get_by_id(self, uid):
        self.cursor.execute("SELECT * FROM users WHERE id=%s", (uid,))
        return self.cursor.fetchone()

    def change_password(self, uid, new_password):
        salt, h = hash_password(new_password)
        self.cursor.execute("UPDATE users SET salt=%s, pwd_hash=%s WHERE id=%s", (b2h(salt), b2h(h), uid))
        self.conn.commit()

    # Product methods
    def get_all_products(self):
        self.cursor.execute("SELECT * FROM products ORDER BY category, name")
        return self.cursor.fetchall()

    def get_products_by_category(self, category):
        self.cursor.execute("SELECT * FROM products WHERE category=%s ORDER BY name", (category,))
        return self.cursor.fetchall()

    def get_categories(self):
        self.cursor.execute("SELECT DISTINCT category FROM products ORDER BY category")
        return [r[0] for r in self.cursor.fetchall()]

    # Cart methods
    def add_to_cart(self, user_id, product_id, quantity=1):
        self.cursor.execute("SELECT * FROM cart WHERE user_id=%s AND product_id=%s", (user_id, product_id))
        existing = self.cursor.fetchone()
        
        if existing:
            self.cursor.execute("UPDATE cart SET quantity=quantity+%s WHERE user_id=%s AND product_id=%s", 
                     (quantity, user_id, product_id))
        else:
            self.cursor.execute("INSERT INTO cart(user_id,product_id,quantity) VALUES(%s,%s,%s)", 
                     (user_id, product_id, quantity))
        self.conn.commit()

    def get_cart(self, user_id):
        self.cursor.execute("""
            SELECT c.id, p.name, p.price, c.quantity, (p.price * c.quantity) as total, p.id
            FROM cart c
            JOIN products p ON c.product_id = p.id
            WHERE c.user_id=%s
        """, (user_id,))
        return self.cursor.fetchall()

    def remove_from_cart(self, cart_id):
        self.cursor.execute("DELETE FROM cart WHERE id=%s", (cart_id,))
        self.conn.commit()

    def clear_cart(self, user_id):
        self.cursor.execute("DELETE FROM cart WHERE user_id=%s", (user_id,))
        self.conn.commit()

# ---------- Main App ----------
class App(ctk.CTk):
    def __init__(self, db):
        super().__init__()
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
        self.db = db
        self.title("Retail Management System")
        self.geometry("950x650")
        self.minsize(800, 550)
        self.resizable(True, True)
        self.current_user = None
        self.configure(fg_color="#f0f0f0")

        style = ttk.Style()
        style.configure("Treeview", font=("Arial", 12))
        style.configure("Treeview.Heading", font=("Arial", 13, "bold"))

        self.container = ctk.CTkFrame(self, fg_color="#f0f0f0")
        self.container.pack(fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for F in (LoginPage, Signup, AdminDashboard, StaffDashboard, CustomerDashboard, ChangePassword, RegisterCustomer):
            f = F(self.container, self)
            self.frames[F.__name__] = f
            f.grid(row=0, column=0, sticky="nsew")

        self.show("LoginPage")

    def show(self, name):
        self.frames[name].tkraise()

    def login_success(self, user):
        self.current_user = user
        role = user["role"]
        if role == "admin":
            self.frames["AdminDashboard"].refresh()
            self.show("AdminDashboard")
        elif role == "customer":
            self.frames["CustomerDashboard"].refresh()
            self.show("CustomerDashboard")
        else:
            self.frames["StaffDashboard"].refresh()
            self.show("StaffDashboard")

    def logout(self):
        self.current_user = None
        self.show("LoginPage")

# ---------- Login Page ----------
class LoginPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="#f0f0f0")
        self.app = app
        
        # Main container
        main_frame = ctk.CTkFrame(self, corner_radius=10, fg_color="#e0e0e0")
        main_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        # Header
        header = ctk.CTkFrame(main_frame, fg_color="transparent")
        header.pack(pady=(20, 30), fill="x")
        
        ctk.CTkLabel(header, text="🔐", font=("Arial", 48)).pack()
        ctk.CTkLabel(header, text="Retail Management System", 
                 font=("Arial", 24, "bold")).pack()
        ctk.CTkLabel(header, text="Secure Login Portal", 
                 font=("Arial", 12)).pack()
        
        # Login Form
        form_frame = ctk.CTkFrame(main_frame, corner_radius=10, fg_color="transparent")
        form_frame.pack(pady=10, padx=40, fill="both")
        
        self.username = tk.StringVar()
        self.password = tk.StringVar()
        
        # Username
        ctk.CTkLabel(form_frame, text="Username:", font=("Arial", 12)).grid(row=0, column=0, sticky="w", pady=(0,5))
        username_entry = ctk.CTkEntry(form_frame, textvariable=self.username, width=300, font=("Arial", 12), corner_radius=6)
        username_entry.grid(row=1, column=0, pady=(0,15))
        username_entry.focus()
        
        # Password
        ctk.CTkLabel(form_frame, text="Password:", font=("Arial", 12)).grid(row=2, column=0, sticky="w", pady=(0,5))
        password_entry = ctk.CTkEntry(form_frame, textvariable=self.password, show="*", width=300, font=("Arial", 12), corner_radius=6)
        password_entry.grid(row=3, column=0, pady=(0,20))
        
        # Bind Enter key
        username_entry.bind('<Return>', lambda e: self.do_login())
        password_entry.bind('<Return>', lambda e: self.do_login())
        
        # Login Button
        login_btn = ctk.CTkButton(form_frame, text="Login", command=self.do_login, width=300, corner_radius=6)
        login_btn.grid(row=4, column=0, pady=(0,10))
        
        # Separator
        ttk.Separator(form_frame, orient="horizontal").grid(row=5, column=0, sticky="ew", pady=15)
        
        # Sign Up Button
        signup_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        signup_frame.grid(row=6, column=0)
        ctk.CTkLabel(signup_frame, text="Don't have an account?", font=("Arial", 11)).pack(side="left", padx=(0,5))
        signup_btn = ctk.CTkButton(signup_frame, text="Sign Up", command=lambda: app.show("Signup"), corner_radius=6)
        signup_btn.pack(side="left")

    def do_login(self):
        username = self.username.get().strip()
        password = self.password.get()
        
        if not username or not password:
            messagebox.showerror("Error", "Please enter both username and password")
            return
            
        user = self.app.db.auth(username, password)
        if not user:
            messagebox.showerror("Login Failed", "Invalid username or password")
            return
        if user["status"] == "pending":
            messagebox.showinfo("Pending Approval", "Your account is awaiting admin approval.")
            return
        if user["status"] == "rejected":
            messagebox.showerror("Access Denied", "Your signup request has been rejected.")
            return
        
        self.username.set("")
        self.password.set("")
        self.app.login_success(user)

# ---------- Signup ----------
class Signup(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="#f0f0f0")
        self.app = app
        
        # Main container
        main_frame = ctk.CTkFrame(self, corner_radius=10, fg_color="#e0e0e0")
        main_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        # Header
        ctk.CTkLabel(main_frame, text="Create New Account", 
                 font=("Arial", 24, "bold")).pack(pady=(20, 20))
        
        # Form
        form = ctk.CTkFrame(main_frame, corner_radius=10, fg_color="transparent")
        form.pack(padx=30)
        
        self.vars = {n: tk.StringVar() for n in ("name", "email", "username", "pwd", "conf", "req")}
        
        fields = [
            ("Full Name", "name"),
            ("Email", "email"),
            ("Username", "username"),
            ("Password", "pwd"),
            ("Confirm Password", "conf")
        ]
        
        for i, (lbl, key) in enumerate(fields):
            ctk.CTkLabel(form, text=lbl + ":", font=("Arial", 12)).grid(row=i, column=0, sticky="e", pady=8, padx=(0,10))
            entry = ctk.CTkEntry(form, textvariable=self.vars[key], width=300, 
                            show="*" if key in ["pwd", "conf"] else "", font=("Arial", 12), corner_radius=6)
            entry.grid(row=i, column=1, pady=8)
        
        ctk.CTkLabel(form, text="Register As:", font=("Arial", 12)).grid(row=5, column=0, sticky="e", pady=8, padx=(0,10))
        cb = ctk.CTkComboBox(form, variable=self.vars["req"], 
                         values=["customer", "staff", "supervisor"], width=300, font=("Arial", 12))
        cb.grid(row=5, column=1, pady=8)
        self.vars["req"].set("customer")
        
        # Info label
        self.info_label = ctk.CTkLabel(form, text="Note: Customer accounts are activated immediately.\nStaff accounts require admin approval.", 
                                   font=("Arial", 10), justify="center")
        self.info_label.grid(row=6, column=0, columnspan=2, pady=10)
        
        # Buttons
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(pady=20)
        ctk.CTkButton(btn_frame, text="Register", command=self.submit, width=150, corner_radius=6).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Back to Login", command=lambda: self.app.show("LoginPage"), width=150, corner_radius=6).pack(side="left", padx=5)

    def submit(self):
        v = self.vars
        if not all(v[k].get().strip() for k in ("name", "email", "username", "pwd", "conf")):
            messagebox.showerror("Error", "All fields are required.")
            return
        if v["pwd"].get() != v["conf"].get():
            messagebox.showerror("Error", "Passwords do not match.")
            return
        if len(v["pwd"].get()) < 6:
            messagebox.showerror("Error", "Password must be at least 6 characters.")
            return
            
        ok = self.app.db.add_user(v["name"].get(), v["email"].get(), 
                                   v["username"].get(), v["pwd"].get(), v["req"].get())
        if ok:
            if v["req"].get() == "customer":
                messagebox.showinfo("Success", "Registration complete! You can now login.")
            else:
                messagebox.showinfo("Success", "Registration complete! Please wait for admin approval.")
            for key in self.vars:
                self.vars[key].set("")
            self.vars["req"].set("customer")
            self.app.show("LoginPage")
        else:
            messagebox.showerror("Error", "Username or email already exists.")

# ---------- Change Password ----------
class ChangePassword(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="#f0f0f0")
        self.app = app
        
        main_frame = ctk.CTkFrame(self, corner_radius=10, fg_color="#e0e0e0")
        main_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        ctk.CTkLabel(main_frame, text="Change Password", 
                 font=("Arial", 24, "bold")).pack(pady=(20, 20))
        
        form = ctk.CTkFrame(main_frame, corner_radius=10, fg_color="transparent")
        form.pack(padx=30)
        
        self.old_pwd = tk.StringVar()
        self.new_pwd = tk.StringVar()
        self.conf_pwd = tk.StringVar()
        
        ctk.CTkLabel(form, text="Current Password:", font=("Arial", 12)).grid(row=0, column=0, sticky="e", pady=8, padx=(0,10))
        ctk.CTkEntry(form, textvariable=self.old_pwd, show="*", width=300, font=("Arial", 12), corner_radius=6).grid(row=0, column=1, pady=8)
        
        ctk.CTkLabel(form, text="New Password:", font=("Arial", 12)).grid(row=1, column=0, sticky="e", pady=8, padx=(0,10))
        ctk.CTkEntry(form, textvariable=self.new_pwd, show="*", width=300, font=("Arial", 12), corner_radius=6).grid(row=1, column=1, pady=8)
        
        ctk.CTkLabel(form, text="Confirm New Password:", font=("Arial", 12)).grid(row=2, column=0, sticky="e", pady=8, padx=(0,10))
        ctk.CTkEntry(form, textvariable=self.conf_pwd, show="*", width=300, font=("Arial", 12), corner_radius=6).grid(row=2, column=1, pady=8)
        
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(pady=20)
        ctk.CTkButton(btn_frame, text="Change Password", command=self.change_pwd, width=180, corner_radius=6).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Cancel", command=self.go_back, width=180, corner_radius=6).pack(side="left", padx=5)

    def change_pwd(self):
        user = self.app.current_user
        old = self.old_pwd.get()
        new = self.new_pwd.get()
        conf = self.conf_pwd.get()
        
        if not old or not new or not conf:
            messagebox.showerror("Error", "All fields are required.")
            return
        
        # Verify old password
        if not self.app.db.auth(user["username"], old):
            messagebox.showerror("Error", "Current password is incorrect.")
            return
        
        if new != conf:
            messagebox.showerror("Error", "New passwords do not match.")
            return
        
        if len(new) < 6:
            messagebox.showerror("Error", "Password must be at least 6 characters.")
            return
        
        self.app.db.change_password(user["id"], new)
        messagebox.showinfo("Success", "Password changed successfully!")
        
        self.old_pwd.set("")
        self.new_pwd.set("")
        self.conf_pwd.set("")
        self.go_back()

    def go_back(self):
        role = self.app.current_user["role"]
        if role == "admin":
            self.app.show("AdminDashboard")
        elif role == "customer":
            self.app.show("CustomerDashboard")
        else:
            self.app.show("StaffDashboard")

# ---------- Register Customer (Staff Feature) ----------
class RegisterCustomer(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="#f0f0f0")
        self.app = app
        
        main_frame = ctk.CTkFrame(self, corner_radius=10, fg_color="#e0e0e0")
        main_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        ctk.CTkLabel(main_frame, text="Register New Customer", 
                 font=("Arial", 24, "bold")).pack(pady=(20, 20))
        
        form = ctk.CTkFrame(main_frame, corner_radius=10, fg_color="transparent")
        form.pack(padx=30)
        
        self.vars = {n: tk.StringVar() for n in ("name", "email", "username", "pwd", "conf")}
        
        fields = [
            ("Full Name", "name"),
            ("Email", "email"),
            ("Username", "username"),
            ("Password", "pwd"),
            ("Confirm Password", "conf")
        ]
        
        for i, (lbl, key) in enumerate(fields):
            ctk.CTkLabel(form, text=lbl + ":", font=("Arial", 12)).grid(row=i, column=0, sticky="e", pady=8, padx=(0,10))
            entry = ctk.CTkEntry(form, textvariable=self.vars[key], width=300, 
                            show="*" if key in ["pwd", "conf"] else "", font=("Arial", 12), corner_radius=6)
            entry.grid(row=i, column=1, pady=8)
        
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(pady=20)
        ctk.CTkButton(btn_frame, text="Register Customer", command=self.submit, width=180, corner_radius=6).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Cancel", command=lambda: self.app.show("StaffDashboard"), width=180, corner_radius=6).pack(side="left", padx=5)

    def submit(self):
        v = self.vars
        if not all(v[k].get().strip() for k in ("name", "email", "username", "pwd", "conf")):
            messagebox.showerror("Error", "All fields are required.")
            return
        if v["pwd"].get() != v["conf"].get():
            messagebox.showerror("Error", "Passwords do not match.")
            return
        if len(v["pwd"].get()) < 6:
            messagebox.showerror("Error", "Password must be at least 6 characters.")
            return
            
        ok = self.app.db.add_user(v["name"].get(), v["email"].get(), 
                                   v["username"].get(), v["pwd"].get(), "customer")
        if ok:
            messagebox.showinfo("Success", "Customer registered successfully!")
            for key in self.vars:
                self.vars[key].set("")
            self.app.show("StaffDashboard")
        else:
            messagebox.showerror("Error", "Username or email already exists.")

# ---------- Admin Dashboard ----------
class AdminDashboard(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.uid = None
        
        # Header
        header = ctk.CTkFrame(self)
        header.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(header, text="Admin Dashboard", font=("Arial", 24, "bold")).pack(side="left")
        
        btn_frame = ctk.CTkFrame(header)
        btn_frame.pack(side="right")
        ctk.CTkButton(btn_frame, text="Change Password", command=lambda: app.show("ChangePassword"), corner_radius=6).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="Logout", command=self.app.logout, corner_radius=6).pack(side="left", padx=2)
        
        # Notebook for tabs
        notebook = ctk.CTkTabview(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Tab 1: Pending Approvals
        pending_tab = notebook.add("Pending Approvals")
        
        ctk.CTkLabel(pending_tab, text="Users Awaiting Approval", font=("Arial", 14, "bold")).pack(pady=10)
        
        list_frame = ctk.CTkFrame(pending_tab)
        list_frame.pack(fill="both", expand=True, padx=10)
        
        self.pending_list = tk.Listbox(list_frame, width=50, height=8, font=("Arial", 12))
        self.pending_list.pack(side="left", fill="both", expand=True)
        self.pending_list.bind("<<ListboxSelect>>", self.sel)
        
        scrollbar = ctk.CTkScrollbar(list_frame, command=self.pending_list.yview)
        scrollbar.pack(side="right", fill="y")
        self.pending_list.config(yscrollcommand=scrollbar.set)
        
        detail_frame = ctk.CTkFrame(pending_tab)
        detail_frame.pack(fill="x", padx=10, pady=10)
        
        self.detail = ctk.CTkTextbox(detail_frame, height=100, width=600, state="disabled", font=("Arial", 12))
        self.detail.pack()
        
        action_frame = ctk.CTkFrame(pending_tab)
        action_frame.pack(pady=10)
        
        ctk.CTkLabel(action_frame, text="Assign Role:", font=("Arial", 12)).pack(side="left", padx=5)
        self.role = tk.StringVar(value="staff")
        ctk.CTkComboBox(action_frame, variable=self.role, values=["staff", "supervisor", "admin"], 
                    width=150).pack(side="left", padx=5)
        ctk.CTkButton(action_frame, text="✓ Approve", command=self.approve, corner_radius=6).pack(side="left", padx=5)
        ctk.CTkButton(action_frame, text="✗ Reject", command=self.reject, corner_radius=6).pack(side="left", padx=5)
        
        # Tab 2: All Users
        users_tab = notebook.add("Staff & Supervisors")
        
        ctk.CTkLabel(users_tab, text="Staff & Supervisor Management", font=("Arial", 14, "bold")).pack(pady=10)
        
        tree_frame = ctk.CTkFrame(users_tab)
        tree_frame.pack(fill="both", expand=True, padx=10)
        
        self.tree = ttk.Treeview(tree_frame, columns=("ID", "Name", "Email", "User", "Role", "Status"), 
                                show="headings", height=12)
        self.tree.heading("ID", text="ID")
        self.tree.heading("Name", text="Full Name")
        self.tree.heading("Email", text="Email")
        self.tree.heading("User", text="Username")
        self.tree.heading("Role", text="Role")
        self.tree.heading("Status", text="Status")
        
        self.tree.column("ID", width=50)
        self.tree.column("Name", width=150)
        self.tree.column("Email", width=180)
        self.tree.column("User", width=120)
        self.tree.column("Role", width=100)
        self.tree.column("Status", width=100)
        
        self.tree.pack(side="left", fill="both", expand=True)
        
        tree_scroll = ctk.CTkScrollbar(tree_frame, command=self.tree.yview)
        tree_scroll.pack(side="right", fill="y")
        self.tree.config(yscrollcommand=tree_scroll.set)
        
        user_btn_frame = ctk.CTkFrame(users_tab)
        user_btn_frame.pack(pady=10)
        ctk.CTkButton(user_btn_frame, text="🗑 Delete Selected User", command=self.delete_user, corner_radius=6).pack(side="left", padx=5)
        ctk.CTkButton(user_btn_frame, text="🔄 Refresh", command=self.refresh, corner_radius=6).pack(side="left", padx=5)
        
        # Tab 3: Customers
        customers_tab = notebook.add("Customers")
        
        ctk.CTkLabel(customers_tab, text="Customer Management", font=("Arial", 14, "bold")).pack(pady=10)
        
        cust_tree_frame = ctk.CTkFrame(customers_tab)
        cust_tree_frame.pack(fill="both", expand=True, padx=10)
        
        self.cust_tree = ttk.Treeview(cust_tree_frame, columns=("ID", "Name", "Email", "Username", "Created"), 
                                show="headings", height=12)
        self.cust_tree.heading("ID", text="ID")
        self.cust_tree.heading("Name", text="Full Name")
        self.cust_tree.heading("Email", text="Email")
        self.cust_tree.heading("Username", text="Username")
        self.cust_tree.heading("Created", text="Registration Date")
        
        self.cust_tree.column("ID", width=50)
        self.cust_tree.column("Name", width=180)
        self.cust_tree.column("Email", width=200)
        self.cust_tree.column("Username", width=150)
        self.cust_tree.column("Created", width=150)
        
        self.cust_tree.pack(side="left", fill="both", expand=True)
        
        cust_scroll = ctk.CTkScrollbar(cust_tree_frame, command=self.cust_tree.yview)
        cust_scroll.pack(side="right", fill="y")
        self.cust_tree.config(yscrollcommand=cust_scroll.set)
        
        cust_btn_frame = ctk.CTkFrame(customers_tab)
        cust_btn_frame.pack(pady=10)
        ctk.CTkButton(cust_btn_frame, text="🗑 Delete Selected Customer", command=self.delete_customer, corner_radius=6).pack(side="left", padx=5)
        ctk.CTkButton(cust_btn_frame, text="🔄 Refresh", command=self.refresh, corner_radius=6).pack(side="left", padx=5)

    def refresh(self):
        # Refresh pending list
        self.pending_list.delete(0, tk.END)
        for r in self.app.db.list_pending():
            self.pending_list.insert(tk.END, f"{r[0]} | {r[3]} | {r[1]} ({r[4]})")
        
        # Refresh staff/supervisor users tree
        for i in self.tree.get_children():
            self.tree.delete(i)
        for r in self.app.db.list_all():
            self.tree.insert("", tk.END, values=(r[0], r[1], r[2], r[3], r[4], r[6]))
        
        # Refresh customers tree
        for i in self.cust_tree.get_children():
            self.cust_tree.delete(i)
        for r in self.app.db.list_customers():
            self.cust_tree.insert("", tk.END, values=r)

    def sel(self, e):
        if not self.pending_list.curselection():
            return
        s = self.pending_list.get(self.pending_list.curselection()[0])
        self.uid = int(s.split("|")[0].strip())
        u = self.app.db.get_by_id(self.uid)
        txt = (f"ID: {u[0]}\nName: {u[1]}\nEmail: {u[2]}\nUsername: {u[3]}\n"
               f"Requested Role: {u[7]}\nStatus: {u[8]}")
        self.detail.configure(state="normal")
        self.detail.delete("1.0", tk.END)
        self.detail.insert("end", txt)
        self.detail.configure(state="disabled")

    def approve(self):
        if not self.uid:
            messagebox.showerror("Error", "Please select a user from the pending list")
            return
        self.app.db.update_role(self.uid, self.role.get())
        messagebox.showinfo("Success", "User approved and activated!")
        self.uid = None
        self.refresh()

    def reject(self):
        if not self.uid:
            messagebox.showerror("Error", "Please select a user from the pending list")
            return
        self.app.db.reject_user(self.uid)
        messagebox.showinfo("Success", "User request rejected.")
        self.uid = None
        self.refresh()

    def delete_user(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showerror("Error", "Please select a user to delete")
            return
        
        item = self.tree.item(selected[0])
        user_id = item['values'][0]
        username = item['values'][3]
        
        # Prevent deleting admin
        if username == "admin":
            messagebox.showerror("Error", "Cannot delete the default admin account")
            return
        
        # Prevent self-deletion
        if user_id == self.app.current_user["id"]:
            messagebox.showerror("Error", "You cannot delete your own account")
            return
        
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete user '{username}'?\n\nThis action cannot be undone."):
            self.app.db.delete_user(user_id)
            messagebox.showinfo("Success", "User deleted successfully")
            self.refresh()
    
    def delete_customer(self):
        selected = self.cust_tree.selection()
        if not selected:
            messagebox.showerror("Error", "Please select a customer to delete")
            return
        
        item = self.cust_tree.item(selected[0])
        user_id = item['values'][0]
        username = item['values'][3]
        
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete customer '{username}'?\n\nThis action cannot be undone."):
            self.app.db.delete_user(user_id)
            messagebox.showinfo("Success", "Customer deleted successfully")
            self.refresh()

# ---------- Staff Dashboard ----------
class StaffDashboard(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        
        # Header
        header = ctk.CTkFrame(self)
        header.pack(fill="x", padx=10, pady=10)
        
        self.welcome = ctk.CTkLabel(header, text="", font=("Arial", 24, "bold"))
        self.welcome.pack(side="left")
        
        btn_frame = ctk.CTkFrame(header)
        btn_frame.pack(side="right")
        ctk.CTkButton(btn_frame, text="Change Password", command=lambda: app.show("ChangePassword"), corner_radius=6).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="Logout", command=self.app.logout, corner_radius=6).pack(side="left", padx=2)
        
        # Notebook
        notebook = ctk.CTkTabview(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Tab 1: My Account
        account_tab = notebook.add("My Account")
        
        # User Info
        info_frame = ctk.CTkFrame(account_tab)
        info_frame.pack(fill="x", padx=10, pady=10)
        
        self.info = ctk.CTkLabel(info_frame, text="", justify="left", font=("Arial", 14))
        self.info.pack()
        
        # Tasks
        task_frame = ctk.CTkFrame(account_tab)
        task_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.taskbox = tk.Listbox(task_frame, height=8, font=("Arial", 12))
        self.taskbox.pack(fill="both", expand=True)
        
        # Actions
        action_frame = ctk.CTkFrame(account_tab)
        action_frame.pack(pady=10)
        ctk.CTkButton(action_frame, text="Request Role Change", command=self.request_role_change, corner_radius=6).pack()
        
        # Tab 2: Customer Management
        customer_tab = notebook.add("Customer Management")
        
        ctk.CTkLabel(customer_tab, text="Customer Management", font=("Arial", 14, "bold")).pack(pady=10)
        
        ctk.CTkButton(customer_tab, text="➕ Register New Customer", 
                  command=lambda: app.show("RegisterCustomer"), corner_radius=6).pack(pady=5)
        
        # Customer list
        cust_frame = ctk.CTkFrame(customer_tab)
        cust_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.cust_tree = ttk.Treeview(cust_frame, columns=("ID", "Name", "Email", "Username", "Created"), 
                                     show="headings", height=12)
        self.cust_tree.heading("ID", text="ID")
        self.cust_tree.heading("Name", text="Full Name")
        self.cust_tree.heading("Email", text="Email")
        self.cust_tree.heading("Username", text="Username")
        self.cust_tree.heading("Created", text="Registration Date")
        
        self.cust_tree.column("ID", width=50)
        self.cust_tree.column("Name", width=150)
        self.cust_tree.column("Email", width=180)
        self.cust_tree.column("Username", width=120)
        self.cust_tree.column("Created", width=150)
        
        self.cust_tree.pack(side="left", fill="both", expand=True)
        
        cust_scroll = ctk.CTkScrollbar(cust_frame, command=self.cust_tree.yview)
        cust_scroll.pack(side="right", fill="y")
        self.cust_tree.config(yscrollcommand=cust_scroll.set)
        
        ctk.CTkButton(customer_tab, text="🔄 Refresh", command=self.refresh, corner_radius=6).pack(pady=5)

    def refresh(self):
        u = self.app.current_user
        self.welcome.configure(text=f"Welcome, {u['full_name']}")
        self.info.configure(text=f"Username: {u['username']}\n"
                              f"Email: {u['email']}\n"
                              f"Role: {u['role'].title()}\n"
                              f"Status: {u['status'].title()}")
        
        # Sample tasks
        self.taskbox.delete(0, tk.END)
        tasks = [
            "✓ Complete onboarding checklist",
            "• Review company policies",
            "• Submit weekly report",
            "• Attend team meeting on Friday",
            "• Update project documentation"
        ]
        for task in tasks:
            self.taskbox.insert(tk.END, task)
        
        # Refresh customer list
        for i in self.cust_tree.get_children():
            self.cust_tree.delete(i)
        for r in self.app.db.list_customers():
            self.cust_tree.insert("", tk.END, values=r)

    def request_role_change(self):
        messagebox.showinfo("Request Sent", 
                          "Your role change request has been noted.\n"
                          "Please contact your administrator for approval.")

# ---------- Customer Dashboard ----------
class CustomerDashboard(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.selected_category = tk.StringVar(value="All")
        
        # Header
        header = ctk.CTkFrame(self)
        header.pack(fill="x", padx=10, pady=10)
        
        self.welcome = ctk.CTkLabel(header, text="", font=("Arial", 24, "bold"))
        self.welcome.pack(side="left")
        
        btn_frame = ctk.CTkFrame(header)
        btn_frame.pack(side="right")
        ctk.CTkButton(btn_frame, text="Change Password", command=lambda: app.show("ChangePassword"), corner_radius=6).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="Logout", command=self.app.logout, corner_radius=6).pack(side="left", padx=2)
        
        # Notebook
        notebook = ctk.CTkTabview(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Tab 1: Browse Products
        browse_tab = notebook.add("Browse Products")
        
        # Filter frame
        filter_frame = ctk.CTkFrame(browse_tab)
        filter_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(filter_frame, text="Category:", font=("Arial", 13)).pack(side="left", padx=5)
        self.category_combo = ctk.CTkComboBox(filter_frame, variable=self.selected_category, 
                                          width=200)
        self.category_combo.pack(side="left", padx=5)
        self.category_combo.bind("<<ComboboxSelected>>", lambda e: self.filter_products())
        
        ctk.CTkButton(filter_frame, text="🔄 Refresh", command=self.refresh, corner_radius=6).pack(side="left", padx=5)
        
        # Products frame
        prod_frame = ctk.CTkFrame(browse_tab)
        prod_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Products treeview
        tree_frame = ctk.CTkFrame(prod_frame)
        tree_frame.pack(fill="both", expand=True)
        
        self.prod_tree = ttk.Treeview(tree_frame, columns=("ID", "Name", "Description", "Price", "Stock", "Category"), 
                                     show="headings", height=10)
        self.prod_tree.heading("ID", text="ID")
        self.prod_tree.heading("Name", text="Product Name")
        self.prod_tree.heading("Description", text="Description")
        self.prod_tree.heading("Price", text="Price")
        self.prod_tree.heading("Stock", text="Stock")
        self.prod_tree.heading("Category", text="Category")
        
        self.prod_tree.column("ID", width=40)
        self.prod_tree.column("Name", width=150)
        self.prod_tree.column("Description", width=250)
        self.prod_tree.column("Price", width=80)
        self.prod_tree.column("Stock", width=60)
        self.prod_tree.column("Category", width=100)
        
        self.prod_tree.pack(side="left", fill="both", expand=True)
        
        prod_scroll = ctk.CTkScrollbar(tree_frame, command=self.prod_tree.yview)
        prod_scroll.pack(side="right", fill="y")
        self.prod_tree.config(yscrollcommand=prod_scroll.set)
        
        # Add to cart section
        cart_action_frame = ctk.CTkFrame(prod_frame)
        cart_action_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(cart_action_frame, text="Quantity:", font=("Arial", 12)).pack(side="left", padx=5)
        self.quantity = tk.StringVar(value="1")
        qty_values = [str(i) for i in range(1, 100)]
        ctk.CTkComboBox(cart_action_frame, values=qty_values, variable=self.quantity, width=100).pack(side="left", padx=5)
        ctk.CTkButton(cart_action_frame, text="🛒 Add to Cart", command=self.add_to_cart, corner_radius=6).pack(side="left", padx=5)
        
        # Tab 2: My Cart
        cart_tab = notebook.add("My Cart")
        
        ctk.CTkLabel(cart_tab, text="Shopping Cart", font=("Arial", 14, "bold")).pack(pady=10)
        
        # Cart treeview
        cart_frame = ctk.CTkFrame(cart_tab)
        cart_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.cart_tree = ttk.Treeview(cart_frame, columns=("ID", "Product", "Price", "Qty", "Total"), 
                                     show="headings", height=10)
        self.cart_tree.heading("ID", text="Cart ID")
        self.cart_tree.heading("Product", text="Product Name")
        self.cart_tree.heading("Price", text="Unit Price")
        self.cart_tree.heading("Qty", text="Quantity")
        self.cart_tree.heading("Total", text="Total")
        
        self.cart_tree.column("ID", width=70)
        self.cart_tree.column("Product", width=250)
        self.cart_tree.column("Price", width=100)
        self.cart_tree.column("Qty", width=80)
        self.cart_tree.column("Total", width=100)
        
        self.cart_tree.pack(side="left", fill="both", expand=True)
        
        cart_scroll = ctk.CTkScrollbar(cart_frame, command=self.cart_tree.yview)
        cart_scroll.pack(side="right", fill="y")
        self.cart_tree.config(yscrollcommand=cart_scroll.set)
        
        # Cart total
        self.cart_total_label = ctk.CTkLabel(cart_tab, text="Cart Total: $0.00", font=("Arial", 16, "bold"))
        self.cart_total_label.pack(pady=10)
        
        # Cart actions
        cart_btn_frame = ctk.CTkFrame(cart_tab)
        cart_btn_frame.pack(pady=10)
        ctk.CTkButton(cart_btn_frame, text="🗑 Remove Selected", command=self.remove_from_cart, corner_radius=6).pack(side="left", padx=5)
        ctk.CTkButton(cart_btn_frame, text="🧹 Clear Cart", command=self.clear_cart, corner_radius=6).pack(side="left", padx=5)
        ctk.CTkButton(cart_btn_frame, text="💳 Checkout (Coming Soon)", corner_radius=6).pack(side="left", padx=5)

    def refresh(self):
        u = self.app.current_user
        self.welcome.configure(text=f"Welcome, {u['full_name']}")
        
        # Load categories
        categories = ["All"] + self.app.db.get_categories()
        self.category_combo.configure(values=categories)
        
        # Load products
        self.filter_products()
        
        # Load cart
        self.load_cart()

    def filter_products(self):
        for i in self.prod_tree.get_children():
            self.prod_tree.delete(i)
        
        category = self.selected_category.get()
        if category == "All":
            products = self.app.db.get_all_products()
        else:
            products = self.app.db.get_products_by_category(category)
        
        for p in products:
            self.prod_tree.insert("", tk.END, values=(p[0], p[1], p[2], f"${p[3]:.2f}", p[4], p[5]))

    def add_to_cart(self):
        selected = self.prod_tree.selection()
        if not selected:
            messagebox.showerror("Error", "Please select a product")
            return
        
        item = self.prod_tree.item(selected[0])
        product_id = item['values'][0]
        stock = item['values'][4]
        
        try:
            qty = int(self.quantity.get())
            if qty < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid quantity")
            return
        
        if qty > stock:
            messagebox.showerror("Error", f"Only {stock} items available in stock")
            return
        
        self.app.db.add_to_cart(self.app.current_user["id"], product_id, qty)
        messagebox.showinfo("Success", f"Added {qty} item(s) to cart!")
        self.load_cart()

    def load_cart(self):
        for i in self.cart_tree.get_children():
            self.cart_tree.delete(i)
        
        cart_items = self.app.db.get_cart(self.app.current_user["id"])
        total = 0
        
        for item in cart_items:
            self.cart_tree.insert("", tk.END, values=(item[0], item[1], f"${item[2]:.2f}", item[3], f"${item[4]:.2f}"))
            total += item[4]
        
        self.cart_total_label.configure(text=f"Cart Total: ${total:.2f}")

    def remove_from_cart(self):
        selected = self.cart_tree.selection()
        if not selected:
            messagebox.showerror("Error", "Please select an item to remove")
            return
        
        item = self.cart_tree.item(selected[0])
        cart_id = item['values'][0]
        
        self.app.db.remove_from_cart(cart_id)
        messagebox.showinfo("Success", "Item removed from cart")
        self.load_cart()

    def clear_cart(self):
        if not self.cart_tree.get_children():
            messagebox.showinfo("Info", "Cart is already empty")
            return
        
        if messagebox.askyesno("Confirm", "Are you sure you want to clear your entire cart?"):
            self.app.db.clear_cart(self.app.current_user["id"])
            messagebox.showinfo("Success", "Cart cleared")
            self.load_cart()

# ---------- Run ----------
if __name__ == "__main__":
    db = DB()
    app = App(db)
    app.mainloop()
