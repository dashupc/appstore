// /pwa/app.js
const API_URL = 'http://localhost:5000/api/software';
const BASE_URL = 'http://localhost:5000';
let allSoftwareData = [];

document.addEventListener('DOMContentLoaded', () => {
    // 注册 Service Worker，启用 PWA 功能
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/service-worker.js')
            .then(reg => console.log('Service Worker 注册成功', reg))
            .catch(err => console.error('Service Worker 注册失败', err));
    }
    
    fetchSoftwareData();

    document.getElementById('search-input').addEventListener('input', filterSoftware);
    document.getElementById('refresh-btn').addEventListener('click', fetchSoftwareData);
});

async function fetchSoftwareData() {
    const statusText = document.getElementById('status-text');
    statusText.textContent = '正在连接服务器并加载数据...';
    statusText.className = 'text-info';

    try {
        const response = await fetch(API_URL);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        allSoftwareData = await response.json();
        filterSoftware(); // 初次加载并渲染所有数据
        statusText.textContent = '软件列表加载成功。';
        statusText.className = 'text-success';
    } catch (error) {
        console.error("Failed to fetch software data:", error);
        statusText.textContent = `连接API失败，请确认后端运行在 ${API_URL}`;
        statusText.className = 'text-danger';
        renderSoftwareList([]);
    }
}

function filterSoftware() {
    const searchTerm = document.getElementById('search-input').value.toLowerCase().trim();
    
    const filteredList = allSoftwareData.filter(software => {
        const nameMatch = software.name.toLowerCase().includes(searchTerm);
        const descMatch = software.description ? software.description.toLowerCase().includes(searchTerm) : false;
        const versionMatch = software.version ? software.version.toLowerCase().includes(searchTerm) : false;
        
        return nameMatch || descMatch || versionMatch;
    });

    renderSoftwareList(filteredList);
}

function getLogoUrl(software) {
    const logoPath = software.logo_url;
    if (logoPath && logoPath.startsWith('/logos/')) {
        return `${BASE_URL}${logoPath}`;
    }
    // TODO: 提供一个合理的默认 Logo 路径
    return '/pwa/icons/placeholder.png'; 
}

function handleInstallClick(software) {
    const installType = software.install_type ? software.install_type.toLowerCase() : 'silent';
    
    if (!software.download_url) {
        alert('错误：下载链接缺失。');
        return;
    }
    
    // PWA 无法执行静默安装或打开文件夹，统一为下载操作并给出提示
    let message = '';
    if (installType === 'manual') {
        message = `您选择了手动安装 ${software.name}。点击确认开始下载。下载完成后请手动安装。`;
    } else {
        message = `PWA 模式无法执行静默安装。点击确认下载 ${software.name} 安装包，下载完成后请手动安装。`;
    }

    if (confirm(message)) {
        // 触发浏览器下载
        window.open(software.download_url, '_blank');
    }
}

function renderSoftwareList(softwareList) {
    const container = document.getElementById('software-list-container');
    container.innerHTML = '';

    if (softwareList.length === 0) {
        container.innerHTML = '<div class="alert alert-warning mt-3">未找到匹配的软件。</div>';
        return;
    }

    softwareList.forEach(software => {
        const logoUrl = getLogoUrl(software);
        const installType = software.install_type ? software.install_type.toLowerCase() : 'silent';
        
        let description = software.description || '无描述';
        if (description.length > 100) {
            description = description.substring(0, 97) + '...';
        }
        
        const item = document.createElement('div');
        item.className = 'row software-item mx-0';
        
        item.innerHTML = `
            <div class="col-1 d-flex justify-content-center">
                <img src="${logoUrl}" alt="${software.name} Logo" class="software-logo" onerror="this.onerror=null;this.src='/pwa/icons/placeholder.png';">
            </div>
            <div class="col-3">
                <h5 class="fw-bold text-primary mb-0">${software.name}</h5>
                <small class="text-muted">${installType === 'manual' ? '手动安装' : '静默安装（需手动）'}</small>
            </div>
            <div class="col-2 text-center text-secondary">
                ${software.version || 'N/A'}
            </div>
            <div class="col-4 text-muted small">
                ${description}
            </div>
            <div class="col-2 text-end">
                <button class="btn ${installType === 'manual' ? 'btn-info' : 'btn-success'} btn-sm install-btn">
                    下载
                </button>
            </div>
        `;
        
        const installButton = item.querySelector('.install-btn');
        installButton.addEventListener('click', () => handleInstallClick(software));

        container.appendChild(item);
    });
}