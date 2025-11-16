/* ===== 画布管理器 - 处理缩放、平移等操作 ===== */

/**
 * 画布管理器类
 */
class CanvasManager {
    constructor(canvasId = 'builderCanvas', contentLayerId = 'canvasContentLayer') {
        this.canvasId = canvasId;
        this.contentLayerId = contentLayerId;
        
        // 变换状态
        this.scale = 1;
        this.offsetX = 0;
        this.offsetY = 0;
        
        // 拖拽状态
        this.isDragging = false;
        this.lastX = 0;
        this.lastY = 0;
        
        // DOM元素
        this.canvas = null;
        this.contentLayer = null;
        
        // 配置
        this.config = {
            minScale: 0.3,
            maxScale: 3,
            zoomStep: 1.2,
            panKeys: ['Space'], // 空格键触发平移模式
        };
        
        // RAF优化
        this.rafId = null;
        this.hideIndicatorTimeout = null;
    }

    /**
     * 初始化画布管理器
     */
    init() {
        this.canvas = document.getElementById(this.canvasId);
        this.contentLayer = document.getElementById(this.contentLayerId);
        
        if (!this.canvas || !this.contentLayer) {
            console.warn('画布元素未找到');
            return false;
        }
        
        this.setupEventListeners();
        console.log('✅ 画布管理器初始化成功');
        return true;
    }

    /**
     * 设置事件监听器
     */
    setupEventListeners() {
        // 鼠标滚轮缩放
        this.canvas.addEventListener('wheel', this.handleWheel.bind(this), { passive: false });
        
        // 画布拖拽
        this.setupPanHandlers();
        
        // 键盘快捷键
        this.setupKeyboardHandlers();
    }

    /**
     * 处理滚轮缩放
     */
    handleWheel(e) {
        e.preventDefault();
        
        const delta = e.deltaY > 0 ? (1 / this.config.zoomStep) : this.config.zoomStep;
        const oldScale = this.scale;
        this.scale = Math.max(
            this.config.minScale, 
            Math.min(this.config.maxScale, this.scale * delta)
        );
        
        // 以鼠标位置为中心缩放
        const rect = this.canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        
        this.offsetX = mouseX - (mouseX - this.offsetX) * (this.scale / oldScale);
        this.offsetY = mouseY - (mouseY - this.offsetY) * (this.scale / oldScale);
        
        this.updateTransform();
    }

    /**
     * 设置平移处理器
     */
    setupPanHandlers() {
        let spacePressed = false;
        
        // 监听空格键
        document.addEventListener('keydown', (e) => {
            if (e.code === 'Space' && !e.repeat && 
                document.activeElement.tagName !== 'INPUT' && 
                document.activeElement.tagName !== 'TEXTAREA') {
                e.preventDefault();
                spacePressed = true;
                this.canvas.style.cursor = 'grab';
            }
        });
        
        document.addEventListener('keyup', (e) => {
            if (e.code === 'Space') {
                spacePressed = false;
                if (!this.isDragging) {
                    this.canvas.style.cursor = 'default';
                }
            }
        });
        
        // 鼠标按下
        this.canvas.addEventListener('mousedown', (e) => {
            // 中键、Shift+左键、空格+左键都可以拖拽
            const canPan = e.button === 1 || (e.button === 0 && (e.shiftKey || spacePressed));
            
            if (canPan) {
                e.preventDefault();
                e.stopPropagation();
                this.startPan(e.clientX, e.clientY);
            }
        }, true);
        
        // 鼠标移动
        document.addEventListener('mousemove', (e) => {
            if (this.isDragging) {
                e.preventDefault();
                this.updatePan(e.clientX, e.clientY);
            }
        });
        
        // 鼠标释放
        document.addEventListener('mouseup', () => {
            if (this.isDragging) {
                this.endPan();
            }
        });
    }

