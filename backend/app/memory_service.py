"""
长期记忆系统 - 智能记忆提取、存储和检索
支持记忆去重和合并
"""
from __future__ import annotations

import json
import logging
import re
from difflib import SequenceMatcher
from typing import List, Optional, Dict, Any, Tuple

import httpx
from sqlalchemy.orm import Session

from .config import Settings
from .database import (
    ConversationHistory,
    LongTermMemory,
    get_conversation_history,
    save_conversation_message,
    save_long_term_memory,
    search_long_term_memory,
    get_recent_memories,
    update_memory_access,
    get_similar_memories,
    update_memory_content,
    merge_memories,
)
from .rag_service import retrieve_context, get_embeddings
from langchain_core.documents import Document
from langchain_community.vectorstores import Chroma

logger = logging.getLogger(__name__)

# 记忆向量数据库缓存（独立的 collection）
_MEMORY_VECTORSTORE_CACHE: Dict[str, Chroma] = {}


# ==================== 记忆相似度检测 ====================

def calculate_text_similarity(text1: str, text2: str) -> float:
    """
    计算两个文本的相似度（0-1）
    使用 SequenceMatcher 计算序列相似度
    """
    if not text1 or not text2:
        return 0.0
    
    # 转换为小写并去除多余空格
    text1 = re.sub(r'\s+', ' ', text1.lower().strip())
    text2 = re.sub(r'\s+', ' ', text2.lower().strip())
    
    # 如果完全相同，返回1.0
    if text1 == text2:
        return 1.0
    
    # 使用 SequenceMatcher 计算相似度
    similarity = SequenceMatcher(None, text1, text2).ratio()
    return similarity


def calculate_jaccard_similarity(text1: str, text2: str) -> float:
    """
    计算两个文本的 Jaccard 相似度（0-1）
    基于词汇集合的交集和并集
    """
    if not text1 or not text2:
        return 0.0
    
    # 分词（简单分词，按空格和标点）
    words1 = set(re.findall(r'\w+', text1.lower()))
    words2 = set(re.findall(r'\w+', text2.lower()))
    
    if not words1 or not words2:
        return 0.0
    
    # 计算交集和并集
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    
    if union == 0:
        return 0.0
    
    return intersection / union


def calculate_semantic_similarity(
    text1: str,
    text2: str,
    embeddings_model=None,
) -> float:
    """
    计算两个文本的语义相似度（0-1）
    使用 embedding 向量计算余弦相似度
    
    注意：这个方法可能较慢，用于高精度相似度检测
    """
    try:
        if embeddings_model is None:
            embeddings_model = get_embeddings()
        
        # 生成 embedding
        emb1 = embeddings_model.embed_query(text1)
        emb2 = embeddings_model.embed_query(text2)
        
        # 计算余弦相似度
        import numpy as np
        
        dot_product = np.dot(emb1, emb2)
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        similarity = dot_product / (norm1 * norm2)
        # 归一化到 0-1（余弦相似度范围是 -1 到 1）
        return (similarity + 1) / 2
        
    except Exception as e:
        logger.warning(f"语义相似度计算失败: {e}，使用文本相似度")
        return calculate_text_similarity(text1, text2)


