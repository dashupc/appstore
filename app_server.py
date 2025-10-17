import sqlite3
import os
import re
import base64
from flask import Flask, jsonify, request, g, redirect, url_for, send_from_directory, abort

# --- 全局配置 ---
app = Flask(__name__)
# 数据库配置
app.config['DATABASE'] = 'appstore.db'

# --- 图片存储配置 ---
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
# Logo 图片将保存在项目根目录下的 'logos' 文件夹中
UPLOAD_FOLDER = os.path.join(APP_ROOT, 'logos')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 确保 logo 文件夹存在
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- 数据库连接管理 ---

def get_db_connection():
    """建立数据库连接，并在 g 对象上缓存"""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(app.config['DATABASE'])
        # 设置行工厂，使查询结果可以像字典一样访问
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    """请求结束后关闭数据库连接"""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    """初始化数据库，创建 software 表（如果不存在）"""
    with app.app_context():
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS software (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                version TEXT NOT NULL,
                description TEXT,
                download_url TEXT NOT NULL,
                silent_args TEXT,
                category TEXT DEFAULT '未分类',
                logo_url TEXT,
                install_type TEXT DEFAULT 'silent'
            )
        ''')
        conn.commit()

# --- 辅助函数：处理 Base64 图片上传/粘贴逻辑 ---

def save_base64_image(base64_data, software_name):
    """将 Base64 数据解码并保存为文件"""
    
    # 查找 Base64 数据头 (e.g., data:image/png;base64,)
    match = re.search(r'data:(?P<mime>image/.*?);base64,(?P<data>.*)', base64_data)
    if not match:
        raise ValueError("Invalid Base64 image format. Data URI prefix (data:image/...) not found.")
    
    # 提取 MIME 类型和实际数据
    mime_type = match.group('mime')
    ext = mime_type.split('/')[-1].split('+')[0] 
    img_data = match.group('data')
    
    if not img_data:
        return None

    try:
        # 尝试解码 Base64 数据
        binary_data = base64.b64decode(img_data)
    except Exception as e:
        raise ValueError(f"Base64 decoding failed: {e}")

    # 清理文件名并生成唯一文件名
    safe_name = re.sub(r'[^a-zA-Z0-9]', '_', software_name)
    # 使用随机字符串确保文件名的唯一性
    filename = f"{safe_name}_{os.urandom(4).hex()}.{ext}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    # 保存二进制数据到文件
    with open(filepath, 'wb') as f:
        f.write(binary_data)
    
    # 返回可访问的 URL 路径 (例如: /logos/filename.png)
    return url_for('uploaded_file', filename=filename, _external=False)


# --- 辅助函数：Logo 文件服务路由 ---
@app.route('/logos/<filename>')
def uploaded_file(filename):
    """用于通过 URL 访问上传的 Logo 文件"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# --- 辅助函数：生成 HTML 表单 (用于 /add 和 /edit) ---

def get_software_form_html(software=None):
    """生成添加/修改软件的 HTML 表单"""
    
    is_edit = software is not None
    
    # 设置默认值或现有值
    name = software['name'] if is_edit else ''
    version = software['version'] if is_edit else ''
    description = software['description'] if is_edit else ''
    download_url = software['download_url'] if is_edit else ''
    silent_args = software['silent_args'] if is_edit else ''
    category = software['category'] if is_edit else '未分类'
    logo_url = software['logo_url'] if is_edit else ''
    install_type = software['install_type'] if is_edit else 'silent'
    
    form_title = f"{'修改' if is_edit else '添加'}软件: {name}" if is_edit else "添加新软件到应用商店"
    api_url = url_for('edit_software', software_id=software['id']) if is_edit else url_for('add_software')
    http_method = 'PUT' if is_edit else 'POST'

    # 所有的 JavaScript/CSS 大括号都必须是 {{ 或 }} 来避免 Python f-string 解析错误
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>应用商店管理后台 - {form_title}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{
                font-family: Arial, sans-serif; 
                padding: 20px; 
                background-color: #f4f4f4; 
            }}
            .container {{ 
                max-width: 600px; 
                margin: 0 auto; 
                background: white; 
                padding: 20px; 
                border-radius: 8px; 
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1); 
            }}
            input[type=text], textarea, select {{ 
                width: 100%; 
                padding: 10px; 
                margin: 5px 0 15px 0; 
                display: inline-block; 
                border: 1px solid #ccc; 
                border-radius: 4px; 
                box-sizing: border-box; 
            }}
            label {{ 
                font-weight: bold; 
                display: block; 
                margin-top: 10px; 
            }}
            button {{ 
                background-color: #007bff; 
                color: white; 
                padding: 14px 20px; 
                margin: 8px 0; 
                border: none; 
                cursor: pointer; 
                width: 100%; 
                border-radius: 4px; 
                font-size: 16px; 
            }}
            button:hover {{ 
                background-color: #0056b3; 
            }}
            .required::after {{ 
                content: "*"; 
                color: red; 
                margin-left: 5px; 
            }}
            .back-link {{ 
                display: block; 
                margin-bottom: 20px; 
            }}
            #logo-preview {{ 
                max-width: 100px; 
                max-height: 100px; 
                margin-top: 10px; 
                border: 1px solid #ccc; 
                padding: 5px; 
                display: {'block' if logo_url else 'none'}; 
            }}
            .logo-controls {{ 
                display: flex; 
                flex-direction: column; 
                gap: 5px; 
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <a href="/" class="back-link">← 返回软件列表</a>
            <h2>{form_title}</h2>
            <form id="softwareForm">
                <input type="hidden" id="httpMethod" value="{http_method}">
                <label for="name" class="required">名称:</label><input type="text" id="name" name="name" value="{name}" required><br>
                <label for="version" class="required">版本:</label><input type="text" id="version" name="version" value="{version}" required><br>
                <label for="description">描述:</label><textarea id="description" name="description">{description}</textarea><br>
                <label for="download_url" class="required">下载URL:</label><input type="text" id="download_url" name="download_url" value="{download_url}" required><br>
                <label for="silent_args">静默参数 (留空表示无):</label><input type="text" id="silent_args" name="silent_args" value="{silent_args}"><br>
                
                <label for="category">分类 (例如：办公软件):</label><input type="text" id="category" name="category" value="{category}"><br>
                
                <label>LOGO 图片 (选择文件 / 粘贴截图 / 填写 URL 或 Base64):</label>
                <div class="logo-controls">
                    <input type="file" id="logo_file_input" accept="image/*">
                    <input type="text" id="logo_base64" name="logo_base64" value="{logo_url}" placeholder="粘贴图片URL或Base64数据，或点击此框后粘贴截图">
                </div>
                <img id="logo-preview" src="{logo_url}">
                
                <label for="install_type">安装类型:</label>
                <select id="install_type" name="install_type">
                    <option value="silent" {'selected' if install_type == 'silent' else ''}>静默安装 (Silent)</option>
                    <option value="manual" {'selected' if install_type == 'manual' else ''}>手动安装 (Manual)</option>
                </select><br>

                <button type="submit">{"保存修改" if is_edit else "提交并添加软件"}</button>
            </form>

            <p id="message" style="font-weight: bold; margin-top: 20px;"></p>
        </div>

        <script>
            const form = document.getElementById('softwareForm');
            const messageElement = document.getElementById('message');
            const logoInput = document.getElementById('logo_base64');
            const logoFileInput = document.getElementById('logo_file_input');
            const logoPreview = document.getElementById('logo-preview');
            const httpMethod = document.getElementById('httpMethod').value;
            const apiEndpoint = "{api_url}";

            function updatePreview(value) {{
                if (value && (value.startsWith('data:image') || value.startsWith('http'))) {{
                    logoPreview.src = value;
                    logoPreview.style.display = 'block';
                }} else {{
                    logoPreview.style.display = 'none';
                    logoPreview.src = '';
                }}
            }}
            
            // 1. 监听 Logo URL/Base64 输入框变化
            logoInput.addEventListener('input', (e) => updatePreview(e.target.value));

            // 2. 监听 文件选择 (将文件转换为 Base64)
            logoFileInput.addEventListener('change', function(e) {{
                const file = e.target.files[0];
                if (file) {{
                    const reader = new FileReader();
                    reader.onload = function(readerEvent) {{
                        const base64Data = readerEvent.target.result;
                        logoInput.value = base64Data; // 将 Base64 填入文本输入框
                        updatePreview(base64Data);
                    }};
                    reader.readAsDataURL(file);
                }}
            }});

            // 3. 监听 粘贴事件 (处理剪贴板截图)
            logoInput.addEventListener('paste', function(e) {{
                // 检查是否有文件（图片）数据
                if (e.clipboardData && e.clipboardData.files.length > 0) {{
                    e.preventDefault(); // 阻止默认的文本粘贴行为
                    
                    const file = e.clipboardData.files[0];
                    if (file.type.startsWith('image/')) {{
                        const reader = new FileReader();
                        reader.onload = function(readerEvent) {{
                            const base64Data = readerEvent.target.result;
                            logoInput.value = base64Data; // 将 Base64 填入输入框
                            updatePreview(base64Data);
                        }};
                        reader.readAsDataURL(file);
                    }}
                }}
                // 如果粘贴的是文本（Base64 字符串或 URL），则由 input 事件处理
            }});

            // 首次加载页面时更新预览
            updatePreview(logoInput.value);

            // 4. 表单提交逻辑
            form.addEventListener('submit', function(e) {{
                e.preventDefault();
                messageElement.textContent = '正在提交...';
                messageElement.style.color = 'gray';

                const data = {{}};
                // 排除 type="file" 的 input
                form.querySelectorAll('input:not([type="hidden"]):not([type="file"]), textarea, select').forEach(input => {{
                    data[input.name] = input.value || '';
                }});

                fetch(apiEndpoint, {{
                    method: httpMethod,
                    headers: {{
                        'Content-Type': 'application/json',
                    }},
                    body: JSON.stringify(data)
                }})
                .then(response => {{
                    if (response.ok || response.status === 201) {{
                        messageElement.style.color = 'green';
                        messageElement.textContent = httpMethod === 'PUT' ? '修改保存成功！正在跳转...' : '软件添加成功！正在跳转...';
                        setTimeout(() => {{ window.location.href = '/'; }}, 1500); 
                    }} else {{
                        const status = response.status;
                        
                        return response.json()
                            .catch(() => {{ 
                                // 捕获非JSON错误
                                throw new Error(`服务器返回非JSON格式错误 (HTTP $${{status}}).`); 
                            }})
                            .then(err => {{
                                throw new Error(err.error || `服务器返回错误 (HTTP $${{status}})`);
                            }});
                    }}
                }})
                .catch(error => {{
                    console.error('Fetch error:', error);
                    messageElement.style.color = 'red';
                    messageElement.textContent = httpMethod === 'PUT' ? '修改失败: ' + error.message : '添加失败: ' + error.message;
                }});
            }});
        </script>
    </body>
    </html>
    """

# --- 辅助函数：生成软件列表 HTML (用于 / 路径) ---

def get_software_list_html(software_list, search_query=""):
    """生成包含软件列表和删除、修改功能的 HTML 页面"""
    
    table_rows = ""
    if not software_list:
        if search_query:
             table_rows = f"<tr><td colspan='7' style='text-align: center; padding: 20px;'>没有找到与 '{search_query}' 匹配的软件。</td></tr>"
        else:
            table_rows = "<tr><td colspan='7' style='text-align: center; padding: 20px;'>数据库中没有软件。请 <a href='/add'>添加新软件</a>。</td></tr>"
    else:
        for soft in software_list:
            # 使用一个默认的空字符串来避免空 Logo URL 导致图片标签出错
            logo_src = soft['logo_url'] if soft['logo_url'] else "" 
            table_rows += f"""
            <tr id="row-{soft['id']}">
                <td>{soft['id']}</td>
                <td><strong>{soft['name']}</strong></td>
                <td>{soft['version']}</td>
                <td>{soft['category']}</td>
                <td>{soft['install_type']}</td>
                <td><img src="{logo_src}" style="max-height: 40px; max-width: 40px; border-radius: 5px;"></td>
                <td>
                    <a href="{url_for('edit_software_page', software_id=soft['id'])}" style="background-color: #ffc107; color: black; border: none; padding: 5px 10px; cursor: pointer; border-radius: 3px; text-decoration: none; margin-right: 5px;">修改</a>
                    <button onclick="deleteSoftware({soft['id']}, '{soft['name']}')" style="background-color: #dc3545; color: white; border: none; padding: 5px 10px; cursor: pointer; border-radius: 3px;">删除</button>
                </td>
            </tr>
            """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>应用商店管理后台 - 软件列表</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{
                font-family: Arial, sans-serif; 
                padding: 20px; 
                background-color: #f4f4f4; 
            }}
            .container {{ 
                max-width: 1200px; 
                margin: 0 auto; 
                background: white; 
                padding: 20px; 
                border-radius: 8px; 
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1); 
            }}
            h2 {{ 
                border-bottom: 2px solid #ccc; 
                padding-bottom: 10px; 
            }}
            table {{ 
                width: 100%; 
                border-collapse: collapse; 
                margin-top: 20px; 
            }}
            th, td {{ 
                border: 1px solid #ddd; 
                padding: 12px; 
                text-align: left; 
                word-break: break-word; 
            }}
            th {{ 
                background-color: #007bff; 
                color: white; 
            }}
            tr:nth-child(even) {{ 
                background-color: #f2f2f2; 
            }}
            .top-controls {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
                flex-wrap: wrap; /* 适应小屏幕 */
            }}
            .add-button {{ 
                background-color: #28a745; 
                color: white; 
                padding: 10px 15px; 
                text-decoration: none; 
                border-radius: 5px; 
                display: inline-block; 
                white-space: nowrap; 
                margin-right: 10px;
            }}
            .search-form {{
                display: flex;
                gap: 10px;
                align-items: center;
            }}
            .search-form input[type="text"] {{
                padding: 10px;
                border: 1px solid #ccc;
                border-radius: 5px;
                width: 300px; 
            }}
            .search-form button, .search-form a {{
                padding: 10px 15px;
                background-color: #17a2b8;
                color: white;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                text-decoration: none;
                white-space: nowrap; 
            }}
            .search-form a.clear-btn {{
                background-color: #6c757d;
            }}
            .message-box {{ 
                padding: 10px; 
                margin-top: 10px; 
                border-radius: 5px; 
                font-weight: bold; 
            }}
            .success {{ 
                background-color: #d4edda; 
                color: #155724; 
                border: 1px solid #c3e6cb; 
            }}
            .error {{ 
                background-color: #f8d7da; 
                color: #721c24; 
                border: 1px solid #f5c6cb; 
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>已安装软件列表 (后台管理)</h2>
            
            <div class="top-controls">
                <a href="/add" class="add-button">+ 添加新软件</a>
                
                <form class="search-form" method="GET" action="/">
                    <input type="text" name="q" placeholder="搜索名称、版本、描述或分类..." value="{search_query}">
                    <button type="submit">搜索</button>
                    {'<a href="/" class="clear-btn">清除</a>' if search_query else ''}
                </form>
            </div>
            
            <div id="message" class="message-box" style="display: none;"></div>

            <table>
                <thead>
                    <tr>
                        <th style="width: 5%;">ID</th>
                        <th style="width: 20%;">名称</th>
                        <th style="width: 10%;">版本</th>
                        <th style="width: 10%;">分类</th>
                        <th style="width: 10%;">安装类型</th>
                        <th style="width: 5%;">Logo</th>
                        <th style="width: 15%;">操作</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
        </div>

        <script>
            function showMessage(text, type) {{
                const msgBox = document.getElementById('message');
                msgBox.textContent = text;
                msgBox.className = 'message-box ' + type;
                msgBox.style.display = 'block';
                setTimeout(() => {{ msgBox.style.display = 'none'; }}, 5000); // 增加显示时间
            }}

            function deleteSoftware(id, name) {{
                // 确保 id 是数字
                const softwareId = parseInt(id, 10); 
                if (isNaN(softwareId)) {{
                    showMessage('删除失败: ID无效。', 'error');
                    return;
                }}

                // 这里的提示框需要使用 JavaScript 模板字符串，因此需要双重转义
                if (!confirm(`确定要删除软件 "$${{name}}" (ID: $${{softwareId}}) 吗？`)) {{ 
                    return;
                }}

                // 使用标准字符串拼接，确保 URL 正确性
                const deleteUrl = '/api/software/' + softwareId;
                
                fetch(deleteUrl, {{ 
                    method: 'DELETE',
                }})
                .then(response => {{
                    if (response.ok) {{
                        showMessage(`软件 "$${{name}}" 删除成功!`, 'success');
                        // 从 DOM 中移除该行
                        document.getElementById(`row-$${{softwareId}}`).remove();
                    }} else {{
                        const status = response.status;
                        
                        // 尝试读取 JSON 错误信息
                        return response.json()
                            .then(err => {{
                                showMessage(`删除失败: $${{err.error || '未知错误'}} (HTTP $${{status}})`, 'error');
                            }})
                            .catch(() => {{ 
                                // 如果无法解析 JSON，显示通用错误
                                showMessage('删除失败: 服务器返回非JSON格式错误 (HTTP ' + status + ')，请检查服务器日志。', 'error');
                            }});
                    }}
                }})
                .catch(error => {{
                    console.error('Delete error:', error);
                    showMessage('删除失败: ' + error.message, 'error');
                }});
            }}
        </script>
    </body>
    </html>
    """

# --- API 路由：获取软件列表 ---

@app.route('/api/software', methods=['GET'])
def get_software():
    """API：获取所有软件列表 (供桌面客户端使用)"""
    conn = get_db_connection()
    software_list = conn.execute('SELECT * FROM software ORDER BY name').fetchall()
    
    result = [dict(row) for row in software_list]
    return jsonify(result)

# --- API 路由：添加软件 ---

@app.route('/api/software', methods=['POST'])
def add_software():
    """API：添加新的软件记录"""
    data = request.get_json()
    
    required_fields = ['name', 'version', 'download_url']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'error': f'Missing or empty required field: {field}'}), 400

    # 1. 处理 Logo Base64/URL/空值
    logo_url = data.get('logo_base64', '')
    
    if logo_url and logo_url.startswith('data:image'):
        # 是 Base64 数据，保存为文件
        try:
            logo_url = save_base64_image(logo_url, data['name'])
        except ValueError as e:
            return jsonify({'error': f'Logo Error: {e}'}), 400
    # 否则，如果它是 URL 或空字符串，则直接使用
    
    # 2. 收集其他字段
    silent_args = data.get('silent_args', '') or ''
    category = data.get('category', '未分类') or '未分类'
    install_type = data.get('install_type', 'silent') or 'silent'
    description = data.get('description', '') or ''
    
    if install_type not in ['silent', 'manual']:
        return jsonify({'error': 'Invalid install_type. Must be "silent" or "manual".'}), 400
    
    try:
        conn = get_db_connection()
        conn.execute(
            """
            INSERT INTO software (name, version, description, download_url, silent_args, category, logo_url, install_type) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (data['name'], data['version'], description, data['download_url'], 
             silent_args, category, logo_url, install_type)
        )
        conn.commit()
        
        # 获取新插入的 ID
        new_id = conn.execute("SELECT id FROM software WHERE name=?", (data['name'],)).fetchone()[0]
        return jsonify({'message': 'Software added successfully', 'id': new_id}), 201
        
    except sqlite3.IntegrityError:
        return jsonify({'error': f"Software with name '{data['name']}' already exists"}), 409
    except Exception as e:
        app.logger.error(f"Database error during software add: {e}")
        return jsonify({'error': f'Database error: {e}'}), 500

# --- API 路由：修改软件 ---

@app.route('/api/software/<int:software_id>', methods=['PUT'])
def edit_software(software_id):
    """API：修改指定的软件记录 (PUT)"""
    data = request.get_json()
    
    required_fields = ['name', 'version', 'download_url']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'error': f'Missing or empty required field: {field}'}), 400

    # 1. 处理 Logo Base64/URL/空值
    logo_url = data.get('logo_base64', '')
    
    if logo_url and logo_url.startswith('data:image'):
        # 是 Base64 数据，保存新文件
        try:
            logo_url = save_base64_image(logo_url, data['name'])
        except ValueError as e:
            return jsonify({'error': f'Logo Error: {e}'}), 400
    # 否则，如果它是 URL 或空字符串，则直接使用
    
    # 2. 收集其他字段
    silent_args = data.get('silent_args', '') or ''
    category = data.get('category', '未分类') or '未分类'
    install_type = data.get('install_type', 'silent') or 'silent'
    description = data.get('description', '') or ''
    
    if install_type not in ['silent', 'manual']:
        return jsonify({'error': 'Invalid install_type. Must be "silent" or "manual".'}), 400
        
    try:
        conn = get_db_connection()
        cursor = conn.execute(
            """
            UPDATE software SET 
                name = ?, 
                version = ?, 
                description = ?, 
                download_url = ?, 
                silent_args = ?, 
                category = ?, 
                logo_url = ?, 
                install_type = ?
            WHERE id = ?
            """,
            (data['name'], data['version'], description, data['download_url'], 
             silent_args, category, logo_url, install_type, software_id)
        )
        conn.commit()
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Software not found for update'}), 404
            
        return jsonify({'message': 'Software updated successfully'}), 200
        
    except sqlite3.IntegrityError:
        return jsonify({'error': f"Software with name '{data['name']}' already exists"}), 409
    except Exception as e:
        app.logger.error(f"Database error during software update: {e}")
        return jsonify({'error': f'Database error: {e}'}), 500

# --- API 路由：删除软件 (DELETE) ---

@app.route('/api/software/<int:software_id>', methods=['DELETE'])
def delete_software(software_id):
    """API：通过 ID 删除软件记录"""
    conn = get_db_connection()
    cursor = conn.execute("DELETE FROM software WHERE id = ?", (software_id,))
    conn.commit()
    
    if cursor.rowcount == 0:
        # 如果没有行被删除，返回 404 (Software Not Found)
        return jsonify({'error': 'Software not found'}), 404
        
    return jsonify({'message': 'Software deleted successfully'}), 200

# --- 网页后台路由 ---

@app.route('/', methods=['GET'])
def list_software_page():
    """根路径：显示已有的软件列表，支持搜索"""
    conn = get_db_connection()
    
    # 接收搜索关键词
    search_query = request.args.get('q', '').strip()
    
    # 构造 SQL 查询和参数
    if search_query:
        # 使用 SQLite 的 LIKE 进行模糊搜索
        search_term = '%' + search_query + '%'
        sql_query = """
            SELECT * FROM software 
            WHERE name LIKE ? OR version LIKE ? OR description LIKE ? OR category LIKE ?
            ORDER BY id DESC
        """
        # 参数列表需要包含搜索词的四次重复
        params = (search_term, search_term, search_term, search_term)
    else:
        # 如果没有搜索词，查询所有
        sql_query = 'SELECT * FROM software ORDER BY id DESC'
        params = ()

    software_list = conn.execute(sql_query, params).fetchall()
    
    result = [dict(row) for row in software_list]
    # 将搜索词传递给 HTML 生成函数，以便在搜索框中保留
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
        # 如果软件 ID 不存在，返回 404
        abort(404)
    
    return get_software_form_html(dict(software))


# --- 启动应用 ---

if __name__ == '__main__':
    # 首次运行时初始化数据库
    init_db() 
    # host='0.0.0.0' 允许从外部网络访问
    app.run(debug=True, host='0.0.0.0', port=5000)