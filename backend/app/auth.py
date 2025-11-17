"""
用户认证模块
提供密码加密、JWT token 生成和验证功能
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import hashlib
import base64
import bcrypt
from .database import User
from .config import get_settings

# 密码加密上下文（作为备用）
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 方案（用于 token 获取）
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

# JWT 配置（生产环境应该从环境变量读取）
SECRET_KEY = "your-secret-key-change-in-production-min-32-chars-please"  # 密钥，至少32字符
ALGORITHM = "HS256"  # 签名算法：HMAC SHA-256
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # Access token 过期时间（分钟）
REFRESH_TOKEN_EXPIRE_DAYS = 7    # Refresh token 过期时间（天）


def _preprocess_password(password: str) -> str:
    """
    预处理密码以支持任意长度
    
    bcrypt 限制密码不能超过 72 字节
    如果密码 >= 72 字节，先使用 SHA-256 哈希，然后用 base64 编码
    这样可以支持任意长度的密码，同时确保结果长度 < 72 字节
    """
    password_bytes = password.encode('utf-8')
    
    # 如果密码 >= 72 字节，先用 SHA-256 哈希
    # 使用 >= 而不是 > 以确保即使恰好 72 字节也会被处理
    if len(password_bytes) >= 72:
        # SHA-256 哈希得到 32 字节，然后用 base64 编码得到 44 字符（固定长度，44 字节）
        # 这比 hexdigest 的 64 字符更短，更安全
        hash_bytes = hashlib.sha256(password_bytes).digest()
        return base64.b64encode(hash_bytes).decode('utf-8')
    
    # 密码长度 < 72 字节，直接返回
    return password


def get_password_hash(password: str) -> str:
    """
    将明文密码加密为哈希密码
    
    支持任意长度的密码（通过 SHA-256 + base64 预处理）
    直接使用 bcrypt 库，避免 passlib 的初始化问题
    """
    # 预处理密码（如果 >= 72 字节，先用 SHA-256 哈希 + base64 编码）
    processed_password = _preprocess_password(password)
    
    # 双重检查：确保编码后的字节长度严格小于 72
    # 这是为了防止边界情况和 bcrypt 内部处理导致的溢出
    processed_bytes = processed_password.encode('utf-8')
    if len(processed_bytes) >= 72:
        # 如果仍然 >= 72 字节（理论上不应该发生，但为了安全），截断到 71 字节
        processed_password = processed_bytes[:71].decode('utf-8', errors='ignore')
        processed_bytes = processed_password.encode('utf-8')
    
    # 直接使用 bcrypt 库，避免 passlib 的初始化问题
    # bcrypt.hashpw 需要字节输入，返回字节输出
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(processed_bytes, salt)
    # 返回字符串格式（bcrypt 哈希是 ASCII 字符串）
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证明文密码是否与哈希密码匹配
    
    使用与 get_password_hash 相同的预处理逻辑
    直接使用 bcrypt 库，避免 passlib 的初始化问题
    """
    # 预处理密码（如果 >= 72 字节，先用 SHA-256 哈希 + base64 编码）
    processed_password = _preprocess_password(plain_password)
    
    # 双重检查：确保编码后的字节长度严格小于 72
    # 与 get_password_hash 保持一致的逻辑
    processed_bytes = processed_password.encode('utf-8')
    if len(processed_bytes) >= 72:
        # 如果仍然 >= 72 字节，截断到 71 字节
        processed_password = processed_bytes[:71].decode('utf-8', errors='ignore')
        processed_bytes = processed_password.encode('utf-8')
    
    # 直接使用 bcrypt 库验证
    try:
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(processed_bytes, hashed_bytes)
    except Exception:
        # 如果出错，尝试使用 passlib 作为备用（向后兼容）
        try:
            return pwd_context.verify(processed_password, hashed_password)
        except Exception:
            return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建 JWT Access Token（用于API访问）"""
    to_encode = data.copy()
    
    # 计算过期时间
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # 添加过期时间和 token 类型到 payload
    to_encode.update({
        "exp": expire,
        "type": "access",
        "iat": datetime.utcnow()
    })
    
    # 使用密钥签名并编码为 JWT
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """创建 JWT Refresh Token（用于刷新 access token）"""
    to_encode = data.copy()
    
    # Refresh token 过期时间更长
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "exp": expire,
        "type": "refresh",
        "iat": datetime.utcnow()
    })
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict:
    """验证并解析 JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"无效的 token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# 注意：get_current_user 函数需要在 main.py 中定义，因为它需要 get_db_session
# 这里只提供辅助函数


def authenticate_user(session: Session, email: str, password: str) -> Optional[User]:
    """验证用户登录凭据"""
    # 根据邮箱查找用户
    user = session.query(User).filter(User.email == email).first()
    
    # 用户不存在
    if not user:
        return None
    
    # 验证密码
    if not verify_password(password, user.hashed_password):
        return None
    
    # 验证成功，返回用户对象
    return user