def find_similar_memory(
    session: Session,
    new_content: str,
    memory_type: str,
    user_id: Optional[str] = None,
    similarity_threshold: float = 0.75,
    use_semantic: bool = False,
) -> Optional[Tuple[LongTermMemory, float]]:
    """
    查找与新记忆相似的已有记忆
    
    Args:
        session: 数据库会话
        new_content: 新记忆的内容
        memory_type: 记忆类型
        user_id: 用户ID
        similarity_threshold: 相似度阈值（0-1），超过此值认为相似
        use_semantic: 是否使用语义相似度（更准确但较慢）
    
    Returns:
        (相似记忆, 相似度) 或 None
    """
    # 获取同类型、同用户的记忆
    similar_memories = get_similar_memories(
        session=session,
        memory_type=memory_type,
        content=new_content,
        user_id=user_id,
        limit=20,  # 检查最多20条记忆
    )
    
    if not similar_memories:
        return None
    
    best_match = None
    best_similarity = 0.0
    embeddings_model = None
    
    if use_semantic:
        embeddings_model = get_embeddings()
    
    # 计算与每条记忆的相似度
    for memory in similar_memories:
        # 优先使用文本相似度（快速）
        text_sim = calculate_text_similarity(new_content, memory.content)
        jaccard_sim = calculate_jaccard_similarity(new_content, memory.content)
        
        # 综合相似度（文本相似度权重0.6，Jaccard相似度权重0.4）
        combined_sim = text_sim * 0.6 + jaccard_sim * 0.4
        
        # 如果需要高精度，使用语义相似度
        if use_semantic and combined_sim > 0.5:
            semantic_sim = calculate_semantic_similarity(
                new_content,
                memory.content,
                embeddings_model,
            )
            # 语义相似度权重更高
            combined_sim = combined_sim * 0.4 + semantic_sim * 0.6
        
        if combined_sim > best_similarity:
            best_similarity = combined_sim
            best_match = memory
    
    # 如果相似度超过阈值，返回最佳匹配
    if best_match and best_similarity >= similarity_threshold:
        return (best_match, best_similarity)
    
    return None


def merge_memory_with_existing(
    session: Session,
    existing_memory: LongTermMemory,
    new_content: str,
    new_importance: int,
    new_source_id: Optional[str] = None,
    new_metadata: Optional[Dict[str, Any]] = None,
    settings: Optional[Settings] = None,
) -> LongTermMemory:
    """
    将新记忆合并到已有记忆中
    
    策略：
    1. 如果新内容更完整或更详细，更新内容
    2. 取更高的重要性评分
    3. 合并元数据
    4. 更新访问统计
    """
    # 判断哪个内容更好（更长或包含更多信息）
    existing_content = existing_memory.content
    should_update_content = False
    
    # 如果新内容更长或包含更多关键词，认为是更好的版本
    if len(new_content) > len(existing_content) * 1.2:
        should_update_content = True
    elif len(new_content) > len(existing_content):
        # 新内容稍长，检查是否包含更多信息
        new_words = set(re.findall(r'\w+', new_content.lower()))
        existing_words = set(re.findall(r'\w+', existing_content.lower()))
        if len(new_words - existing_words) > len(existing_words - new_words):
            should_update_content = True
    
    # 更新内容（如果需要）
    final_content = new_content if should_update_content else existing_content
    
    # 取更高的重要性评分
    final_importance = max(existing_memory.importance_score, new_importance)
    
    # 准备元数据
    merged_metadata = new_metadata or {}
    merged_metadata["merged_count"] = merged_metadata.get("merged_count", 0) + 1
    if new_source_id:
        merged_metadata["latest_source_id"] = new_source_id
    
    # 更新记忆
    updated_memory = update_memory_content(
        session=session,
        memory_id=existing_memory.id,
        new_content=final_content,
        new_importance_score=final_importance,
        new_metadata=merged_metadata,
    )
    
    logger.info(
        f"合并记忆: {existing_memory.id} <- 新记忆 "
        f"(相似度: 高, 内容{'已更新' if should_update_content else '保留原版'}, "
        f"重要性: {final_importance})"
    )
    
    return updated_memory


