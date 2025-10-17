import sqlite3
import os
import re
import base64
import uuid
from flask import Flask, jsonify, request, g, redirect, url_for, send_from_directory, abort
# 导入 CORS 和 cross_origin
from flask_cors import CORS, cross_origin 
from werkzeug.utils import secure_filename

# --- 全局配置 ---
app = Flask(__name__)
app.config['DATABASE'] = 'appstore.db'

# 启用 CORS，允许所有域名的前端访问 API 接口
CORS(app) 

# --- 图片存储配置 ---
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(APP_ROOT, 'logos')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- 数据库连接管理 (省略，保持不变) ---

def get_db_connection():
    """建立数据库连接，并在 g 对象上缓存"""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(app.config['DATABASE'])
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    """请求结束后关闭数据库连接"""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    """初始化数据库表结构"""
    with app.app_context():
        db = get_db_connection()
        db.executescript('''
            CREATE TABLE IF NOT EXISTS software (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                version TEXT NOT NULL,
                install_type TEXT NOT NULL,
                description TEXT,
                download_url TEXT NOT NULL,
                logo_url TEXT,
                silent_args TEXT
            );
        ''')
        # 检查是否需要插入初始数据
        if db.execute('SELECT COUNT(*) FROM software').fetchone()[0] == 0:
            initial_data = [
                ('VS Code', '1.83.0', 'silent', '轻量级但功能强大的源代码编辑器。', 'http://localhost:5000/download/vscode.exe', 'http://localhost:5000/logos/vscode.png', '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART'),
                ('7-Zip', '23.01', 'silent', '一款高压缩比的开源文件压缩与解压缩软件。', 'http://localhost:5000/download/7zip.exe', 'http://localhost:5000/logos/7zip.png', '/S'),
                ('Chrome', '118.0', 'manual', '由Google开发的网页浏览器，速度快，安全。', 'http://localhost:5000/download/chrome_installer.exe', 'http://localhost:5000/logos/chrome.png', ''),
                ('Node.js', '18.18.2', 'silent', '基于Chrome V8引擎的JavaScript运行环境。', 'http://localhost:5000/download/nodejs.msi', 'http://localhost:5000/logos/nodejs.png', '/qn /norestart'),
                ('Zoom Client', '5.16.2', 'manual', '领先的视频会议软件，用于远程协作。', 'http://localhost:5000/download/zoom_installer.exe', 'http://localhost:5000/logos/zoom.png', '')
            ]
            db.executemany("""
                INSERT INTO software (name, version, install_type, description, download_url, logo_url, silent_args) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, initial_data)
        db.commit()

# 在应用启动时初始化数据库
init_db()

# --- 辅助函数：Logo/Download URL 处理 ---

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    """虚拟下载路由，返回一个占位符文件"""
    return send_from_directory(APP_ROOT, 'placeholder.txt', as_attachment=True, download_name=filename)


@app.route('/logos/<filename>', methods=['GET'])
@cross_origin() # <--- 关键修复: 显式启用 Logo 路由的 CORS
def serve_logo(filename):
    """提供存储在 'logos' 文件夹中的 Logo 文件"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

def get_base_url():
    """获取应用的根 URL (用于构建绝对链接)"""
    return "http://localhost:5000"


# --- 新增 Logo 上传 API ---

@app.route('/api/upload_logo', methods=['POST'])
def upload_logo():
    """处理 Logo 文件上传和 Base64 截图粘贴上传。"""
    if 'file' in request.files and request.files['file'].filename:
        # 1. 处理文件上传 (来自 <input type="file">)
        file = request.files['file']
        filename = secure_filename(file.filename)
        unique_filename = str(uuid.uuid4()) + os.path.splitext(filename)[1]
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        try:
            file.save(filepath)
            logo_url = f"/logos/{unique_filename}"
            return jsonify({'logo_url': logo_url, 'message': '文件上传成功'})
        except Exception as e:
            print(f"File save error: {e}")
            return jsonify({'error': f'文件保存失败: {str(e)}'}), 500

    elif 'base64_image' in request.form:
        # 2. 处理 Base64 数据上传 (来自剪贴板粘贴)
        base64_data = request.form['base64_image']
        
        if ',' in base64_data:
            base64_data = base64_data.split(',', 1)[1]
        
        try:
            image_data = base64.b64decode(base64_data)
            unique_filename = str(uuid.uuid4()) + '.png'
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            
            with open(filepath, 'wb') as f:
                f.write(image_data)

            logo_url = f"/logos/{unique_filename}"
            return jsonify({'logo_url': logo_url, 'message': '截图粘贴成功'})
            
        except Exception as e:
            print(f"Base64 decode or file write error: {e}")
            return jsonify({'error': '无效的 Base64 图像数据或写入失败'}), 400
            
    return jsonify({'error': '没有找到文件或 Base64 数据'}), 400


# --- API 路由 ---

@app.route('/api/software', methods=['GET'])
def get_software_list():
    """API：获取所有软件列表"""
    conn = get_db_connection()
    software_list = conn.execute('SELECT * FROM software ORDER BY id DESC').fetchall()
    
    result = []
    base_url = get_base_url()
    
    for row in software_list:
        soft = dict(row)
        # 确保 logo 和下载链接是绝对路径，方便前端 PWA 使用
        if soft.get('logo_url'):
            # 无论存储的是否是 http 链接，我们都使用 base_url 重新构建绝对路径，
            # 以应对前端 PWA 跨域访问需求。
            # 注意：这里我们提取了 Logo URL 的文件名部分
            logo_filename = os.path.basename(soft['logo_url'])
            soft['logo_url'] = f"{base_url}/logos/{logo_filename}"
            
        if soft.get('download_url') and not soft['download_url'].startswith('http'):
            soft['download_url'] = f"{base_url}/download/{os.path.basename(soft['download_url'])}"
            
        result.append(soft)
        
    return jsonify(result)

@app.route('/api/software', methods=['POST'])
def add_software():
    """API：添加新软件"""
    data = request.json
    required_fields = ['name', 'version', 'install_type', 'description', 'download_url', 'logo_url', 'silent_args']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing fields'}), 400

    conn = get_db_connection()
    conn.execute("""
        INSERT INTO software (name, version, install_type, description, download_url, logo_url, silent_args) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (data['name'], data['version'], data['install_type'], data['description'], data['download_url'], data['logo_url'], data['silent_args']))
    conn.commit()
    return jsonify({'message': 'Software added successfully'}), 201

@app.route('/api/software/<int:software_id>', methods=['PUT'])
def update_software(software_id):
    """API：通过 ID 更新软件记录"""
    data = request.json
    
    conn = get_db_connection()
    cursor = conn.execute("""
        UPDATE software SET name=?, version=?, install_type=?, description=?, download_url=?, logo_url=?, silent_args=? 
        WHERE id = ?
    """, (data.get('name'), data.get('version'), data.get('install_type'), data.get('description'), 
          data.get('download_url'), data.get('logo_url'), data.get('silent_args'), software_id))
    conn.commit()
    
    if cursor.rowcount == 0:
        return jsonify({'error': 'Software not found'}), 404
        
    return jsonify({'message': 'Software updated successfully'}), 200

@app.route('/api/software/<int:software_id>', methods=['DELETE'])
def delete_software(software_id):
    """API：通过 ID 删除软件记录"""
    conn = get_db_connection()
    cursor = conn.execute("DELETE FROM software WHERE id = ?", (software_id,))
    conn.commit()
    
    if cursor.rowcount == 0:
        return jsonify({'error': 'Software not found'}), 404
        
    return jsonify({'message': 'Software deleted successfully'}), 200

# --- 网页后台路由 (HTML 模板不变，保持原有风格) ---

def get_software_list_html(software_list, search_query=''):
    """生成软件列表页面 HTML (新增搜索功能)"""
    rows = ""
    for soft in software_list:
        logo_url = soft['logo_url']
        if logo_url and not logo_url.startswith('http'):
            logo_url = f"/logos/{os.path.basename(logo_url)}"
        
        rows += f"""
        <tr class="align-middle">
            <td class="text-center"><img src="{logo_url}" alt="{soft['name']} Logo" style="width: 40px; height: 40px; border-radius: 8px;"></td>
            <td>{soft['name']}</td>
            <td>{soft['version']}</td>
            <td><span class="badge bg-{'success' if soft['install_type'] == 'silent' else 'info'}">{soft['install_type'].capitalize()}</span></td>
            <td>{soft['description']}</td>
            <td>
                <a href="/edit/{soft['id']}" class="btn btn-sm btn-outline-primary me-2">编辑</a>
                <button class="btn btn-sm btn-outline-danger" onclick="showDeleteModal({soft['id']})">删除</button>
            </td>
        </tr>
        """

    return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>企业软件部署后台管理</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <div class="container mt-5">
        <h1 class="mb-4">软件部署列表</h1>
        <div class="d-flex justify-content-between align-items-center mb-3">
             <a href="/add" class="btn btn-success">添加新软件</a>
        </div>
        
        <!-- 搜索表单 -->
        <form class="d-flex mb-4" method="GET" action="/">
            <input class="form-control me-2" type="search" name="search" placeholder="输入软件名称或描述搜索..." aria-label="Search" value="{search_query}">
            <button class="btn btn-primary" type="submit">搜索</button>
            <a href="/" class="btn btn-outline-secondary ms-2">重置</a>
        </form>
        
        <div class="table-responsive bg-white rounded shadow-sm">
            <table class="table table-hover table-striped">
                <thead class="table-primary">
                    <tr>
                        <th class="text-center">Logo</th>
                        <th>名称</th>
                        <th>版本</th>
                        <th>安装类型</th>
                        <th>描述</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody>
                    {rows if rows else '<tr><td colspan="6" class="text-center py-4 text-muted">未找到匹配的软件记录。</td></tr>'}
                </tbody>
            </table>
        </div>
    </div>
    
    <!-- Confirmation Modal (用于删除确认) -->
    <div class="modal fade" id="deleteConfirmModal" tabindex="-1" aria-labelledby="deleteConfirmModalLabel" aria-hidden="true">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="deleteConfirmModalLabel">确认删除</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body text-center">
            <p><strong>您确定要删除此软件记录吗？此操作不可撤销。</strong></p>
            <p class="text-muted small">软件ID: <span id="softwareIdPlaceholder"></span></p>
          </div>
          <div class="modal-footer d-flex justify-content-center">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
            <button type="button" class="btn btn-danger" id="confirmDeleteBtn">确认删除</button>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Status Modal (用于显示操作结果) -->
    <div class="modal fade" id="statusModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="statusModalTitle"></h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <p id="statusModalMessage"></p>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // 初始化模态框对象
        let softwareToDeleteId = null;
        const deleteModal = new bootstrap.Modal(document.getElementById('deleteConfirmModal'));
        const statusModal = new bootstrap.Modal(document.getElementById('statusModal'));
        const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');

        // 通用状态显示函数
        function showStatus(title, message, isSuccess = true) {{
            document.getElementById('statusModalTitle').textContent = title;
            document.getElementById('statusModalMessage').textContent = message;
            
            const modalTitle = document.getElementById('statusModalTitle');
            modalTitle.className = 'modal-title ' + (isSuccess ? 'text-success' : 'text-danger');
            
            statusModal.show();
        }}

        // 显示删除确认模态框
        function showDeleteModal(id) {{
            softwareToDeleteId = id;
            document.getElementById('softwareIdPlaceholder').textContent = id;
            deleteModal.show();
        }}

        // 绑定删除按钮的点击事件
        confirmDeleteBtn.addEventListener('click', function() {{
            if (softwareToDeleteId !== null) {{
                deleteModal.hide();
                
                fetch(`/api/software/${{softwareToDeleteId}}`, {{
                    method: 'DELETE',
                    headers: {{
                        'Content-Type': 'application/json'
                    }}
                }})
                .then(response => {{
                    if (response.ok) {{
                        showStatus('删除成功', '软件记录已成功删除。', true);
                        setTimeout(() => window.location.reload(), 1500);
                    }} else {{
                        response.json().then(errorData => showStatus('删除失败', '删除操作未能完成：' + (errorData.error || '未知错误'), false));
                    }}
                }})
                .catch(error => {{
                    console.error('Error:', error);
                    showStatus('网络错误', '无法连接到服务器，请检查后端运行状态。', false);
                }});
            }}
        }});
    </script>
</body>
</html>
"""

def get_software_form_html(software=None):
    """生成添加/编辑软件的表单 HTML (新增 Logo 上传/粘贴功能)"""
    is_edit = software is not None
    action_url = f"/api/software/{software['id']}" if is_edit else "/api/software"
    method = 'PUT' if is_edit else 'POST'
    title = '编辑软件信息' if is_edit else '添加新软件'
    
    # 默认值
    name = software['name'] if is_edit else ''
    version = software['version'] if is_edit else ''
    install_type = software['install_type'] if is_edit else 'silent'
    description = software['description'] if is_edit else ''
    download_url = software['download_url'] if is_edit else 'http://localhost:5000/download/installer.exe'
    logo_url = software['logo_url'] if is_edit else '/logos/default.png'
    silent_args = software['silent_args'] if is_edit else '/S'
    
    # 确保 Logo URL 是相对路径，以便预览正确显示
    if logo_url and logo_url.startswith(('http', get_base_url())):
        logo_url = "/" + logo_url.split("/logos/")[-1]
    
    # 安装类型选项
    silent_checked = 'checked' if install_type == 'silent' else ''
    manual_checked = 'checked' if install_type == 'manual' else ''

    return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        #logoPreview {{
            border: 1px dashed #ccc;
            background-color: #f8f9fa;
        }}
    </style>
