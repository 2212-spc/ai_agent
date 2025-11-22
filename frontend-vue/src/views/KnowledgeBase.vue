<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import axios from 'axios';

const router = useRouter();
const documents = ref([]);
const isLoading = ref(false);
const isUploading = ref(false);
const fileInput = ref(null);
const apiBase = 'http://127.0.0.1:8000';

async function loadDocuments() {
    isLoading.value = true;
    try {
        const response = await axios.get(`${apiBase}/documents`);
        documents.value = response.data;
    } catch (error) {
        console.error('加载文档失败:', error);
    } finally {
        isLoading.value = false;
    }
}

async function deleteDocument(docId) {
    if (!confirm('确定要删除这个文档吗？')) return;
    
    try {
        await axios.delete(`${apiBase}/documents/${docId}`);
        loadDocuments();
    } catch (error) {
        console.error('删除文档失败:', error);
    }
}

async function handleFileUpload(event) {
    const files = event.target.files;
    if (!files || files.length === 0) return;
    
    isUploading.value = true;
    try {
        for (const file of files) {
            const formData = new FormData();
            formData.append('file', file);
            
            await axios.post(`${apiBase}/documents/upload`, formData, {
                headers: {
                    'Content-Type': 'multipart/form-data'
                }
            });
        }
        
        alert(`成功上传 ${files.length} 个文件`);
        loadDocuments();
    } catch (error) {
        console.error('上传失败:', error);
        alert('文件上传失败: ' + (error.response?.data?.detail || error.message));
    } finally {
        isUploading.value = false;
        event.target.value = ''; // 清空input
    }
}

function triggerFileUpload() {
    fileInput.value.click();
}

onMounted(() => {
    loadDocuments();
});
</script>

<template>
    <div class="page-container">
        <div class="header">
            <div class="header-left">
                <button class="btn-icon" @click="router.push('/chat')">←</button>
                <div>
                    <h1>知识库管理</h1>
                    <p class="subtitle">管理上传的文档和知识</p>
                </div>
            </div>
            <div class="header-actions">
                <button class="btn btn-secondary" @click="loadDocuments">🔄 刷新</button>
                <button class="btn btn-primary" @click="triggerFileUpload" :disabled="isUploading">
                    {{ isUploading ? '上传中...' : '📤 上传文档' }}
                </button>
                <input
                    ref="fileInput"
                    type="file"
                    multiple
                    accept=".pdf,.doc,.docx,.txt,.md"
                    @change="handleFileUpload"
                    style="display: none;"
                />
            </div>
        </div>

        <div class="content">
            <div v-if="isLoading" class="loading">加载中...</div>
            <div v-else-if="documents.length === 0" class="empty-state">
                <div class="empty-state-icon">📚</div>
                <h3>暂无文档</h3>
                <p>上传文档开始构建知识库</p>
            </div>
            <div v-else class="documents-list">
                <div v-for="doc in documents" :key="doc.id" class="document-card">
                    <div class="doc-icon">📄</div>
                    <div class="doc-info">
                        <h3>{{ doc.filename }}</h3>
                        <div class="doc-meta">
                            <span>📊 {{ doc.chunk_count }} 个片段</span>
                            <span>📅 {{ new Date(doc.created_at).toLocaleDateString() }}</span>
                            <span>💾 {{ (doc.file_size / 1024).toFixed(1) }} KB</span>
                        </div>
                    </div>
                    <div class="doc-actions">
                        <button class="btn-icon" title="删除" @click="deleteDocument(doc.id)">
                            🗑️
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.page-container {
    height: 100vh;
    display: flex;
    flex-direction: column;
    background: var(--bg-secondary);
}

.header {
    background: var(--bg-primary);
    padding: 20px;
    border-bottom: 1px solid var(--border-primary);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.header-left {
    display: flex;
    gap: 16px;
    align-items: center;
}

.header-actions {
    display: flex;
    gap: 12px;
}

.header h1 {
    margin: 0;
    font-size: 24px;
}

.subtitle {
    color: var(--text-secondary);
    margin: 4px 0 0 0;
    font-size: 14px;
}

.content {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
}

.documents-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.document-card {
    background: var(--bg-primary);
    border: 1px solid var(--border-primary);
    border-radius: 12px;
    padding: 16px;
    display: flex;
    align-items: center;
    gap: 16px;
    transition: all 0.2s;
}

.document-card:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    transform: translateY(-2px);
}

.doc-icon {
    font-size: 32px;
    flex-shrink: 0;
}

.doc-info {
    flex: 1;
}

.doc-info h3 {
    margin: 0 0 8px 0;
    font-size: 16px;
}

.doc-meta {
    display: flex;
    gap: 16px;
    font-size: 13px;
    color: var(--text-secondary);
}

.doc-actions {
    display: flex;
    gap: 8px;
}

.loading, .empty-state {
    text-align: center;
    padding: 60px 20px;
    color: var(--text-tertiary);
}

.empty-state-icon {
    font-size: 48px;
    margin-bottom: 16px;
}

.empty-state h3 {
    margin: 0 0 8px 0;
}
</style>