def save_memory_with_dedup(
    session: Session,
    memory_type: str,
    content: str,
    importance_score: int = 50,
    user_id: Optional[str] = None,
    source_conversation_id: Optional[str] = None,
    metadata: Optional[dict] = None,
    similarity_threshold: float = 0.75,
    use_semantic_similarity: bool = False,
    settings: Optional[Settings] = None,
) -> LongTermMemory:
    """
    保存记忆，并在保存前检查重复并合并
    
    Args:
        session: 数据库会话
        memory_type: 记忆类型
        content: 记忆内容
        importance_score: 重要性评分
        user_id: 用户ID
        source_conversation_id: 来源对话ID
        metadata: 元数据
        similarity_threshold: 相似度阈值（0-1）
        use_semantic_similarity: 是否使用语义相似度检测
        settings: 配置对象（用于向量化）
    
    Returns:
        保存或合并后的记忆对象
    """
    if settings is None:
        from .config import get_settings
        settings = get_settings()
    
    # 查找相似记忆
    similar_result = find_similar_memory(
        session=session,
        new_content=content,
        memory_type=memory_type,
        user_id=user_id,
        similarity_threshold=similarity_threshold,
        use_semantic=use_semantic_similarity,
    )
    
    if similar_result:
        existing_memory, similarity = similar_result
        # 合并到已有记忆
        merged_metadata = metadata or {}
        merged_metadata["similarity_score"] = similarity
        
        merged_memory = merge_memory_with_existing(
            session=session,
            existing_memory=existing_memory,
            new_content=content,
            new_importance=importance_score,
            new_source_id=source_conversation_id,
            new_metadata=merged_metadata,
            settings=settings,
        )
        
        # 如果内容已更新，同步更新向量数据库
        if merged_memory.content != existing_memory.content:
            update_memory_in_vectorstore(
                memory_id=merged_memory.id,
                content=merged_memory.content,
                memory_type=merged_memory.memory_type,
                user_id=merged_memory.user_id,
                settings=settings,
            )
        
        return merged_memory
    else:
        # 没有找到相似记忆，保存新记忆
        new_memory = save_long_term_memory(
            session=session,
            memory_type=memory_type,
            content=content,
            importance_score=importance_score,
            user_id=user_id,
            source_conversation_id=source_conversation_id,
            metadata=metadata,
        )
        
        # 向量化并存储到向量数据库
        add_memory_to_vectorstore(
            memory_id=new_memory.id,
            content=new_memory.content,
            memory_type=new_memory.memory_type,
            user_id=new_memory.user_id,
            settings=settings,
        )
        
        return new_memory