</head>
<body class="bg-light">
    <div class="container mt-5">
        <h1 class="mb-4">{title}</h1>
        <div class="card p-4 shadow-sm">
            <form id="softwareForm">
                <div class="mb-3">
                    <label for="name" class="form-label">软件名称</label>
                    <input type="text" class="form-control" id="name" value="{name}" required>
                </div>
                <div class="mb-3">
                    <label for="version" class="form-label">版本号</label>
                    <input type="text" class="form-control" id="version" value="{version}" required>
                </div>
                
                <div class="mb-3">
                    <label class="form-label d-block">安装类型</label>
                    <div class="form-check form-check-inline">
                        <input class="form-check-input" type="radio" name="install_type" id="silent" value="silent" {silent_checked} required>
                        <label class="form-check-label" for="silent">静默安装 (Silent)</label>
                    </div>
                    <div class="form-check form-check-inline">
                        <input class="form-check-input" type="radio" name="install_type" id="manual" value="manual" {manual_checked} required>
                        <label class="form-check-label" for="manual">手动安装 (Manual)</label>
                    </div>
                </div>
                
                <div class="mb-3">
                    <label for="silent_args" class="form-label">静默安装参数 (非静默安装可留空)</label>
                    <input type="text" class="form-control" id="silent_args" value="{silent_args}">
                </div>

                <div class="mb-3">
                    <label for="description" class="form-label">描述</label>
                    <textarea class="form-control" id="description" rows="3" required>{description}</textarea>
                </div>
                
                <div class="mb-3">
                    <label for="download_url" class="form-label">安装包下载 URL</label>
                    <input type="url" class="form-control" id="download_url" value="{download_url}" required>
                </div>
                
                <!-- Logo 上传/粘贴区域 -->
                <div class="mb-3 border p-3 rounded">
                    <label class="form-label">软件 Logo (上传或粘贴)</label>
                    <div class="d-flex align-items-center mb-3 p-2 border rounded">
                        <!-- Logo 预览使用相对路径，由 Flask 后端直接提供 -->
                        <img id="logoPreview" src="{logo_url}" alt="Logo 预览" class="me-3" style="width: 60px; height: 60px; object-fit: contain;">
                        <span>当前 Logo 预览</span>
                    </div>

                    <!-- 文件上传 -->
                    <input class="form-control mb-2" type="file" id="logoUpload" accept="image/*">
                    
                    <!-- 粘贴截图 -->
                    <div class="input-group">
                        <span class="input-group-text">粘贴 Logo</span>
                        <input type="text" class="form-control" id="pasteInput" placeholder="点击此处，然后 Ctrl+V 粘贴截图/图片">
                    </div>
                    <small class="form-text text-muted">提示：文件上传将覆盖当前 Logo，粘贴截图会自动上传。</small>
                    
                    <!-- 隐藏的字段，用于存储最终的 logo_url (必需，因为下载URL不再是实际输入) -->
                    <input type="hidden" id="logo_url" value="{logo_url}">
                </div>
                
                <a href="/" class="btn btn-secondary me-2">返回列表</a>
                <button type="submit" class="btn btn-primary">保存</button>
            </form>
        </div>
    </div>
    
    <!-- Status Modal (用于显示操作结果) -->
    <div class="modal fade" id="statusModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="statusModalTitle"></h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <p id="statusModalMessage"></p>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        const statusModal = new bootstrap.Modal(document.getElementById('statusModal'));
        const logoUploadInput = document.getElementById('logoUpload');
        const pasteInput = document.getElementById('pasteInput');
        const logoPreview = document.getElementById('logoPreview');
        const logoUrlHidden = document.getElementById('logo_url');

        // 通用状态显示函数
        function showStatus(title, message, isSuccess = true) {{
            document.getElementById('statusModalTitle').textContent = title;
            document.getElementById('statusModalMessage').textContent = message;
            
            const modalTitle = document.getElementById('statusModalTitle');
            modalTitle.className = 'modal-title ' + (isSuccess ? 'text-success' : 'text-danger');

            statusModal.show();
        }}
        
        // --- 上传处理函数 ---
        function handleUpload(data, isBase64 = false) {{
            const formData = new FormData();
            
            if (isBase64) {{
                formData.append('base64_image', data);
            }} else {{
                formData.append('file', data);
            }}

            // 临时设置预览，直到上传完成
            logoUrlHidden.value = 'Uploading...'; 

            fetch('/api/upload_logo', {{
                method: 'POST',
                body: formData 
            }})
            .then(response => response.json())
            .then(data => {{
                if (data.logo_url) {{
                    // data.logo_url 是 /logos/uuid.png 这样的相对路径
                    logoUrlHidden.value = data.logo_url; 
                    // 确保预览图使用的是新的 URL
                    logoPreview.src = data.logo_url;
                    showStatus('上传成功', data.message, true);
                }} else {{
                    logoUrlHidden.value = '{logo_url}'; 
                    showStatus('上传失败', data.error || '上传失败', false);
                }}
            }})
            .catch(error => {{
                console.error('Upload Error:', error);
                logoUrlHidden.value = '{logo_url}';
                showStatus('网络错误', '无法连接到上传服务。', false);
            }});
        }}

        // 1. 文件上传监听
        logoUploadInput.addEventListener('change', function() {{
            if (this.files.length > 0) {{
                handleUpload(this.files[0], false);
            }}
        }});

        // 2. 剪贴板粘贴监听
        pasteInput.addEventListener('paste', function(e) {{
            e.preventDefault();
            const items = (e.clipboardData || e.originalEvent.clipboardData).items;
            let imageFound = false;

            for (let i = 0; i < items.length; i++) {{
                if (items[i].type.indexOf('image') !== -1) {{
                    imageFound = true;
                    const blob = items[i].getAsFile();
                    
                    // 立即在本地预览
                    const reader = new FileReader();
                    reader.onload = function(event) {{
                        logoPreview.src = event.target.result;
                    }};
                    reader.readAsDataURL(blob);

                    // 转换为 Base64 上传
                    const base64Reader = new FileReader();
                    base64Reader.onloadend = function() {{
                        const base64Data = base64Reader.result;
                        handleUpload(base64Data, true);
                    }};
                    base64Reader.readAsDataURL(blob);
                    
                    break;
                }}
            }}

            if (!imageFound) {{
                showStatus('粘贴失败', '剪贴板中没有图片数据。', false);
            }}
        }});

        // --- 表单提交处理 ---
        document.getElementById('softwareForm').addEventListener('submit', function(e) {{
            e.preventDefault();

            // 关键：从隐藏字段获取最终的 Logo URL (是相对路径 /logos/filename)
            const final_logo_url = document.getElementById('logo_url').value; 
            
            if (final_logo_url === 'Uploading...' || final_logo_url === 'Pasting...') {{
                showStatus('请等待', 'Logo 正在上传中，请稍候再提交。', false);
                return;
            }}

            const data = {{
                name: document.getElementById('name').value,
                version: document.getElementById('version').value,
                install_type: document.querySelector('input[name="install_type"]:checked').value,
                description: document.getElementById('description').value,
                download_url: document.getElementById('download_url').value,
                logo_url: final_logo_url, // 存储相对路径
                silent_args: document.getElementById('silent_args').value
            }};
            
            const action_url = '{action_url}';
            const method = '{method}';

            fetch(action_url, {{
                method: method,
                headers: {{
                    'Content-Type': 'application/json'
                }},
                body: JSON.stringify(data)
            }})
            .then(response => {{
                if (response.ok) {{
                    showStatus('保存成功', '软件信息已成功保存。', true);
                    setTimeout(() => window.location.href = '/', 1500);
                }} else {{
                    response.json().then(errorData => showStatus('保存失败', '保存操作未能完成：' + (errorData.error || '未知错误'), false));
                }}
            }})
            .catch(error => {{
                console.error('Error:', error);
                showStatus('网络错误', '无法连接到服务器，请检查后端运行状态。', false);
            }});
        }});
    </script>