    /**
     * 设置键盘快捷键
     */
    setupKeyboardHandlers() {
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + 0: 重置视图
            if ((e.ctrlKey || e.metaKey) && e.key === '0') {
                e.preventDefault();
                this.resetView();
            }
            
            // Ctrl/Cmd + +: 放大
            if ((e.ctrlKey || e.metaKey) && (e.key === '+' || e.key === '=')) {
                e.preventDefault();
                this.zoomIn();
            }
            
            // Ctrl/Cmd + -: 缩小
            if ((e.ctrlKey || e.metaKey) && e.key === '-') {
                e.preventDefault();
                this.zoomOut();
            }
        });
    }

    /**
     * 开始平移
     */
    startPan(x, y) {
        this.isDragging = true;
        this.lastX = x;
        this.lastY = y;
        this.canvas.classList.add('panning');
        this.canvas.style.cursor = 'grabbing';
    }

    /**
     * 更新平移
     */
    updatePan(x, y) {
        const dx = x - this.lastX;
        const dy = y - this.lastY;
        this.offsetX += dx;
        this.offsetY += dy;
        this.lastX = x;
        this.lastY = y;
        this.updateTransform();
    }

    /**
     * 结束平移
     */
    endPan() {
        this.isDragging = false;
        this.canvas.classList.remove('panning');
        this.canvas.style.cursor = 'default';
    }

    /**
     * 更新变换
     */
    updateTransform() {
        if (!this.contentLayer) return;
        
        // 使用 requestAnimationFrame 优化性能
        if (this.rafId) {
            cancelAnimationFrame(this.rafId);
        }
        
        this.rafId = requestAnimationFrame(() => {
            this.contentLayer.style.transform = 
                `translate(${this.offsetX}px, ${this.offsetY}px) scale(${this.scale})`;
            this.showZoomIndicator();
        });
    }

    /**
     * 显示缩放指示器
     */
    showZoomIndicator() {
        const indicator = document.getElementById('zoomIndicator');
        if (!indicator) return;
        
        indicator.textContent = `${Math.round(this.scale * 100)}%`;
        indicator.classList.add('show');
        
        // 2秒后自动隐藏
        clearTimeout(this.hideIndicatorTimeout);
        this.hideIndicatorTimeout = setTimeout(() => {
            indicator.classList.remove('show');
        }, 2000);
    }

    /**
     * 放大
     */
    zoomIn() {
        const oldScale = this.scale;
        this.scale = Math.min(this.config.maxScale, this.scale * this.config.zoomStep);
        
        // 以画布中心为缩放中心
        const rect = this.canvas.getBoundingClientRect();
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;
        
        this.offsetX = centerX - (centerX - this.offsetX) * (this.scale / oldScale);
        this.offsetY = centerY - (centerY - this.offsetY) * (this.scale / oldScale);
        
        this.updateTransform();
    }

    /**
     * 缩小
     */
    zoomOut() {
        const oldScale = this.scale;
        this.scale = Math.max(this.config.minScale, this.scale / this.config.zoomStep);
        
        const rect = this.canvas.getBoundingClientRect();
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;
        
        this.offsetX = centerX - (centerX - this.offsetX) * (this.scale / oldScale);
        this.offsetY = centerY - (centerY - this.offsetY) * (this.scale / oldScale);
        
        this.updateTransform();
    }

    /**
     * 重置视图
     */
    resetView() {
        this.scale = 1;
        this.offsetX = 0;
        this.offsetY = 0;
        this.updateTransform();
    }

    /**
     * 居中显示所有内容
     */
    centerContent(nodes = []) {
        if (nodes.length === 0) return;
        
        // 计算所有节点的边界
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        
        nodes.forEach(node => {
            minX = Math.min(minX, node.x);
            minY = Math.min(minY, node.y);
            maxX = Math.max(maxX, node.x + 160); // 假设节点宽度160
            maxY = Math.max(maxY, node.y + 80);  // 假设节点高度80
        });
        
        const contentWidth = maxX - minX;
        const contentHeight = maxY - minY;
        const contentCenterX = (minX + maxX) / 2;
        const contentCenterY = (minY + maxY) / 2;
        
        const rect = this.canvas.getBoundingClientRect();
        const canvasCenterX = rect.width / 2;
        const canvasCenterY = rect.height / 2;
        
        // 计算合适的缩放比例
        const scaleX = rect.width / (contentWidth + 100); // 留边距
        const scaleY = rect.height / (contentHeight + 100);
        this.scale = Math.min(scaleX, scaleY, 1); // 不放大，只缩小
        
        // 计算偏移使内容居中
        this.offsetX = canvasCenterX - contentCenterX * this.scale;
        this.offsetY = canvasCenterY - contentCenterY * this.scale;
        
        this.updateTransform();
    }

    /**
     * 获取当前变换状态
     */
    getTransform() {
        return {
            scale: this.scale,
            offsetX: this.offsetX,
            offsetY: this.offsetY
        };
    }

    /**
     * 设置变换状态
     */
    setTransform(scale, offsetX, offsetY) {
        this.scale = Math.max(this.config.minScale, Math.min(this.config.maxScale, scale));
        this.offsetX = offsetX;
        this.offsetY = offsetY;
        this.updateTransform();
    }

    /**
     * 销毁管理器
     */
    destroy() {
        if (this.rafId) {
            cancelAnimationFrame(this.rafId);
        }
        if (this.hideIndicatorTimeout) {
            clearTimeout(this.hideIndicatorTimeout);
        }
        // 移除事件监听器（如果需要）
    }
}

// 导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { CanvasManager };
}