async def extract_memories_from_conversation(
    conversation_text: str,
    settings: Settings,
    session_id: str,
    user_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    使用 LLM 从对话中提取重要信息作为长期记忆
    
    Returns:
        提取的记忆列表，每个记忆包含 type, content, importance_score
    """
    try:
        extraction_prompt = f"""请分析以下对话，提取出应该被长期记住的重要信息。

对话内容：
{conversation_text}

请提取以下类型的信息：
1. **fact** - 明确的事实信息（如：用户的名字、职业、工作地点、居住地等）
   - **特别注意**：如果对话中提到用户的名字，必须提取为 fact 类型，重要性设为 90-100
   - 例如："我叫张三" → {{"type": "fact", "content": "用户的名字是张三", "importance": 95}}
2. **preference** - 用户的偏好和习惯（如：喜欢的食物、编程语言、工作习惯等）
3. **event** - 重要的事件或经历（如：生日、旅行计划、会议安排等）
4. **relationship** - 人物关系或社交信息

请以 JSON 格式输出提取的记忆：
{{
  "memories": [
    {{
      "type": "fact|preference|event|relationship",
      "content": "记忆内容的简洁描述",
      "importance": 50-100  // 重要性评分，50为一般重要，100为非常重要。姓名等重要信息应设为90-100
    }}
  ]
}}

要求：
1. **必须提取用户姓名**：如果对话中提到用户的名字（如"我叫XXX"、"我是XXX"），必须提取为 fact 类型，importance 设为 90-100
2. 只提取真正重要、值得长期记住的信息
3. 内容要简洁、明确，使用第三人称描述（如"用户的名字是XXX"而不是"我的名字是XXX"）
4. importance 评分要合理：
   - 姓名、职业等关键信息：90-100
   - 重要偏好、事件：70-89
   - 一般信息：50-69
5. 如果对话中没有重要信息，返回空的 memories 数组
6. 只返回 JSON，不要其他解释
"""

        headers = {
            "Authorization": f"Bearer {settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }
        endpoint = f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"

        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": extraction_prompt}],
            "temperature": 0.3,  # 低温度保证提取稳定
            "max_tokens": 1000,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            response = await client.post(endpoint, json=payload, headers=headers)

        if response.status_code != 200:
            logger.error(f"记忆提取 API 错误 {response.status_code}: {response.text}")
            return []

        data = response.json()
        reply_text = data["choices"][0]["message"]["content"]

        # 解析 JSON 响应
        memories = _parse_memory_extraction(reply_text)

        logger.info(f"从对话中提取了 {len(memories)} 条记忆")
        return memories

    except Exception as e:
        logger.error(f"记忆提取失败: {e}", exc_info=True)
        return []


def _parse_memory_extraction(text: str) -> List[Dict[str, Any]]:
    """解析 LLM 返回的记忆提取结果"""
    try:
        # 移除可能的 markdown 代码块标记
        cleaned = text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        data = json.loads(cleaned)
        memories = data.get("memories", [])

        # 验证和清理记忆数据
        validated = []
        for mem in memories:
            mem_type = mem.get("type", "").lower()
            if mem_type not in ["fact", "preference", "event", "relationship"]:
                continue
            
            content = mem.get("content", "").strip()
            if not content:
                continue
            
            importance = int(mem.get("importance", 50))
            importance = max(50, min(100, importance))  # 限制在 50-100

            validated.append({
                "type": mem_type,
                "content": content,
                "importance": importance,
            })

        return validated

    except json.JSONDecodeError as e:
        logger.warning(f"JSON 解析失败: {e}, 原始文本: {text[:200]}")
        return []
    except Exception as e:
        logger.error(f"记忆解析失败: {e}", exc_info=True)
        return []


async def save_conversation_and_extract_memories(
    session: Session,
    session_id: str,
    user_query: str,
    assistant_reply: str,
    settings: Settings,
    user_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> List[LongTermMemory]:
    """
    保存对话并自动提取记忆
    返回新保存的记忆列表
    """
    # 保存用户消息
    save_conversation_message(
        session=session,
        session_id=session_id,
        role="user",
        content=user_query,
        user_id=user_id,
        metadata=metadata,
    )

    # 保存助手回复
    save_conversation_message(
        session=session,
        session_id=session_id,
        role="assistant",
        content=assistant_reply,
        user_id=user_id,
        metadata=metadata,
    )

    # 构建对话文本用于提取记忆
    conversation_text = f"用户: {user_query}\n助手: {assistant_reply}"

    # 提取记忆
    extracted_memories = await extract_memories_from_conversation(
        conversation_text=conversation_text,
        settings=settings,
        session_id=session_id,
        user_id=user_id,
    )

    # 保存提取的记忆（使用去重和合并逻辑，并自动向量化）
    saved_memories = []
    for mem in extracted_memories:
        try:
            # 使用带去重的保存函数（会自动向量化）
            memory_record = save_memory_with_dedup(
                session=session,
                memory_type=mem["type"],
                content=mem["content"],
                importance_score=mem["importance"],
                user_id=user_id,
                source_conversation_id=session_id,
                metadata={"extracted_at": "auto"},
                similarity_threshold=0.75,  # 相似度阈值，可配置
                use_semantic_similarity=False,  # 默认使用快速文本相似度，需要高精度时可设为True
                settings=settings,  # 传入 settings 用于向量化
            )
            saved_memories.append(memory_record)
        except Exception as e:
            logger.error(f"保存记忆失败: {e}", exc_info=True)

    return saved_memories


async def retrieve_relevant_memories(
    session: Session,
    query: str,
    settings: Settings,
    user_id: Optional[str] = None,
    max_memories: int = 5,
    session_id: Optional[str] = None,
    share_memory: Optional[bool] = None,
) -> List[LongTermMemory]:
    """
    检索与查询相关的长期记忆
    
    使用向量检索和关键词检索结合的方式
    同时确保返回重要的用户信息（如姓名等）
    
    Args:
        session: 数据库会话
        query: 查询文本
        settings: 配置对象
        user_id: 用户ID
        max_memories: 最大返回记忆数
        session_id: 当前会话ID（用于记忆隔离）
        share_memory: 是否共享记忆（None 表示使用会话配置）
    
    Returns:
        相关记忆列表
    """
    # 检查会话配置，决定是否共享记忆
    should_share = True  # 默认共享
    
    if session_id:
        from .database import get_session_config
        config = get_session_config(session, session_id)
        if config:
            should_share = config.share_memory_across_sessions
        elif share_memory is not None:
            should_share = share_memory
    elif share_memory is not None:
        should_share = share_memory
    
    # 如果不应共享记忆，只检索当前会话的记忆
    if not should_share and session_id:
        # 只检索来自当前会话的记忆
        keyword_memories = search_long_term_memory(
            session=session,
            query=query,
            user_id=user_id,
            limit=max_memories * 2,
            min_importance=40,
        )
        
        # 过滤出当前会话的记忆
        session_memories = [
            m for m in keyword_memories
            if m.source_conversation_id == session_id
        ]
        
        # 更新访问信息
        for mem in session_memories:
            update_memory_access(session, mem.id)
        
        # 按重要性排序
        sorted_memories = sorted(
            session_memories,
            key=lambda m: (
                m.memory_type == "fact",  # fact 类型优先
                m.importance_score,
                m.access_count
            ),
            reverse=True,
        )[:max_memories]
        
        logger.debug(f"会话隔离模式：只检索当前会话 {session_id} 的记忆，找到 {len(sorted_memories)} 条")
        return sorted_memories
    
    # 原有逻辑（共享记忆模式）
    all_memories = {}
    
    # 1. 先尝试向量检索（如果向量数据库中有记忆）
    vector_memories = _retrieve_memories_by_embedding(
        query=query,
        session=session,
        settings=settings,
        user_id=user_id,
        limit=max_memories,
    )
    for mem in vector_memories:
        all_memories[mem.id] = mem

    # 2. 关键词检索作为补充
    keyword_memories = search_long_term_memory(
        session=session,
        query=query,
        user_id=user_id,
        limit=max_memories,
        min_importance=50,  # 只检索重要记忆
    )
    for mem in keyword_memories:
        all_memories[mem.id] = mem
    
    # 3. 如果查询匹配的记忆较少，补充一些重要的用户记忆（特别是 fact 类型，如姓名）
    # 这样可以确保用户信息（如姓名）总是可用的
    if len(all_memories) < max_memories:
        try:
            # 获取最近的重要记忆，特别是 fact 类型（包含姓名等信息）
            recent_facts = get_recent_memories(
                session=session,
                user_id=user_id,
                limit=max_memories * 2,  # 获取更多候选
            )
            
            # 优先选择 fact 类型的高重要性记忆
            fact_memories = [m for m in recent_facts if m.memory_type == "fact" and m.importance_score >= 60]
            preference_memories = [m for m in recent_facts if m.memory_type == "preference" and m.importance_score >= 60]
            
            # 补充 fact 类型记忆（通常是姓名等关键信息）
            for mem in fact_memories:
                if mem.id not in all_memories and len(all_memories) < max_memories:
                    all_memories[mem.id] = mem
            
            # 如果还有空间，补充 preference 类型记忆
            if len(all_memories) < max_memories:
                for mem in preference_memories:
                    if mem.id not in all_memories and len(all_memories) < max_memories:
                        all_memories[mem.id] = mem
            
            # 最后补充其他重要记忆
            if len(all_memories) < max_memories:
                for mem in recent_facts:
                    if mem.id not in all_memories and mem.importance_score >= 60:
                        if len(all_memories) < max_memories:
                            all_memories[mem.id] = mem
                        else:
                            break
        except Exception as e:
            logger.warning(f"获取补充记忆失败: {e}")

    # 更新访问信息
    for mem_id in all_memories:
        update_memory_access(session, mem_id)

    # 按重要性排序
    sorted_memories = sorted(
        all_memories.values(),
        key=lambda m: (
            m.memory_type == "fact",  # fact 类型优先
            m.importance_score,
            m.access_count
        ),
        reverse=True,
    )[:max_memories]

    return sorted_memories


def get_memory_vectorstore(settings: Settings) -> Chroma:
    """
    获取记忆向量数据库（独立的 collection）
    使用独立的 collection 存储记忆，与文档分开
    """
    key = str(settings.chroma_dir)
    store = _MEMORY_VECTORSTORE_CACHE.get(key)
    if store is None:
        settings.chroma_dir.mkdir(parents=True, exist_ok=True)
        store = Chroma(
            collection_name="memories",  # 独立的 collection 名称
            embedding_function=get_embeddings(),
            persist_directory=str(settings.chroma_dir),
        )
        _MEMORY_VECTORSTORE_CACHE[key] = store
        logger.info("记忆向量数据库初始化完成")
    return store


def add_memory_to_vectorstore(
    memory_id: str,
    content: str,
    memory_type: str,
    user_id: Optional[str] = None,
    settings: Settings = None,
) -> None:
    """
    将记忆添加到向量数据库
    
    Args:
        memory_id: 记忆ID
        content: 记忆内容
        memory_type: 记忆类型
        user_id: 用户ID
        settings: 配置对象
    """
    try:
        if settings is None:
            from .config import get_settings
            settings = get_settings()
        
        vectorstore = get_memory_vectorstore(settings)
        
        # 创建 Document 对象，metadata 包含记忆的所有信息
        metadata = {
            "memory_id": memory_id,
            "memory_type": memory_type,
        }
        if user_id:
            metadata["user_id"] = user_id
        
        doc = Document(page_content=content, metadata=metadata)
        
        # 添加到向量数据库，使用 memory_id 作为唯一ID
        vectorstore.add_documents([doc], ids=[memory_id])
        
        logger.debug(f"记忆已向量化并存储: {memory_id}")
        
    except Exception as e:
        logger.error(f"向量化记忆失败 {memory_id}: {e}", exc_info=True)
        # 不抛出异常，允许记忆保存继续，只是没有向量化


def update_memory_in_vectorstore(
    memory_id: str,
    content: str,
    memory_type: str,
    user_id: Optional[str] = None,
    settings: Settings = None,
) -> None:
    """
    更新向量数据库中的记忆
    
    先删除旧向量，再添加新向量
    """
    try:
        if settings is None:
            from .config import get_settings
            settings = get_settings()
        
        vectorstore = get_memory_vectorstore(settings)
        
        # 删除旧向量
        try:
            vectorstore.delete(ids=[memory_id])
        except Exception as e:
            logger.warning(f"删除旧向量失败（可能不存在）: {e}")
        
        # 添加新向量
        add_memory_to_vectorstore(
            memory_id=memory_id,
            content=content,
            memory_type=memory_type,
            user_id=user_id,
            settings=settings,
        )
        
        logger.debug(f"记忆向量已更新: {memory_id}")
        
    except Exception as e:
        logger.error(f"更新记忆向量失败 {memory_id}: {e}", exc_info=True)


def delete_memory_from_vectorstore(
    memory_id: str,
    settings: Settings = None,
) -> None:
    """
    从向量数据库中删除记忆
    """
    try:
        if settings is None:
            from .config import get_settings
            settings = get_settings()
        
        vectorstore = get_memory_vectorstore(settings)
        
        # 删除向量
        vectorstore.delete(ids=[memory_id])
        
        logger.debug(f"记忆向量已删除: {memory_id}")
        
    except Exception as e:
        logger.warning(f"删除记忆向量失败（可能不存在）: {e}")


def vectorize_existing_memories(
    session: Session,
    settings: Settings,
    user_id: Optional[str] = None,
    batch_size: int = 100,
) -> int:
    """
    批量向量化已有记忆（用于迁移或初始化）
    
    Args:
        session: 数据库会话
        settings: 配置对象
        user_id: 用户ID（可选，如果指定则只向量化该用户的记忆）
        batch_size: 批量处理大小
    
    Returns:
        成功向量化的记忆数量
    """
    try:
        vectorstore = get_memory_vectorstore(settings)
        
        # 获取已有向量ID列表（避免重复向量化）
        existing_ids = set()
        try:
            existing_vectors = vectorstore.get()
            if existing_vectors and existing_vectors.get("ids"):
                existing_ids = set(existing_vectors["ids"])
        except Exception as e:
            logger.warning(f"获取已有向量列表失败: {e}")
        
        # 查询需要向量化的记忆
        if user_id:
            # 查询特定用户的记忆
            from .database import LongTermMemory
            from sqlalchemy import select
            statement = select(LongTermMemory).where(LongTermMemory.user_id == user_id)
            memories = list(session.execute(statement).scalars())
        else:
            # 查询所有记忆
            from .database import LongTermMemory
            from sqlalchemy import select
            statement = select(LongTermMemory)
            memories = list(session.execute(statement).scalars())
        
        # 过滤掉已向量化的记忆
        memories_to_vectorize = [
            mem for mem in memories
            if mem.id not in existing_ids
        ]
        
        if not memories_to_vectorize:
            logger.info("没有需要向量化的记忆")
            return 0
        
        logger.info(f"开始向量化 {len(memories_to_vectorize)} 条记忆...")
        
        # 批量处理
        success_count = 0
        for i in range(0, len(memories_to_vectorize), batch_size):
            batch = memories_to_vectorize[i:i + batch_size]
            
            documents = []
            ids = []
            for mem in batch:
                metadata = {
                    "memory_id": mem.id,
                    "memory_type": mem.memory_type,
                }
                if mem.user_id:
                    metadata["user_id"] = mem.user_id
                
                doc = Document(page_content=mem.content, metadata=metadata)
                documents.append(doc)
                ids.append(mem.id)
            
            try:
                vectorstore.add_documents(documents, ids=ids)
                success_count += len(batch)
                logger.info(f"已向量化 {success_count}/{len(memories_to_vectorize)} 条记忆")
            except Exception as e:
                logger.error(f"批量向量化失败: {e}", exc_info=True)
        
        logger.info(f"向量化完成，成功 {success_count}/{len(memories_to_vectorize)} 条")
        return success_count
        
    except Exception as e:
        logger.error(f"批量向量化记忆失败: {e}", exc_info=True)
        return 0


def _retrieve_memories_by_embedding(
    query: str,
    session: Session,
    settings: Settings,
    user_id: Optional[str] = None,
    limit: int = 5,
) -> List[LongTermMemory]:
    """
    使用向量检索记忆（真正的向量相似度搜索）
    
    使用 Chroma 向量数据库进行语义相似度搜索
    """
    try:
        vectorstore = get_memory_vectorstore(settings)
        
        # 执行向量相似度搜索
        # 搜索更多候选（limit * 3），然后根据用户过滤
        search_k = min(limit * 5, 100)  # 搜索更多候选以应对过滤后的损失
        
        try:
            # 尝试使用 filter 参数（新版本 Chroma 支持）
            if user_id:
                results = vectorstore.similarity_search_with_score(
                    query,
                    k=search_k,
                    filter={"user_id": user_id},
                )
            else:
                results = vectorstore.similarity_search_with_score(
                    query,
                    k=search_k,
                )
        except TypeError:
            # 如果不支持 filter 参数，使用旧方法：先搜索再过滤
            results = vectorstore.similarity_search_with_score(query, k=search_k)
        
        if not results:
            logger.debug("向量搜索未找到相关记忆")
            return []
        
        # 从向量数据库中获取的 (Document, score) 列表
        # score 是距离（越小越相似），需要转换为相似度
        memory_ids = []
        scored_memories = {}
        
        for doc, distance in results:
            memory_id = doc.metadata.get("memory_id")
            if not memory_id:
                continue
            
            # 跳过不同用户（如果指定了 user_id）
            if user_id and doc.metadata.get("user_id") != user_id:
                continue
            
            # 将距离转换为相似度分数（Chroma 使用余弦距离，范围 0-2）
            # 相似度 = 1 - (distance / 2)
            similarity_score = max(0.0, 1.0 - (distance / 2.0))
            
            memory_ids.append(memory_id)
            scored_memories[memory_id] = similarity_score
        
        if not memory_ids:
            return []
        
        # 从数据库加载记忆对象
        memories = []
        for memory_id in memory_ids[:limit * 2]:  # 加载更多用于后续筛选
            try:
                # 从 session 中获取记忆（需要从 LongTermMemory 表中查询）
                memory = session.get(LongTermMemory, memory_id)
                if memory:
                    # 将相似度分数存储在临时属性中
                    memory._vector_similarity = scored_memories.get(memory_id, 0.0)
                    memories.append(memory)
            except Exception as e:
                logger.warning(f"加载记忆失败 {memory_id}: {e}")
                continue
        
        # 按相似度分数和重要性综合排序
        memories.sort(
            key=lambda m: (
                getattr(m, '_vector_similarity', 0.0),  # 向量相似度
                m.importance_score / 100.0,  # 重要性评分归一化
            ),
            reverse=True,
        )
        
        # 只返回前 limit 条
        result = memories[:limit]
        
        logger.debug(f"向量检索找到 {len(result)} 条记忆（从 {len(memories)} 条中筛选）")
        return result

    except Exception as e:
        logger.error(f"向量检索记忆失败: {e}", exc_info=True)
        # 失败时回退到关键词检索
        logger.info("向量检索失败，回退到关键词检索")
        return search_long_term_memory(
            session=session,
            query=query,
            user_id=user_id,
            limit=limit,
            min_importance=40,
        )


def format_memories_for_context(memories: List[LongTermMemory]) -> str:
    """
    将记忆格式化为上下文提示词（隐式格式，用于内部处理）
    不显示"记忆"、"记录"等标签，让信息看起来像是已知的背景知识
    """
    if not memories:
        return ""

    parts = []
    for mem in memories:
        # 直接显示内容，不添加序号和标签，让信息更自然
        parts.append(mem.content)

    return "\n".join(parts)


def format_memories_for_prompt(memories: List[LongTermMemory]) -> str:
    """
    将记忆格式化为用于 LLM prompt 的格式（完全隐式）
    不显示任何"记忆"、"信息"等标签，只提供纯内容
    """
    if not memories:
        return ""
    
    # 只返回记忆内容，一行一个，没有任何标签
    return "\n".join(mem.content for mem in memories)


def get_conversation_context(
    session: Session,
    session_id: str,
    limit: int = 10,
    user_id: Optional[str] = None,
) -> List[Dict[str, str]]:
    """
    获取对话历史作为上下文
    
    Returns:
        格式化的对话消息列表，格式: [{"role": "user|assistant", "content": "..."}, ...]
    """
    history = get_conversation_history(
        session=session,
        session_id=session_id,
        limit=limit,
        user_id=user_id,
    )

    messages = []
    for record in history:
        messages.append({
            "role": record.role,
            "content": record.content,
        })

    return messages