</body>
</html>
"""

@app.route('/', methods=['GET'])
def list_software_page():
    """根路径：显示已有的软件列表 (支持搜索)"""
    search_query = request.args.get('search', '').strip()
    conn = get_db_connection()
    
    if search_query:
        # 模糊搜索软件名称和描述
        like_query = f"%{search_query}%"
        software_list = conn.execute(
            'SELECT * FROM software WHERE name LIKE ? OR description LIKE ? ORDER BY id DESC', 
            (like_query, like_query)
        ).fetchall()
    else:
        software_list = conn.execute('SELECT * FROM software ORDER BY id DESC').fetchall()
    
    result = [dict(row) for row in software_list]
    return get_software_list_html(result, search_query)

@app.route('/add', methods=['GET'])
def add_software_page():
    """/add 路径：显示添加新软件的表单"""
    return get_software_form_html()

@app.route('/edit/<int:software_id>', methods=['GET'])
def edit_software_page(software_id):
    """/edit/<id> 路径：显示修改软件的表单"""
    conn = get_db_connection()
    software = conn.execute('SELECT * FROM software WHERE id = ?', (software_id,)).fetchone()
    
    if software is None:
        return "Software not found", 404
        
    return get_software_form_html(dict(software))

if __name__ == '__main__':
    # 确保 placeholder.txt 存在，用于虚拟下载
    if not os.path.exists('placeholder.txt'):
        with open('placeholder.txt', 'w', encoding='utf-8') as f:
            f.write('This is a placeholder file for software download demonstration.')
            
    # 确保默认 logo 存在
    default_logo_path = os.path.join(UPLOAD_FOLDER, 'default.png')
    if not os.path.exists(default_logo_path):
        # 创建一个简单的占位符 PNG 文件 (1x1 透明像素)
        default_png_data = b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
        try:
            with open(default_logo_path, 'wb') as f:
                f.write(base64.b64decode(default_png_data))
        except Exception as e:
            print(f"Could not create default logo: {e}")
            
    app.run(debug=True)
