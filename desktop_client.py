import os
import sys
import subprocess
import requests
import tkinter as tk
import ttkbootstrap as tkb 
from tkinter import messagebox
from threading import Thread
import io 
from PIL import Image, ImageTk 

# --- 配置 ---
API_URL = 'http://localhost:5000/api/software' 
BASE_URL = 'http://localhost:5000' 

# 临时下载目录
TEMP_DIR = os.path.join(os.environ.get('TEMP', 'C:\\Temp'), 'AppStoreDownloads')
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

# --- 权限和系统操作 ---
def is_admin():
    """检查当前进程是否具有管理员权限 (仅适用于 Windows)"""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

def elevate_privileges():
    """以管理员身份重新启动程序"""
    if not is_admin():
        import ctypes
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, __file__, None, 1)
        sys.exit(0)
    return True

def download_file(url, local_path):
    """下载文件到本地路径"""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(local_path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        return True
    except requests.exceptions.RequestException as e:
        print(f"下载失败: {e}")
        return False

def execute_silent_install(installer_path, silent_args):
    """执行静默安装命令"""
    command = [installer_path] + silent_args.split()
    print(f"执行命令: {command}")
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, shell=True)
        return True, "安装成功"
    except subprocess.CalledProcessError as e:
        error_msg = f"安装失败 (返回码 {e.returncode}): {e.stderr}"
        print(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"执行安装时发生未知错误: {e}"
        print(error_msg)
        return False, error_msg

def open_download_folder(file_path):
    """打开文件所在的文件夹并高亮显示该文件 (仅适用于 Windows)"""
    try:
        # 使用 explorer /select 打开文件夹并高亮显示文件
        subprocess.run(f'explorer /select,"{file_path}"', shell=True)
        return True
    except Exception as e:
        # 备用方案：如果 /select 失败，尝试直接打开文件夹
        try:
            folder_path = os.path.dirname(file_path)
            os.startfile(folder_path)
            return True
        except Exception as e2:
            print(f"无法打开下载文件夹: {e2}")
            return False
            

# --- 应用程序类 ---

class AppStoreClient(tkb.Window):
    def __init__(self):
        super().__init__(themename="cosmo") 
        self.title("内部静默应用商店")
        self.geometry("1000x600") 
        self.resizable(True, True) 
        
        # --- 设置窗口图标 (必须是 ICO 格式) ---
        try:
            self.iconbitmap('icon.ico') 
        except tk.TclError:
            print("Warning: Failed to load icon.ico. Please ensure it is in the correct format and path.")
        # ------------------------------------
        
        if not elevate_privileges():
            self.destroy()
            return
            
        self.all_software_data = {} 
        self.install_buttons = {} 
        self.logo_cache = {} 
        
        # 定义固定宽度
        self.COL_LOGO_WIDTH_PX = 60      
        self.COL_NAME_WIDTH_PX = 150     
        self.COL_VERSION_WIDTH_PX = 80   
        self.COL_DESC_WIDTH_PX = 350     
        self.COL_BUTTON_WIDTH_PX = 80    
        self.MAX_DESC_CHARS = 80 
        
        self.create_widgets()
        self.center_window()
        
        Thread(target=self._initial_data_load).start()
    
    # --- 省略其他方法以保持简洁，但这些方法在实际文件中应全部保留 ---

    def _initial_data_load(self):
        self.after(0, lambda: self.status_bar.config(text="正在连接服务器并加载数据...", bootstyle="info"))
        try:
            response = requests.get(API_URL)
            response.raise_for_status()
            software_list = response.json()
            self.all_software_data = {soft['name']: soft for soft in software_list}
            self.after(0, lambda: self.search_var.set(""))
            self.after(0, self.load_software_list) 
        except requests.exceptions.RequestException as e:
            self.after(0, lambda: self.status_bar.config(
                text=f"连接API失败，请确认后端运行在 {API_URL}", 
                bootstyle="danger"
            ))
            print(f"API Connection Error: {e}")

    def center_window(self):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def create_widgets(self):
        header_frame = tkb.Frame(self, padding="15 10 15 10")
        header_frame.pack(fill='x')
        tkb.Label(header_frame, text="企业软件部署中心", font=('Segoe UI', 18, 'bold'), bootstyle="primary").pack(side='left')
        self.status_bar = tkb.Label(self, text="初始化中...", bootstyle="info", anchor='w')
        self.status_bar.pack(side='bottom', fill='x')

        main_content_frame = tkb.Frame(self, padding=15)
        main_content_frame.pack(fill='both', expand=True)
        
        search_frame = tkb.Frame(main_content_frame, padding=(0, 0, 0, 10))
        search_frame.pack(fill='x')
        
        self.search_var = tk.StringVar()
        self.search_entry = tkb.Entry(search_frame, textvariable=self.search_var, bootstyle="primary", width=50)
        self.search_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        self.search_entry.insert(0, "输入软件名称或描述进行搜索...")
        self.search_entry.bind("<FocusIn>", self._clear_placeholder)
        self.search_entry.bind("<FocusOut>", self._set_placeholder)
        self.search_entry.bind("<KeyRelease>", self._search_software)
        
        tkb.Button(search_frame, text="清空", command=lambda: self.search_var.set(""), bootstyle="secondary-outline").pack(side='left', padx=(0, 5))
        tkb.Button(search_frame, text="刷新", command=self._refresh_list, bootstyle="info-outline").pack(side='left')
        
        header = tkb.Frame(main_content_frame)
        header.pack(fill='x')
        
        header.grid_columnconfigure(0, minsize=self.COL_LOGO_WIDTH_PX, weight=0)         
        header.grid_columnconfigure(1, minsize=self.COL_NAME_WIDTH_PX + 10, weight=1)    
        header.grid_columnconfigure(2, minsize=self.COL_VERSION_WIDTH_PX + 10, weight=0) 
        header.grid_columnconfigure(3, minsize=self.COL_DESC_WIDTH_PX + 10, weight=3)    
        header.grid_columnconfigure(4, minsize=self.COL_BUTTON_WIDTH_PX + 10, weight=0)  

        column_titles = ["", "名称", "版本", "描述", "操作"]
        for i, title in enumerate(column_titles):
            anchor_val = 'center' if i == 0 or i == 2 else ('w' if i == 1 or i == 3 else 'e')
            lbl = tkb.Label(header, text=title, bootstyle="inverse-primary", anchor=anchor_val, padding=8)
            lbl.grid(row=0, column=i, sticky='nsew')
            
        list_container = tkb.Frame(main_content_frame)
        list_container.pack(fill='both', expand=True)

        scrollbar = tkb.Scrollbar(list_container, orient="vertical")
        scrollbar.pack(side='right', fill='y')
        
        list_canvas = tkb.Canvas(list_container, yscrollcommand=scrollbar.set, highlightthickness=0)
        list_canvas.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=list_canvas.yview)

        self.list_inner_frame = tkb.Frame(list_canvas, padding=(0, 0), bootstyle='light') 
        canvas_window = list_canvas.create_window((0, 0), window=self.list_inner_frame, anchor="nw")
        
        self.list_inner_frame.bind("<Configure>", 
            lambda e: list_canvas.configure(scrollregion=list_canvas.bbox("all"))
        )
        def on_canvas_configure(event):
            list_canvas.itemconfig(canvas_window, width=event.width)
        list_canvas.bind('<Configure>', on_canvas_configure)
        
        self.list_inner_frame.grid_columnconfigure(0, weight=1) 

    def _refresh_list(self):
        Thread(target=self._initial_data_load).start()
    
    def _clear_placeholder(self, event):
        if self.search_entry.get() == "输入软件名称或描述进行搜索...":
            self.search_entry.delete(0, 'end')
            self.search_entry.config(bootstyle="primary")

    def _set_placeholder(self, event):
        if not self.search_entry.get():
            self.search_entry.insert(0, "输入软件名称或描述进行搜索...")
            self.search_entry.config(bootstyle="primary")

    def _search_software(self, event=None):
        search_term = self.search_var.get().lower().strip()
        
        if search_term == "输入软件名称或描述进行搜索...".lower():
            search_term = ""
            
        filtered_software = {}
        if search_term:
            for name, soft in self.all_software_data.items():
                if (search_term in name.lower() or
                    search_term in soft['version'].lower() or
                    search_term in soft['description'].lower() or
                    search_term in soft['category'].lower()):
                    
                    filtered_software[name] = soft
        else:
            filtered_software = self.all_software_data

        self.load_software_list(filtered_software)
        
    def load_software_list(self, filtered_data=None):
        software_to_display = filtered_data if filtered_data is not None else self.all_software_data
        software_list = list(software_to_display.values())
        self._render_list_items(software_list)
        self.list_inner_frame.update_idletasks() 
        self.status_bar.config(text="软件列表加载成功。", bootstyle="success")

    def _get_logo_url(self, software):
        logo_url_path = software.get('logo_url')
        if logo_url_path and logo_url_path.startswith('/logos/'):
            return f"{BASE_URL}{logo_url_path}"
        if logo_url_path and logo_url_path.startswith('http'):
             return logo_url_path
        return None 

    def _load_logo_async(self, url, soft_name, label_widget):
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            
            image_data = io.BytesIO(response.content)
            pil_image = Image.open(image_data)
            
            if pil_image.mode != 'RGBA':
                pil_image = pil_image.convert("RGBA")

            size = (40, 40)
            pil_image = pil_image.resize(size, Image.Resampling.LANCZOS)
            
            photo_image = ImageTk.PhotoImage(pil_image)
            
            self.after(0, lambda: self._update_logo_label(soft_name, photo_image, label_widget))
            
        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch logo for {soft_name} from {url}: {e}")
            self.after(0, lambda: label_widget.config(text="失败")) 
        except Exception as e:
            print(f"Failed to process image for {soft_name}: {e}")
            self.after(0, lambda: label_widget.config(text="失败"))

    def _update_logo_label(self, soft_name, photo_image, label_widget):
        try:
            self.logo_cache[soft_name] = photo_image
            label_widget.config(image=photo_image, text="")
            label_widget.image = photo_image 
        except tk.TclError:
            pass 
        except Exception as e:
            print(f"Error updating logo label for {soft_name}: {e}")

    def _render_list_items(self, software_list):
        for widget in self.list_inner_frame.winfo_children():
            widget.destroy()
        
        if not software_list:
             msg = "未找到匹配的软件。" if self.search_var.get().strip() and self.search_var.get() != "输入软件名称或描述进行搜索..." else "当前没有软件，请在后台添加。"
             tkb.Label(self.list_inner_frame, text=msg, bootstyle="secondary").grid(row=0, column=0, pady=20)
             self.list_inner_frame.update_idletasks() 
             return

        for i, soft in enumerate(software_list):
            row_frame = tkb.Frame(self.list_inner_frame, padding=(10, 8), bootstyle="default") 
            row_frame.grid(row=i, column=0, sticky='ew', pady=(1, 0)) 
            
            row_frame.grid_columnconfigure(0, minsize=self.COL_LOGO_WIDTH_PX, weight=0) 
            row_frame.grid_columnconfigure(1, minsize=self.COL_NAME_WIDTH_PX, weight=1) 
            row_frame.grid_columnconfigure(2, minsize=self.COL_VERSION_WIDTH_PX, weight=0) 
            row_frame.grid_columnconfigure(3, minsize=self.COL_DESC_WIDTH_PX, weight=3) 
            row_frame.grid_columnconfigure(4, minsize=self.COL_BUTTON_WIDTH_PX, weight=0) 
            
            current_col = 0
            
            # === COLUMN 0: LOGO ===
            logo_label = tkb.Label(
                row_frame, 
                text="", 
                bootstyle="default", # 确保背景色是透明的（继承父 Frame）
                anchor='center', 
                width=int(self.COL_LOGO_WIDTH_PX / 10)
            )
            logo_label.grid(row=0, column=current_col, sticky='nsew', padx=(0, 5))
            current_col += 1
            
            logo_url = self._get_logo_url(soft)
            if logo_url:
                logo_label.config(text="加载中...")
                Thread(target=self._load_logo_async, args=(logo_url, soft['name'], logo_label)).start()
            else:
                logo_label.config(text="无图")

            # === COLUMN 1: 名称 ===
            tkb.Label(row_frame, 
                      text=soft['name'], 
                      font=('Segoe UI', 11, 'bold'), 
                      bootstyle="primary", 
                      anchor='w',
                      wraplength=self.COL_NAME_WIDTH_PX
            ).grid(row=0, column=current_col, sticky='nw', padx=(0, 5)) 
            current_col += 1
            
            # === COLUMN 2: 版本 ===
            tkb.Label(row_frame, 
                      text=soft['version'], 
                      bootstyle="secondary", 
                      anchor='center',
                      width=int(self.COL_VERSION_WIDTH_PX / 10)
            ).grid(row=0, column=current_col, sticky='n', padx=(5, 5)) 
            current_col += 1
            
            # === COLUMN 3: 描述 (截断控制) ===
            description = soft.get('description', '')
            if len(description) > self.MAX_DESC_CHARS:
                description = description[:self.MAX_DESC_CHARS-3].strip() + "..."
                
            desc_label = tkb.Label(row_frame, 
                                   text=description, 
                                   bootstyle="secondary", 
                                   anchor='w', 
                                   wraplength=self.COL_DESC_WIDTH_PX,
                                   justify='left' 
            )
            desc_label.grid(row=0, column=current_col, sticky='nw', padx=(5, 5)) 
            current_col += 1

            # === COLUMN 4: 操作 (按钮) ===
            install_btn = tkb.Button(row_frame, text="安装", bootstyle="success", 
                                     width=int(self.COL_BUTTON_WIDTH_PX / 10)) 
            install_btn.config(command=lambda s=soft, b=install_btn: self.start_install(s, b))
            install_btn.grid(row=0, column=current_col, sticky='ne', padx=(5, 0)) 
            
            self.install_buttons[soft['name']] = install_btn

    def start_install(self, soft, button_widget):
        install_type = soft.get('install_type', 'silent').lower()
        if install_type == 'manual':
             button_widget.config(state='disabled', text="下载中...")
        else:
             button_widget.config(state='disabled', text="安装中...")
             
        self.status_bar.config(text=f"开始处理 {soft['name']} ({install_type})...")
        Thread(target=self.install_software, args=(soft, button_widget)).start()

    def install_software(self, soft, button_widget):
        file_name = os.path.basename(soft['download_url'])
        local_installer_path = os.path.join(TEMP_DIR, file_name)
        install_type = soft.get('install_type', 'silent').lower()

        self.after(0, lambda: self.status_bar.config(text=f"下载 {soft['name']}..."))
        if not download_file(soft['download_url'], local_installer_path):
            self.after(0, lambda: self.installation_finished(soft, False, f"下载失败: {soft['download_url']}", button_widget))
            return
        
        if install_type == 'silent':
            self.after(0, lambda: self.status_bar.config(text=f"执行静默安装..."))
            success, message = execute_silent_install(local_installer_path, soft.get('silent_args', ''))
            
            if success and os.path.exists(local_installer_path):
                 try:
                     os.remove(local_installer_path)
                 except Exception as e:
                     print(f"无法删除安装包: {e}")
            
            self.after(0, lambda: self.installation_finished(soft, success, message, button_widget))

        elif install_type == 'manual':
            self.after(0, lambda: self.status_bar.config(text=f"下载完成，正在打开安装目录..."))
            
            if open_download_folder(local_installer_path):
                 message = f"'{soft['name']}' 下载完成。请在打开的文件夹中双击文件手动安装。"
                 self.after(0, lambda: self.installation_finished(soft, True, message, button_widget, is_manual=True))
            else:
                 message = f"下载完成，但无法打开安装目录：{TEMP_DIR}。请手动前往安装。"
                 self.after(0, lambda: self.installation_finished(soft, False, message, button_widget, is_manual=True))
                 
        else:
            self.after(0, lambda: self.installation_finished(soft, False, f"软件 '{soft['name']}' 的安装类型未知: {install_type}", button_widget))
            

    def installation_finished(self, soft, success, message, button_widget, is_manual=False):
        button_text = "安装" # 手动和静默安装失败/成功后都显示“安装”
        button_widget.config(state='enabled', text=button_text)
        
        if success:
            if is_manual:
                messagebox.showinfo("下载完成", message)
                self.status_bar.config(text=f"{soft['name']} 下载完成，等待手动安装。", bootstyle="success")
            else:
                messagebox.showinfo("安装成功", f"软件已静默安装完成。\n{message}")
                self.status_bar.config(text=f"{soft['name']} 安装成功。", bootstyle="success")
        else:
            messagebox.showerror("操作失败", message)
            self.status_bar.config(text=f"{soft['name']} 操作失败。", bootstyle="danger")


if __name__ == '__main__':
    try:
        from PIL import Image, ImageTk
    except ImportError:
        print("错误: 缺少 'Pillow' 库。")
        print("请在命令行运行 'pip install Pillow' 进行安装。")
        sys.exit(1)
        
    app_client = AppStoreClient()
    app_client.mainloop()